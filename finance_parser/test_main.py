"""Unit tests for Venmo parsing and Sure matching (no API)."""

# pylint: disable=missing-class-docstring,missing-function-docstring

from __future__ import annotations

import io
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path

from main import (
    RobinhoodRow,
    SureTxn,
    VenmoRow,
    arrow_select,
    move_menu_index,
    categorize_transaction,
    clean_amount,
    INSTITUTIONS,
    Planned,
    PreviewLine,
    confirm_choices,
    cycle_sort,
    format_preview_row,
    sort_preview_lines,
    csv_menu_options,
    find_match,
    pick_account,
    format_csv_choice,
    import_window,
    load_robinhood_rows,
    load_venmo_rows,
    match_score,
    month_bounds,
    previous_month_bounds,
    recent_csvs,
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


ROBINHOOD_CSV = """Date,Time,Cardholder,Amount,Points,Balance,Status,Type,Merchant,Description
2026-09-30,"3:21 PM","Tyler Woodfin",738.88,2217,3408.97,Posted,Purchase,Agoda,"AGODA.COM APA HOTEL New York NY"
2026-09-28,"2:48 PM","Tyler Woodfin",73.61,221,2670.09,Posted,Purchase,"Troops Mowing","TROOPS MOWING WWW.TROOPSMOWTX"
2026-09-27,"1:40 PM","Tyler Woodfin",10.00,30,2596.48,Posted,Purchase,"SAN FRANCISCO STREET FA","SAN FRANCISCO STREET FA OAKLAND CA"
2026-09-26,"9:00 AM","Tyler Woodfin",-12.50,0,2586.48,Posted,Refund,Agoda,"AGODA.COM REFUND"
2026-09-26,"8:00 AM","Tyler Woodfin",4.00,0,2599.00,Pending,Purchase,Cafe,"CAFE"
2026-09-25,"8:00 AM","Tyler Woodfin",0.00,0,2599.00,Posted,Purchase,Zero,"ZERO"
"""


class RobinhoodCsvTests(unittest.TestCase):
    mapping = {"Vacation Flights, Hotels, and Activities": ["agoda", "hotel"]}

    def _load(self, filtered: list[str] | None = None) -> list[RobinhoodRow]:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "card.csv"
            path.write_text(ROBINHOOD_CSV, encoding="utf-8")
            return load_robinhood_rows(
                path,
                self.mapping,
                filtered or [],
                start=date.min,
                end=date.max,
            )

    def test_posted_purchases_are_expenses(self) -> None:
        rows = self._load()
        self.assertEqual(len(rows), 4)
        hotel = rows[0]
        self.assertEqual(hotel.txn_date, date(2026, 9, 30))
        self.assertEqual(hotel.display_name, "Agoda")
        self.assertEqual(hotel.notes, "AGODA.COM APA HOTEL New York NY")
        self.assertEqual(hotel.amount, -738.88)
        self.assertEqual(hotel.nature, "expense")
        self.assertEqual(hotel.amount_cents, -73888)
        self.assertEqual(hotel.category, "Vacation Flights, Hotels, and Activities")
        self.assertEqual(hotel.source, "robinhood_cc")

    def test_refund_is_income_and_pending_and_zero_are_skipped(self) -> None:
        rows = self._load()
        refund = rows[-1]
        self.assertEqual(refund.amount, 12.50)
        self.assertEqual(refund.nature, "income")
        self.assertTrue(all(row.display_name != "Cafe" for row in rows))
        self.assertTrue(all(row.display_name != "Zero" for row in rows))

    def test_external_id_is_stable_and_matches(self) -> None:
        first = self._load()[0]
        second = self._load()[0]
        self.assertEqual(first.external_id, second.external_id)
        txn = SureTxn(
            txn_id="sure-rh",
            txn_date=first.txn_date,
            name="Something else",
            signed_amount_cents=first.amount_cents,
            category_name=None,
            source="robinhood_cc",
            external_id=first.external_id,
        )
        self.assertEqual(find_match(first, [txn]), txn)

    def test_filtered_description(self) -> None:
        rows = self._load(filtered=["street fa"])
        self.assertTrue(all("STREET" not in row.display_name for row in rows))

    def test_rejects_venmo_header(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "venmo.csv"
            path.write_text("ID,Datetime,Note\n", encoding="utf-8")
            with self.assertRaises(RuntimeError):
                load_robinhood_rows(path, {}, [], date.min, date.max)


class PickerTests(unittest.TestCase):
    def test_recent_csvs_keeps_five_newest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            for index in range(7):
                path = folder / f"f{index}.csv"
                path.write_text("a", encoding="utf-8")
                os.utime(path, (index, 1_700_000_000 + index))
            (folder / "notes.txt").write_text("no", encoding="utf-8")
            names = [path.name for path in recent_csvs(folder)]
        self.assertEqual(names, ["f6.csv", "f5.csv", "f4.csv", "f3.csv", "f2.csv"])

    def test_format_includes_name_and_modified_time(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "card.csv"
            path.write_text("a", encoding="utf-8")
            os.utime(path, (1_700_000_000, 1_700_000_000))
            label = format_csv_choice(path)
        self.assertIn("card.csv", label)
        self.assertRegex(label, r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}")

    def test_menu_offers_skip_under_the_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "card.csv"
            path.write_text("a", encoding="utf-8")
            options = csv_menu_options([path], skip_label="skip Robinhood")
        self.assertEqual(options[0][1], path)
        self.assertEqual(options[1], ("skip Robinhood", None))
        self.assertEqual(len(options), 2)

    def test_institutions_are_a_registry(self) -> None:
        self.assertEqual([item.label for item in INSTITUTIONS], ["Robinhood", "Venmo"])
        self.assertEqual(
            [item.skip_label for item in INSTITUTIONS],
            ["skip Robinhood", "skip Venmo"],
        )
        self.assertEqual(
            [item.prompt for item in INSTITUTIONS],
            ["Robinhood CSV?", "Venmo CSV?"],
        )

    def test_arrow_select_moves_then_confirms(self) -> None:
        keys = iter(["down", "enter"])
        output = io.StringIO()
        choice = arrow_select(
            "Robinhood CSV?",
            [("one", "a"), ("two", "b")],
            read_key=lambda: next(keys),
            write=output.write,
        )
        self.assertEqual(choice, "b")
        self.assertIn("Robinhood CSV?", output.getvalue())
        self.assertIn("> two", output.getvalue())

    def test_arrow_up_on_a_csv_menu_wraps_to_the_bottom(self) -> None:
        keys = iter(["up", "enter"])
        choice = arrow_select(
            "Robinhood CSV?",
            [("one.csv", "a"), ("two.csv", "b"), ("skip Robinhood", None)],
            read_key=lambda: next(keys),
            write=io.StringIO().write,
            wrap=True,
        )
        self.assertIsNone(choice)
        self.assertEqual(move_menu_index(0, "up", 3, wrap=False), 0)

    def test_confirm_choices_include_rerun(self) -> None:
        labels = [label for label, _ in confirm_choices()]
        self.assertEqual(labels, ["Keep", "Undo", "Re-run Categories"])
        self.assertEqual(confirm_choices()[2][1], "rerun")
        without_keep = [label for label, _ in confirm_choices(include_keep=False)]
        self.assertEqual(without_keep, ["Undo", "Re-run Categories"])

    def test_import_window(self) -> None:
        start, end = import_window(None, legacy_previous_month=False)
        self.assertEqual(start, date.min)
        self.assertEqual(end, date.max)
        start, end = import_window("2026-09", legacy_previous_month=False)
        self.assertEqual((start, end), month_bounds("2026-09"))


class PreviewTableTests(unittest.TestCase):
    def _line(self, day: int, category: str, name: str, action: str = "create") -> PreviewLine:
        row = VenmoRow(
            venmo_id=name,
            txn_date=date(2026, 9, day),
            note=name,
            from_name="",
            to_name="",
            amount=-10.0,
            txn_type="Payment",
            category=category,
        )
        return PreviewLine("Venmo", Planned(action, row, None, None))

    def test_sort_by_date_and_category(self) -> None:
        lines = [
            self._line(18, "Restaurants", "Coffee"),
            self._line(17, "Games/Apps", "Steam"),
            self._line(18, "Cursor", "IDE"),
        ]
        by_date = sort_preview_lines(lines, "date", reverse=True)
        self.assertEqual(
            [line.planned.row.display_name for line in by_date],
            ["Coffee", "IDE", "Steam"],
        )
        by_category = sort_preview_lines(lines, "category", reverse=False)
        self.assertEqual(
            [line.planned.row.category for line in by_category],
            ["Cursor", "Games/Apps", "Restaurants"],
        )

    def test_same_column_reverses_direction(self) -> None:
        directions = {"date": True, "category": False}
        column, directions = cycle_sort("date", directions, "date")
        self.assertEqual(column, "date")
        self.assertFalse(directions["date"])
        column, directions = cycle_sort(column, directions, "category")
        self.assertEqual(column, "category")
        self.assertFalse(directions["category"])
        column, directions = cycle_sort(column, directions, "category")
        self.assertTrue(directions["category"])

    def test_update_is_a_star_and_new_rows_have_no_action_word(self) -> None:
        new = format_preview_row(
            self._line(18, "Restaurants", "Coffee").planned,
            category_width=20,
            name_width=20,
            color=False,
        )
        update = format_preview_row(
            self._line(17, "Other", "BILL PAYMENT", action="update").planned,
            category_width=20,
            name_width=20,
            color=True,
        )
        self.assertNotIn("create", new)
        self.assertTrue(new.startswith(" "))
        self.assertIn("\033[31m*\033[0m", update)
        self.assertNotIn("update", update.split("BILL", 1)[0])


class AccountMatchTests(unittest.TestCase):
    accounts = [
        {"id": "venmo", "name": "Venmo"},
        {"id": "card", "name": "Robinhood Credit Card **4696"},
        {"id": "broker", "name": "Robinhood Investments"},
    ]

    def test_exact_name(self) -> None:
        self.assertEqual(pick_account(self.accounts, "Venmo")["id"], "venmo")

    def test_robinhood_card_prefix(self) -> None:
        chosen = pick_account(self.accounts, "Robinhood Credit Card")
        self.assertEqual(chosen["id"], "card")

    def test_investments_does_not_match_the_card(self) -> None:
        chosen = pick_account(self.accounts, "Robinhood Investments")
        self.assertEqual(chosen["id"], "broker")


if __name__ == "__main__":
    unittest.main()
