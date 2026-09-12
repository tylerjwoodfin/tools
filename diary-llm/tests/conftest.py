"""Shared fixtures for diary-llm tests."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
import yaml

from diary_llm.config import ConversationConfig, DiaryConfig, HistoryConfig, LLMConfig, ProactiveConfig
from diary_llm.llm import StubLLM
from diary_llm.telegram import TelegramSender
from diary_llm.workflow import DiaryWorkflow


@pytest.fixture
def tmp_cfg(tmp_path: Path) -> DiaryConfig:
    diary_dir = tmp_path / "diary"
    state_dir = tmp_path / "state"
    conversations = diary_dir / "conversations"
    diary_dir.mkdir()
    state_dir.mkdir()
    conversations.mkdir()
    return DiaryConfig(
        diary_dir=diary_dir,
        conversations_dir=conversations,
        state_dir=state_dir,
        proactive=ProactiveConfig(
            enabled=True,
            min_days=2,
            max_days=4,
            allowed_hours=list(range(24)),
        ),
        conversation=ConversationConfig(soft_user_replies=4, max_user_replies=6),
        inactivity_timeout_hours=3,
        history=HistoryConfig(recent_entries=5, topic_entries=3, recent_prompt_limit=20),
        llm=LLMConfig(backend="stub"),
        timezone="UTC",
    )


@pytest.fixture
def fixed_now():
    current = {"t": datetime(2026, 9, 10, 19, 0, tzinfo=timezone.utc)}

    def now():
        return current["t"]

    def set_now(value: datetime):
        current["t"] = value

    now.set = set_now  # type: ignore[attr-defined]
    return now


@pytest.fixture
def workflow(tmp_cfg: DiaryConfig, fixed_now) -> DiaryWorkflow:
    llm = StubLLM()
    sender = TelegramSender(dry_run=True)
    return DiaryWorkflow(
        tmp_cfg,
        llm=llm,
        sender=sender,
        rng=__import__("random").Random(0),
        now_fn=fixed_now,
    )


@pytest.fixture
def config_file(tmp_path: Path, tmp_cfg: DiaryConfig) -> Path:
    path = tmp_path / "config.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "diary_dir": str(tmp_cfg.diary_dir),
                "conversations_dir": str(tmp_cfg.conversations_dir),
                "state_dir": str(tmp_cfg.state_dir),
                "proactive": {
                    "enabled": True,
                    "min_days": 2,
                    "max_days": 4,
                    "allowed_hours": list(range(24)),
                },
                "inactivity_timeout_hours": 3,
                "llm": {"backend": "stub"},
                "timezone": "UTC",
            }
        ),
        encoding="utf-8",
    )
    return path
