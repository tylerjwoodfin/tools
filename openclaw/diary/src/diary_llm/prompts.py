"""Prompt library and selection for diary conversations."""

from __future__ import annotations

import json
import random
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

from .atomic import atomic_write_json
from .config import DiaryConfig


@dataclass(frozen=True)
class PromptTemplate:
    id: str
    category: str
    text: str


PROMPT_LIBRARY: tuple[PromptTemplate, ...] = (
    PromptTemplate(
        "events-1",
        "recent_events",
        "What's something that happened recently that still feels unfinished in your head?",
    ),
    PromptTemplate(
        "events-2",
        "recent_events",
        "Was there a small moment this week that mattered more than it looked like at the time?",
    ),
    PromptTemplate(
        "emotions-1",
        "emotions",
        "What emotion have you been carrying around the most lately, even if you haven't named it out loud?",
    ),
    PromptTemplate(
        "emotions-2",
        "emotions",
        "When did you last feel unexpectedly calm or unexpectedly tense?",
    ),
    PromptTemplate(
        "bothering-1",
        "things_bothering_me",
        "What's something that's been taking up more mental space than it deserves lately?",
    ),
    PromptTemplate(
        "bothering-2",
        "things_bothering_me",
        "Is there a low-grade annoyance you've been ignoring that might be worth naming?",
    ),
    PromptTemplate(
        "positive-1",
        "positive_experiences",
        "What's one thing that went better than expected recently?",
    ),
    PromptTemplate(
        "positive-2",
        "positive_experiences",
        "What made you smile or feel a little lighter this week?",
    ),
    PromptTemplate(
        "people-1",
        "relationships_people",
        "Who's been on your mind lately, and what about them keeps coming up?",
    ),
    PromptTemplate(
        "people-2",
        "relationships_people",
        "Was there a conversation recently that stuck with you afterward?",
    ),
    PromptTemplate(
        "changes-1",
        "changes_in_life",
        "What feels like it's shifting in your life right now, even slowly?",
    ),
    PromptTemplate(
        "changes-2",
        "changes_in_life",
        "Compared to a month ago, what feels different about how your days are going?",
    ),
    PromptTemplate(
        "opinions-1",
        "opinions_changed",
        "Have you changed your mind about anything lately—big or small?",
    ),
    PromptTemplate(
        "opinions-2",
        "opinions_changed",
        "Is there a belief or assumption you've been quietly reconsidering?",
    ),
    PromptTemplate(
        "memories-1",
        "memories",
        "What memory keeps resurfacing for no obvious reason?",
    ),
    PromptTemplate(
        "memories-2",
        "memories",
        "Is there a past version of a regular day you suddenly miss or feel grateful for?",
    ),
    PromptTemplate(
        "looking-1",
        "looking_forward",
        "What are you looking forward to, even if it's something small?",
    ),
    PromptTemplate(
        "looking-2",
        "looking_forward",
        "Is there something upcoming that you're curious about more than anxious about?",
    ),
    PromptTemplate(
        "decisions-1",
        "decisions",
        "What decision are you circling around without quite landing on?",
    ),
    PromptTemplate(
        "decisions-2",
        "decisions",
        "Is there a choice you've been delaying because both options feel incomplete?",
    ),
    PromptTemplate(
        "observations-1",
        "observations",
        "What's an observation about your life lately that you haven't written down yet?",
    ),
    PromptTemplate(
        "observations-2",
        "observations",
        "If you zoomed out on the past couple weeks, what pattern would stand out?",
    ),
)


@dataclass
class PromptHistory:
    recent_ids: list[str]
    recent_categories: list[str]
    last_proactive_at: str | None = None
    next_eligible_after: str | None = None

    def to_dict(self) -> dict:
        return {
            "recent_ids": self.recent_ids,
            "recent_categories": self.recent_categories,
            "last_proactive_at": self.last_proactive_at,
            "next_eligible_after": self.next_eligible_after,
        }

    @classmethod
    def from_dict(cls, data: dict | None) -> PromptHistory:
        data = data or {}
        return cls(
            recent_ids=list(data.get("recent_ids") or []),
            recent_categories=list(data.get("recent_categories") or []),
            last_proactive_at=data.get("last_proactive_at"),
            next_eligible_after=data.get("next_eligible_after"),
        )


def load_prompt_history(path: Path) -> PromptHistory:
    if not path.is_file():
        return PromptHistory(recent_ids=[], recent_categories=[])
    try:
        return PromptHistory.from_dict(json.loads(path.read_text(encoding="utf-8")))
    except (json.JSONDecodeError, OSError):
        return PromptHistory(recent_ids=[], recent_categories=[])


def save_prompt_history(path: Path, history: PromptHistory) -> None:
    atomic_write_json(path, history.to_dict())


def record_prompt_use(
    history: PromptHistory,
    prompt: PromptTemplate,
    *,
    limit: int,
) -> PromptHistory:
    ids = [prompt.id, *[i for i in history.recent_ids if i != prompt.id]]
    cats = [
        prompt.category,
        *[c for c in history.recent_categories if c != prompt.category],
    ]
    history.recent_ids = ids[:limit]
    history.recent_categories = cats[:limit]
    return history


def select_library_prompt(
    history: PromptHistory,
    *,
    rng: random.Random | None = None,
) -> PromptTemplate:
    rng = rng or random.Random()
    recent_ids = set(history.recent_ids[:8])
    recent_cats = set(history.recent_categories[:4])

    preferred = [
        p
        for p in PROMPT_LIBRARY
        if p.id not in recent_ids and p.category not in recent_cats
    ]
    if not preferred:
        preferred = [p for p in PROMPT_LIBRARY if p.id not in recent_ids]
    if not preferred:
        preferred = list(PROMPT_LIBRARY)
    return rng.choice(preferred)


def format_opening(prompt_text: str) -> str:
    text = prompt_text.strip()
    if text.lower().startswith("random question:"):
        return text
    return f"Random question: {text[0].lower() + text[1:] if text else text}"


def choose_next_proactive_delay_days(cfg: DiaryConfig, rng: random.Random | None = None) -> float:
    rng = rng or random.Random()
    lo = float(cfg.proactive.min_days)
    hi = float(cfg.proactive.max_days)
    if hi < lo:
        lo, hi = hi, lo
    return rng.uniform(lo, hi)


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def prompts_by_ids(ids: Sequence[str]) -> list[PromptTemplate]:
    index = {p.id: p for p in PROMPT_LIBRARY}
    return [index[i] for i in ids if i in index]
