"""Unit tests for amazon order helpers (no browser required)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from main import parse_pick_response  # noqa: E402


def test_parse_pick_json_object() -> None:
    assert parse_pick_response('{"index": 2}', 5) == 2


def test_parse_pick_no_match() -> None:
    assert parse_pick_response('{"index": -1}', 5) is None


def test_parse_pick_bare_int() -> None:
    assert parse_pick_response("1", 3) == 1


def test_parse_pick_out_of_range() -> None:
    assert parse_pick_response('{"index": 9}', 3) is None


def test_parse_pick_markdown_noise() -> None:
    assert parse_pick_response('Sure\n```json\n{"index": 0}\n```', 2) == 0
