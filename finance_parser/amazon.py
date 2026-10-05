#!/usr/bin/env python3
"""Export last month's Amazon orders and import them into Sure.

Playwright drives the Order History Exporter extension in Firefox. Sure is
updated through its API on the cloud host (``sure.base_url``), not the
Authentik UI at sure.tyler.cloud.
"""

from __future__ import annotations

import argparse
import csv
import sys
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Iterable, Optional

from main import (
    SureClient,
    SureTxn,
    categorize_transaction,
    load_category_config,
    month_bounds,
    previous_month_bounds,
    resolve_credentials,
    should_include_transaction,
)

AMAZON_ACCOUNT = "Amazon Credit Card [Ally Checking]"
SOURCE = "amazon"
NAME_LIMIT = 180


@dataclass
class AmazonOrder:
    """One Amazon order, collapsed from exporter line items."""

    order_id: str
    txn_date: date
    amount: float
    nature: str
    status: str
    name: str
    notes: str
    category: str

    @property
    def signed_cents(self) -> int:
        """Signed cents matching Sure: income positive, expense negative."""
        cents = int(round(self.amount * 100))
        return cents if self.nature == "income" else -cents


@dataclass
class ImportSummary:
    """Counts from one Sure import."""

    created: int
    skipped: int
    created_spend: float


def month_label(start: date) -> str:
    """Calendar label for Cherry, e.g. ``August 2026``."""
    return start.strftime("%B %Y")


def confirmation_message(
    label: str, created: int, skipped: int, created_spend: float
) -> str:
    """Conversational note Cherry sends after a finished import."""
    if created == 0 and skipped == 0:
        return f"I didn't find any Amazon orders for {label}."
    if created == 0:
        return (
            f"Your {label} Amazon orders were already in Sure, so I left them as they are."
        )
    noun = "order" if created == 1 else "orders"
    if skipped == 1:
        extra = " 1 was already there."
    elif skipped:
        extra = f" {skipped} were already there."
    else:
        extra = ""
    return (
        f"I added {created} {label} Amazon {noun} (${created_spend:.2f}) to Sure.{extra}"
    )


def failure_message(label: str, reason: str) -> str:
    """Conversational note when the monthly run fails."""
    text = " ".join(reason.split())
    if len(text) > 180:
        text = text[:177] + "..."
    return f"I couldn't pull your {label} Amazon orders into Sure. {text}"


def parse_amount(value: object) -> float:
    """Parse an exporter amount like ``25.50`` or ``$1,000.00``."""
    text = str(value or "").replace("$", "").replace(",", "").strip()
    if not text:
        return 0.0
    try:
        return float(text)
    except ValueError:
        return 0.0


def parse_order_date(value: str) -> Optional[date]:
    """Parse ``YYYY-MM-DD`` or ``Month D, YYYY``."""
    text = (value or "").strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        pass
    try:
        return datetime.strptime(text, "%B %d, %Y").date()
    except ValueError:
        return None


def _is_cancelled(status: str) -> bool:
    return "cancel" in status.casefold()


def _display_name(order_id: str, titles: list[str]) -> str:
    if not titles:
        return f"Amazon {order_id}"
    name = "; ".join(titles)
    if len(name) > NAME_LIMIT:
        return name[: NAME_LIMIT - 3] + "..."
    return name


