"""Tests for the SFPL DIY Digi Lab appointment check."""

from __future__ import annotations

import sys
import types
import unittest
from datetime import datetime
from unittest import mock

import main

NOW = datetime(2026, 11, 27, 12, 0, tzinfo=main.TZ)
ROW = {"start": "2026-12-02T10:00:00-08:00", "startDisplay": "2026-12-02T10:00:00-08:00",
       "endDisplay": "2026-12-02T13:00:00-08:00", "userId": 114640, "crc": "x"}


class FakeCabinet:
    """In-memory stand-in for Cabinet get/put."""

    def __init__(self, sent):
        self.sent = sent
        self.puts = []

    def get(self, *_keys):
        return self.sent

    def put(self, *_keys, value=None):
        self.sent = value
        self.puts.append(value)


class ParseTests(unittest.TestCase):
    def test_parse_time_naive_is_pacific(self):
        self.assertEqual(main.parse_time("2026-12-02 10:00:00").tzinfo, main.TZ)

    def test_parse_slots(self):
        [slot] = main.parse_slots([ROW, {"start": ""}])
        self.assertEqual(slot.key, "2026-12-02T10:00:00-08:00")
        self.assertEqual(main.describe(slot), "Wed, Dec 2 · 10:00 AM – 1:00 PM")

    def test_parse_slots_none(self):
        self.assertEqual(main.parse_slots(None), [])

    def test_prune_drops_older_than_48_hours(self):
        sent = ["2026-11-25T11:00:00-08:00", "2026-11-25T13:00:00-08:00", "garbage"]
        self.assertEqual(main.prune(sent, NOW), ["2026-11-25T13:00:00-08:00"])

    def test_find_service(self):
        page = ('<p class="form-control-static groupcat_filtering" id="cat_19254" '
                'data-value="7355">x</p><input data-uid="0" data-gid="19254">')
        with mock.patch.object(main, "get_json", return_value={"html": page}):
            self.assertEqual(main.find_service(), (19254, 7355))


class MainTests(unittest.TestCase):
    def run_main(self, sent, slots, send_ok=True):
        cab = FakeCabinet(sent)
        mail = mock.Mock()
        mail.send.return_value = send_ok
        fake = types.SimpleNamespace(Cabinet=lambda: cab, Mail=lambda: mail)
        with mock.patch.dict(sys.modules, {"cabinet": fake}), \
                mock.patch.object(main, "fetch_slots", return_value=slots), \
                mock.patch.object(main, "datetime") as fake_dt:
            fake_dt.now.return_value = NOW
            fake_dt.fromisoformat = datetime.fromisoformat
            code = main.main()
        return code, cab, mail

    def test_emails_new_slots_once(self):
        slots = main.parse_slots([ROW])
        code, cab, mail = self.run_main([], slots)
        self.assertEqual(code, 0)
        mail.send.assert_called_once()
        self.assertIn("1 new appointment", mail.send.call_args.args[0])
        self.assertEqual(cab.sent, [slots[0].key])

        _, _, mail = self.run_main(cab.sent, slots)
        mail.send.assert_not_called()

    def test_failed_email_does_not_record(self):
        code, cab, _ = self.run_main([], main.parse_slots([ROW]), send_ok=False)
        self.assertEqual(code, 1)
        self.assertEqual(cab.puts, [])

    def test_prunes_before_checking(self):
        _, cab, mail = self.run_main(["2026-11-01T10:00:00-07:00"], [])
        mail.send.assert_not_called()
        self.assertEqual(cab.sent, [])


if __name__ == "__main__":
    unittest.main()
