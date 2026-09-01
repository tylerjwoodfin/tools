"""Unit tests for Venmo parsing and Sure matching (no API)."""

# pylint: disable=missing-class-docstring,missing-function-docstring

from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path

from main import (
    SureTxn,
    VenmoRow,
    categorize_transaction,
    clean_amount,
    find_match,
    load_venmo_rows,
    match_score,
    month_bounds,
    previous_month_bounds,
    should_include_transaction,
)


class AmountTests(unittest.TestCase):
    def test_venmo_formats(self) -> None:
        self.assertEqual(clean_amount("- $58.44"), -58.44)
        self.assertEqual(clean_amount("+ $3.50"), 3.5)
        self.assertEqual(clean_amount("- $1,000.00"), -1000.0)

    def test_amount_cents_matches_sure_signed(self) -> None:
        expense = VenmoRow(
            venmo_id="1",
            txn_date=date(2026, 8, 1),
            note="PG&E",
            from_name="Tyler",
            to_name="Huy",
            amount=-58.44,
            txn_type="Payment",
            category="PG&E",
        )
        income = VenmoRow(
            venmo_id="2",
            txn_date=date(2026, 8, 2),
            note="Fruit",
            from_name="Huy",
            to_name="Tyler",
            amount=3.5,
            txn_type="Payment",
            category="Groceries",
        )
        self.assertEqual(expense.amount_cents, -5844)
        self.assertEqual(expense.nature, "expense")
        self.assertEqual(income.amount_cents, 350)
        self.assertEqual(income.nature, "income")


class CategoryTests(unittest.TestCase):
    mapping = {
        "Groceries": ["groceries", "trader joe"],
        "Vacation Flights, Hotels, and Activities": ["hotel", "Travel-", "!UNITED PACIFIC"],
        "Birthdays and Gifts": ["👶"],
    }

    def test_keyword_and_exclusion(self) -> None:
        self.assertEqual(categorize_transaction("Trader joe", self.mapping), "Groceries")
        self.assertEqual(
            categorize_transaction("Hotel, Kyoto", self.mapping),
            "Vacation Flights, Hotels, and Activities",
        )
        self.assertEqual(categorize_transaction("UNITED PACIFIC", self.mapping), "Other")
        self.assertEqual(categorize_transaction("Benji 👶", self.mapping), "Birthdays and Gifts")
        self.assertEqual(categorize_transaction("Benji baby", self.mapping), "Other")

    def test_filtered_rows(self) -> None:
        self.assertFalse(should_include_transaction("Posted", ["Posted"]))
        self.assertTrue(should_include_transaction("Groceries", ["Posted"]))


class DateWindowTests(unittest.TestCase):
    def test_previous_month(self) -> None:
        start, end = previous_month_bounds(date(2026, 9, 1))
        self.assertEqual(start, date(2026, 8, 1))
        self.assertEqual(end, date(2026, 8, 31))

    def test_month_flag(self) -> None:
        start, end = month_bounds("2026-08")
        self.assertEqual(start, date(2026, 8, 1))
        self.assertEqual(end, date(2026, 8, 31))


class MatchTests(unittest.TestCase):
    def _row(self, **kwargs: object) -> VenmoRow:
        base = dict(
            venmo_id="x",
            txn_date=date(2026, 8, 1),
            note="Toll",
            from_name="Tyler Woodfin",
            to_name="Huy Le",
            amount=-4.25,
            txn_type="Payment",
            category="Transit/Clipper/Rentals/Tolls/Ridehshares",
        )
        base.update(kwargs)
        return VenmoRow(**base)  # type: ignore[arg-type]

    def _txn(self, **kwargs: object) -> SureTxn:
        base = dict(
            txn_id="sure-1",
            txn_date=date(2026, 8, 1),
            name='Huy Le "Toll"',
            signed_amount_cents=-425,
            category_name="Transit/Clipper/Rentals/Tolls/Ridehshares",
            source="plaid",
            external_id="plaid-1",
        )
        base.update(kwargs)
        return SureTxn(**base)  # type: ignore[arg-type]

    def test_quoted_note_beats_same_amount(self) -> None:
        row = self._row()
        toll = self._txn()
        parking = self._txn(
            txn_id="sure-2", name='Huy Le "Parking"', signed_amount_cents=-425
        )
        self.assertGreater(match_score(row, toll), match_score(row, parking))
        self.assertEqual(find_match(row, [parking, toll]).txn_id, "sure-1")

    def test_unique_date_amount_without_name(self) -> None:
        row = self._row(note="PG&E, August", amount=-58.44)
        txn = self._txn(name="PG&E", signed_amount_cents=-5844)
        self.assertEqual(find_match(row, [txn]), txn)

    def test_ambiguous_same_amount_unmatched_without_name(self) -> None:
        row = self._row(note="Mystery", from_name="", to_name="", amount=-50.0)
        a = self._txn(txn_id="a", name="Alpha", signed_amount_cents=-5000)
        b = self._txn(txn_id="b", name="Beta", signed_amount_cents=-5000)
        self.assertIsNone(find_match(row, [a, b]))


class CsvLoadTests(unittest.TestCase):
    def test_skips_footer_and_filters_month(self) -> None:
        csv_text = """Account Statement
Account Activity
,ID,Datetime,Type,Status,Note,From,To,Amount (total)
,$215.99
,abc,2026-08-01T20:18:48,Payment,Complete,Toll,Tyler,Huy,- $4.25
,def,2026-07-15T12:00:00,Payment,Complete,Old,Tyler,Huy,- $1.00
,ghi,2026-08-02T10:00:00,Payment,Complete,Posted promo,Tyler,Huy,- $2.00
,,,,,,,,disclaimer
"""
        mapping = {"Transit/Clipper/Rentals/Tolls/Ridehshares": ["toll"]}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "VenmoStatement_Aug_2026.csv"
            path.write_text(csv_text, encoding="utf-8")
            rows = load_venmo_rows(
                path,
                mapping,
                filtered_rows=["Posted"],
                start=date(2026, 8, 1),
                end=date(2026, 8, 31),
            )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].note, "Toll")
        self.assertEqual(rows[0].category, "Transit/Clipper/Rentals/Tolls/Ridehshares")


if __name__ == "__main__":
    unittest.main()
