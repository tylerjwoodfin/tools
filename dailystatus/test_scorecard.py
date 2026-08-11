"""Tests for dailystatus Personal SRE scorecard (TJW-316)."""

import datetime
import unittest
from unittest import mock

from scorecard import (
    ScorecardRow,
    build_scorecard_rows,
    check_pihole,
    check_spotify,
    check_ssl_expiry,
    check_warnings_summary,
    collect_log_issues,
    parse_borg_archive_name,
    parse_quality_updated_at,
    parse_spotify_last_success,
    rainbow_host_from_borg_path,
    render_issues_html,
    render_scorecard_html,
)


class ParseHelpersTests(unittest.TestCase):
    def test_parse_borg_archive_name(self):
        dt = parse_borg_archive_name("cloud-2026-08-10T03:05:37")
        self.assertEqual(dt, datetime.datetime(2026, 8, 10, 3, 5, 37))
        self.assertIsNone(parse_borg_archive_name("not-an-archive"))

    def test_parse_quality_updated_at(self):
        dt = parse_quality_updated_at("2026-08-10 19:00:02 PDT")
        self.assertEqual(dt, datetime.datetime(2026, 8, 10, 19, 0, 2))
        self.assertIsNone(parse_quality_updated_at(None))
        self.assertIsNone(parse_quality_updated_at("bogus"))

    def test_parse_spotify_last_success(self):
        dt = parse_spotify_last_success("2026-08-10 19:20")
        self.assertEqual(dt, datetime.datetime(2026, 8, 10, 19, 20))
        self.assertIsNone(parse_spotify_last_success("nope"))

    def test_rainbow_host_from_borg_path(self):
        self.assertEqual(
            rainbow_host_from_borg_path(
                "ssh://tyler@38.102.87.250:22/~/syncthing-backups-borg-repo"
            ),
            "38.102.87.250",
        )
        self.assertIsNone(rainbow_host_from_borg_path("/local/path"))


class CollectLogIssuesTests(unittest.TestCase):
    def test_prefers_loki_when_configured(self):
        cab = mock.Mock()
        cab.logging_loki_url = "http://loki.example:3100"
        cab.log_query_issues_loki.return_value = ["ERROR line"]
        lines, source = collect_log_issues(cab)
        self.assertEqual(source, "loki")
        self.assertEqual(lines, ["ERROR line"])
        cab.log_query_issues.assert_not_called()

    def test_falls_back_to_local_when_loki_fails(self):
        cab = mock.Mock()
        cab.logging_loki_url = "http://loki.example:3100"
        cab.log_query_issues_loki.side_effect = OSError("down")
        cab.log_query_issues.return_value = ["WARN local"]
        lines, source = collect_log_issues(cab)
        self.assertEqual(source, "local")
        self.assertEqual(lines, ["WARN local"])
        # configured URL + localhost retry
        self.assertGreaterEqual(cab.log_query_issues_loki.call_count, 2)

    def test_unavailable_when_both_fail(self):
        cab = mock.Mock()
        cab.logging_loki_url = ""
        cab.log_query_issues.side_effect = RuntimeError("boom")
        lines, source = collect_log_issues(cab)
        self.assertEqual(source, "unavailable")
        self.assertEqual(lines, [])


class CheckHelpersTests(unittest.TestCase):
    def test_check_spotify_fresh(self):
        now = datetime.datetime(2026, 8, 10, 20, 0)
        cab = mock.Mock()
        cab.get.return_value = {"last_success": "2026-08-10 19:20"}
        row = check_spotify(cab, now)
        self.assertEqual(row.status, "ok")

    def test_check_spotify_stale(self):
        now = datetime.datetime(2026, 8, 12, 20, 0)
        cab = mock.Mock()
        cab.get.return_value = {"last_success": "2026-08-10 19:20"}
        row = check_spotify(cab, now)
        self.assertEqual(row.status, "error")

    def test_check_spotify_missing(self):
        cab = mock.Mock()
        cab.get.return_value = {}
        row = check_spotify(cab, datetime.datetime(2026, 8, 10, 20, 0))
        self.assertEqual(row.status, "unknown")
        self.assertIn("unknown / not configured", row.detail)

    def test_check_pihole_ok(self):
        def run(cmd):
            if cmd[:2] == ["docker", "ps"]:
                return 0, "pihole Up 2 weeks (healthy)", ""
            if "status" in cmd:
                return 0, "  [✓] Pi-hole blocking is enabled", ""
            return 1, "", "nope"

        row = check_pihole(run_command=run)
        self.assertEqual(row.status, "ok")
        self.assertIn("blocking enabled", row.detail)

    def test_check_pihole_docker_missing(self):
        row = check_pihole(run_command=lambda _cmd: (127, "", "missing"))
        self.assertEqual(row.status, "unknown")

    def test_check_ssl_expiry_with_mock(self):
        # Avoid real network: patch socket path by stubbing results via empty hosts
        row = check_ssl_expiry(hosts=())
        self.assertEqual(row.status, "unknown")

    def test_warnings_summary(self):
        row = check_warnings_summary(
            ["2026 WARNING foo", "2026 ERROR bar"], "loki"
        )
        self.assertEqual(row.status, "error")
        self.assertIn("1 error", row.detail)
        self.assertIn("loki", row.detail)


class RenderTests(unittest.TestCase):
    def test_render_scorecard_html(self):
        html = render_scorecard_html(
            [ScorecardRow("Borg backups", "ok", "last success today")]
        )
        self.assertIn("Personal SRE Scorecard", html)
        self.assertIn("Borg backups", html)
        self.assertIn("OK", html.upper())

    def test_render_issues_html_empty(self):
        html = render_issues_html([], "loki")
        self.assertIn("None detected", html)

    def test_render_issues_html_escapes(self):
        html = render_issues_html(["ERROR <script>alert(1)</script>"], "local")
        self.assertIn("&lt;script&gt;", html)
        self.assertNotIn("<script>", html)


class BuildScorecardTests(unittest.TestCase):
    def test_build_does_not_crash_on_missing_data(self):
        cab = mock.Mock()
        cab.get.side_effect = lambda *args, **kwargs: None
        cab.logging_loki_url = ""
        cab.log_query_issues.return_value = []

        with mock.patch("scorecard._list_borg_archives", return_value=None):
            with mock.patch("scorecard.check_ssl_expiry") as ssl_check:
                ssl_check.return_value = ScorecardRow(
                    "SSL expiry", "unknown", "unknown / not configured"
                )
                with mock.patch(
                    "scorecard.check_pihole",
                    return_value=ScorecardRow(
                        "Pi-hole", "unknown", "unknown / not configured"
                    ),
                ):
                    with mock.patch("scorecard.ping_host", return_value=False):
                        rows, issues, source = build_scorecard_rows(
                            cab,
                            now=datetime.datetime(2026, 8, 10, 20, 0),
                            quality_data={},
                        )

        self.assertTrue(rows)
        self.assertEqual(source, "local")
        self.assertEqual(issues, [])
        # Every row should be a ScorecardRow with a known status token
        for row in rows:
            self.assertIn(row.status, {"ok", "warn", "error", "unknown"})
            self.assertIsInstance(row.detail, str)


if __name__ == "__main__":
    unittest.main()
