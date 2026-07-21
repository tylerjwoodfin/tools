"""Tests for foodlog 2.0 helpers (TJW-245)."""

import datetime
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import main as foodlog


class FoodlogHelpersTests(unittest.TestCase):
    def test_day_total_calories_normalizes_nested(self):
        entries = [
            {"food": "apple", "calories": 50},
            {"food": "weird", "calories": {"calories": 100}},
        ]
        self.assertEqual(foodlog.day_total_calories(entries), 150)

    def test_is_day_submitted_bool_and_dict(self):
        self.assertFalse(foodlog.is_day_submitted("2026-07-20", {}))
        self.assertTrue(foodlog.is_day_submitted("2026-07-20", {"2026-07-20": True}))
        self.assertTrue(
            foodlog.is_day_submitted(
                "2026-07-20", {"2026-07-20": {"submitted": True}}
            )
        )
        self.assertFalse(
            foodlog.is_day_submitted(
                "2026-07-20", {"2026-07-20": {"submitted": False}}
            )
        )

    def test_build_daily_grafana_event(self):
        event = foodlog.build_daily_grafana_event(
            "2026-07-20",
            [{"food": "huel", "calories": 400}],
            submitted=True,
            hostname="test-host",
        )
        self.assertEqual(event["type"], "daily")
        self.assertEqual(event["date"], "2026-07-20")
        self.assertEqual(event["total_calories"], 400)
        self.assertEqual(event["entry_count"], 1)
        self.assertTrue(event["submitted"])
        self.assertEqual(event["hostname"], "test-host")

    def test_build_loki_push_body_anchors_daily_at_noon_utc(self):
        event = {
            "type": "daily",
            "date": "2026-07-20",
            "total_calories": 100,
            "hostname": "h",
        }
        body = foodlog.build_loki_push_body(event)
        stream = body["streams"][0]
        self.assertEqual(stream["stream"]["job"], "foodlog")
        self.assertEqual(stream["stream"]["type"], "daily")
        ns = int(stream["values"][0][0])
        ts = datetime.datetime.fromtimestamp(ns / 1_000_000_000, tz=datetime.timezone.utc)
        self.assertEqual(ts, datetime.datetime(2026, 7, 20, 12, 0, tzinfo=datetime.timezone.utc))
        payload = json.loads(stream["values"][0][1])
        self.assertEqual(payload["total_calories"], 100)

    def test_mark_day_submitted_writes_flat_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            submitted_path = Path(tmp) / "food_submitted.json"
            with mock.patch.object(foodlog, "FOOD_SUBMITTED_FILE", str(submitted_path)):
                with mock.patch.object(foodlog, "LOG_DIR", tmp):
                    day = foodlog.mark_day_submitted("2026-07-20")
            self.assertEqual(day, "2026-07-20")
            data = json.loads(submitted_path.read_text(encoding="utf-8"))
            self.assertTrue(data["2026-07-20"]["submitted"])
            self.assertIn("submitted_at", data["2026-07-20"])

    def test_push_event_to_loki_noop_without_url(self):
        with mock.patch.object(foodlog, "_loki_base_url", return_value=None):
            self.assertFalse(foodlog.push_event_to_loki({"type": "daily", "date": "2026-07-20"}))

    def test_push_event_to_loki_posts(self):
        class FakeResp:
            status = 204

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        with mock.patch("urllib.request.urlopen", return_value=FakeResp()) as urlopen:
            ok = foodlog.push_event_to_loki(
                {
                    "type": "daily",
                    "date": "2026-07-20",
                    "total_calories": 10,
                    "hostname": "h",
                },
                loki_url="http://loki.example:3100",
            )
        self.assertTrue(ok)
        req = urlopen.call_args[0][0]
        self.assertEqual(req.full_url, "http://loki.example:3100/loki/api/v1/push")
        self.assertEqual(req.get_method(), "POST")


if __name__ == "__main__":
    unittest.main()
