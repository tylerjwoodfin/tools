#!/usr/bin/env python3
"""Import Robinhood credit card and Venmo CSVs into Sure."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import select
import sys
import termios
import tty
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Iterable, Optional, Protocol, Union

import requests
from cabinet import Cabinet

DEFAULT_CATEGORIES = Path.home() / "syncthing/notes/docs/selfhosted/transaction_categories.json"
DEFAULT_SURE_BASE_URL = "http://192.168.1.101:3006"
DEFAULT_ACCOUNT_NAME = "Venmo"
ROBINHOOD_ACCOUNT_NAME = "Robinhood Credit Card"
SKIP_SURE_NAMES = {"manual balance update"}
QUOTED_NOTE = re.compile(r'"([^"]+)"')
RECENT_CSV_LIMIT = 5
MenuValue = Union[Path, str, None]


@dataclass
class VenmoRow:
    """One Venmo statement line after cleaning."""

    venmo_id: str
    txn_date: date
    note: str
    from_name: str
    to_name: str
    amount: float
    txn_type: str
    category: str

    @property
    def amount_cents(self) -> int:
        """Signed cents matching Sure's signed_amount_cents (income +, expense -)."""
        return int(round(self.amount * 100))

    @property
    def nature(self) -> str:
        """Sure nature: money in is income, money out is expense."""
        return "income" if self.amount > 0 else "expense"

    @property
    def display_name(self) -> str:
        """Name to store in Sure: Venmo note, or type if the note is blank."""
        return self.note or self.txn_type or "Venmo"

    @property
    def notes(self) -> str:
        """Sure notes: the Venmo from/to line."""
        return _party_note(self)

    @property
    def external_id(self) -> str:
        """Stable id stored on the Sure transaction."""
        return self.venmo_id

    @property
    def source(self) -> str:
        """Sure transaction source."""
        return "venmo"


class StatementRow(Protocol):
    """Fields both CSV shapes need in order to match and write a Sure transaction."""

    txn_date: date
    amount: float
    category: str
    from_name: str
    to_name: str

    @property
    def amount_cents(self) -> int:
        """Signed cents (income +, expense -)."""

    @property
    def nature(self) -> str:
        """Sure nature: income or expense."""

    @property
    def display_name(self) -> str:
        """Transaction name stored in Sure."""

    @property
    def notes(self) -> str:
        """Transaction notes stored in Sure."""

    @property
    def external_id(self) -> str:
        """Stable id stored on the Sure transaction."""

    @property
    def source(self) -> str:
        """Sure transaction source."""


@dataclass
class RobinhoodRow:
    """One posted Robinhood credit-card line. ``amount`` is Sure-signed (income +)."""

    external_id: str
    txn_date: date
    merchant: str
    description: str
    amount: float
    category: str

    @property
    def amount_cents(self) -> int:
        """Signed cents matching Sure (income +, expense -)."""
        return int(round(self.amount * 100))

    @property
    def nature(self) -> str:
        """Purchases are expenses; refunds and payments are income."""
        return "income" if self.amount > 0 else "expense"

    @property
    def display_name(self) -> str:
        """Merchant, or the description when the merchant is blank."""
        return self.merchant or self.description or "Robinhood"

    @property
    def notes(self) -> str:
        """Card description stored in Sure notes."""
        return self.description

    @property
    def source(self) -> str:
        """Sure transaction source."""
        return "robinhood_cc"

    @property
    def from_name(self) -> str:
        """Unused for card rows; kept so matching can share the Venmo scorer."""
        return ""

    @property
    def to_name(self) -> str:
        """Unused for card rows; kept so matching can share the Venmo scorer."""
        return ""


@dataclass
class SureTxn:
    """Subset of a Sure transaction used for matching and updates."""

    txn_id: str
    txn_date: date
    name: str
    signed_amount_cents: int
    category_name: Optional[str]
    source: Optional[str]
    external_id: Optional[str]
    notes: str = ""
    category_id: Optional[str] = None


