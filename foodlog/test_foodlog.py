"""Tests for foodlog 2.0 helpers and Mongo store (TJW-245)."""

import datetime
import json
import unittest
from unittest import mock

import main as foodlog
from store import FoodlogStore, day_total_calories, is_submitted_value
from pymongo import MongoClient


class FoodlogHelpersTests(unittest.TestCase):
    def test_day_total_calories_normalizes_nested(self):
        entries = [
            {"food": "apple", "calories": 50},
            {"food": "weird", "calories": {"calories": 100}},
        ]
        self.assertEqual(day_total_calories(entries), 150)

    def test_is_day_submitted_bool_and_dict(self):
        self.assertFalse(is_submitted_value(None))
        self.assertTrue(is_submitted_value(True))
        self.assertTrue(is_submitted_value({"submitted": True}))
        self.assertFalse(is_submitted_value({"submitted": False}))

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

    def test_push_event_to_loki_noop_without_url(self):
        with mock.patch.object(foodlog, "_loki_base_url", return_value=None):
            self.assertFalse(
                foodlog.push_event_to_loki({"type": "daily", "date": "2026-07-20"})
            )

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


class FoodlogStoreMongoTests(unittest.TestCase):
    """Integration tests against local Mongo (skips if unavailable)."""

    @classmethod
    def setUpClass(cls):
        try:
            client = MongoClient("mongodb://localhost:27017/", serverSelectionTimeoutMS=2000)
            client.admin.command("ping")
        except Exception as exc:  # pylint: disable=broad-exception-caught
            raise unittest.SkipTest(f"MongoDB not available: {exc}") from exc
        cls.client = client
        cls.db_name = "foodlog_test_tjw245"

    def setUp(self):
        self.client.drop_database(self.db_name)
        self.store = FoodlogStore(client=self.client, db_name=self.db_name)

    def tearDown(self):
        self.client.drop_database(self.db_name)

    def test_append_submit_and_totals(self):
        self.store.append_entry("2026-07-20", "Huel", 400)
        self.store.append_entry("2026-07-20", "apple", 50)
        doc = self.store.get_day("2026-07-20")
        self.assertEqual(doc["total_calories"], 450)
        self.assertEqual(doc["entry_count"], 2)
        self.assertFalse(doc["submitted"])
        self.store.mark_submitted("2026-07-20")
        self.assertTrue(self.store.is_day_submitted("2026-07-20"))

    def test_import_from_maps(self):
        n = self.store.replace_all_from_maps(
            {"2026-07-19": [{"food": "tea", "calories": 5}]},
            {"tea": {"calories": 5, "type": "healthy"}},
            {"2026-07-19": {"submitted": True, "submitted_at": "x"}},
        )
        self.assertEqual(n, 1)
        self.assertTrue(self.store.is_day_submitted("2026-07-19"))
        self.assertEqual(self.store.get_lookup()["tea"]["type"], "healthy")


if __name__ == "__main__":
    unittest.main()
