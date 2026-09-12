"""End-to-end diary conversation workflow."""

from __future__ import annotations

import json
import random
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from .config import DiaryConfig
from .history import DiaryHistory, MarkdownDiaryHistory
from .llm import (
    LLMClient,
    build_llm,
    generate_entry,
    generate_followup,
    generate_parting_words,
    generate_personalized_prompt,
)
from .models import DiarySession, utc_now, utc_now_iso
from .prompts import (
    PromptTemplate,
    choose_next_proactive_delay_days,
    format_opening,
    load_prompt_history,
    parse_iso,
    record_prompt_use,
    save_prompt_history,
    select_library_prompt,
)
from .sanitize import sanitize_user_text
from .session import SessionStore
from .storage import append_entry
from .telegram import TelegramSender


@dataclass
class ActionResult:
    ok: bool
    action: str
    message: str | None = None
    session_id: str | None = None
    details: dict | None = None

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "action": self.action,
            "message": self.message,
            "session_id": self.session_id,
            "details": self.details or {},
        }


class DiaryWorkflow:
    def __init__(
        self,
        cfg: DiaryConfig,
        *,
        llm: LLMClient | None = None,
        history: DiaryHistory | None = None,
        sender: TelegramSender | None = None,
        rng: random.Random | None = None,
        now_fn=None,
    ) -> None:
        self.cfg = cfg
        self.store = SessionStore(cfg.active_session_path, cfg.conversations_dir)
        self.llm = llm or build_llm(cfg.llm)
        self.history = history or MarkdownDiaryHistory(cfg.diary_dir)
        self.sender = sender or TelegramSender()
        self.rng = rng or random.Random()
        self.now_fn = now_fn or utc_now

    def status(self) -> dict:
        active = self.store.get_active()
        if not active:
            return {"active": False}
        return {
            "active": True,
            "session_id": active.session_id,
            "origin": active.origin,
            "started_at": active.started_at,
            "last_interaction_at": active.last_interaction_at,
            "initial_prompt": active.initial_prompt,
            "message_count": len(active.messages),
            "status": active.status,
        }

    def start_manual(self, *, prompt_text: str | None = None) -> ActionResult:
        active = self.store.get_active()
        if active:
            if active.messages:
                msg = (
                    "Diary session already in progress.\n\n"
                    f"{active.messages[-1].content}"
                )
            else:
                msg = "Diary session already in progress."
            return ActionResult(
                ok=True,
                action="continue",
                message=msg,
                session_id=active.session_id,
                details={"continued": True},
            )
        return self._start(origin="manual", prompt_text=prompt_text, send=False)

    def start_proactive(self, *, force: bool = False, send: bool = True) -> ActionResult:
        if self.store.get_active():
            return ActionResult(
                ok=True,
                action="skip",
                message="Active diary session exists; skipping proactive prompt.",
                details={"reason": "active_session"},
            )
        if not self.cfg.proactive.enabled and not force:
            return ActionResult(
                ok=True,
                action="skip",
                message="Proactive diary prompts disabled.",
                details={"reason": "disabled"},
            )
        if not force and not self._proactive_due():
            return ActionResult(
                ok=True,
                action="skip",
                message="Proactive prompt not due yet.",
                details={"reason": "not_due"},
            )
        if not force and not self._within_allowed_hours():
            return ActionResult(
                ok=True,
                action="skip",
                message="Outside allowed prompt hours.",
                details={"reason": "outside_hours"},
            )
        result = self._start(origin="proactive", send=send)
        if result.ok and result.action == "started":
            self._mark_proactive_sent()
        return result

    def handle_user_message(self, text: str) -> ActionResult:
        text = sanitize_user_text(text)
        if not text:
            return ActionResult(ok=False, action="error", message="Empty message.")

        lowered = text.lower().strip()
        if lowered in {"/diary", "/diary start"}:
            started = self.start_manual()
            if started.message and started.action in {"started", "continue"}:
                # For slash-start, return the opening/continuation text to the user.
                return started
            return started
        if lowered in {"/diary done", "/diary end", "/diary finish"}:
            return self.finish(reason="explicit")

        active = self.store.get_active()
        if not active:
            return ActionResult(
                ok=False,
                action="not_diary",
                message="No active diary session.",
                details={"diary": False},
            )

        # Avoid duplicating the same user turn if a previous attempt crashed mid-reply.
        last = active.messages[-1] if active.messages else None
        if not (last and last.role == "user" and last.content.strip() == text):
            active.append("user", text, timestamp=self.now_fn().isoformat())
            self.store.save_active(active)

        try:
            kind, followup = generate_followup(
                self.llm,
                active,
                soft_user_replies=self.cfg.conversation.soft_user_replies,
                max_user_replies=self.cfg.conversation.max_user_replies,
            )
        except Exception as exc:  # noqa: BLE001 - surface to Telegram, keep session
            return ActionResult(
                ok=False,
                action="error",
                message=(
                    "I saved your reply, but diary follow-up generation failed. "
                    f"Try again in a moment. ({exc})"
                ),
                session_id=active.session_id,
                details={"error": str(exc)},
            )

        if kind == "closing":
            active.append("assistant", followup, timestamp=self.now_fn().isoformat())
            self.store.save_active(active)
            return self.finish(
                reason="model_complete",
                session=active,
                parting_words=followup,
            )

        active.append("assistant", followup, timestamp=self.now_fn().isoformat())
        self.store.save_active(active)
        return ActionResult(
            ok=True,
            action="reply",
            message=followup,
            session_id=active.session_id,
        )

    def finish(
        self,
        *,
        reason: str = "explicit",
        session: DiarySession | None = None,
        parting_words: str | None = None,
    ) -> ActionResult:
        active = session or self.store.get_active()
        if not active:
            return ActionResult(
                ok=True,
                action="noop",
                message="No active diary session to finish.",
            )
        if active.user_message_count() == 0:
            active.status = "abandoned"
            self.store.save_conversation(active)
            self.store.clear_active()
            return ActionResult(
                ok=True,
                action="abandoned",
                message="Diary session ended with no replies; nothing saved.",
                session_id=active.session_id,
                details={"reason": reason},
            )

        if parting_words is None and reason in {"explicit", "inactivity", "model_complete"}:
            # Explicit/timeout closes should still get a brief human ending when possible.
            if reason != "model_complete":
                try:
                    parting_words = generate_parting_words(self.llm, active)
                    active.append(
                        "assistant",
                        parting_words,
                        timestamp=self.now_fn().isoformat(),
                    )
                except Exception:  # noqa: BLE001
                    parting_words = (
                        "Thanks for sharing that. I'll leave it here and write it up."
                    )

        active.status = "finalizing"
        self.store.save_conversation(active)

        local_date = self._local_now().date().isoformat()
        entry = generate_entry(self.llm, active, date=local_date)
        path = append_entry(self.cfg.diary_dir, entry)
        active.status = "completed"
        active.entry_path = str(path)
        self.store.save_conversation(active)
        self.store.clear_active()

        if parting_words:
            message = parting_words.strip()
        elif reason == "inactivity":
            message = f"Conversation timed out — saved diary entry “{entry.title}.”"
        else:
            message = f"Saved diary entry “{entry.title}” to {path.name}."

        return ActionResult(
            ok=True,
            action="finalized",
            message=message,
            session_id=active.session_id,
            details={
                "reason": reason,
                "entry_path": str(path),
                "title": entry.title,
                "parting_words": parting_words,
            },
        )

    def tick(self, *, send: bool = True) -> list[ActionResult]:
        results: list[ActionResult] = []
        timed_out = self.finalize_if_inactive(send=send)
        if timed_out:
            results.append(timed_out)
        proactive = self.start_proactive(send=send)
        results.append(proactive)
        return results

    def finalize_if_inactive(self, *, send: bool = False) -> ActionResult | None:
        active = self.store.get_active()
        if not active:
            return None
        last = parse_iso(active.last_interaction_at)
        if not last:
            return None
        timeout = timedelta(hours=self.cfg.inactivity_timeout_hours)
        if self.now_fn() - last < timeout:
            return None
        result = self.finish(reason="inactivity", session=active)
        if send and result.message:
            self.sender.send(result.message)
        return result

    def _start(
        self,
        *,
        origin: str,
        prompt_text: str | None = None,
        send: bool = False,
    ) -> ActionResult:
        history = load_prompt_history(self.cfg.prompt_history_path)
        template: PromptTemplate | None = None
        opening = prompt_text

        if not opening and origin == "proactive" and self.rng.random() < 0.25:
            opening = self._maybe_personalized_prompt(history)

        if not opening:
            template = select_library_prompt(history, rng=self.rng)
            opening = format_opening(template.text)
            history = record_prompt_use(
                history,
                template,
                limit=self.cfg.history.recent_prompt_limit,
            )
            save_prompt_history(self.cfg.prompt_history_path, history)
        elif template is None and origin == "proactive":
            # Personalized / custom prompts still get recorded as used text ids.
            fake = PromptTemplate(
                id=f"custom-{self.now_fn().strftime('%Y%m%d%H%M%S')}",
                category="retrospective",
                text=opening,
            )
            history = record_prompt_use(
                history,
                fake,
                limit=self.cfg.history.recent_prompt_limit,
            )
            save_prompt_history(self.cfg.prompt_history_path, history)
            template = fake

        session = DiarySession.create(
            initial_prompt=opening,
            origin=origin,  # type: ignore[arg-type]
            prompt_category=template.category if template else None,
            prompt_id=template.id if template else None,
        )
        # Align timestamps with injectable clock (tests / deterministic runs).
        now_iso = self.now_fn().isoformat()
        session.started_at = now_iso
        session.last_interaction_at = now_iso
        if session.messages:
            session.messages[0].timestamp = now_iso
        self.store.save_active(session)
        if send:
            send_result = self.sender.send(opening)
            if not send_result.ok:
                return ActionResult(
                    ok=False,
                    action="error",
                    message=f"Started session but failed to send: {send_result.output}",
                    session_id=session.session_id,
                )
        return ActionResult(
            ok=True,
            action="started",
            message=opening,
            session_id=session.session_id,
            details={"origin": origin},
        )

    def _maybe_personalized_prompt(self, history) -> str | None:
        recent = [e.text for e in self.history.recent(self.cfg.history.recent_entries)]
        topic = []
        if recent:
            # Use keywords from the newest entry for a light topical pull.
            topic = [
                e.text
                for e in self.history.search(recent[0][:200], self.cfg.history.topic_entries)
            ]
        recent_prompts = history.recent_ids[:]
        text = generate_personalized_prompt(
            self.llm,
            recent_entries=recent,
            topic_entries=topic,
            recent_prompts=recent_prompts,
        )
        if not text:
            return None
        return format_opening(text)

    def _local_now(self) -> datetime:
        now = self.now_fn()
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        try:
            return now.astimezone(ZoneInfo(self.cfg.timezone))
        except Exception:
            return now.astimezone()

    def _within_allowed_hours(self) -> bool:
        hour = self._local_now().hour
        return hour in set(self.cfg.proactive.allowed_hours)

    def _proactive_due(self) -> bool:
        history = load_prompt_history(self.cfg.prompt_history_path)
        next_after = parse_iso(history.next_eligible_after)
        if next_after and self.now_fn() < next_after:
            return False
        if not history.last_proactive_at and not next_after:
            # First run: allow, but only inside allowed hours (checked separately).
            return True
        last = parse_iso(history.last_proactive_at)
        if not last:
            return True
        min_delta = timedelta(days=self.cfg.proactive.min_days)
        return self.now_fn() - last >= min_delta

    def _mark_proactive_sent(self) -> None:
        history = load_prompt_history(self.cfg.prompt_history_path)
        now = self.now_fn()
        history.last_proactive_at = now.isoformat()
        delay_days = choose_next_proactive_delay_days(self.cfg, self.rng)
        history.next_eligible_after = (now + timedelta(days=delay_days)).isoformat()
        save_prompt_history(self.cfg.prompt_history_path, history)
        atomic_scheduler = {
            "last_proactive_at": history.last_proactive_at,
            "next_eligible_after": history.next_eligible_after,
            "updated_at": utc_now_iso(),
        }
        from .atomic import atomic_write_json

        atomic_write_json(self.cfg.scheduler_state_path, atomic_scheduler)


def result_json(results: ActionResult | list[ActionResult]) -> str:
    if isinstance(results, list):
        payload = [r.to_dict() for r in results]
    else:
        payload = results.to_dict()
    return json.dumps(payload, indent=2, ensure_ascii=False)
