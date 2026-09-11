"""LLM backends for diary conversation and entry generation."""

from __future__ import annotations

import json
import os
import re
import subprocess
import urllib.error
import urllib.request
from typing import Protocol

from .config import LLMConfig
from .models import DiaryEntry, DiarySession, Message


FOLLOWUP_SYSTEM = """You are Cherry, helping Tyler journal through a natural Telegram conversation.
Be conversational and thoughtful — like a good therapist or trusted friend, not an interviewer.
Ask at most one question at a time.
Use his previous answers to decide the next question.
Do not invent facts.

Pacing:
- Early turns: one short follow-up question.
- Once the thread feels naturally complete, or once enough has been shared, stop asking questions.
- Prefer closing sooner rather than excavating endlessly.
- Typical sessions are about 3–5 user replies total; do not keep probing after the core theme is clear.

When it is time to end, do NOT ask another question.
Reply with exactly this format:
CLOSING
<2–4 warm parting sentences that reflect what he shared, without diagnosing him or inventing new insights. No question mark.>

If you are told this must be the final turn, you MUST close with CLOSING as above."""


CLOSING_PREFIX = "CLOSING"


def parse_followup_response(raw: str) -> tuple[str, str]:
    """Return (kind, text) where kind is 'question' or 'closing'."""
    text = (raw or "").strip()
    if not text:
        return "question", "What feels most true about that right now?"
    upper = text.upper()
    if upper == "DONE" or upper.startswith("DONE\n"):
        remainder = text[4:].lstrip(" \n:").strip()
        return "closing", remainder or (
            "Thanks for sitting with that. I'll leave it here for now."
        )
    if upper.startswith(CLOSING_PREFIX):
        remainder = text[len(CLOSING_PREFIX) :].lstrip(" \n:").strip()
        return "closing", remainder or (
            "Thanks for sitting with that. I'll leave it here for now."
        )
    return "question", text


def generate_followup(
    llm: LLMClient,
    session: DiarySession,
    *,
    soft_user_replies: int = 4,
    max_user_replies: int = 6,
) -> tuple[str, str]:
    """Generate the next assistant turn.

    Returns (kind, text) with kind in {'question', 'closing'}.
    """
    user_count = session.user_message_count()
    must_close = user_count >= max_user_replies
    prefer_close = user_count >= soft_user_replies

    guidance = ""
    if must_close:
        guidance = (
            "\n\nThis is the final turn. You MUST end with CLOSING and parting words. "
            "Do not ask another question."
        )
    elif prefer_close:
        guidance = (
            "\n\nEnough has likely been shared. Prefer CLOSING with warm parting words "
            "unless one brief clarifying question is truly needed."
        )

    raw = llm.complete(
        system=FOLLOWUP_SYSTEM + guidance,
        messages=session.messages,
        temperature=0.7 if must_close else 0.8,
    ).strip()
    kind, text = parse_followup_response(raw)
    if must_close and kind != "closing":
        # Hard stop even if the model ignored instructions.
        kind = "closing"
        text = text if not text.endswith("?") else (
            "It sounds like you're holding a few competing needs at once. "
            "Thanks for talking that through — I'll leave it here for tonight."
        )
    return kind, text


def generate_parting_words(llm: LLMClient, session: DiarySession) -> str:
    system = (
        "Write 2–4 warm parting sentences for the end of a diary conversation. "
        "Reflect only what Tyler actually shared. No questions. No diagnosis. "
        "Return only the parting words."
    )
    raw = llm.complete(
        system=system,
        messages=session.messages,
        temperature=0.5,
    ).strip()
    kind, text = parse_followup_response(raw)
    if kind == "closing":
        return text
    if text.endswith("?"):
        return (
            "Thanks for sharing that. I'll leave it here for now and write it up."
        )
    return text or "Thanks for sharing that. I'll leave it here for now."


ENTRY_SYSTEM = """Convert a diary conversation into a compact first-person Markdown diary entry.
Write as if Tyler wrote it.
Preserve concrete events, thoughts, and feelings he actually expressed.
Remove conversational filler.
Do not invent events or psychological interpretations.
Preserve uncertainty when he was uncertain.
Be conservative about inference.

Return ONLY valid JSON with keys:
- title: short descriptive title
- body: diary body paragraphs (no heading)
- tags: array of 0-5 short tags without # prefix
"""


class LLMClient(Protocol):
    def complete(self, *, system: str, messages: list[Message], temperature: float = 0.7) -> str:
        ...


class StubLLM:
    """Deterministic offline backend for tests."""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    def complete(self, *, system: str, messages: list[Message], temperature: float = 0.7) -> str:
        self.calls.append({"system": system, "messages": messages, "temperature": temperature})
        last_user = next((m.content for m in reversed(messages) if m.role == "user"), "")
        if "Convert a diary conversation" in system or "Return ONLY valid JSON" in system:
            return json.dumps(
                {
                    "title": "Conversation notes",
                    "body": last_user or "I talked through a few thoughts.",
                    "tags": ["reflection"],
                }
            )
        if "DONE" in last_user.upper() or last_user.upper().startswith("CLOSING"):
            return "CLOSING\nThanks for sitting with that. I'll leave it here for now."
        user_count = len([m for m in messages if m.role == "user"])
        # Only force-close when the runtime guidance marks a hard stop.
        if user_count >= 4 or "this is the final turn" in system.lower():
            return (
                "CLOSING\nIt sounds like a few things are competing for your energy. "
                "Thanks for talking that through — I'll leave it here for now."
            )
        return "What's the most important part of that for you?"


