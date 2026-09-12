"""CLI entrypoint for diary-llm."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .config import load_config
from .llm import StubLLM, build_llm
from .telegram import TelegramSender
from .workflow import DiaryWorkflow, result_json


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="diary-llm",
        description="Conversational diary workflow for OpenClaw / Telegram",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Path to config.yaml (default: ~/.config/diary-llm/config.yaml)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable JSON",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Do not send Telegram messages",
    )
    parser.add_argument(
        "--stub-llm",
        action="store_true",
        help="Use deterministic stub LLM (for tests / offline)",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("status", help="Show active diary session status")

    start = sub.add_parser("start", help="Start or continue a manual diary session")
    start.add_argument("--prompt", default=None, help="Optional opening prompt override")
    start.add_argument(
        "--send",
        action="store_true",
        help="Also send the opening prompt via Telegram",
    )

    reply = sub.add_parser("reply", help="Handle a user message in an active diary session")
    reply.add_argument("text", nargs="?", default=None, help="User message text")
    reply.add_argument(
        "--text-file",
        type=Path,
        default=None,
        help="Read user message from a file",
    )

    sub.add_parser("done", help="Explicitly finish the active diary session")

    tick = sub.add_parser(
        "tick",
        help="Finalize inactive sessions and maybe send a proactive prompt",
    )
    tick.add_argument(
        "--no-send",
        action="store_true",
        help="Do not deliver Telegram messages",
    )
    tick.add_argument(
        "--force-proactive",
        action="store_true",
        help="Ignore cadence/hours gates for proactive prompt",
    )

    proactive = sub.add_parser("proactive", help="Attempt a proactive diary prompt")
    proactive.add_argument("--force", action="store_true")
    proactive.add_argument("--no-send", action="store_true")

    handle = sub.add_parser(
        "handle",
        help="Route an inbound Telegram text (slash commands + active session)",
    )
    handle.add_argument("text", nargs="?", default=None)
    handle.add_argument("--text-file", type=Path, default=None)

    return parser


def _read_text_arg(text: str | None, text_file: Path | None) -> str:
    if text_file is not None:
        return text_file.read_text(encoding="utf-8")
    if text is None:
        if not sys.stdin.isatty():
            return sys.stdin.read()
        raise SystemExit("Message text required")
    return text


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    cfg = load_config(args.config)

    llm = StubLLM() if args.stub_llm else build_llm(cfg.llm)
    sender = TelegramSender(dry_run=args.dry_run)
    wf = DiaryWorkflow(cfg, llm=llm, sender=sender)

    if args.command == "status":
        payload = wf.status()
        print(json.dumps(payload, indent=2) if args.json else _format_status(payload))
        return 0

    if args.command == "start":
        result = wf.start_manual(prompt_text=args.prompt)
        if args.send and result.ok and result.message and result.action == "started":
            sender.send(result.message)
        _emit(result, as_json=args.json)
        return 0 if result.ok else 1

    if args.command == "reply":
        text = _read_text_arg(args.text, args.text_file)
        result = wf.handle_user_message(text)
        _emit(result, as_json=args.json)
        return 0 if result.ok else 1

    if args.command == "done":
        result = wf.finish(reason="explicit")
        _emit(result, as_json=args.json)
        return 0 if result.ok else 1

    if args.command == "tick":
        if args.force_proactive:
            timed = wf.finalize_if_inactive(send=not args.no_send)
            results = [timed] if timed else []
            results.append(wf.start_proactive(force=True, send=not args.no_send))
        else:
            results = wf.tick(send=not args.no_send)
        results = [r for r in results if r is not None]

        if args.json:
            print(result_json(results))
            return 0 if all(r.ok for r in results) else 1

        # Cron jobs often use --announce. Skip/status chatter must stay silent.
        # When tick itself already delivered via Telegram, also stay silent to
        # avoid duplicate messages.
        announceable = [
            r
            for r in results
            if r.action in {"started", "finalized"} and (r.message or "").strip()
        ]
        if args.no_send and announceable:
            for r in announceable:
                _emit(r, as_json=False)
        else:
            print("NO_REPLY")
        return 0 if all(r.ok for r in results) else 1

    if args.command == "proactive":
        result = wf.start_proactive(force=args.force, send=not args.no_send)
        if args.json:
            _emit(result, as_json=True)
        elif result.action == "skip":
            # Keep cron/announce quiet when nothing should be sent.
            print("NO_REPLY")
        elif args.no_send:
            # Caller (e.g. announce) will deliver stdout.
            _emit(result, as_json=False)
        else:
            # Already delivered via TelegramSender.
            print("NO_REPLY")
        return 0 if result.ok else 1

    if args.command == "handle":
        text = _read_text_arg(args.text, args.text_file)
        result = wf.handle_user_message(text)
        _emit(result, as_json=args.json)
        # not_diary is a soft miss for the OpenClaw plugin
        if result.action == "not_diary":
            return 2
        return 0 if result.ok else 1

    parser.error(f"Unknown command: {args.command}")
    return 2


def _format_status(payload: dict) -> str:
    if not payload.get("active"):
        return "No active diary session."
    return (
        f"Active diary session {payload['session_id']}\n"
        f"  origin: {payload.get('origin')}\n"
        f"  started: {payload.get('started_at')}\n"
        f"  last interaction: {payload.get('last_interaction_at')}\n"
        f"  messages: {payload.get('message_count')}\n"
        f"  prompt: {payload.get('initial_prompt')}"
    )


def _emit(result, *, as_json: bool) -> None:
    if as_json:
        print(result_json(result))
        return
    if result.message:
        print(result.message)
    elif result.details:
        print(json.dumps(result.details, ensure_ascii=False))


if __name__ == "__main__":
    raise SystemExit(main())