def load_amazon_orders(
    path: Path,
    start: date,
    end: date,
    category_mapping: dict[str, list],
    filtered_rows: list[str],
) -> list[AmazonOrder]:
    """Collapse exporter line items into one order per Order ID inside the window."""
    orders: list[AmazonOrder] = []
    grouped: dict[str, list[dict[str, str]]] = {}
    order_ids: list[str] = []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or "Order ID" not in reader.fieldnames:
            raise RuntimeError(f"{path} is not an Amazon order export (missing Order ID).")
        for raw in reader:
            order_id = (raw.get("Order ID") or "").strip()
            if not order_id:
                continue
            if order_id not in grouped:
                order_ids.append(order_id)
                grouped[order_id] = []
            grouped[order_id].append(raw)

    for order_id in order_ids:
        rows = grouped[order_id]
        first = rows[0]
        status = (first.get("Status") or "").strip()
        if _is_cancelled(status):
            continue
        amount = parse_amount(first.get("Total Amount"))
        if amount == 0:
            continue
        txn_date = parse_order_date(first.get("Order Date") or "")
        if txn_date is None or txn_date < start or txn_date > end:
            continue
        titles: list[str] = []
        for raw in rows:
            title = (raw.get("Item Title") or "").strip()
            if title and title not in titles:
                titles.append(title)
        name = _display_name(order_id, titles)
        if not should_include_transaction(name, filtered_rows):
            continue
        nature = "income" if amount < 0 else "expense"
        notes = f"Amazon order {order_id}"
        if status:
            notes = f"{notes} ({status})"
        currency = (first.get("Currency") or "").strip().upper()
        if currency and currency != "USD":
            notes = f"{notes} {currency}"
        orders.append(
            AmazonOrder(
                order_id=order_id,
                txn_date=txn_date,
                amount=abs(amount),
                nature=nature,
                status=status,
                name=name,
                notes=notes,
                category=categorize_transaction(name, category_mapping),
            )
        )
    return orders


def plan_imports(
    orders: list[AmazonOrder], existing: list[SureTxn]
) -> list[tuple[str, AmazonOrder]]:
    """Pair each order with ``create`` or ``skip`` without writing to Sure."""
    by_external = {txn.external_id: txn for txn in existing if txn.external_id}
    used: set[str] = set()
    planned: list[tuple[str, AmazonOrder]] = []
    for order in orders:
        prior = by_external.get(order.order_id)
        if prior is not None:
            used.add(prior.txn_id)
            planned.append(("skip", order))
            continue
        match = next(
            (
                txn
                for txn in existing
                if txn.txn_id not in used
                and txn.txn_date == order.txn_date
                and txn.signed_amount_cents == order.signed_cents
            ),
            None,
        )
        if match is not None:
            used.add(match.txn_id)
            planned.append(("skip", order))
            continue
        planned.append(("create", order))
    return planned


def amazon_account_name() -> str:
    """Sure account for Amazon orders. Does not use the Venmo account setting."""
    from cabinet import Cabinet

    override = Cabinet().get("sure", "amazon_account_name")
    text = str(override).strip() if override else ""
    return text or AMAZON_ACCOUNT


def import_orders(
    client: SureClient,
    account_id: str,
    orders: list[AmazonOrder],
    existing: list[SureTxn],
    category_ids: dict[str, str],
    dry_run: bool,
) -> ImportSummary:
    """Create Sure transactions for orders that are not already present."""
    created = skipped = 0
    created_spend = 0.0
    print(f"{'action':<8} {'date':<12} {'amount':>10}  {'category':<42} name")
    for action, order in plan_imports(orders, existing):
        category_id = None
        if order.category != "Other":
            category_id = category_ids.get(order.category)
        if action == "create":
            created += 1
            if order.nature == "expense":
                created_spend += order.amount
            if not dry_run:
                body: dict[str, object] = {
                    "account_id": account_id,
                    "date": order.txn_date.isoformat(),
                    "amount": order.amount,
                    "nature": order.nature,
                    "name": order.name,
                    "notes": order.notes,
                    "external_id": order.order_id,
                    "source": SOURCE,
                    "user_modified": True,
                }
                if category_id:
                    body["category_id"] = category_id
                client.post_transaction(body)
        else:
            skipped += 1
        sign = "+" if order.nature == "income" else "-"
        print(
            f"{action:<8} {order.txn_date.isoformat():<12} {sign}{order.amount:>9.2f}  "
            f"{order.category:<42} {order.name}"
        )
    verb = "would be " if dry_run else ""
    print(f"\n{verb}create={created} skip={skipped} orders={len(orders)}")
    return ImportSummary(created=created, skipped=skipped, created_spend=created_spend)


