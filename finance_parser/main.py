#!/usr/bin/env python3
"""Import the latest Venmo statement CSV into Sure."""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable, Optional

import requests
from cabinet import Cabinet

VENMO_PATTERN = "VenmoStatement*.csv"
DEFAULT_CATEGORIES = Path.home() / "syncthing/notes/docs/selfhosted/transaction_categories.json"
DEFAULT_SURE_BASE_URL = "http://192.168.1.101:3006"
DEFAULT_ACCOUNT_NAME = "Venmo"
SKIP_SURE_NAMES = {"manual balance update"}
QUOTED_NOTE = re.compile(r'"([^"]+)"')


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
        """Return the Sure account whose name matches ``name`` (case-insensitive)."""
        accounts = self.paginate("/api/v1/accounts", "accounts")
        for account in accounts:
            if (account.get("name") or "").strip().lower() == name.strip().lower():
                return account
        names = ", ".join(a.get("name") or "?" for a in accounts)
        raise RuntimeError(f"Sure account {name!r} not found. Available: {names}")

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
                )
            )
        return result

    def create_transaction(
        self,
        account_id: str,
        row: VenmoRow,
        category_id: Optional[str],
    ) -> dict[str, Any]:
        """Create a Sure transaction from a Venmo CSV row."""
        body: dict[str, Any] = {
            "account_id": account_id,
            "date": row.txn_date.isoformat(),
            "amount": abs(row.amount),
            "nature": row.nature,
            "name": row.display_name,
            "notes": _party_note(row),
            "external_id": row.venmo_id,
            "source": "venmo",
            "user_modified": True,
        }
        if category_id:
            body["category_id"] = category_id
        return self._post("/api/v1/transactions", {"transaction": body})

    def update_transaction(
        self,
        txn_id: str,
        row: VenmoRow,
        category_id: Optional[str],
    ) -> dict[str, Any]:
        """Update name/notes/category on an existing Sure transaction."""
        body: dict[str, Any] = {
            "name": row.display_name,
            "notes": _party_note(row),
            "user_modified": True,
        }
        if category_id:
            body["category_id"] = category_id
        return self._put(f"/api/v1/transactions/{txn_id}", {"transaction": body})


def find_latest_file_in_downloads(pattern: str) -> Optional[Path]:
    """Return the newest file in ~/Downloads matching pattern, if any."""
    downloads = Path.home() / "Downloads"
    matches = list(downloads.glob(pattern))
    if not matches:
        return None
    return max(matches, key=lambda path: path.stat().st_mtime)


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


def match_score(row: VenmoRow, txn: SureTxn) -> int:
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


def find_match(row: VenmoRow, unmatched: list[SureTxn]) -> Optional[SureTxn]:
    """Pick the best unmatched Sure txn for this CSV row, or None."""
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


def _fmt_amount(row: VenmoRow) -> str:
    return f"{row.amount:+.2f}"


def import_rows(
    client: SureClient,
    account_id: str,
    rows: list[VenmoRow],
    existing: list[SureTxn],
    category_ids: dict[str, str],
    dry_run: bool,
) -> None:
    """Match CSV rows to Sure, then update or create."""
    unmatched = list(existing)
    created = updated = skipped = 0

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
                skipped += 1
            else:
                action = "update"
                updated += 1
                if not dry_run:
                    client.update_transaction(match.txn_id, row, category_id)
        else:
            action = "create"
            created += 1
            if not dry_run:
                client.create_transaction(
                    account_id,
                    row,
                    category_ids.get(row.category) if row.category != "Other" else None,
                )
        print(
            f"{action:<8} {row.txn_date.isoformat():<12} {_fmt_amount(row):>10}  "
            f"{row.category:<42} {row.display_name}"
        )

    verb = "would be " if dry_run else ""
    print(
        f"\n{verb}create={created} update={updated} skip={skipped} "
        f"csv_rows={len(rows)} unmatched_in_sure={len(unmatched)}"
    )
    if unmatched:
        print("Unmatched Sure transactions (not in this CSV):")
        for txn in unmatched:
            print(f"  {txn.txn_date} {txn.signed_amount_cents / 100:+.2f}  {txn.name}")


def parse_args(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    """CLI for Venmo → Sure import."""
    parser = argparse.ArgumentParser(
        description="Import the latest Venmo statement into Sure (previous month by default)."
    )
    parser.add_argument(
        "--file",
        type=Path,
        help="Venmo CSV path (default: newest VenmoStatement*.csv in ~/Downloads)",
    )
    parser.add_argument(
        "--month",
        help="Import YYYY-MM instead of the previous calendar month",
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
    return parser.parse_args(list(argv) if argv is not None else None)


def main(argv: Optional[Iterable[str]] = None) -> int:
    """Load Venmo CSV, categorize, and import into Sure."""
    args = parse_args(argv)
    csv_path = args.file or find_latest_file_in_downloads(VENMO_PATTERN)
    if csv_path is None:
        print(
            "No VenmoStatement*.csv found in ~/Downloads. "
            "Download the monthly statement from Venmo and retry.",
            file=sys.stderr,
        )
        return 1
    csv_path = csv_path.expanduser()
    if not csv_path.is_file():
        print(f"CSV not found: {csv_path}", file=sys.stderr)
        return 1

    if not args.categories.is_file():
        print(f"Categories JSON not found: {args.categories}", file=sys.stderr)
        return 1

    start, end = month_bounds(args.month) if args.month else previous_month_bounds()
    category_mapping, filtered_rows = load_category_config(args.categories)
    rows = load_venmo_rows(csv_path, category_mapping, filtered_rows, start, end)
    print(f"Loaded {csv_path.name}: {len(rows)} row(s) for {start} → {end}")
    if not rows:
        print("Nothing to import.")
        return 0

    try:
        base_url, api_key, account_name = resolve_credentials()
        client = SureClient(base_url, api_key)
        account = client.account_by_name(account_name)
        category_ids = client.categories_by_name()
        existing = client.transactions_for_account(account["id"], start, end)
    except Exception as exc:
        print(f"Sure API error: {exc}", file=sys.stderr)
        return 1

    print(f"Sure account {account_name!r} ({account['id']}), {len(existing)} existing txn(s)")
    if args.dry_run:
        print("Dry run — no writes.")
    import_rows(client, account["id"], rows, existing, category_ids, args.dry_run)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt as exc:
        print("\nInterrupted.", file=sys.stderr)
        raise SystemExit(130) from exc
