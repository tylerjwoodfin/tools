"""Unit tests for amazon cart helpers (no browser required)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from main import (  # noqa: E402
    is_sponsored_result,
    item_in_cart,
    parse_manual_pick,
    parse_pick_response,
    scrape_search_results,
    text_has_sponsored_badge,
    title_marked_sponsored,
)


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


def test_parse_manual_pick_number() -> None:
    assert parse_manual_pick("4", 8) == 4


def test_parse_manual_pick_quit() -> None:
    assert parse_manual_pick("q", 8) == "quit"
    assert parse_manual_pick(" quit ", 8) == "quit"


def test_parse_manual_pick_invalid() -> None:
    assert parse_manual_pick("", 8) == "invalid"
    assert parse_manual_pick("n", 8) == "invalid"
    assert parse_manual_pick("9", 8) == "invalid"
    assert parse_manual_pick("-1", 8) == "invalid"


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


class _FakeEl:
    """Minimal element stand-in for search-card checks."""

    def __init__(
        self,
        *,
        attrs: dict[str, str] | None = None,
        text: str = "",
        children: dict[str, object] | None = None,
    ) -> None:
        self._attrs = attrs or {}
        self._text = text
        self._children = children or {}

    def get_attribute(self, name: str) -> str | None:
        return self._attrs.get(name)

    def query_selector(self, sel: str) -> object | None:
        return self._children.get(sel)

    def inner_text(self) -> str:
        return self._text


class _FakeSearchPage:
    """Minimal Page stand-in for search-result scraping."""

    def __init__(self, cards: list[_FakeEl]) -> None:
        self._cards = cards

    def wait_for_selector(self, _sel: str, timeout: int = 0) -> None:
        return None

    def query_selector_all(self, sel: str) -> list[_FakeEl]:
        if sel == '[data-component-type="s-search-result"]':
            return self._cards
        return []


def _result_card(asin: str, title: str, *, text: str | None = None, **attrs: str) -> _FakeEl:
    img = _FakeEl(attrs={"alt": title})
    card_attrs = {"data-asin": asin, "data-component-type": "s-search-result"}
    card_attrs.update(attrs)
    return _FakeEl(
        attrs=card_attrs,
        text=title if text is None else text,
        children={"img.s-image": img},
    )


def test_sponsored_ad_label_is_detected() -> None:
    card = _result_card(
        "B00AD00001",
        "Loop Quiet 2 Earplugs",
        text="Sponsored ad Loop Quiet 2 Earplugs 4.6 out of 5 stars",
    )
    assert text_has_sponsored_badge(card.inner_text()) is True
    assert is_sponsored_result(card) is True


def test_sponsored_badge_after_merchandising_chip() -> None:
    text = "Overall Pick Sponsored ad Mack's Ultra Soft Foam Earplugs"
    assert text_has_sponsored_badge(text) is True


def test_organic_earplugs_are_not_sponsored() -> None:
    card = _result_card(
        "B00ORG0001",
        "Mack's Ultra Soft Foam Earplugs, 50 Pair",
        text="Mack's Ultra Soft Foam Earplugs 4.7 out of 5 stars 12,000",
    )
    assert is_sponsored_result(card) is False
    assert title_marked_sponsored("Mack's Ultra Soft Foam Earplugs, 50 Pair") is False


def test_title_suffix_sponsored_is_an_ad() -> None:
    assert title_marked_sponsored("Loop Quiet Earplugs Sponsored") is True
    assert title_marked_sponsored("Loop Quiet Earplugs Sponsored ad") is True
    assert title_marked_sponsored("Concert earplugs sponsored by musicians") is False


def test_adholder_class_is_sponsored() -> None:
    card = _result_card(
        "B00AD00002",
        "Foam earplugs",
        **{"class": "s-result-item s-asin AdHolder"},
    )
    assert is_sponsored_result(card) is True


def test_scrape_skips_sponsored_ads_and_keeps_organic() -> None:
    page = _FakeSearchPage(
        [
            _result_card(
                "B00AD00001",
                "Loop Quiet 2 Earplugs",
                text="Sponsored ad Loop Quiet 2 Earplugs",
            ),
            _result_card(
                "B00AD00002",
                "Mack's Earplugs Sponsored",
                text="Mack's Earplugs 4.5 out of 5 stars",
                **{"class": "s-result-item AdHolder"},
            ),
            _result_card(
                "B00ORG0001",
                "Mack's Ultra Soft Foam Earplugs, 50 Pair",
                text="Best Seller Mack's Ultra Soft Foam Earplugs 4.7 out of 5 stars",
            ),
        ]
    )
    results = scrape_search_results(page, limit=8)
    assert [item.asin for item in results] == ["B00ORG0001"]
    assert results[0].index == 0
