"""Unit tests for Amazon order collapse and Sure matching (no browser, no API)."""

from __future__ import annotations

import csv
import tempfile
import unittest
from datetime import date
from pathlib import Path

from amazon import (
    AmazonOrder,
    confirmation_message,
    failure_message,
    load_amazon_orders,
    month_label,
    parse_amount,
    plan_imports,
)
from export_firefox import (
    _expiry_seconds,
    _same_site,
    merge_cards,
    parse_parsed_order_line,
    write_export_csv,
)
from main import SureTxn

HEADER = [
    "Order ID",
    "Order Date",
    "Total Amount",
    "Currency",
    "Total Savings",
    "Status",
    "Item Title",
    "Item ASIN",
    "Item Quantity",
    "Item Price",
    "Item Discount",
]


def _csv(rows: list[list[str]]) -> Path:
    handle = tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, encoding="utf-8", newline="")
    writer = csv.writer(handle)
    writer.writerow(HEADER)
    writer.writerows(rows)
    handle.close()
    return Path(handle.name)


class ParseTests(unittest.TestCase):
    def test_amount(self) -> None:
        self.assertEqual(parse_amount("$1,234.50"), 1234.5)
        self.assertEqual(parse_amount(""), 0.0)

    def test_collapses_line_items_and_skips(self) -> None:
        path = _csv(
            [
                ["111-0000001-0000001", "2026-08-02", "25.50", "USD", "0", "Delivered", "Widgets", "A", "1", "10", "0"],
                ["111-0000001-0000001", "2026-08-02", "25.50", "USD", "", "Delivered", "Gadget", "B", "1", "15.50", "0"],
                ["111-0000002-0000002", "2026-08-03", "12.00", "USD", "0", "Cancelled", "Nope", "C", "1", "12", "0"],
                ["111-0000003-0000003", "2026-08-04", "0", "USD", "0", "Delivered", "Free", "D", "1", "0", "0"],
                ["111-0000004-0000004", "2026-07-31", "9.00", "USD", "0", "Delivered", "Old", "E", "1", "9", "0"],
                ["111-0000005-0000005", "2026-08-20", "8.00", "USD", "0", "Delivered", "Tea, loose", "F", "1", "8", "0"],
            ]
        )
        orders = load_amazon_orders(
            path,
            date(2026, 8, 1),
            date(2026, 8, 31),
            {"Groceries": ["tea"]},
            [],
        )
        self.assertEqual([order.order_id for order in orders], [
            "111-0000001-0000001",
            "111-0000005-0000005",
        ])
        first = orders[0]
        self.assertEqual(first.name, "Widgets; Gadget")
        self.assertEqual(first.amount, 25.5)
        self.assertEqual(first.nature, "expense")
        self.assertEqual(first.signed_cents, -2550)
        self.assertEqual(first.category, "Other")
        self.assertEqual(orders[1].category, "Groceries")
        self.assertEqual(orders[1].name, "Tea, loose")


class PlanTests(unittest.TestCase):
    def _order(self, order_id: str = "111-1", amount: float = 10.0) -> AmazonOrder:
        return AmazonOrder(
            order_id=order_id,
            txn_date=date(2026, 8, 2),
            amount=amount,
            nature="expense",
            status="Delivered",
            name="Widgets",
            notes="Amazon order",
            category="Other",
        )

    def test_skip_external_id_and_date_amount(self) -> None:
        orders = [self._order("111-1", 10), self._order("111-2", 4)]
        existing = [
            SureTxn(
                txn_id="a",
                txn_date=date(2026, 8, 2),
                name="Widgets",
                signed_amount_cents=-1000,
                category_name=None,
                source="amazon",
                external_id="111-1",
            ),
            SureTxn(
                txn_id="b",
                txn_date=date(2026, 8, 2),
                name="Something",
                signed_amount_cents=-400,
                category_name=None,
                source="manual",
                external_id=None,
            ),
        ]
        self.assertEqual(
            [action for action, _order in plan_imports(orders, existing)],
            ["skip", "skip"],
        )

    def test_create_when_unmatched(self) -> None:
        planned = plan_imports([self._order()], [])
        self.assertEqual(planned[0][0], "create")


class CookieTests(unittest.TestCase):
    def test_expiry_milliseconds(self) -> None:
        self.assertEqual(_expiry_seconds(1_820_000_000_000), 1_820_000_000)
        self.assertEqual(_expiry_seconds(1_820_000_000), 1_820_000_000)

    def test_same_site(self) -> None:
        self.assertEqual(_same_site(256, False), "Lax")
        self.assertEqual(_same_site(256, True), "None")
        self.assertEqual(_same_site(1, True), "Lax")
        self.assertEqual(_same_site(2, True), "Strict")


class ExportCaptureTests(unittest.TestCase):
    def test_parse_and_write(self) -> None:
        line = "[Amazon Exporter] Parsed order: 111-1, 2026-08-02, 25.5 USD"
        self.assertEqual(
            parse_parsed_order_line(line),
            {"id": "111-1", "date": "2026-08-02", "amount": "25.5", "currency": "USD"},
        )
        self.assertIsNone(parse_parsed_order_line("Scraping visible page..."))
        cards: dict[str, dict[str, object]] = {}
        merge_cards(
            cards,
            [{"id": "111-1", "titles": ["Widgets", "Widgets"], "status": "Delivered"}],
        )
        path = Path(tempfile.mkdtemp()) / "orders.csv"
        write_export_csv(
            path,
            [{"id": "111-1", "date": "2026-08-02", "amount": "25.5", "currency": "USD"}],
            cards,
        )
        orders = load_amazon_orders(path, date(2026, 8, 1), date(2026, 8, 31), {}, [])
        self.assertEqual(len(orders), 1)
        self.assertEqual(orders[0].name, "Widgets")
        self.assertEqual(orders[0].amount, 25.5)
        self.assertEqual(orders[0].status, "Delivered")


class MessageTests(unittest.TestCase):
    def test_month_label(self) -> None:
        self.assertEqual(month_label(date(2026, 8, 1)), "August 2026")

    def test_confirmation(self) -> None:
        self.assertIn(
            "didn't find",
            confirmation_message("August 2026", 0, 0, 0),
        )
        self.assertIn(
            "already in Sure",
            confirmation_message("August 2026", 0, 3, 0),
        )
        text = confirmation_message("August 2026", 2, 1, 12.5)
        self.assertIn("I added 2 August 2026 Amazon orders ($12.50) to Sure.", text)
        self.assertIn("1 was already there.", text)
        one = confirmation_message("August 2026", 1, 0, 4)
        self.assertIn("1 August 2026 Amazon order ($4.00)", one)

    def test_failure_collapses_whitespace(self) -> None:
        text = failure_message("August 2026", "Amazon\nasked   to sign in")
        self.assertEqual(
            text,
            "I couldn't pull your August 2026 Amazon orders into Sure. Amazon asked to sign in",
        )


if __name__ == "__main__":
    unittest.main()
