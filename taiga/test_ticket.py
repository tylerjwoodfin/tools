"""Unit tests for taiga ls sorting and formatting (no API)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ticket import (  # noqa: E402
    StorySummary,
    format_story_list,
    sort_story_rows,
    status_order_map,
    summarize_story,
)


def _row(
    ref: int,
    subject: str,
    status_name: str,
    status_order: int,
    kanban_order: int = 0,
) -> StorySummary:
    return StorySummary(
        ref=ref,
        subject=subject,
        status_name=status_name,
        status_order=status_order,
        kanban_order=kanban_order,
        is_closed=False,
    )


class StatusHelpersTests(unittest.TestCase):
    def test_status_order_map(self) -> None:
        statuses = [
            {"name": "New", "order": 1},
            {"name": "In progress", "order": 2},
        ]
        self.assertEqual(status_order_map(statuses), {"New": 1, "In progress": 2})

    def test_summarize_story(self) -> None:
        raw = {
            "ref": 314,
            "subject": "taiga ls function",
            "kanban_order": 5,
            "is_closed": False,
            "status_extra_info": {"name": "In progress"},
        }
        row = summarize_story(raw, {"In progress": 2, "New": 1})
        self.assertEqual(row.ref, 314)
        self.assertEqual(row.subject, "taiga ls function")
        self.assertEqual(row.status_name, "In progress")
        self.assertEqual(row.status_order, 2)
        self.assertEqual(row.kanban_order, 5)


class SortStoryRowsTests(unittest.TestCase):
    def test_sort_by_status_then_kanban_order(self) -> None:
        rows = [
            _row(2, "later in new", "New", 1, kanban_order=20),
            _row(314, "ls", "In progress", 2, kanban_order=1),
            _row(1, "first in new", "New", 1, kanban_order=10),
        ]
        sorted_rows = sort_story_rows(rows, "status")
        self.assertEqual([r.ref for r in sorted_rows], [1, 2, 314])

    def test_sort_by_ref(self) -> None:
        rows = [
            _row(314, "c", "In progress", 2),
            _row(10, "a", "New", 1),
            _row(20, "b", "New", 1),
        ]
        sorted_rows = sort_story_rows(rows, "ref")
        self.assertEqual([r.ref for r in sorted_rows], [10, 20, 314])

    def test_sort_by_subject(self) -> None:
        rows = [
            _row(2, "Zebra", "New", 1),
            _row(1, "apple", "New", 1),
        ]
        sorted_rows = sort_story_rows(rows, "subject")
        self.assertEqual([r.subject for r in sorted_rows], ["apple", "Zebra"])


class FormatStoryListTests(unittest.TestCase):
    def test_format_grouped_by_status(self) -> None:
        rows = sort_story_rows(
            [
                _row(314, "taiga ls function", "In progress", 2),
                _row(10, "older ticket", "New", 1),
            ],
            "status",
        )
        text = format_story_list(rows, group_by_status=True, color=False)
        self.assertEqual(
            text,
            "New (1)\n"
            "  TJW-10   older ticket\n"
            "\n"
            "In progress (1)\n"
            "  TJW-314  taiga ls function\n",
        )

    def test_format_flat_table(self) -> None:
        rows = sort_story_rows(
            [
                _row(314, "taiga ls function", "In progress", 2),
                _row(10, "older ticket", "New", 1),
            ],
            "ref",
        )
        text = format_story_list(rows, group_by_status=False, color=False)
        self.assertEqual(
            text,
            "TJW-10   New          older ticket\n"
            "TJW-314  In progress  taiga ls function\n",
        )

    def test_format_empty(self) -> None:
        self.assertEqual(
            format_story_list([], group_by_status=True),
            "No tickets.\n",
        )


if __name__ == "__main__":
    unittest.main()