class SureClient:
    """Minimal Sure API client (LAN origin; public hostname is behind Authentik)."""

    def __init__(self, base_url: str, api_key: str, timeout: int = 30) -> None:
        """Configure the API origin and X-Api-Key session."""
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update(
            {"X-Api-Key": api_key, "Accept": "application/json"}
        )
        self.timeout = timeout

    def _url(self, path: str) -> str:
        return f"{self.base_url}{path}"

    def _raise_for_status(self, response: requests.Response) -> None:
        if response.ok:
            return
        detail = response.text[:800]
        raise RuntimeError(f"Sure API {response.status_code} {response.request.method} "
                           f"{response.request.url}: {detail}")

    def _get(self, path: str, params: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        response = self.session.get(self._url(path), params=params, timeout=self.timeout)
        self._raise_for_status(response)
        return response.json()

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        response = self.session.post(self._url(path), json=payload, timeout=self.timeout)
        self._raise_for_status(response)
        return response.json()

    def _put(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        response = self.session.put(self._url(path), json=payload, timeout=self.timeout)
        self._raise_for_status(response)
        return response.json()

    def paginate(
        self, path: str, list_key: str, extra: Optional[dict[str, Any]] = None
    ) -> list[dict[str, Any]]:
        """Fetch every page of a list endpoint (max 100 per page)."""
        items: list[dict[str, Any]] = []
        page = 1
        while True:
            params = {"page": page, "per_page": 100, **(extra or {})}
            payload = self._get(path, params=params)
            chunk = payload.get(list_key) or []
            items.extend(chunk)
            pagination = payload.get("pagination") or {}
            total_pages = int(pagination.get("total_pages") or 1)
            if page >= total_pages:
                break
            page += 1
        return items

    def account_by_name(self, name: str) -> dict[str, Any]:
        """Return the Sure account named ``name``.

        Exact match wins. Otherwise a unique account whose name starts with
        ``name`` matches, so ``Robinhood Credit Card`` finds
        ``Robinhood Credit Card **4696``.
        """
        accounts = self.paginate("/api/v1/accounts", "accounts")
        return pick_account(accounts, name)

    def categories_by_name(self) -> dict[str, str]:
        """Map Sure category display name → id."""
        categories = self.paginate("/api/v1/categories", "categories")
        return {c["name"]: c["id"] for c in categories if c.get("name") and c.get("id")}

    def transactions_for_account(
        self, account_id: str, start: date, end: date
    ) -> list[SureTxn]:
        """List Venmo-relevant Sure transactions in an inclusive date window."""
        raw = self.paginate(
            "/api/v1/transactions",
            "transactions",
            extra={
                "account_id": account_id,
                "start_date": start.isoformat(),
                "end_date": end.isoformat(),
            },
        )
        result: list[SureTxn] = []
        for item in raw:
            name = (item.get("name") or "").strip()
            if name.lower() in SKIP_SURE_NAMES:
                continue
            category = item.get("category") or {}
            result.append(
                SureTxn(
                    txn_id=str(item["id"]),
                    txn_date=_parse_date(item.get("date")),
                    name=name,
                    signed_amount_cents=int(item.get("signed_amount_cents") or 0),
                    category_name=category.get("name"),
                    source=item.get("source"),
                    external_id=item.get("external_id"),
                    notes=str(item.get("notes") or ""),
                    category_id=category.get("id"),
                )
            )
        return result

    def create_transaction(
        self,
        account_id: str,
        row: StatementRow,
        category_id: Optional[str],
    ) -> dict[str, Any]:
        """Create a Sure transaction from a CSV row."""
        body: dict[str, Any] = {
            "account_id": account_id,
            "date": row.txn_date.isoformat(),
            "amount": abs(row.amount),
            "nature": row.nature,
            "name": row.display_name,
            "notes": row.notes,
            "external_id": row.external_id,
            "source": row.source,
            "user_modified": True,
        }
        if category_id:
            body["category_id"] = category_id
        return self._post("/api/v1/transactions", {"transaction": body})

    def update_transaction(
        self,
        txn_id: str,
        row: StatementRow,
        category_id: Optional[str],
    ) -> dict[str, Any]:
        """Update name/notes/category on an existing Sure transaction."""
        body: dict[str, Any] = {
            "name": row.display_name,
            "notes": row.notes,
            "user_modified": True,
        }
        if category_id:
            body["category_id"] = category_id
        return self._put(f"/api/v1/transactions/{txn_id}", {"transaction": body})

    def delete_transaction(self, txn_id: str) -> None:
        """Delete a Sure transaction (used to roll back a failed import)."""
        response = self.session.delete(
            self._url(f"/api/v1/transactions/{txn_id}"), timeout=self.timeout
        )
        self._raise_for_status(response)

    def restore_transaction(
        self,
        txn_id: str,
        *,
        name: str,
        notes: str,
        category_id: Optional[str],
    ) -> dict[str, Any]:
        """Put a transaction back to the name, notes, and category it had before import."""
        body: dict[str, Any] = {
            "name": name,
            "notes": notes,
            "category_id": category_id,
            "user_modified": True,
        }
        return self._put(f"/api/v1/transactions/{txn_id}", {"transaction": body})


def previous_month_bounds(today: Optional[date] = None) -> tuple[date, date]:
    """Inclusive first/last day of the previous calendar month."""
    today = today or date.today()
    first_this_month = today.replace(day=1)
    last_prev = first_this_month - timedelta(days=1)
    first_prev = last_prev.replace(day=1)
    return first_prev, last_prev


def month_bounds(year_month: str) -> tuple[date, date]:
    """Inclusive bounds for YYYY-MM."""
    parsed = datetime.strptime(year_month, "%Y-%m").date()
    if parsed.month == 12:
        next_month = parsed.replace(year=parsed.year + 1, month=1, day=1)
    else:
        next_month = parsed.replace(month=parsed.month + 1, day=1)
    return parsed, next_month - timedelta(days=1)


def clean_amount(value: str) -> float:
    """Parse Venmo amounts like '- $58.44' or '+ $1,000.00'."""
    if value is None:
        return 0.0
    text = str(value).replace("$", "").replace(",", "").replace(" ", "").strip()
    if not text or text.startswith("="):
        return 0.0
    try:
        return float(text)
    except ValueError:
        print(f"Warning: Could not parse amount {value!r}, using 0.0")
        return 0.0


def should_include_transaction(description: str, filtered_rows: list[str]) -> bool:
    """False when description contains any filteredRows substring."""
    if not description or not isinstance(description, str):
        return True
    lowered = description.lower()
    return not any(token.lower() in lowered for token in filtered_rows)


def categorize_transaction(note: str, category_mapping: dict[str, list]) -> str:
    """First matching category from the JSON keyword lists. '!' prefixes exclude."""
    if not note or not isinstance(note, str):
        return "Other"
    note_lower = note.lower()
    for category, keywords in category_mapping.items():
        include_keywords = [k for k in keywords if not k.startswith("!")]
        exclude_keywords = [k[1:] for k in keywords if k.startswith("!")]
        if any(keyword.lower() in note_lower for keyword in exclude_keywords):
            continue
        if any(keyword.lower() in note_lower for keyword in include_keywords):
            return category
    return "Other"


def load_category_config(path: Path) -> tuple[dict[str, list], list[str]]:
    """Load categories + filteredRows from transaction_categories.json."""
    with path.open(encoding="utf-8") as handle:
        config = json.load(handle)
    return config.get("categories") or {}, config.get("filteredRows") or []


def _parse_date(value: Any) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    text = str(value)
    if "T" in text:
        return datetime.fromisoformat(text.replace("Z", "")).date()
    return date.fromisoformat(text[:10])


def _party_note(row: VenmoRow) -> str:
    parts = [p for p in (row.from_name, row.to_name) if p]
    if not parts:
        return ""
    return f"From {row.from_name} to {row.to_name}".strip()


def _quoted_note(name: str) -> str:
    match = QUOTED_NOTE.search(name or "")
    return match.group(1).strip() if match else ""


def match_score(row: StatementRow, txn: SureTxn) -> int:
    """Higher is better. 0 means date/amount matched with no name signal."""
    if row.txn_date != txn.txn_date or row.amount_cents != txn.signed_amount_cents:
        return -1
    sure_name = txn.name.lower()
    note = row.display_name.lower()
    quoted = _quoted_note(txn.name).lower()
    score = 0
    if quoted and quoted == note:
        score += 5
    elif quoted and (quoted in note or note in quoted):
        score += 4
    elif note and note in sure_name:
        score += 3
    for party in (row.from_name, row.to_name):
        if party and party.lower() in sure_name:
            score += 1
            break
    return score


def find_match(row: StatementRow, unmatched: list[SureTxn]) -> Optional[SureTxn]:
    """Pick the best unmatched Sure txn for this CSV row, or None."""
    if row.external_id:
        for txn in unmatched:
            if txn.external_id and txn.external_id == row.external_id:
                return txn
    scored: list[tuple[int, SureTxn]] = []
    for txn in unmatched:
        score = match_score(row, txn)
        if score >= 0:
            scored.append((score, txn))
    if not scored:
        return None
    scored.sort(key=lambda item: item[0], reverse=True)
    best_score, best = scored[0]
    same_score = [txn for score, txn in scored if score == best_score]
    if best_score > 0:
        return best
    if len(same_score) == 1:
        return best
    return None


def pick_account(accounts: list[dict[str, Any]], name: str) -> dict[str, Any]:
    """Choose one Sure account by exact name, or a unique prefix of that name."""
    wanted = name.strip().lower()
    named = [(account, (account.get("name") or "").strip()) for account in accounts]
    exact = [account for account, label in named if label.lower() == wanted]
    if len(exact) == 1:
        return exact[0]
    prefixed = [
        account
        for account, label in named
        if label.lower().startswith(wanted) and label.lower() != wanted
    ]
    if len(exact) == 0 and len(prefixed) == 1:
        return prefixed[0]
    available = ", ".join(label or "?" for _, label in named)
    if len(prefixed) > 1:
        raise RuntimeError(
            f"Sure account {name!r} matches more than one name. Available: {available}"
        )
    raise RuntimeError(f"Sure account {name!r} not found. Available: {available}")


def find_header_row(path: Path) -> int:
    """Index of the Venmo CSV header row containing Datetime and Note."""
    with path.open(encoding="utf-8", newline="") as handle:
        for index, line in enumerate(handle):
            if "Datetime" in line and "Note" in line:
                return index
    raise RuntimeError(f"Could not find the Venmo header row in {path}")


def load_venmo_rows(
    path: Path,
    category_mapping: dict[str, list],
    filtered_rows: list[str],
    start: date,
    end: date,
) -> list[VenmoRow]:
    """Parse, categorize, and date-filter a Venmo statement CSV."""
    header_row = find_header_row(path)
    rows: list[VenmoRow] = []
    with path.open(encoding="utf-8", newline="") as handle:
        for _ in range(header_row):
            next(handle)
        reader = csv.DictReader(handle)
        for raw in reader:
            venmo_id = (raw.get("ID") or "").strip()
            timestamp = (raw.get("Datetime") or "").strip()
            if not venmo_id or not timestamp:
                continue
            note = (raw.get("Note") or "").strip()
            if not should_include_transaction(note, filtered_rows):
                continue
            amount = clean_amount(raw.get("Amount (total)") or "")
            if amount == 0.0:
                continue
            txn_date = _parse_date(timestamp)
            if txn_date < start or txn_date > end:
                continue
            rows.append(
                VenmoRow(
                    venmo_id=venmo_id,
                    txn_date=txn_date,
                    note=note,
                    from_name=(raw.get("From") or "").strip(),
                    to_name=(raw.get("To") or "").strip(),
                    amount=amount,
                    txn_type=(raw.get("Type") or "").strip(),
                    category=categorize_transaction(note, category_mapping),
                )
            )
    return rows


def robinhood_external_id(
    txn_date: date, amount: float, merchant: str, description: str
) -> str:
    """Stable id from the card line. Robinhood exports have no transaction id."""
    payload = f"{txn_date.isoformat()}|{amount:.2f}|{merchant}|{description}"
    digest = hashlib.sha256(payload.encode()).hexdigest()[:20]
    return f"rh-{digest}"


def load_robinhood_rows(
    path: Path,
    category_mapping: dict[str, list],
    filtered_rows: list[str],
    start: date,
    end: date,
) -> list[RobinhoodRow]:
    """Parse a Robinhood credit-card CSV. Positive amounts are purchases (expenses)."""
    rows: list[RobinhoodRow] = []
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = reader.fieldnames or []
        if "Merchant" not in fieldnames or "Amount" not in fieldnames:
            raise RuntimeError(
                f"{path.name} is not a Robinhood CSV "
                "(expected columns Merchant and Amount)."
            )
        for raw in reader:
            status = (raw.get("Status") or "").strip().lower()
            if status != "posted":
                continue
            merchant = (raw.get("Merchant") or "").strip()
            description = (raw.get("Description") or "").strip()
            blob = f"{merchant} {description}".strip()
            if not should_include_transaction(blob, filtered_rows):
                continue
            raw_amount = clean_amount(raw.get("Amount") or "")
            signed = -raw_amount
            if int(round(signed * 100)) == 0:
                continue
            timestamp = (raw.get("Date") or "").strip()
            if not timestamp:
                continue
            txn_date = _parse_date(timestamp)
            if txn_date < start or txn_date > end:
                continue
            rows.append(
                RobinhoodRow(
                    external_id=robinhood_external_id(
                        txn_date, raw_amount, merchant, description
                    ),
                    txn_date=txn_date,
                    merchant=merchant,
                    description=description,
                    amount=signed,
                    category=categorize_transaction(blob, category_mapping),
                )
            )
    return rows


RowLoader = Callable[[Path, dict[str, list], list[str], date, date], list[Any]]


@dataclass(frozen=True)
class Institution:
    """One CSV source. Append to ``INSTITUTIONS`` to add another import.

    ``label`` drives the prompt (``Robinhood CSV?``) and the skip row
    (``skip Robinhood``). ``load`` parses that institution's CSV. ``account_name``
    is the Sure account to match; set ``uses_cabinet_account`` when Cabinet
    ``sure.account_name`` should override it.
    """

    source: str
    label: str
    account_name: str
    load: RowLoader
    cli_flag: str
    uses_cabinet_account: bool = False
    file_alias: bool = False

    @property
    def prompt(self) -> str:
        """Menu title for this institution's CSV."""
        return f"{self.label} CSV?"

    @property
    def skip_label(self) -> str:
        """Row under the file list that imports nothing for this institution."""
        return f"skip {self.label}"


INSTITUTIONS: tuple[Institution, ...] = (
    Institution(
        source="robinhood_cc",
        label="Robinhood",
        account_name=ROBINHOOD_ACCOUNT_NAME,
        load=load_robinhood_rows,
        cli_flag="robinhood",
    ),
    Institution(
        source="venmo",
        label="Venmo",
        account_name=DEFAULT_ACCOUNT_NAME,
        load=load_venmo_rows,
        cli_flag="venmo",
        uses_cabinet_account=True,
        file_alias=True,
    ),
)


def institution_by_source(source: str) -> Institution:
    """Registry lookup. Sources in ``INSTITUTIONS`` must be unique."""
    for institution in INSTITUTIONS:
        if institution.source == source:
            return institution
    known = ", ".join(institution.source for institution in INSTITUTIONS)
    raise KeyError(f"Unknown source {source!r}. Known: {known}")


def recent_csvs(directory: Path, limit: int = RECENT_CSV_LIMIT) -> list[Path]:
    """Newest CSV files in ``directory``, by last-modified time."""
    if not directory.is_dir():
        return []
    files = [
        path
        for path in directory.iterdir()
        if path.is_file() and path.suffix.lower() == ".csv"
    ]
    files.sort(key=lambda path: (-path.stat().st_mtime, path.name.lower()))
    return files[:limit]


def format_csv_choice(path: Path) -> str:
    """Menu label: filename and local last-modified time."""
    modified = datetime.fromtimestamp(path.stat().st_mtime)
    return f"{path.name}    {modified.strftime('%Y-%m-%d %H:%M')}"


def csv_menu_options(
    paths: list[Path], *, skip_label: str
) -> list[tuple[str, MenuValue]]:
    """File rows, then skip for this institution."""
    options: list[tuple[str, MenuValue]] = [
        (format_csv_choice(path), path) for path in paths
    ]
    options.append((skip_label, None))
    return options


class SelectionCancelled(Exception):
    """The user left the arrow menu without choosing a row."""


def _read_byte(fd: int) -> str:
    """One raw byte from the terminal. Empty input is EOF."""
    raw = os.read(fd, 1)
    if not raw:
        return ""
    return raw.decode("latin-1")


def read_navigation_key() -> str:
    """Read one key: up, down, enter, quit, or esc.

    Bytes come from the terminal fd. ``sys.stdin.read`` would buffer the rest
    of an arrow-key sequence and the following ``select`` would miss it.
    """
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd, termios.TCSANOW)
        char = _read_byte(fd)
        if char == "":
            return "quit"
        if char == "\x03":
            raise KeyboardInterrupt
        if char in ("\r", "\n"):
            return "enter"
        if char in ("q", "Q"):
            return "quit"
        if char != "\x1b":
            return char
        if not select.select([fd], [], [], 0.08)[0]:
            return "esc"
        sequence = _read_byte(fd)
        if select.select([fd], [], [], 0.08)[0]:
            sequence += _read_byte(fd)
        if sequence in ("[A", "OA"):
            return "up"
        if sequence in ("[B", "OB"):
            return "down"
        return "esc"
    finally:
        termios.tcsetattr(fd, termios.TCSANOW, old)


def move_menu_index(index: int, key: str, count: int, *, wrap: bool) -> int:
    """Move the highlight. With wrap, Up on the first row lands on the last."""
    if count <= 0:
        return 0
    if key == "up":
        if wrap:
            return (index - 1) % count
        return max(0, index - 1)
    if key == "down":
        if wrap:
            return (index + 1) % count
        return min(count - 1, index + 1)
    return index


def arrow_select(
    title: str,
    options: list[tuple[str, MenuValue]],
    *,
    read_key: Optional[Callable[[], str]] = None,
    write: Optional[Callable[[str], Any]] = None,
    wrap: bool = False,
) -> MenuValue:
    """Arrow-key menu. Enter selects the highlighted row. q or esc cancels."""
    if not options:
        raise ValueError("arrow_select needs at least one option")
    if read_key is None and not sys.stdin.isatty():
        return _numbered_select(title, options, write=write)

    emit = write or sys.stdout.write
    fetch = read_key or read_navigation_key
    labels = [label for label, _ in options]
    index = 0
    first = True
    total_lines = 1 + len(labels)
    if write is None:
        sys.stdout.write("\033[?25l")
    try:
        while True:
            if not first:
                emit(f"\033[{total_lines}A")
            first = False
            emit(f"\r\033[2K{title}\n")
            for row_index, label in enumerate(labels):
                marker = ">" if row_index == index else " "
                emit(f"\r\033[2K {marker} {label}\n")
            if write is None:
                sys.stdout.flush()
            key = fetch()
            if key in ("up", "down"):
                index = move_menu_index(index, key, len(options), wrap=wrap)
            elif key == "enter":
                return options[index][1]
            elif key in ("quit", "esc"):
                raise SelectionCancelled()
    finally:
        if write is None:
            sys.stdout.write("\033[?25h")
            sys.stdout.flush()


def _numbered_select(
    title: str,
    options: list[tuple[str, MenuValue]],
    *,
    write: Optional[Callable[[str], Any]] = None,
) -> MenuValue:
    """Numbered fallback when stdin is not a terminal."""
    emit = write or sys.stdout.write
    emit(f"{title}\n")
    for number, (label, _) in enumerate(options, start=1):
        emit(f"  {number}) {label}\n")
    if write is None:
        sys.stdout.flush()
    raw = input("Number: ").strip()
    if not raw.isdigit():
        raise SelectionCancelled()
    chosen = int(raw)
    if chosen < 1 or chosen > len(options):
        raise SelectionCancelled()
    return options[chosen - 1][1]


@dataclass
class CsvSelection:
    """One chosen statement. ``source`` is an ``Institution.source`` value."""

    source: str
    path: Path


def prompt_csv_selections(downloads: Path) -> list[CsvSelection]:
    """Ask for each institution's CSV, in ``INSTITUTIONS`` order. Skip imports nothing."""
    paths = recent_csvs(downloads)
    if not paths:
        print("No CSV files in ~/Downloads.")
    selections: list[CsvSelection] = []
    for institution in INSTITUTIONS:
        choice = arrow_select(
            institution.prompt,
            csv_menu_options(paths, skip_label=institution.skip_label),
            wrap=True,
        )
        if isinstance(choice, Path):
            selections.append(CsvSelection(institution.source, choice))
    return selections


def resolve_credentials() -> tuple[str, str, str]:
    """Cabinet sure.api_key / sure.base_url / sure.account_name."""
    cabinet = Cabinet()
    api_key = cabinet.get("sure", "api_key")
    if not api_key:
        raise RuntimeError(
            "Missing Cabinet sure.api_key. Create a read_write Sure API key "
            "(Settings → API Key) and store it with "
            "`cabinet put sure api_key --value <key>`."
        )
    base_url = cabinet.get("sure", "base_url") or DEFAULT_SURE_BASE_URL
    account_name = cabinet.get("sure", "account_name") or DEFAULT_ACCOUNT_NAME
    return str(base_url), str(api_key), str(account_name)


def _fmt_amount(amount: float) -> str:
    return f"{amount:+.2f}"


def import_window(month: Optional[str], *, legacy_previous_month: bool) -> tuple[date, date]:
    """Date filter for a run. Interactive picks import the whole file."""
    if month:
        return month_bounds(month)
    if legacy_previous_month:
        return previous_month_bounds()
    return date.min, date.max


@dataclass
class Planned:
    """One CSV row after it has been matched to Sure."""

    action: str
    row: StatementRow
    match: Optional[SureTxn]
    category_id: Optional[str]


@dataclass
class Mutation:
    """A Sure write that can be rolled back if a later write fails."""

    kind: str
    txn_id: str
    previous_name: str = ""
    previous_notes: str = ""
    previous_category_id: Optional[str] = None


def plan_rows(
    rows: list[StatementRow],
    existing: list[SureTxn],
    category_ids: dict[str, str],
) -> tuple[list[Planned], list[SureTxn]]:
    """Match CSV rows to Sure and print the plan. Does not write."""
    unmatched = list(existing)
    planned: list[Planned] = []
    print(f"{'action':<8} {'date':<12} {'amount':>10}  {'category':<42} name")
    for row in rows:
        match = find_match(row, unmatched)
        if match:
            unmatched.remove(match)
            apply_category = row.category != "Other"
            category_id = category_ids.get(row.category) if apply_category else None
            name_changed = match.name != row.display_name
            cat_changed = apply_category and match.category_name != row.category
            if not name_changed and not cat_changed:
                action = "skip"
            else:
                action = "update"
        else:
            match = None
            action = "create"
            category_id = category_ids.get(row.category) if row.category != "Other" else None
        planned.append(Planned(action, row, match, category_id))
        print(
            f"{action:<8} {row.txn_date.isoformat():<12} {_fmt_amount(row.amount):>10}  "
            f"{row.category:<42} {row.display_name}"
        )
    return planned, unmatched


def transaction_id(payload: dict[str, Any]) -> str:
    """Id from a Sure create response, either flat or wrapped."""
    if payload.get("id"):
        return str(payload["id"])
    nested = payload.get("transaction")
    if isinstance(nested, dict) and nested.get("id"):
        return str(nested["id"])
    raise RuntimeError("Sure create response did not include an id")


def undo_mutations(client: SureClient, mutations: list[Mutation]) -> None:
    """Reverse writes from a partial import. Later failures are printed and kept going."""
    for mutation in reversed(mutations):
        try:
            if mutation.kind == "create":
                client.delete_transaction(mutation.txn_id)
            else:
                client.restore_transaction(
                    mutation.txn_id,
                    name=mutation.previous_name,
                    notes=mutation.previous_notes,
                    category_id=mutation.previous_category_id,
                )
        except Exception as exc:
            print(f"Could not undo {mutation.txn_id}: {exc}", file=sys.stderr)


def apply_planned(
    client: SureClient,
    account_id: str,
    planned: list[Planned],
    done: list[Mutation],
) -> None:
    """Write create/update rows, appending each write to ``done`` for rollback."""
    for item in planned:
        if item.action == "skip":
            continue
        if item.action == "update":
            if item.match is None:
                continue
            client.update_transaction(item.match.txn_id, item.row, item.category_id)
            done.append(
                Mutation(
                    "update",
                    item.match.txn_id,
                    previous_name=item.match.name,
                    previous_notes=item.match.notes,
                    previous_category_id=item.match.category_id,
                )
            )
            continue
        payload = client.create_transaction(account_id, item.row, item.category_id)
        done.append(Mutation("create", transaction_id(payload)))


def confirm_choices(*, include_keep: bool = True) -> list[tuple[str, MenuValue]]:
    """Keep posts the preview. Re-run reloads the JSON. Undo writes nothing."""
    choices: list[tuple[str, MenuValue]] = []
    if include_keep:
        choices.append(("Keep", "keep"))
    choices.append(("Undo", "undo"))
    choices.append(("Re-run Categories", "rerun"))
    return choices


def confirm_import(
    count: int, *, assume_yes: bool, include_keep: bool = True
) -> str:
    """Return keep, undo, rerun, or blocked. Only keep writes to Sure."""
    if include_keep:
        title = f"{count} transaction(s). Keep, re-run categories, or undo?"
    else:
        title = "Re-run categories, or undo?"
    if assume_yes:
        print(f"\n{title}")
        return "keep"
    if not sys.stdin.isatty():
        print(
            f"\n{title}\nNothing written. Re-run in a terminal and choose Keep, or pass --yes.",
            file=sys.stderr,
        )
        return "blocked"
    print()
    try:
        choice = arrow_select(title, confirm_choices(include_keep=include_keep))
    except SelectionCancelled:
        choice = "undo"
    if choice == "rerun":
        return "rerun"
    if choice == "keep":
        return "keep"
    print("Undone. Sure was not changed.")
    return "undo"


def account_name_for(source: str, configured_account: str) -> str:
    """Sure account name for a CSV source."""
    institution = institution_by_source(source)
    if institution.uses_cabinet_account:
        return configured_account
    return institution.account_name


def load_selection(
    selection: CsvSelection,
    category_mapping: dict[str, list],
    filtered_rows: list[str],
    start: date,
    end: date,
) -> list[StatementRow]:
    """Parse one chosen CSV with that institution's loader."""
    institution = institution_by_source(selection.source)
    return institution.load(
        selection.path, category_mapping, filtered_rows, start, end
    )


def parse_args(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    """CLI for Robinhood and Venmo CSV import."""
    parser = argparse.ArgumentParser(
        description="Pick CSVs from ~/Downloads and import them into Sure."
    )
    parser.add_argument("--file", type=Path, help="Venmo CSV path (skips the menu)")
    for institution in INSTITUTIONS:
        parser.add_argument(
            f"--{institution.cli_flag}",
            type=Path,
            help=f"{institution.label} CSV path (skips the menu)",
        )
    parser.add_argument(
        "--month",
        help="Only import YYYY-MM. Omit this to import every row in the chosen files",
    )
    parser.add_argument(
        "--categories",
        type=Path,
        default=DEFAULT_CATEGORIES,
        help="Path to transaction_categories.json",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and match, but do not write to Sure",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Write without the keep/undo prompt",
    )
    return parser.parse_args(list(argv) if argv is not None else None)


def path_from_args(args: argparse.Namespace, institution: Institution) -> Optional[Path]:
    """CSV path for one institution, including the Venmo ``--file`` alias."""
    path = getattr(args, institution.cli_flag, None)
    if path is None and institution.file_alias:
        path = args.file
    return path


def resolve_selections(args: argparse.Namespace) -> list[CsvSelection]:
    """CLI paths, or one menu per institution."""
    if args.file and args.venmo:
        raise ValueError("Pass either --file or --venmo, not both.")
    selections: list[CsvSelection] = []
    for institution in INSTITUTIONS:
        path = path_from_args(args, institution)
        if path is not None:
            selections.append(CsvSelection(institution.source, path.expanduser()))
    if selections:
        return selections
    return prompt_csv_selections(Path.home() / "Downloads")


def preview_accounts(
    client: SureClient,
    loaded: list[tuple[CsvSelection, list[StatementRow]]],
    configured_account: str,
    category_ids: dict[str, str],
) -> tuple[list[tuple[str, list[Planned]]], int]:
    """Match parsed rows to Sure and print the plan. Return plans and write count."""
    ready: list[tuple[str, list[Planned]]] = []
    created = updated = skipped = 0
    for selection, rows in loaded:
        if not rows:
            continue
        account_name = account_name_for(selection.source, configured_account)
        account = client.account_by_name(account_name)
        row_start = min(row.txn_date for row in rows)
        row_end = max(row.txn_date for row in rows)
        existing = client.transactions_for_account(account["id"], row_start, row_end)
        print(
            f"\n{account_name} ({account['id']}), "
            f"{len(existing)} existing txn(s)"
        )
        planned, unmatched = plan_rows(rows, existing, category_ids)
        _print_unmatched(unmatched)
        ready.append((str(account["id"]), planned))
        created += sum(1 for item in planned if item.action == "create")
        updated += sum(1 for item in planned if item.action == "update")
        skipped += sum(1 for item in planned if item.action == "skip")
    print(
        f"\ncreate={created} update={updated} skip={skipped} "
        f"csv_rows={created + updated + skipped}"
    )
    return ready, created + updated


def _print_unmatched(unmatched: list[SureTxn]) -> None:
    if not unmatched:
        return
    print("Unmatched Sure transactions (not in this CSV):")
    for txn in unmatched:
        print(f"  {txn.txn_date} {txn.signed_amount_cents / 100:+.2f}  {txn.name}")


def run_import(args: argparse.Namespace, selections: list[CsvSelection]) -> int:
    """Categorize the chosen CSVs, preview them, then keep or undo."""
    for selection in selections:
        if not selection.path.is_file():
            print(f"CSV not found: {selection.path}", file=sys.stderr)
            return 1
    flagged = any(getattr(args, institution.cli_flag) for institution in INSTITUTIONS)
    legacy = bool(args.file) and not flagged
    start, end = import_window(args.month, legacy_previous_month=legacy)
    entire_file = start == date.min and end == date.max
    if not entire_file:
        print(f"Date window {start.isoformat()} → {end.isoformat()}")

    try:
        base_url, api_key, configured_account = resolve_credentials()
        client = SureClient(base_url, api_key)
    except Exception as exc:
        print(f"Sure API error: {exc}", file=sys.stderr)
        return 1

    ready: list[tuple[str, list[Planned]]] = []
    while True:
        try:
            if not args.categories.is_file():
                raise FileNotFoundError(f"Categories JSON not found: {args.categories}")
            category_mapping, filtered_rows = load_category_config(args.categories)
            loaded: list[tuple[CsvSelection, list[StatementRow]]] = []
            for selection in selections:
                rows = load_selection(
                    selection, category_mapping, filtered_rows, start, end
                )
                print(f"Loaded {selection.path.name}: {len(rows)} row(s)")
                loaded.append((selection, rows))
        except json.JSONDecodeError as exc:
            print(f"Could not read categories: {exc}", file=sys.stderr)
            loaded = []
        except OSError as exc:
            print(str(exc), file=sys.stderr)
            loaded = []
        except (RuntimeError, ValueError) as exc:
            print(str(exc), file=sys.stderr)
            return 1

        if not loaded:
            if args.dry_run or args.yes or not sys.stdin.isatty():
                return 1
            decision = confirm_import(0, assume_yes=False, include_keep=False)
            if decision == "rerun":
                print(f"\nRe-reading {args.categories}…")
                continue
            return 1 if decision == "blocked" else 0

        if not any(rows for _, rows in loaded):
            print("Nothing to import.")
            ready = []
            to_write = 0
        else:
            try:
                category_ids = client.categories_by_name()
                ready, to_write = preview_accounts(
                    client, loaded, configured_account, category_ids
                )
            except Exception as exc:
                print(f"Sure API error: {exc}", file=sys.stderr)
                return 1

        if args.dry_run:
            print("Dry run — nothing written.")
            return 0
        if to_write == 0 and (args.yes or not sys.stdin.isatty()):
            print("Nothing to write.")
            return 0

        decision = confirm_import(to_write, assume_yes=args.yes)
        if decision == "rerun":
            print(f"\nRe-reading {args.categories}…")
            continue
        if decision != "keep":
            return 1 if decision == "blocked" else 0
        if to_write == 0:
            print("Nothing to write.")
            return 0
        break

    written: list[Mutation] = []
    try:
        for account_id, planned in ready:
            apply_planned(client, account_id, planned, written)
    except Exception as exc:
        print(f"Sure API error: {exc}", file=sys.stderr)
        undo_mutations(client, written)
        print("Undid the writes from this import.", file=sys.stderr)
        return 1

    print(f"Kept {to_write} transaction(s).")
    return 0


def main(argv: Optional[Iterable[str]] = None) -> int:
    """Pick Robinhood and Venmo CSVs, categorize, and import into Sure."""
    args = parse_args(argv)
    try:
        selections = resolve_selections(args)
    except SelectionCancelled:
        print("Cancelled. Nothing imported.")
        return 0
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if not selections:
        print("Nothing selected.")
        return 0
    return run_import(args, selections)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt as exc:
        print("\nInterrupted.", file=sys.stderr)
        raise SystemExit(130) from exc
