#!/usr/bin/env python3
"""Word-recall quizzes for Cherry.

Reads ~/syncthing/notes/words_to_remember.md, asks for the word that matches
a definition, and moves a word to the completed section after three correct
answers. A tick on the diary cadence sends one quiz; /words starts one now.
"""

from __future__ import annotations

import argparse
import difflib
import json
import os
import random
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

TZ = ZoneInfo("America/Los_Angeles")
MIN_DAYS = 3.0
MAX_DAYS = 5.0
ALLOWED_HOURS = {17, 18, 19, 20, 21}
CORRECT_TO_COMPLETE = 3
REVISIT_AFTER_DAYS = 21
COMPLETED_PICK_CHANCE = 0.2
FUZZY_RATIO = 0.86

NOTES_PATH = Path.home() / "syncthing/notes/words_to_remember.md"
STATE_PATH = Path.home() / ".local/share/word-recall/state.json"
OPENCLAW_BIN = Path.home() / "git/tools/openclaw/openclaw-gateway"
INFER_MODEL = os.environ.get("WORDS_INFER_MODEL", "openai/gpt-5.6-sol")
INFER_TIMEOUT = int(os.environ.get("WORDS_INFER_TIMEOUT", "60"))

ITEM_RE = re.compile(
    r"^[-*]\s+\*\*(?P<word>.+?)\*\*\s*(?:—|–|-|:)\s*(?P<definition>.+?)\s*$"
)
SECTION_RE = re.compile(r"^##\s+(active|completed)\s*$", re.IGNORECASE)
COMMAND_RE = re.compile(r"^/(?:words|recall)(?:@\S+)?(?:\s+(.*))?$", re.IGNORECASE | re.DOTALL)
OTHER_COMMAND_RE = re.compile(r"^/(?:diary|food|new|reset)\b", re.IGNORECASE)

DEFAULT_PREAMBLE = """# Words to remember

Add a word and a short definition under Active. Cherry will send the definition and ask you to name the word. Three correct recalls move it to Completed.

Example (this line is not quizzed):

- **ephemeral** — lasting for a very short time
"""


@dataclass
class WordItem:
    word: str
    definition: str
    section: str  # active | completed


def now_local() -> datetime:
    return datetime.now(TZ)


def word_key(word: str) -> str:
    return normalize(word)


