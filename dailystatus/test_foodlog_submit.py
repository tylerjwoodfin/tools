"""Tests for foodlog submit gating in dailystatus (TJW-245)."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from main import append_food_log, is_foodlog_submitted


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
        with tempfile.TemporaryDirectory() as tmp:
            log_file = Path(tmp) / "food.json"
            submitted_file = Path(tmp) / "food_submitted.json"
            today = "2026-07-20"
            log_file.write_text(
                json.dumps({today: [{"food": "apple", "calories": 50}]}),
                encoding="utf-8",
            )
            submitted_file.write_text("{}", encoding="utf-8")

            with mock.patch("main.datetime") as dt:
                dt.date.today.return_value = __import__("datetime").date(2026, 7, 20)
                with mock.patch(
                    "main._food_log_paths",
                    return_value=(str(log_file), str(submitted_file)),
                ):
                    with mock.patch("main.mail") as mail:
                        email = append_food_log("", dry_run=False)

            mail.send.assert_called_once()
            self.assertIn("50 calories", email)
            self.assertNotIn("submitted", email)

    def test_append_food_log_skips_reminder_when_submitted(self):
        with tempfile.TemporaryDirectory() as tmp:
            log_file = Path(tmp) / "food.json"
            submitted_file = Path(tmp) / "food_submitted.json"
            today = "2026-07-20"
            log_file.write_text(
                json.dumps({today: [{"food": "apple", "calories": 50}]}),
                encoding="utf-8",
            )
            submitted_file.write_text(
                json.dumps({today: {"submitted": True}}),
                encoding="utf-8",
            )

            with mock.patch("main.datetime") as dt:
                dt.date.today.return_value = __import__("datetime").date(2026, 7, 20)
                with mock.patch(
                    "main._food_log_paths",
                    return_value=(str(log_file), str(submitted_file)),
                ):
                    with mock.patch("main.mail") as mail:
                        email = append_food_log("", dry_run=False)

            mail.send.assert_not_called()
            self.assertIn("50 calories (submitted)", email)

    def test_append_food_log_reminds_even_with_no_entries(self):
        with tempfile.TemporaryDirectory() as tmp:
            log_file = Path(tmp) / "food.json"
            submitted_file = Path(tmp) / "food_submitted.json"
            log_file.write_text("{}", encoding="utf-8")
            submitted_file.write_text("{}", encoding="utf-8")

            with mock.patch("main.datetime") as dt:
                dt.date.today.return_value = __import__("datetime").date(2026, 7, 20)
                with mock.patch(
                    "main._food_log_paths",
                    return_value=(str(log_file), str(submitted_file)),
                ):
                    with mock.patch("main.mail") as mail:
                        email = append_food_log("base", dry_run=False)

            mail.send.assert_called_once()
            self.assertEqual(email, "base")


if __name__ == "__main__":
    unittest.main()
