"""Configuration loading for diary-llm."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


DEFAULT_CONFIG_PATHS = (
    Path(os.path.expanduser("~/.config/diary-llm/config.yaml")),
    Path(os.path.expanduser("~/.config/diary-llm/config.yml")),
)


@dataclass
class ProactiveConfig:
    enabled: bool = True
    min_days: float = 2.0
    max_days: float = 4.0
    allowed_hours: list[int] = field(default_factory=lambda: [17, 18, 19, 20, 21])


@dataclass
class HistoryConfig:
    recent_entries: int = 5
    topic_entries: int = 3
    recent_prompt_limit: int = 20


@dataclass
class LLMConfig:
    backend: str = "openai"
    base_url: str = "http://127.0.0.1:1234/v1"
    api_key: str = "lmstudio-local"
    model: str = "supergemma4-26b-uncensored-mlx-v2"
    timeout_seconds: int = 120
    openclaw_bin: str = "openclaw"


@dataclass
class ConversationConfig:
    # Prefer winding down after this many user replies (opening question not counted).
    soft_user_replies: int = 4
    # Always close after this many user replies.
    max_user_replies: int = 6


@dataclass
class DiaryConfig:
    diary_dir: Path
    conversations_dir: Path
    state_dir: Path
    proactive: ProactiveConfig = field(default_factory=ProactiveConfig)
    conversation: ConversationConfig = field(default_factory=ConversationConfig)
    inactivity_timeout_hours: float = 3.0
    history: HistoryConfig = field(default_factory=HistoryConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    timezone: str = "America/Los_Angeles"
    tick_cron: str = "0 */2 * * *"
    config_path: Path | None = None

    @property
    def active_session_path(self) -> Path:
        return self.state_dir / "active_session.json"

    @property
    def scheduler_state_path(self) -> Path:
        return self.state_dir / "scheduler.json"

    @property
    def prompt_history_path(self) -> Path:
        return self.state_dir / "prompt_history.json"


def _expand(path: str | Path) -> Path:
    return Path(os.path.expanduser(str(path))).resolve()


def default_diary_dir() -> Path:
    return _expand("~/syncthing/notes/diary")


def default_state_dir() -> Path:
    return _expand("~/.local/share/diary-llm")


def load_raw_config(path: Path | None = None) -> tuple[dict[str, Any], Path | None]:
    if path is not None:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return data, path
    for candidate in DEFAULT_CONFIG_PATHS:
        if candidate.is_file():
            data = yaml.safe_load(candidate.read_text(encoding="utf-8")) or {}
            return data, candidate
    return {}, None


def load_config(
    path: Path | None = None,
    *,
    overrides: dict[str, Any] | None = None,
) -> DiaryConfig:
    raw, used = load_raw_config(path)
    if overrides:
        raw = {**raw, **overrides}

    diary_dir = _expand(raw.get("diary_dir") or default_diary_dir())
    conversations_dir = _expand(
        raw.get("conversations_dir") or (diary_dir / "conversations")
    )
    state_dir = _expand(raw.get("state_dir") or default_state_dir())

    proactive_raw = raw.get("proactive") or {}
    conversation_raw = raw.get("conversation") or {}
    history_raw = raw.get("history") or {}
    llm_raw = raw.get("llm") or {}

    return DiaryConfig(
        diary_dir=diary_dir,
        conversations_dir=conversations_dir,
        state_dir=state_dir,
        proactive=ProactiveConfig(
            enabled=bool(proactive_raw.get("enabled", True)),
            min_days=float(proactive_raw.get("min_days", 2)),
            max_days=float(proactive_raw.get("max_days", 4)),
            allowed_hours=[
                int(h) for h in (proactive_raw.get("allowed_hours") or [17, 18, 19, 20, 21])
            ],
        ),
        conversation=ConversationConfig(
            soft_user_replies=int(conversation_raw.get("soft_user_replies", 4)),
            max_user_replies=int(conversation_raw.get("max_user_replies", 6)),
        ),
        inactivity_timeout_hours=float(raw.get("inactivity_timeout_hours", 3)),
        history=HistoryConfig(
            recent_entries=int(history_raw.get("recent_entries", 5)),
            topic_entries=int(history_raw.get("topic_entries", 3)),
            recent_prompt_limit=int(history_raw.get("recent_prompt_limit", 20)),
        ),
        llm=LLMConfig(
            backend=str(llm_raw.get("backend") or "openai"),
            base_url=str(llm_raw.get("base_url") or "http://127.0.0.1:1234/v1"),
            api_key=str(llm_raw.get("api_key") or "lmstudio-local"),
            model=str(llm_raw.get("model") or "supergemma4-26b-uncensored-mlx-v2"),
            timeout_seconds=int(llm_raw.get("timeout_seconds") or 120),
            openclaw_bin=str(llm_raw.get("openclaw_bin") or "openclaw"),
        ),
        timezone=str(raw.get("timezone") or "America/Los_Angeles"),
        tick_cron=str(raw.get("tick_cron") or "0 */2 * * *"),
        config_path=used,
    )
