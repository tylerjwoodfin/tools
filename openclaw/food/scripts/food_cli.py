#!/usr/bin/env python3
"""Non-interactive foodlog helper for the OpenClaw food plugin.

Keeps /food and reminder follow-ups off the main Telegram session (which is
often pinned to a local 26B model that cannot compact a large transcript).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

FOODLOG_DIR = Path.home() / "git/tools/foodlog"
OPENCLAW_BIN = Path.home() / "git/tools/openclaw/openclaw-gateway"
PENDING_PATH = Path.home() / ".local/share/openclaw-food/pending"
INFER_MODEL = os.environ.get("FOOD_INFER_MODEL", "openai/gpt-5.6-sol")
INFER_TIMEOUT = int(os.environ.get("FOOD_INFER_TIMEOUT", "60"))

SIMPLE = re.compile(
    r"^\s*(?:/food\s+)?(?P<name>.+?)\s+"
    r"(?:(?:should\s+be|is|=)\s+)?"
    r"(?P<cal>\d+)\s*(?:cal(?:ories)?)?\s*$",
    re.IGNORECASE,
)
NOT_FOOD = re.compile(
    r"^\s*(?:thanks|thank you|thx|later|ok|okay|k|no|nah|nope|"
    r"already logged|n/?a|/diary(?:\s|$)|/new(?:\s|$)|/reset(?:\s|$))\s*$",
    re.IGNORECASE,
)


def _load_foodlog():
    sys.path.insert(0, str(FOODLOG_DIR))
    import main as foodlog  # pylint: disable=import-outside-toplevel

    return foodlog


def today_iso() -> str:
    return date.today().isoformat()


def pending_is_today() -> bool:
    try:
        return PENDING_PATH.read_text(encoding="utf-8").strip() == today_iso()
    except OSError:
        return False


def set_pending() -> None:
    PENDING_PATH.parent.mkdir(parents=True, exist_ok=True)
    PENDING_PATH.write_text(today_iso() + "\n", encoding="utf-8")


def clear_pending() -> None:
    try:
        PENDING_PATH.unlink()
    except FileNotFoundError:
        pass


def strip_food_prefix(text: str) -> str:
    return re.sub(r"^\s*/food(?:@\S+)?\s*", "", text.strip(), flags=re.IGNORECASE).strip()


def parse_simple(text: str) -> list[dict] | None:
    cleaned = strip_food_prefix(text)
    if not cleaned:
        return None
    match = SIMPLE.match(cleaned)
    if not match:
        return None
    name = re.sub(r"\s+", " ", match.group("name")).strip(" .,-")
    if not name or name.lower() in {"food", "log"}:
        return None
    return [{"food": name.lower(), "calories": int(match.group("cal"))}]


def looks_like_food(text: str) -> bool:
    cleaned = strip_food_prefix(text)
    if not cleaned or NOT_FOOD.match(cleaned):
        return False
    if parse_simple(cleaned):
        return True
    if cleaned.lower().startswith("/food"):
        return True
    lowered = cleaned.lower()
    return bool(
        re.search(r"\b(i had|i ate|for (?:breakfast|lunch|dinner|snack)|calories?|cal\b)\b", lowered)
        or re.search(r"\b\d+\s*cal", lowered)
    )


def _extract_infer_text(raw: str) -> str:
    raw = raw.strip()
    if not raw:
        return ""
    candidates: list[str] = []
    if raw.startswith("{"):
        candidates.append(raw)
    else:
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
    env = {**os.environ, "FOOD_CLI_INTERNAL": "1", "DIARY_LLM_INTERNAL": "1"}
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


def parse_with_llm(text: str) -> list[dict]:
    prompt = f"""Extract food log entries from this message.
Return ONLY a JSON array of objects: [{{"food": "name", "calories": 123}}]
Rules:
- Split into discrete items. Keep restaurant/brand when given.
- User-provided calorie numbers always win.
- If calories are missing, estimate a reasonable adult portion and round to the nearest 10.
- Food names lowercase.
- If the text is not food to log, return []

