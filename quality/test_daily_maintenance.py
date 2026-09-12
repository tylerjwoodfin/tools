#!/usr/bin/env python3
"""Tests for daily_maintenance Git backup helpers."""

import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from daily_maintenance import (
    _ensure_clean_tree_for_pull,
    _move_uncommitted_changes_to_backup_branch,
    _working_tree_is_dirty,
)


def _git(args, cwd):
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=True,
    )


def _init_repo(path):
    _git(["init", "-b", "main"], path)
    _git(["config", "user.email", "test@example.com"], path)
    _git(["config", "user.name", "Test"], path)
    (Path(path) / "file.txt").write_text("hello\n", encoding="utf-8")
    _git(["add", "file.txt"], path)
    _git(["commit", "-m", "init"], path)


class TestBackupBranchLeavesTreeClean(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()  # pylint: disable=consider-using-with
        self.repo = self._tmpdir.name
        _init_repo(self.repo)
        self._orig_cwd = os.getcwd()
        os.chdir(self.repo)

    def tearDown(self):
        os.chdir(self._orig_cwd)
        self._tmpdir.cleanup()

    def test_uncommitted_changes_are_committed_on_backup_not_carried_to_main(self):
        Path("file.txt").write_text("local edit\n", encoding="utf-8")
        Path("untracked.txt").write_text("new\n", encoding="utf-8")
        self.assertTrue(_working_tree_is_dirty())

        cab = MagicMock()
        ok, backup_branch = _move_uncommitted_changes_to_backup_branch(cab)

        self.assertTrue(ok)
        self.assertIsNotNone(backup_branch)
        self.assertTrue(backup_branch.startswith("backup_"))
        self.assertFalse(_working_tree_is_dirty())
        self.assertEqual(
            _git(["branch", "--show-current"], self.repo).stdout.strip(), "main"
        )
        self.assertEqual(Path("file.txt").read_text(encoding="utf-8"), "hello\n")
        self.assertFalse(Path("untracked.txt").exists())

        diff = _git(["diff", f"main..{backup_branch}"], self.repo).stdout
        self.assertIn("local edit", diff)
        self.assertIn("untracked.txt", diff)

    def test_clean_tree_is_noop(self):
        cab = MagicMock()
        ok, backup_branch = _move_uncommitted_changes_to_backup_branch(cab)
        self.assertTrue(ok)
        self.assertIsNone(backup_branch)
        cab.log.assert_not_called()

    def test_safety_stash_clears_remaining_dirt(self):
        Path("file.txt").write_text("still dirty\n", encoding="utf-8")
        cab = MagicMock()
        self.assertTrue(_ensure_clean_tree_for_pull(cab))
        self.assertFalse(_working_tree_is_dirty())
        stash = _git(["stash", "list"], self.repo).stdout
        self.assertIn("Safety stash before pulling main", stash)


if __name__ == "__main__":
    unittest.main()
