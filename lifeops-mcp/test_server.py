"""Unit tests for lifeops-mcp helpers (no live Cabinet/Immich)."""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

SERVER_PATH = Path(__file__).resolve().parent / "server.py"
SPEC = importlib.util.spec_from_file_location("lifeops_server", SERVER_PATH)
assert SPEC and SPEC.loader
server = importlib.util.module_from_spec(SPEC)
sys.modules["lifeops_server"] = server
SPEC.loader.exec_module(server)


class RedactTests(unittest.TestCase):
    def test_redact_nested_secrets(self):
        data = {"api_root": "http://x", "auth_token": "secret", "nested": {"password": "p"}}
        out = server._redact(data)
        self.assertEqual(out["api_root"], "http://x")
        self.assertEqual(out["auth_token"], "***REDACTED***")
        self.assertEqual(out["nested"]["password"], "***REDACTED***")

    def test_looks_sensitive(self):
        self.assertTrue(server._looks_sensitive(["taiga", "auth_token"]))
        self.assertFalse(server._looks_sensitive(["quality", "cloud"]))


class ToolTests(unittest.TestCase):
    @patch.object(server, "_run", return_value='{"free_gb": 10}')
    def test_cabinet_get_json(self, _mock):
        out = server.cabinet_get("quality.cloud")
        self.assertIn("free_gb", out)

    @patch.object(server, "_run", return_value="sekrit")
    def test_cabinet_get_redacts_sensitive_path(self, _mock):
        out = server.cabinet_get("taiga auth_token")
        self.assertEqual(out, "***REDACTED***")

    @patch.object(server, "_run", return_value="saved")
    @patch.object(server.shutil, "which", return_value="/usr/bin/remind")
    def test_remind_save(self, _which, mock_run):
        out = server.remind_save("Buy milk", "tomorrow")
        self.assertEqual(out, "saved")
        args = mock_run.call_args[0][0]
        self.assertIn("--save", args)
        self.assertIn("Buy milk", args)


if __name__ == "__main__":
    unittest.main()
