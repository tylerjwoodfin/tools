from pathlib import Path
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import food_cli


def test_parse_simple_tacos():
    assert food_cli.parse_simple("tacos 100") == [{"food": "tacos", "calories": 100}]


def test_parse_simple_should_be():
    assert food_cli.parse_simple("matcha should be 200") == [
        {"food": "matcha", "calories": 200}
    ]


def test_parse_simple_slash_food():
    assert food_cli.parse_simple("/food chicken salad 540") == [
        {"food": "chicken salad", "calories": 540}
    ]


def test_not_food():
    assert food_cli.NOT_FOOD.match("later")
    assert not food_cli.looks_like_food("anyway about that PR")


def test_tick_still_nudges_when_the_model_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(food_cli, "PENDING_PATH", tmp_path / "pending")
    sent = {}

    def boom(_prompt):
        raise RuntimeError('Auth lookup failed for provider "openai"')

    result = food_cli.cmd_tick(
        send=True,
        infer_fn=boom,
        send_fn=lambda message: sent.setdefault("message", message) or True,
        status={"total_calories": 0, "entry_count": 0, "submitted": False},
    )
    assert result["ok"] is True
    assert result["action"] == "reminded"
    assert "eat" in sent["message"].lower()


def test_tick_stays_quiet_once_the_day_is_logged(tmp_path, monkeypatch):
    monkeypatch.setattr(food_cli, "PENDING_PATH", tmp_path / "pending")
    result = food_cli.cmd_tick(
        send=False,
        infer_fn=lambda _prompt: "should not be called",
        status={"total_calories": 1200, "entry_count": 2, "submitted": False},
    )
    assert result["action"] == "skip"


class _Proc:
    def __init__(self, code: int, stderr: str = "", stdout: str = ""):
        self.returncode = code
        self.stderr = stderr
        self.stdout = stdout


def test_infer_retries_when_state_lifecycle_is_busy():
    calls = {"n": 0}
    lock = "[openclaw] Reason: another OpenClaw process owns state-lifecycle"

    def fake_run(*_args, **_kwargs):
        calls["n"] += 1
        if calls["n"] < 3:
            return _Proc(1, lock)
        return _Proc(0, stdout='{"outputs":[{"text":"tacos 100"}]}')

    with patch.object(food_cli.subprocess, "run", fake_run), patch.object(
        food_cli.time, "sleep", lambda _seconds: None
    ):
        text = food_cli.infer_text("tacos")
    assert calls["n"] == 3
    assert "tacos" in text


def test_infer_does_not_retry_other_failures():
    calls = {"n": 0}

    def fake_run(*_args, **_kwargs):
        calls["n"] += 1
        return _Proc(1, "auth failed")

    with patch.object(food_cli.subprocess, "run", fake_run), patch.object(
        food_cli.time, "sleep", lambda _seconds: None
    ):
        try:
            food_cli.infer_text("tacos")
        except RuntimeError as exc:
            assert "auth failed" in str(exc)
        else:
            raise AssertionError("expected infer to fail")
    assert calls["n"] == 1
