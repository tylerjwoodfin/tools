"""Persistent diary-session state."""

from __future__ import annotations

import json
from pathlib import Path

from .atomic import atomic_write_json
from .models import DiarySession


class SessionStore:
    """Tracks at most one active diary session."""

    def __init__(self, active_path: Path, conversations_dir: Path) -> None:
        self.active_path = active_path
        self.conversations_dir = conversations_dir
        self.conversations_dir.mkdir(parents=True, exist_ok=True)
        self.active_path.parent.mkdir(parents=True, exist_ok=True)

    def get_active(self) -> DiarySession | None:
        if not self.active_path.is_file():
            return None
        try:
            data = json.loads(self.active_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
        session = DiarySession.from_dict(data)
        if session.status != "active":
            return None
        return session

    def save_active(self, session: DiarySession) -> None:
        atomic_write_json(self.active_path, session.to_dict())
        self.save_conversation(session)

    def clear_active(self) -> None:
        if self.active_path.exists():
            self.active_path.unlink()

    def conversation_path(self, session_id: str) -> Path:
        return self.conversations_dir / f"{session_id}.json"

    def save_conversation(self, session: DiarySession) -> Path:
        path = self.conversation_path(session.session_id)
        atomic_write_json(path, session.to_dict())
        return path

    def load_conversation(self, session_id: str) -> DiarySession | None:
        path = self.conversation_path(session_id)
        if not path.is_file():
            return None
        try:
            return DiarySession.from_dict(json.loads(path.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError, KeyError):
            return None
