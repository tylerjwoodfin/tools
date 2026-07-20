"""Tests for foodlog goal date normalization (TJW-279)."""

import datetime
import unittest

from main import (
    _next_week_date_context,
    _normalize_foodlog_goal_when,
    _parse_goal_calendar_date,
)


class FoodlogGoalWhenTests(unittest.TestCase):
    def setUp(self):
        self.today = datetime.date(2026, 7, 19)

    def test_april_example_rejected_as_next_year(self):
        """Prompt examples like 'april 1' must not become 2027 reminders."""
        self.assertIsNone(_normalize_foodlog_goal_when("april 1", today=self.today))
        self.assertIsNone(_normalize_foodlog_goal_when("April 3rd", today=self.today))

    def test_near_term_month_day_becomes_iso(self):
        self.assertEqual(
            _normalize_foodlog_goal_when("july 20", today=self.today),
            "2026-07-20",
        )
        self.assertEqual(
            _normalize_foodlog_goal_when("July 26th", today=self.today),
            "2026-07-26",
        )

    def test_explicit_iso_in_range(self):
        self.assertEqual(
            _normalize_foodlog_goal_when("2026-07-22", today=self.today),
            "2026-07-22",
        )

    def test_explicit_iso_too_far_rejected(self):
        self.assertIsNone(
            _normalize_foodlog_goal_when("2027-04-01", today=self.today)
        )

    def test_relative_phrases_pass_through(self):
        self.assertEqual(
            _normalize_foodlog_goal_when("tomorrow", today=self.today),
            "tomorrow",
        )
        self.assertEqual(
            _normalize_foodlog_goal_when("in 3 days", today=self.today),
            "in 3 days",
        )
        self.assertEqual(
            _normalize_foodlog_goal_when("monday", today=self.today),
            "monday",
        )

    def test_parse_rolls_past_month_day_forward(self):
        parsed = _parse_goal_calendar_date("april 1", self.today)
        self.assertEqual(parsed, datetime.date(2027, 4, 1))

    def test_date_context_includes_iso_bounds(self):
        ctx = _next_week_date_context(self.today)
        self.assertIn("2026-07-19", ctx)
        self.assertIn("2026-07-20", ctx)
        self.assertIn("2026-07-26", ctx)
        self.assertIn("YYYY-MM-DD", ctx)


if __name__ == "__main__":
    unittest.main()