def normalize(text: str) -> str:
    text = text.lower().strip()
    text = text.replace("’", "'")
    text = re.sub(r"[^a-z0-9' -]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def parse_words(text: str) -> tuple[str, list[WordItem]]:
    preamble: list[str] = []
    section: str | None = None
    items: list[WordItem] = []
    seen: set[str] = set()
    for line in text.splitlines():
        header = SECTION_RE.match(line.strip())
        if header:
            section = header.group(1).lower()
            continue
        if section is None:
            preamble.append(line)
            continue
        match = ITEM_RE.match(line.strip())
        if not match:
            continue
        word = match.group("word").strip()
        definition = match.group("definition").strip()
        key = word_key(word)
        if not key or not definition or key in seen:
            continue
        seen.add(key)
        items.append(WordItem(word=word, definition=definition, section=section))
    return "\n".join(preamble).strip(), items


def render_words(preamble: str, items: list[WordItem]) -> str:
    header = (preamble or DEFAULT_PREAMBLE).strip()
    lines = [header, "", "## Active", ""]
    active = [item for item in items if item.section == "active"]
    completed = [item for item in items if item.section == "completed"]
    if active:
        lines.extend(f"- **{item.word}** — {item.definition}" for item in active)
    else:
        lines.append("_(none yet)_")
    lines.extend(["", "## Completed", ""])
    if completed:
        lines.extend(f"- **{item.word}** — {item.definition}" for item in completed)
    else:
        lines.append("_(none yet)_")
    lines.append("")
    return "\n".join(lines)


def load_notes(path: Path) -> tuple[str, list[WordItem]]:
    if not path.exists():
        return DEFAULT_PREAMBLE.strip(), []
    return parse_words(path.read_text(encoding="utf-8"))


def save_notes(path: Path, preamble: str, items: list[WordItem]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write(path, render_words(preamble, items))


def load_state(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        data = {}
    if not isinstance(data, dict):
        data = {}
    data.setdefault("words", {})
    if not isinstance(data["words"], dict):
        data["words"] = {}
    return data


def save_state(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write(path, json.dumps(state, indent=2, ensure_ascii=False) + "\n")


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def word_stats(state: dict, word: str) -> dict:
    stats = state["words"].get(word_key(word))
    if not isinstance(stats, dict):
        stats = {"correct": 0}
        state["words"][word_key(word)] = stats
    stats.setdefault("correct", 0)
    return stats


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=TZ)
    return parsed.astimezone(TZ)


def is_stale(state: dict, word: str, moment: datetime) -> bool:
    last = parse_iso(word_stats(state, word).get("last_asked"))
    if last is None:
        return True
    return moment - last >= timedelta(days=REVISIT_AFTER_DAYS)


def _oldest(items: list[WordItem], state: dict) -> WordItem:
    def sort_key(item: WordItem) -> tuple:
        last = parse_iso(word_stats(state, item.word).get("last_asked"))
        return (last is not None, last or datetime.min.replace(tzinfo=TZ))

    return sorted(items, key=sort_key)[0]


def choose_word(
    items: list[WordItem],
    state: dict,
    *,
    moment: datetime,
    rng: random.Random,
    force: bool,
) -> WordItem | None:
    """Pick a list word. None means the list cannot supply one."""
    active = [item for item in items if item.section == "active"]
    completed = [item for item in items if item.section == "completed"]
    stale_completed = [item for item in completed if is_stale(state, item.word, moment)]

    if active:
        if stale_completed and rng.random() < COMPLETED_PICK_CHANCE:
            return _oldest(stale_completed, state)
        return _oldest(active, state)
    if not completed:
        return None
    if force:
        return _oldest(completed, state)
    if not stale_completed:
        return None
    return _oldest(stale_completed, state)


def is_correct(guess: str, word: str) -> bool:
    expected = normalize(word)
    given = normalize(guess)
    if not expected or not given:
        return False
    if given == expected:
        return True
    if re.search(rf"(?:^| ){re.escape(expected)}(?:$| )", given):
        return True
    return difflib.SequenceMatcher(None, given, expected).ratio() >= FUZZY_RATIO


def quiz_message(item: WordItem) -> str:
    return f"What's the word?\n\n{item.definition}"


def record_ask(state: dict, item: WordItem, moment: datetime, *, source: str) -> None:
    stats = word_stats(state, item.word)
    stats["last_asked"] = moment.isoformat()
    state["pending"] = {
        "word": item.word,
        "definition": item.definition,
        "section": item.section,
        "asked_at": moment.isoformat(),
        "source": source,
    }


def schedule_next(state: dict, moment: datetime, rng: random.Random) -> None:
    delay = rng.uniform(MIN_DAYS, MAX_DAYS)
    state["last_proactive_at"] = moment.isoformat()
    state["next_proactive_at"] = (moment + timedelta(days=delay)).isoformat()


def proactive_due(state: dict, moment: datetime) -> bool:
    if state.get("pending"):
        return False
    if moment.hour not in ALLOWED_HOURS:
        return False
    nxt = parse_iso(state.get("next_proactive_at"))
    if nxt is None:
        return True
    return moment >= nxt


def apply_grade(
    items: list[WordItem],
    state: dict,
    guess: str,
    *,
    moment: datetime,
) -> tuple[list[WordItem], str]:
    pending = state.get("pending") or {}
    word = str(pending.get("word") or "")
    definition = str(pending.get("definition") or "")
    section = str(pending.get("section") or "active")
    state["pending"] = None
    if not word:
        return items, "No quiz is waiting."

    stats = word_stats(state, word)
    if not is_correct(guess, word):
        stats["last_result"] = "wrong"
        stats["last_answered"] = moment.isoformat()
        return items, f"That was **{word}** — {definition}"

    stats["last_result"] = "correct"
    stats["last_answered"] = moment.isoformat()
    if section == "completed":
        return items, f"Yes — **{word}**."

    stats["correct"] = int(stats.get("correct") or 0) + 1
    count = stats["correct"]
    if count < CORRECT_TO_COMPLETE:
        return items, f"Yes — **{word}**. That's {count} of {CORRECT_TO_COMPLETE}."

    for item in items:
        if word_key(item.word) == word_key(word):
            item.section = "completed"
            break
    stats["completed_at"] = moment.isoformat()
    return (
        items,
        f"Yes — **{word}**. That's {CORRECT_TO_COMPLETE} of {CORRECT_TO_COMPLETE}, "
        "so I'm moving it to completed. I'll only bring it back occasionally.",
    )


def add_word(items: list[WordItem], word: str, definition: str) -> tuple[list[WordItem], str]:
    word = word.strip().strip("*")
    definition = definition.strip()
    if not word or not definition:
        return items, "Add a word like `/words add ephemeral — lasting for a very short time`."
    key = word_key(word)
    for item in items:
        if word_key(item.word) == key:
            item.definition = definition
            if item.section != "active":
                item.section = "active"
            return items, f"Updated **{item.word}** and put it back in active."
    items.append(WordItem(word=word, definition=definition, section="active"))
    return items, f"Added **{word}**."


def list_message(items: list[WordItem], state: dict) -> str:
    def line(item: WordItem) -> str:
        correct = int(word_stats(state, item.word).get("correct") or 0)
        if item.section == "active":
            return f"- **{item.word}** ({correct}/{CORRECT_TO_COMPLETE}) — {item.definition}"
        return f"- **{item.word}** — {item.definition}"

    active = [item for item in items if item.section == "active"]
    completed = [item for item in items if item.section == "completed"]
    parts = ["Active:"]
    parts.extend(line(item) for item in active)
    if not active:
        parts.append("- (none)")
    parts.append("")
    parts.append("Completed:")
    parts.extend(line(item) for item in completed)
    if not completed:
        parts.append("- (none)")
    return "\n".join(parts)


def _extract_infer_text(raw: str) -> str:
    raw = raw.strip()
    if not raw:
        return ""
    start = raw.find("{")
    candidate = raw[start:] if start >= 0 else raw
    try:
        data = json.loads(candidate)
    except json.JSONDecodeError:
        return raw
    if not isinstance(data, dict):
        return raw
    outputs = data.get("outputs")
    if isinstance(outputs, list) and outputs:
        first = outputs[0]
        if isinstance(first, dict) and isinstance(first.get("text"), str):
            return first["text"].strip()
        if isinstance(first, str):
            return first.strip()
    for key in ("text", "content", "output"):
        if isinstance(data.get(key), str) and data[key].strip():
            return data[key].strip()
    return raw


def infer_text(prompt: str) -> str:
    binary = str(OPENCLAW_BIN if OPENCLAW_BIN.exists() else "openclaw")
    cmd = [
        binary,
        "infer",
        "model",
        "run",
        "--local",
        "--json",
        "--thinking",
        "off",
        "--model",
        INFER_MODEL,
        "--prompt",
        prompt,
    ]
    env = {**os.environ, "WORDS_CLI_INTERNAL": "1", "DIARY_LLM_INTERNAL": "1", "FOOD_CLI_INTERNAL": "1"}
    proc = subprocess.run(
        cmd,
        check=False,
        capture_output=True,
        text=True,
        timeout=INFER_TIMEOUT + 15,
        env=env,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or "openclaw infer failed")
    return _extract_infer_text(proc.stdout)


def generate_word(infer_fn=infer_text) -> WordItem:
    prompt = """Pick one English word that a college-educated adult sometimes uses in everyday speech.
Not slang, not a proper noun, not technical jargon, not an everyday word like "happy" or "because".
Return ONLY JSON: {"word":"lowercase","definition":"one short sentence that does not contain the word"}"""
    raw = infer_fn(prompt)
    start = raw.find("{")
    end = raw.rfind("}")
    if start < 0 or end < start:
        raise RuntimeError(f"LLM did not return JSON: {raw[:200]}")
    data = json.loads(raw[start : end + 1])
    word = str(data.get("word") or "").strip()
    definition = str(data.get("definition") or "").strip()
    if not word or not definition:
        raise RuntimeError("LLM JSON missing word or definition")
    if word_key(word) in word_key(definition):
        definition = re.sub(re.escape(word), "this", definition, flags=re.IGNORECASE).strip()
    return WordItem(word=word, definition=definition, section="active")


def looks_like_answer(text: str) -> bool:
    cleaned = text.strip()
    if not cleaned or cleaned.startswith("/"):
        return False
    if OTHER_COMMAND_RE.match(cleaned):
        return False
    if re.search(r"\d", cleaned):
        return False
    words = cleaned.split()
    return 1 <= len(words) <= 4 and len(cleaned) <= 40


def parse_add(rest: str) -> tuple[str, str] | None:
    match = re.match(r"add\s+(.+?)\s*(?:—|–|-|:)\s*(.+)", rest.strip(), re.IGNORECASE | re.DOTALL)
    if not match:
        return None
    return match.group(1).strip(), match.group(2).strip()


def _send_telegram(message: str) -> bool:
    from cabinet import telegram as cabinet_telegram

    return bool(cabinet_telegram(message, is_quiet=True))


def start_quiz(
    *,
    notes_path: Path,
    state_path: Path,
    moment: datetime,
    rng: random.Random,
    force: bool,
    source: str,
    infer_fn=infer_text,
) -> dict:
    preamble, items = load_notes(notes_path)
    state = load_state(state_path)
    if state.get("pending") and not force:
        pending = state["pending"]
        return {
            "ok": True,
            "action": "pending",
            "message": quiz_message(
                WordItem(pending["word"], pending["definition"], pending.get("section") or "active")
            ),
        }

    item = choose_word(items, state, moment=moment, rng=rng, force=force)
    generated = False
    if item is None and not any(entry.section == "active" for entry in items):
        if any(entry.section == "completed" for entry in items) and not force:
            return {"ok": True, "action": "skip", "message": None}
        try:
            item = generate_word(infer_fn)
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "action": "error", "message": f"Could not choose a word: {exc}"}
        items.append(item)
        generated = True
    if item is None:
        return {"ok": True, "action": "skip", "message": None}

    if force and state.get("pending"):
        state["pending"] = None
    record_ask(state, item, moment, source="generated" if generated else source)
    if source == "proactive":
        schedule_next(state, moment, rng)
    elif force:
        nxt = parse_iso(state.get("next_proactive_at"))
        earliest = moment + timedelta(days=MIN_DAYS)
        if nxt is None or nxt < earliest:
            state["next_proactive_at"] = earliest.isoformat()
    save_notes(notes_path, preamble, items)
    save_state(state_path, state)
    return {
        "ok": True,
        "action": "asked",
        "message": quiz_message(item),
        "word": item.word,
        "generated": generated,
    }


def cmd_handle(
    text: str,
    *,
    notes_path: Path,
    state_path: Path,
    moment: datetime | None = None,
    rng: random.Random | None = None,
    force: bool = False,
    infer_fn=infer_text,
) -> dict:
    moment = moment or now_local()
    rng = rng or random.Random()
    cleaned = (text or "").strip()
    command = COMMAND_RE.match(cleaned)
    if command or force:
        rest = ""
        if command:
            rest = (command.group(1) or "").strip()
        elif force:
            rest = re.sub(r"^/(?:words|recall)(?:@\S+)?\s*", "", cleaned, flags=re.IGNORECASE).strip()
        lowered = rest.lower()
        preamble, items = load_notes(notes_path)
        state = load_state(state_path)
        if lowered in {"", "quiz", "practice"}:
            return start_quiz(
                notes_path=notes_path,
                state_path=state_path,
                moment=moment,
                rng=rng,
                force=True,
                source="manual",
                infer_fn=infer_fn,
            )
        if lowered in {"skip", "cancel", "done"}:
            state["pending"] = None
            save_state(state_path, state)
            return {"ok": True, "action": "skipped", "message": "Skipped. Ask again with /words."}
        if lowered in {"list", "status"}:
            return {"ok": True, "action": "list", "message": list_message(items, state)}
        added = parse_add(rest)
        if added or lowered.startswith("add"):
            if not added:
                return {
                    "ok": False,
                    "action": "error",
                    "message": "Add a word like `/words add ephemeral — lasting for a very short time`.",
                }
            items, message = add_word(items, added[0], added[1])
            save_notes(notes_path, preamble, items)
            return {"ok": True, "action": "added", "message": message}
        return {
            "ok": False,
            "action": "error",
            "message": "Try `/words`, `/words add word — definition`, `/words list`, or `/words skip`.",
        }

    state = load_state(state_path)
    if not state.get("pending"):
        return {"ok": True, "action": "skip", "message": None}
    if not looks_like_answer(cleaned):
        return {"ok": True, "action": "skip", "message": None}
    preamble, items = load_notes(notes_path)
    items, message = apply_grade(items, state, cleaned, moment=moment)
    save_notes(notes_path, preamble, items)
    save_state(state_path, state)
    return {"ok": True, "action": "graded", "message": message}


def cmd_tick(
    *,
    notes_path: Path,
    state_path: Path,
    moment: datetime | None = None,
    rng: random.Random | None = None,
    send: bool = True,
    infer_fn=infer_text,
    send_fn=_send_telegram,
) -> dict:
    moment = moment or now_local()
    rng = rng or random.Random()
    state = load_state(state_path)
    if not proactive_due(state, moment):
        return {"ok": True, "action": "skip", "message": None}
    result = start_quiz(
        notes_path=notes_path,
        state_path=state_path,
        moment=moment,
        rng=rng,
        force=False,
        source="proactive",
        infer_fn=infer_fn,
    )
    if result.get("action") != "asked":
        return result
    message = result["message"]
    if not send:
        return result
    if not send_fn(message):
        return {"ok": False, "action": "error", "message": None, "error": "telegram send failed"}
    return {"ok": True, "action": "asked", "message": None, "sent": message}


def _emit(payload: dict, *, as_json: bool) -> int:
    if as_json:
        print(json.dumps(payload, ensure_ascii=False))
    elif payload.get("message"):
        print(payload["message"])
    else:
        print("NO_REPLY")
    return 0 if payload.get("ok", True) else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="words-cli")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--notes", type=Path, default=NOTES_PATH)
    parser.add_argument("--state", type=Path, default=STATE_PATH)
    sub = parser.add_subparsers(dest="command", required=True)
    handle = sub.add_parser("handle")
    handle.add_argument("text", nargs="?", default="")
    handle.add_argument("--force", action="store_true")
    tick = sub.add_parser("tick")
    tick.add_argument("--no-send", action="store_true")
    sub.add_parser("list")
    args = parser.parse_args(argv)

    if args.command == "list":
        preamble, items = load_notes(args.notes)
        if not args.notes.exists():
            save_notes(args.notes, preamble, items)
        state = load_state(args.state)
        return _emit({"ok": True, "action": "list", "message": list_message(items, state)}, as_json=args.json)
    if args.command == "handle":
        text = args.text
        if not text and not sys.stdin.isatty():
            text = sys.stdin.read()
        payload = cmd_handle(
            text,
            notes_path=args.notes,
            state_path=args.state,
            force=args.force,
        )
        return _emit(payload, as_json=args.json)
    if args.command == "tick":
        payload = cmd_tick(
            notes_path=args.notes,
            state_path=args.state,
            send=not args.no_send,
        )
        return _emit(payload, as_json=args.json)
    parser.error(f"unknown command {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
