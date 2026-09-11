"""Core diary workflow behavior tests."""

from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path

from diary_llm.config import load_config
from diary_llm.llm import StubLLM
from diary_llm.models import DiaryEntry
from diary_llm.prompts import load_prompt_history, select_library_prompt
from diary_llm.storage import append_entry
from diary_llm.telegram import TelegramSender
from diary_llm.workflow import DiaryWorkflow


def test_manual_start_creates_session(workflow: DiaryWorkflow):
    result = workflow.start_manual()
    assert result.ok
    assert result.action == "started"
    assert result.message
    status = workflow.status()
    assert status["active"] is True
    assert status["origin"] == "manual"
    assert status["session_id"] == result.session_id


def test_continue_existing_session_instead_of_second(workflow: DiaryWorkflow):
    first = workflow.start_manual()
    second = workflow.start_manual()
    assert second.action == "continue"
    assert second.session_id == first.session_id
    assert workflow.status()["active"] is True


def test_normal_chat_not_diary_without_session(workflow: DiaryWorkflow):
    result = workflow.handle_user_message("What's the weather?")
    assert result.action == "not_diary"
    assert result.ok is False
    assert workflow.status()["active"] is False


def test_continue_diary_session_with_followups(workflow: DiaryWorkflow):
    workflow.start_manual(prompt_text="Random question: what's on your mind?")
    reply = workflow.handle_user_message("Work stuff with QA.")
    assert reply.action == "reply"
    assert reply.message
    assert "?" in reply.message
    status = workflow.status()
    assert status["active"] is True
    assert status["message_count"] >= 3


def test_soft_close_after_four_user_replies(workflow: DiaryWorkflow):
    workflow.start_manual(prompt_text="Random question: what's on your mind?")
    for i, text in enumerate(
        ["One", "Two", "Three", "Four"],
        start=1,
    ):
        result = workflow.handle_user_message(text)
        if i < 4:
            assert result.action == "reply"
            assert workflow.status()["active"] is True
        else:
            assert result.action == "finalized"
            assert result.message
            assert "?" not in result.message
            assert workflow.status()["active"] is False


def test_hard_close_even_if_model_keeps_asking(tmp_cfg, fixed_now):
    class ClingyLLM(StubLLM):
        def complete(self, *, system, messages, temperature=0.7):
            if "Return ONLY valid JSON" in system or "Convert a diary" in system:
                return super().complete(system=system, messages=messages, temperature=temperature)
            return "And what else is on your mind?"

    wf = DiaryWorkflow(
        tmp_cfg,
        llm=ClingyLLM(),
        sender=TelegramSender(tmp_cfg.telegram, dry_run=True),
        rng=__import__("random").Random(0),
        now_fn=fixed_now,
    )
    tmp_cfg.conversation.soft_user_replies = 99
    tmp_cfg.conversation.max_user_replies = 3
    wf.start_manual(prompt_text="Random question: what's up?")
    assert wf.handle_user_message("A").action == "reply"
    assert wf.handle_user_message("B").action == "reply"
    done = wf.handle_user_message("C")
    assert done.action == "finalized"
    assert "?" not in (done.message or "")


def test_explicit_finalization_writes_markdown_and_conversation(
    workflow: DiaryWorkflow, tmp_cfg
):
    workflow.start_manual(prompt_text="Random question: what's bothering you?")
    workflow.handle_user_message("I'm worried about QA with my manager.")
    done = workflow.finish(reason="explicit")
    assert done.action == "finalized"
    assert workflow.status()["active"] is False

    day_file = tmp_cfg.diary_dir / "2026" / "09" / "2026-09-10.md"
    assert day_file.is_file()
    content = day_file.read_text(encoding="utf-8")
    assert content.startswith("## 2026-09-10")
    assert "### " in content

    conv = tmp_cfg.conversations_dir / f"{done.session_id}.json"
    assert conv.is_file()
    raw = json.loads(conv.read_text(encoding="utf-8"))
    assert raw["status"] == "completed"
    assert any(m["role"] == "user" for m in raw["messages"])


