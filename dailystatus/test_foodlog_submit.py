"""Tests for foodlog submit gating in dailystatus (TJW-245)."""

import unittest
from unittest import mock

from main import append_food_log, is_foodlog_submitted


class _FakeStore:
    def __init__(self, entries=None, submitted=False):
        self._entries = entries or []
        self._submitted = submitted

    def is_day_submitted(self, day):  # pylint: disable=unused-argument
        return self._submitted

    def get_entries(self, day):  # pylint: disable=unused-argument
        return self._entries

    def migrate_from_json_files(self, *args, **kwargs):  # pylint: disable=unused-argument
        return 0


class FoodlogSubmitTests(unittest.TestCase):
    def test_is_foodlog_submitted_shapes(self):
        self.assertFalse(is_foodlog_submitted("2026-07-20", {}))
        self.assertTrue(is_foodlog_submitted("2026-07-20", {"2026-07-20": True}))
        self.assertTrue(
            is_foodlog_submitted("2026-07-20", {"2026-07-20": {"submitted": True}})
        )
        self.assertFalse(
            is_foodlog_submitted("2026-07-20", {"2026-07-20": {"submitted": False}})
        )

    def test_append_food_log_reminds_when_not_submitted(self):
        store = _FakeStore(
            entries=[{"food": "apple", "calories": 50}],
            submitted=False,
        )
        with mock.patch("main.datetime") as dt:
            dt.date.today.return_value = __import__("datetime").date(2026, 7, 20)
            with mock.patch("main._foodlog_store", return_value=store):
                with mock.patch("main.mail") as mail:
                    email = append_food_log("", dry_run=False)

        mail.send.assert_called_once()
        self.assertIn("50 calories", email)
        self.assertNotIn("submitted", email)

    def test_append_food_log_skips_reminder_when_submitted(self):
        store = _FakeStore(
            entries=[{"food": "apple", "calories": 50}],
            submitted=True,
        )
        with mock.patch("main.datetime") as dt:
            dt.date.today.return_value = __import__("datetime").date(2026, 7, 20)
            with mock.patch("main._foodlog_store", return_value=store):
                with mock.patch("main.mail") as mail:
                    email = append_food_log("", dry_run=False)

        mail.send.assert_not_called()
        self.assertIn("50 calories (submitted)", email)

    def test_append_food_log_reminds_even_with_no_entries(self):
        store = _FakeStore(entries=[], submitted=False)
        with mock.patch("main.datetime") as dt:
            dt.date.today.return_value = __import__("datetime").date(2026, 7, 20)
            with mock.patch("main._foodlog_store", return_value=store):
                with mock.patch("main.mail") as mail:
                    email = append_food_log("base", dry_run=False)

        mail.send.assert_called_once()
        self.assertEqual(email, "base")


if __name__ == "__main__":
    unittest.main()
