"""Tests for Cabinet-backed TelegramSender."""

from __future__ import annotations

import sys
import types

from diary_llm.telegram import TelegramSender, _cabinet_send


def test_dry_run_records_without_calling_send_fn():
    calls: list[str] = []
    sender = TelegramSender(dry_run=True, send_fn=lambda m: calls.append(m) or True)
    result = sender.send("hello")
    assert result.ok
    assert result.output == "dry-run"
    assert sender.sent == ["hello"]
    assert calls == []


def test_empty_message_is_noop():
    sender = TelegramSender(send_fn=lambda _m: False)
    result = sender.send("  ")
    assert result.ok
    assert sender.sent == []


def test_send_fn_success():
    sender = TelegramSender(send_fn=lambda _m: True)
    result = sender.send("hi")
    assert result.ok
    assert sender.sent == ["hi"]


def test_send_fn_failure():
    sender = TelegramSender(send_fn=lambda _m: False)
    result = sender.send("hi")
    assert result.ok is False
    assert "cabinet.telegram" in result.output


def test_send_fn_exception():
    def boom(_message: str) -> bool:
        raise RuntimeError("nope")

    sender = TelegramSender(send_fn=boom)
    result = sender.send("hi")
    assert result.ok is False
    assert "nope" in result.output


def test_cabinet_send_delegates(monkeypatch):
    seen: list[tuple[str, bool]] = []

    def fake_telegram(message: str, is_quiet: bool = False) -> bool:
        seen.append((message, is_quiet))
        return True

    fake_mod = types.ModuleType("cabinet")
    fake_mod.telegram = fake_telegram  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "cabinet", fake_mod)
    assert _cabinet_send("ping") is True
    assert seen == [("ping", True)]