def test_multiple_entries_same_date_append(tmp_cfg):
    path = append_entry(
        tmp_cfg.diary_dir,
        DiaryEntry(date="2026-09-10", title="First", body="One.", tags=["a"]),
    )
    append_entry(
        tmp_cfg.diary_dir,
        DiaryEntry(date="2026-09-10", title="Second", body="Two.", tags=["b"]),
    )
    text = path.read_text(encoding="utf-8")
    assert text.count("## 2026-09-10") == 2
    assert "### First" in text and "### Second" in text


def test_inactivity_finalization(workflow: DiaryWorkflow, fixed_now):
    workflow.start_manual(prompt_text="Random question: how are you?")
    workflow.handle_user_message("A bit tired.")
    fixed_now.set(fixed_now() + timedelta(hours=4))
    result = workflow.finalize_if_inactive(send=False)
    assert result is not None
    assert result.action == "finalized"
    assert result.details["reason"] == "inactivity"
    assert workflow.status()["active"] is False


def test_proactive_skipped_when_active(workflow: DiaryWorkflow):
    workflow.start_manual()
    result = workflow.start_proactive(force=True, send=True)
    assert result.action == "skip"
    assert result.details["reason"] == "active_session"
    assert len(workflow.sender.sent) == 0


def test_proactive_sends_when_due(workflow: DiaryWorkflow):
    result = workflow.start_proactive(force=True, send=True)
    assert result.action == "started"
    assert result.message
    assert workflow.sender.sent[-1] == result.message
    assert workflow.status()["active"] is True
    assert workflow.status()["origin"] == "proactive"


def test_avoid_recently_used_prompts(tmp_cfg):
    history_path = tmp_cfg.prompt_history_path
    history_path.parent.mkdir(parents=True, exist_ok=True)
    history_path.write_text(
        json.dumps(
            {
                "recent_ids": ["bothering-1", "emotions-1", "events-1"],
                "recent_categories": [
                    "things_bothering_me",
                    "emotions",
                    "recent_events",
                ],
            }
        ),
        encoding="utf-8",
    )
    history = load_prompt_history(history_path)
    chosen = select_library_prompt(history, rng=__import__("random").Random(1))
    assert chosen.id not in {"bothering-1", "emotions-1", "events-1"}
    assert chosen.category not in {
        "things_bothering_me",
        "emotions",
        "recent_events",
    }


def test_handle_slash_diary_and_done(workflow: DiaryWorkflow):
    start = workflow.handle_user_message("/diary")
    assert start.action in {"started", "continue"}
    workflow.handle_user_message("Thinking about travel plans.")
    done = workflow.handle_user_message("/diary done")
    assert done.action == "finalized"


def test_cli_tick_is_silent_when_nothing_to_announce(config_file: Path, capsys):
    from diary_llm.cli import main

    # Default stub tick: no active session to finalize; proactive may start or skip.
    # With send enabled (default), stdout must be NO_REPLY so cron --announce stays quiet.
    code = main(["--config", str(config_file), "--stub-llm", "--dry-run", "tick"])
    captured = capsys.readouterr()
    assert code == 0
    assert captured.out.strip() == "NO_REPLY"
    assert "Proactive prompt not due yet" not in captured.out
    assert "not due" not in captured.out.lower()


def test_cli_start_reply_done(config_file: Path, tmp_path: Path):
    from diary_llm.cli import main

    assert main(["--config", str(config_file), "--stub-llm", "--json", "start"]) == 0
    assert (
        main(
            [
                "--config",
                str(config_file),
                "--stub-llm",
                "--json",
                "reply",
                "Something about work.",
            ]
        )
        == 0
    )
    assert main(["--config", str(config_file), "--stub-llm", "--json", "done"]) == 0

    cfg = load_config(config_file)
    files = list(cfg.diary_dir.rglob("*.md"))
    assert files
    convs = list(cfg.conversations_dir.glob("*.json"))
    assert convs


def test_tick_finalizes_then_can_prompt(workflow: DiaryWorkflow, fixed_now):
    workflow.start_manual(prompt_text="Random question: what changed?")
    workflow.handle_user_message("A few things at work.")
    fixed_now.set(fixed_now() + timedelta(hours=5))
    results = workflow.tick(send=True)
    actions = [r.action for r in results]
    assert "finalized" in actions
    # After finalize, proactive may start a new session
    assert any(a in {"started", "skip"} for a in actions)
