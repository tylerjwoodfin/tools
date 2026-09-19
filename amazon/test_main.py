"""Unit tests for amazon cart helpers (no browser required)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from main import item_in_cart, parse_pick_response  # noqa: E402


class _FakePage:
    """Minimal Page stand-in for cart checks."""

    def __init__(self, *, selector: str | None = None, content: str = "") -> None:
        self._selector = selector
        self._content = content

    def query_selector(self, sel: str) -> object | None:
        return object() if sel == self._selector else None

    def content(self) -> str:
        return self._content


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


def test_item_in_cart_by_data_asin() -> None:
    page = _FakePage(selector='[data-asin="B00TESTASIN"]')
    assert item_in_cart(page, "B00TESTASIN") is True


def test_item_in_cart_by_html() -> None:
    page = _FakePage(content="cart html B00TESTASIN more")
    assert item_in_cart(page, "B00TESTASIN") is True


def test_item_in_cart_missing() -> None:
    page = _FakePage(content="empty cart")
    assert item_in_cart(page, "B00TESTASIN") is False


def test_item_in_cart_blank_asin() -> None:
    page = _FakePage(content="B00TESTASIN")
    assert item_in_cart(page, "") is False