class OpenAICompatLLM:
    def __init__(self, cfg: LLMConfig) -> None:
        self.cfg = cfg

    def complete(self, *, system: str, messages: list[Message], temperature: float = 0.7) -> str:
        payload = {
            "model": self.cfg.model,
            "temperature": temperature,
            "messages": [
                {"role": "system", "content": system},
                *[{"role": m.role, "content": m.content} for m in messages],
            ],
        }
        req = urllib.request.Request(
            f"{self.cfg.base_url.rstrip('/')}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.cfg.api_key}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.cfg.timeout_seconds) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.URLError as exc:
            raise RuntimeError(f"LLM request failed: {exc}") from exc
        try:
            return data["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError(f"Unexpected LLM response: {data!r}") from exc


class OpenClawAgentLLM:
    """One-shot text inference via `openclaw infer model run --local`.

    Uses local transport so diary completions do not re-enter Gateway
    `before_agent_reply` hooks (which previously caused recursive diary claims).
    """

    def __init__(self, cfg: LLMConfig) -> None:
        self.cfg = cfg

    def complete(self, *, system: str, messages: list[Message], temperature: float = 0.7) -> str:
        del temperature
        transcript = "\n".join(f"{m.role}: {m.content}" for m in messages)
        prompt = f"{system}\n\nConversation so far:\n{transcript}\n\nRespond now."
        cmd = [
            self.cfg.openclaw_bin,
            "infer",
            "model",
            "run",
            "--local",
            "--json",
            "--thinking",
            "off",
            "--prompt",
            prompt,
        ]
        if self.cfg.model:
            cmd.extend(["--model", self.cfg.model])
        env = {
            **os.environ,
            "DIARY_LLM_INTERNAL": "1",
        }
        try:
            proc = subprocess.run(
                cmd,
                check=False,
                capture_output=True,
                text=True,
                timeout=self.cfg.timeout_seconds + 15,
                env=env,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(
                f"openclaw infer timed out after {self.cfg.timeout_seconds}s"
            ) from exc
        except OSError as exc:
            raise RuntimeError(f"openclaw infer failed: {exc}") from exc
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or "openclaw infer failed")
        out = proc.stdout.strip()
        # Prefer the last JSON object in case provider logs precede it.
        text = _extract_infer_text(out)
        if text:
            return text
        return out


def _extract_infer_text(raw: str) -> str | None:
    raw = raw.strip()
    if not raw:
        return None
    candidates: list[str] = []
    if raw.startswith("{"):
        candidates.append(raw)
    else:
        start = raw.rfind("\n{")
        if start >= 0:
            candidates.append(raw[start + 1 :])
        start = raw.find("{")
        if start >= 0:
            candidates.append(raw[start:])
    for candidate in candidates:
        try:
            data = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if not isinstance(data, dict):
            continue
        outputs = data.get("outputs")
        if isinstance(outputs, list) and outputs:
            first = outputs[0]
            if isinstance(first, dict) and isinstance(first.get("text"), str):
                text = first["text"].strip()
                if text:
                    return text
        for key in ("text", "message", "output", "reply"):
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return None


def build_llm(cfg: LLMConfig) -> LLMClient:
    backend = (cfg.backend or "openai").lower()
    if backend == "stub":
        return StubLLM()
    if backend == "openclaw":
        return OpenClawAgentLLM(cfg)
    return OpenAICompatLLM(cfg)


def _extract_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", text)
        if not match:
            raise
        return json.loads(match.group(0))


def generate_entry(
    llm: LLMClient,
    session: DiarySession,
    *,
    date: str,
) -> DiaryEntry:
    payload = {
        "initial_prompt": session.initial_prompt,
        "messages": [m.to_dict() for m in session.messages],
    }
    raw = llm.complete(
        system=ENTRY_SYSTEM,
        messages=[Message(role="user", content=json.dumps(payload, ensure_ascii=False))],
        temperature=0.3,
    )
    try:
        data = _extract_json(raw)
        title = str(data.get("title") or "Diary entry").strip()
        body = str(data.get("body") or "").strip()
        tags = [str(t).lstrip("#").strip() for t in (data.get("tags") or []) if str(t).strip()]
    except (json.JSONDecodeError, TypeError, ValueError):
        title = "Diary entry"
        body = raw.strip() or "I had a short reflective conversation."
        tags = []
    if not body:
        user_bits = [m.content for m in session.messages if m.role == "user"]
        body = " ".join(user_bits) if user_bits else "I checked in briefly."
    return DiaryEntry(
        date=date,
        title=title,
        body=body,
        tags=tags,
        session_id=session.session_id,
    )


def generate_personalized_prompt(
    llm: LLMClient,
    *,
    recent_entries: list[str],
    topic_entries: list[str],
    recent_prompts: list[str],
) -> str | None:
    """Optionally craft a retrospective prompt from prior entries.

    Returns None when there isn't enough material.
    """
    if not recent_entries and not topic_entries:
        return None
    system = (
        "Write one short diary reflection question for Tyler based on prior entries. "
        "Most questions should feel spontaneous; only lightly reference past writing. "
        "Do not lecture. Return only the question text."
    )
    user = json.dumps(
        {
            "recent_entries": recent_entries,
            "topic_entries": topic_entries,
            "avoid_similar_to": recent_prompts,
        },
        ensure_ascii=False,
    )
    text = llm.complete(
        system=system,
        messages=[Message(role="user", content=user)],
        temperature=0.9,
    ).strip()
    if not text or len(text) < 12:
        return None
    return text.splitlines()[0].strip().strip('"')
