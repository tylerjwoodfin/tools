"""Domain models for diary sessions."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4


SessionStatus = Literal["active", "finalizing", "completed", "abandoned"]
SessionOrigin = Literal["manual", "proactive"]
Role = Literal["assistant", "user", "system"]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_now_iso() -> str:
    return utc_now().isoformat()


@dataclass
class Message:
    role: Role
    content: str
    timestamp: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Message:
        return cls(
            role=data["role"],
            content=data["content"],
            timestamp=data.get("timestamp") or utc_now_iso(),
        )


@dataclass
class DiarySession:
    session_id: str
    started_at: str
    last_interaction_at: str
    initial_prompt: str
    messages: list[Message]
    origin: SessionOrigin
    status: SessionStatus
    prompt_category: str | None = None
    prompt_id: str | None = None
    entry_path: str | None = None

    @classmethod
    def create(
        cls,
        *,
        initial_prompt: str,
        origin: SessionOrigin,
        prompt_category: str | None = None,
        prompt_id: str | None = None,
        session_id: str | None = None,
    ) -> DiarySession:
        now = utc_now_iso()
        return cls(
            session_id=session_id or str(uuid4()),
            started_at=now,
            last_interaction_at=now,
            initial_prompt=initial_prompt,
            messages=[Message(role="assistant", content=initial_prompt, timestamp=now)],
            origin=origin,
            status="active",
            prompt_category=prompt_category,
            prompt_id=prompt_id,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "started_at": self.started_at,
            "last_interaction_at": self.last_interaction_at,
            "initial_prompt": self.initial_prompt,
            "messages": [m.to_dict() for m in self.messages],
            "origin": self.origin,
            "status": self.status,
            "prompt_category": self.prompt_category,
            "prompt_id": self.prompt_id,
            "entry_path": self.entry_path,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DiarySession:
        return cls(
            session_id=data["session_id"],
            started_at=data["started_at"],
            last_interaction_at=data["last_interaction_at"],
            initial_prompt=data["initial_prompt"],
            messages=[Message.from_dict(m) for m in data.get("messages", [])],
            origin=data.get("origin", "manual"),
            status=data.get("status", "active"),
            prompt_category=data.get("prompt_category"),
            prompt_id=data.get("prompt_id"),
            entry_path=data.get("entry_path"),
        )

    def append(self, role: Role, content: str, *, timestamp: str | None = None) -> Message:
        msg = Message(role=role, content=content, timestamp=timestamp or utc_now_iso())
        self.messages.append(msg)
        self.last_interaction_at = msg.timestamp
        return msg

    def user_message_count(self) -> int:
        return sum(1 for m in self.messages if m.role == "user")


@dataclass
class DiaryEntry:
    date: str
    title: str
    body: str
    tags: list[str] = field(default_factory=list)
    session_id: str | None = None

    def to_markdown(self) -> str:
        tags_line = ""
        if self.tags:
            normalized = []
            for tag in self.tags:
                tag = tag.strip()
                if not tag:
                    continue
                if not tag.startswith("#"):
                    tag = f"#{tag}"
                normalized.append(tag)
            if normalized:
                tags_line = f"\n\nTags: {' '.join(normalized)}"
        return f"## {self.date}\n\n### {self.title}\n\n{self.body.strip()}{tags_line}\n"