def notify(text: str) -> None:
    """Send a Cherry telegram. A delivery failure does not undo the import."""
    from cabinet import telegram as cabinet_telegram

    if cabinet_telegram(text, is_quiet=True):
        print("Cherry notified.")
    else:
        print("Cherry notification failed.", file=sys.stderr)


def parse_args(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    """CLI for the monthly Amazon → Sure import."""
    parser = argparse.ArgumentParser(
        description="Export the previous month of Amazon orders and import them into Sure."
    )
    parser.add_argument(
        "--file",
        type=Path,
        help="Importer CSV from the extension (skips Firefox)",
    )
    parser.add_argument("--month", help="Use YYYY-MM instead of the previous calendar month")
    parser.add_argument(
        "--categories",
        type=Path,
        default=None,
        help="Path to transaction_categories.json",
    )
    parser.add_argument("--dry-run", action="store_true", help="Match only; do not write to Sure")
    parser.add_argument("--headed", action="store_true", help="Show the Firefox window")
    parser.add_argument("--export-only", action="store_true", help="Write the CSV and stop")
    parser.add_argument("--no-notify", action="store_true", help="Do not message Cherry")
    return parser.parse_args(list(argv) if argv is not None else None)


def _categories_path(args: argparse.Namespace) -> Path:
    if args.categories is not None:
        return args.categories
    from main import DEFAULT_CATEGORIES

    return DEFAULT_CATEGORIES


def run(args: argparse.Namespace, start: date, end: date) -> ImportSummary:
    """Export if needed, then import the month into Sure."""
    categories_path = _categories_path(args)
    if not categories_path.is_file():
        raise RuntimeError(f"Categories JSON not found: {categories_path}")
    category_mapping, filtered_rows = load_category_config(categories_path)

    if args.file:
        csv_path = args.file.expanduser()
        if not csv_path.is_file():
            raise RuntimeError(f"CSV not found: {csv_path}")
    else:
        from export_firefox import export_amazon_csv

        print(f"Exporting Amazon orders for {start.isoformat()} → {end.isoformat()}")
        csv_path = export_amazon_csv(start, end, headless=not args.headed)
        print(f"Exported {csv_path}")

    if args.export_only:
        return ImportSummary(created=0, skipped=0, created_spend=0.0)

    orders = load_amazon_orders(csv_path, start, end, category_mapping, filtered_rows)
    print(f"Loaded {csv_path.name}: {len(orders)} order(s) for {start} → {end}")
    base_url, api_key, _venmo_account = resolve_credentials()
    account_name = amazon_account_name()
    client = SureClient(base_url, api_key)
    account = client.account_by_name(account_name)
    category_ids = client.categories_by_name()
    existing = client.transactions_for_account(account["id"], start, end)
    print(f"Sure account {account_name!r} ({account['id']}), {len(existing)} existing txn(s)")
    if args.dry_run:
        print("Dry run — no writes.")
    return import_orders(
        client, account["id"], orders, existing, category_ids, args.dry_run
    )


def main(argv: Optional[Iterable[str]] = None) -> int:
    """Export the previous month and import it into Sure."""
    args = parse_args(argv)
    start, end = month_bounds(args.month) if args.month else previous_month_bounds()
    label = month_label(start)
    try:
        summary = run(args, start, end)
    except Exception as exc:
        print(f"Amazon import failed: {exc}", file=sys.stderr)
        if not args.no_notify and not args.dry_run and not args.export_only:
            notify(failure_message(label, str(exc)))
        return 1
    if not args.no_notify and not args.dry_run and not args.export_only:
        notify(
            confirmation_message(
                label, summary.created, summary.skipped, summary.created_spend
            )
        )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt as exc:
        print("\nInterrupted.", file=sys.stderr)
        raise SystemExit(130) from exc