Message:
{text}
"""
    raw = infer_text(prompt)
    start = raw.find("[")
    end = raw.rfind("]")
    if start < 0 or end < start:
        raise RuntimeError(f"LLM did not return a JSON array: {raw[:200]}")
    data = json.loads(raw[start : end + 1])
    items = []
    for row in data:
        if not isinstance(row, dict):
            continue
        name = str(row.get("food") or "").strip().lower()
        try:
            calories = int(row.get("calories"))
        except (TypeError, ValueError):
            continue
        if name and calories >= 0:
            items.append({"food": name, "calories": calories})
    return items


def parse_items(text: str) -> list[dict]:
    simple = parse_simple(text)
    if simple:
        return simple
    cleaned = strip_food_prefix(text)
    if not cleaned:
        return []
    return parse_with_llm(cleaned)


def log_items(items: list[dict]) -> dict:
    foodlog = _load_foodlog()
    for item in items:
        foodlog.log_food(item["food"], item["calories"])
        foodlog.update_food_lookup(item["food"], item["calories"])
    status = foodlog.day_status()
    return status


def format_logged(items: list[dict], status: dict) -> str:
    lines = [f"Logged {item['food']} ({item['calories']} cal)" for item in items]
    lines.append(f"Today: {status.get('total_calories', 0)} cal")
    return "\n".join(lines)


def cmd_status() -> dict:
    return _load_foodlog().day_status()


def cmd_handle(text: str, *, force: bool = False) -> dict:
    cleaned = strip_food_prefix(text)
    if not cleaned:
        status = cmd_status()
        return {"ok": True, "action": "status", "status": status, "message": json.dumps(status, indent=2)}
    if NOT_FOOD.match(cleaned) and not force:
        clear_pending()
        return {"ok": True, "action": "skip", "message": None}
    if not force and not looks_like_food(text) and not pending_is_today():
        return {"ok": True, "action": "not_food", "message": None}
    try:
        items = parse_items(text)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "action": "error", "message": f"Could not parse food: {exc}"}
    if not items:
        if force:
            return {
                "ok": False,
                "action": "empty",
                "message": "I couldn't turn that into a food log. Try `tacos 100` or a short meal list.",
            }
        return {"ok": True, "action": "not_food", "message": None}
    status = log_items(items)
    if status.get("total_calories", 0) >= 1000 or status.get("submitted"):
        clear_pending()
    return {
        "ok": True,
        "action": "logged",
        "items": items,
        "status": status,
        "message": format_logged(items, status),
    }


def cmd_tick(*, send: bool = True) -> dict:
    foodlog = _load_foodlog()
    status = foodlog.day_status()
    if status.get("total_calories", 0) >= 1000 or status.get("submitted"):
        return {"ok": True, "action": "skip", "message": None}
    set_pending()
    total = status.get("total_calories", 0)
    prompt = f"""Write a short Telegram nudge asking Tyler to log today's food.
Facts: today has {status.get('entry_count', 0)} entries totaling {total} calories.
Rules: one or two sentences, gentle, fresh wording (never a canned phrase), no lecture.
Invite a reply with what he ate; he should not need /food.
If some calories are already logged, mention the current total in passing.
Return only the message text."""
    try:
        message = infer_text(prompt).strip()
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "action": "error", "message": None, "error": str(exc)}
    message = message.strip().strip('"')
    if not message or message.upper() == "NO_REPLY":
        return {"ok": True, "action": "skip", "message": None}
    if send:
        from cabinet import telegram as cabinet_telegram

        if not cabinet_telegram(message, is_quiet=True):
            return {"ok": False, "action": "error", "message": None, "error": "telegram send failed"}
        return {"ok": True, "action": "reminded", "message": None, "sent": message}
    return {"ok": True, "action": "reminded", "message": message, "sent": message}


def _emit(payload: dict, *, as_json: bool) -> int:
    if as_json:
        print(json.dumps(payload, ensure_ascii=False))
    elif payload.get("message"):
        print(payload["message"])
    else:
        print("NO_REPLY")
    return 0 if payload.get("ok", True) else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="food-cli")
    parser.add_argument("--json", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    handle = sub.add_parser("handle")
    handle.add_argument("text", nargs="?", default="")
    handle.add_argument("--force", action="store_true")
    tick = sub.add_parser("tick")
    tick.add_argument("--no-send", action="store_true")
    args = parser.parse_args(argv)

    if args.command == "status":
        payload = {"ok": True, "action": "status", "status": cmd_status()}
        if args.json:
            print(json.dumps(payload, ensure_ascii=False))
        else:
            print(json.dumps(payload["status"], indent=2))
        return 0
    if args.command == "handle":
        text = args.text
        if not text and not sys.stdin.isatty():
            text = sys.stdin.read()
        return _emit(cmd_handle(text, force=args.force), as_json=args.json)
    if args.command == "tick":
        payload = cmd_tick(send=not args.no_send)
        return _emit(payload, as_json=args.json)
    parser.error(f"unknown command {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
