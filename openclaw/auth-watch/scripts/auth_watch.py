#!/usr/bin/env python3
"""Tell Cherry when OpenAI subscription auth is unusable.

Food reminders, word quizzes, and the cloud fallback all use that login.
This check sends the repair steps once per outage, then stays quiet until
the sign-in works again.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

OPENCLAW_BIN = Path.home() / "git/tools/openclaw/openclaw-gateway"
STATE_PATH = Path.home() / ".local/share/openclaw-auth/openai-alert"

REPAIR_MESSAGE = """\
OpenAI sign-in for Cherry is not usable. Food reminders, word quizzes, and the cloud fallback will fail until you sign in again.

In a terminal:

~/git/tools/openclaw/openclaw-gateway models auth login --provider openai --force

Leave off --set-default so Cherry stays on the local Gemma model.

Then confirm:

~/git/tools/openclaw/openclaw-gateway models status --plain
~/git/tools/openclaw/openclaw-gateway infer model run --local --json --thinking off --model openai/gpt-5.6-sol --prompt "Reply with exactly: hi"

Status should no longer list OpenAI under missing auth. The infer command should return hi.
"""


def openai_auth_problem(status: dict) -> str | None:
    """Return a short reason when OpenAI auth cannot serve Cherry, else None."""
    auth = status.get("auth") if isinstance(status, dict) else None
    if not isinstance(auth, dict):
        return None

    profiles = [
        profile
        for profile in ((auth.get("oauth") or {}).get("profiles") or [])
        if isinstance(profile, dict) and profile.get("provider") == "openai"
    ]
    usable = [profile for profile in profiles if profile.get("status") == "ok"]
    route_notes = _openai_route_notes(auth)
    missing = "openai" in (auth.get("missingProvidersInUse") or [])

    if usable and not route_notes and not missing:
        return None

    notes: list[str] = []
    for profile in profiles:
        if profile.get("status") == "ok":
            continue
        label = profile.get("label") or profile.get("profileId") or "openai"
        notes.append(f"{label} is {profile.get('status') or 'unusable'}")
    notes.extend(route_notes)
    if missing and not any("missing" in note.lower() for note in notes):
        notes.append("OpenAI is missing usable auth")
    if not notes and not usable:
        notes.append("OpenAI subscription auth is missing")
    if usable and not notes:
        return None
    # A healthy profile plus a route block still needs the same repair.
    if not notes:
        return None
    return "; ".join(dict.fromkeys(notes))


def _openai_route_notes(auth: dict) -> list[str]:
    notes: list[str] = []
    for issue in auth.get("modelRouteIssues") or []:
        if not isinstance(issue, dict) or issue.get("provider") != "openai":
            continue
        message = str(issue.get("message") or issue.get("kind") or "openai route blocked")
        notes.append(message)
    return notes


def load_model_status(binary: Path | None = None) -> dict:
    program = str(binary if binary and binary.exists() else OPENCLAW_BIN)
    if program == str(OPENCLAW_BIN) and not OPENCLAW_BIN.exists():
        program = "openclaw"
    proc = subprocess.run(
        [program, "models", "status", "--json"],
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )
    if proc.returncode != 0:
        detail = proc.stderr.strip() or proc.stdout.strip() or "models status failed"
        raise RuntimeError(detail)
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("models status did not return JSON") from exc
    if not isinstance(data, dict):
        raise RuntimeError("models status JSON was not an object")
    return data


def alert_open(path: Path) -> bool:
    return path.is_file()


def mark_alert(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("open\n", encoding="utf-8")


def clear_alert(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        pass


def cmd_tick(
    *,
    send: bool = True,
    status: dict | None = None,
    state_path: Path = STATE_PATH,
    send_fn=None,
) -> dict:
    if status is None:
        status = load_model_status()
    problem = openai_auth_problem(status)
    open_already = alert_open(state_path)
    if problem is None:
        if open_already:
            clear_alert(state_path)
            return {"ok": True, "action": "cleared", "message": None}
        return {"ok": True, "action": "ok", "message": None}
    if open_already:
        return {"ok": True, "action": "quiet", "message": None, "problem": problem}
    if not send:
        return {"ok": True, "action": "would-send", "message": REPAIR_MESSAGE, "problem": problem}
    if send_fn is None:
        from cabinet import telegram as cabinet_telegram

        def send_fn(message: str) -> bool:
            return bool(cabinet_telegram(message, is_quiet=True))
    if not send_fn(REPAIR_MESSAGE):
        return {"ok": False, "action": "error", "message": None, "error": "telegram send failed"}
    mark_alert(state_path)
    return {"ok": True, "action": "sent", "message": None, "problem": problem}


def _emit(payload: dict, *, as_json: bool) -> int:
    if as_json:
        print(json.dumps(payload, ensure_ascii=False))
    elif payload.get("message"):
        print(payload["message"])
    else:
        print("NO_REPLY")
    return 0 if payload.get("ok", True) else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="auth-watch")
    parser.add_argument("--json", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)
    tick = sub.add_parser("tick")
    tick.add_argument("--no-send", action="store_true")
    args = parser.parse_args(argv)
    if args.command == "tick":
        try:
            payload = cmd_tick(send=not args.no_send)
        except (OSError, subprocess.TimeoutExpired, RuntimeError) as exc:
            payload = {"ok": False, "action": "error", "message": None, "error": str(exc)}
        return _emit(payload, as_json=args.json)
    parser.error(f"unknown command {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
