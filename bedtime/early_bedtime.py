#!/usr/bin/env python3
"""Early bedtime when last night's sleep was under 7 hours.

At noon, an iPhone shortcut reads Apple Health and calls ``check``. When the
asleep time from 6pm yesterday through noon is under 7 hours, and today is not
in ``cabinet -g holidays``, this sends a RemindMail named Early Bedtime and
arms 8:30pm. At 8:30pm, ``apply`` blocks the Pi-hole afternoon list (the same
list as the 9:30pm cron) and asks Cherry to remind Tyler to be in bed by 10.

No sleep samples means the watch did not report a night, so the protocol stays
off. A holiday today clears an arm set earlier the same day.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from pathlib import Path

THRESHOLD_HOURS = 7.0
WINDOW_HOURS = 18
BLOCK_MODE = "afternoon"
REMIND_TITLE = "Early Bedtime"
CHERRY_MESSAGE = (
    "Early bedtime tonight. Pi-hole is blocking now. "
    "Start winding down so you can be in bed by 10."
)
DOWNTIME = Path(__file__).resolve().parent.parent / "pihole" / "downtime.py"

ASLEEP_KEYS = {
    "asleep",
    "asleepunspecified",
    "asleepcore",
    "asleepdeep",
    "asleeprem",
    "core",
    "deep",
    "rem",
}


@dataclass(frozen=True)
class Sample:
    """One Apple Health sleep row: value and start/end."""

    value: str
    start: datetime
    end: datetime


@dataclass(frozen=True)
class State:
    """Cabinet ``bedtime`` fields. Empty strings mean unset."""

    early_date: str = ""
    reminded: str = ""
    blocked: str = ""
    cherry: str = ""
    sleep_hours: str = ""


@dataclass(frozen=True)
class CheckPlan:
    """What ``check`` should store, and whether to send RemindMail."""

    outcome: str
    state: State
    send_remind: bool
    hours: float | None


@dataclass(frozen=True)
class ApplyPlan:
    """What ``apply`` should do at 8:30pm."""

    block: bool
    cherry: bool


def kind(value: str) -> str:
    """Map a Health sleep value onto asleep, inbed, awake, or other."""
    key = re.sub(r"[^a-z]", "", value.casefold())
    if key.startswith("awake"):
        return "awake"
    if "inbed" in key:
        return "inbed"
    if key in ASLEEP_KEYS or key.startswith("asleep"):
        return "asleep"
    return "other"


def parse_dt(raw: str, tz) -> datetime | None:
    """Parse an ISO timestamp. Naive values use ``tz``."""
    text = raw.strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=tz)
    return parsed


def parse_samples(text: str, tz) -> list[Sample]:
    """Parse ``value<TAB>start<TAB>end`` lines. Bad lines are skipped."""
    samples: list[Sample] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        parts = stripped.split("\t")
        if len(parts) != 3:
            continue
        start = parse_dt(parts[1], tz)
        end = parse_dt(parts[2], tz)
        if start is None or end is None or end <= start:
            continue
        samples.append(Sample(parts[0].strip(), start, end))
    return samples


def night_window(now: datetime) -> tuple[datetime, datetime]:
    """Yesterday 6pm through today noon, in ``now``'s timezone."""
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    local = now.astimezone(now.tzinfo)
    end = local.replace(hour=12, minute=0, second=0, microsecond=0)
    return end - timedelta(hours=WINDOW_HOURS), end


def _clip(
    start: datetime, end: datetime, window_start: datetime, window_end: datetime
) -> tuple[datetime, datetime] | None:
    clipped_start = max(start, window_start)
    clipped_end = min(end, window_end)
    if clipped_end <= clipped_start:
        return None
    return clipped_start, clipped_end


def _union(intervals: list[tuple[datetime, datetime]]) -> list[tuple[datetime, datetime]]:
    if not intervals:
        return []
    ordered = sorted(intervals)
    merged: list[list[datetime]] = [[ordered[0][0], ordered[0][1]]]
    for start, end in ordered[1:]:
        if start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return [(start, end) for start, end in merged]


def _subtract(
    base: list[tuple[datetime, datetime]], cuts: list[tuple[datetime, datetime]]
) -> list[tuple[datetime, datetime]]:
    remaining: list[tuple[datetime, datetime]] = []
    cut_list = _union(cuts)
    for start, end in _union(base):
        cursor = start
        for cut_start, cut_end in cut_list:
            if cut_end <= cursor:
                continue
            if cut_start >= end:
                break
            if cut_start > cursor:
                remaining.append((cursor, min(cut_start, end)))
            cursor = max(cursor, cut_end)
            if cursor >= end:
                break
        if cursor < end:
            remaining.append((cursor, end))
    return remaining


def _hours(intervals: list[tuple[datetime, datetime]]) -> float:
    seconds = sum((end - start).total_seconds() for start, end in intervals)
    return seconds / 3600


def sleep_hours(samples: list[Sample], now: datetime) -> float | None:
    """Hours asleep in the previous-night window.

    Stage samples are unioned so a second source does not double-count.
    With no stages, time asleep is in-bed minus awake. None means no samples
    landed in the window.
    """
    window_start, window_end = night_window(now)
    asleep: list[tuple[datetime, datetime]] = []
    inbed: list[tuple[datetime, datetime]] = []
    awake: list[tuple[datetime, datetime]] = []
    for sample in samples:
        interval = _clip(sample.start, sample.end, window_start, window_end)
        if interval is None:
            continue
        group = kind(sample.value)
        if group == "asleep":
            asleep.append(interval)
        elif group == "inbed":
            inbed.append(interval)
        elif group == "awake":
            awake.append(interval)
    if asleep:
        return _hours(_union(asleep))
    if inbed:
        return _hours(_subtract(inbed, awake))
    if awake:
        return 0.0
    return None


def plan_check(
    state: State,
    today: str,
    hours: float | None,
    holidays: list[str] | None,
) -> CheckPlan:
    """Decide the noon outcome. ``holidays`` None means the list could not be read."""
    if holidays is None:
        return CheckPlan("holiday-unknown", state, False, hours)
    if today in holidays:
        cleared = state
        if state.early_date == today:
            cleared = replace(state, early_date="", blocked="", cherry="")
        if hours is not None:
            cleared = replace(cleared, sleep_hours=f"{hours:.2f}")
        return CheckPlan("holiday", cleared, False, hours)
    if hours is None:
        return CheckPlan("no-data", state, False, None)

    stored = replace(state, sleep_hours=f"{hours:.2f}")
    if hours < THRESHOLD_HOURS:
        send = state.reminded != today
        armed = replace(stored, early_date=today, reminded=today if send else state.reminded)
        return CheckPlan("early", armed, send, hours)

    disarmed = stored
    if state.early_date == today:
        disarmed = replace(stored, early_date="", blocked="", cherry="")
    return CheckPlan("normal", disarmed, False, hours)


def state_before_remind(previous: State, plan: CheckPlan) -> State:
    """State to store before the email attempt, so a failed send can retry."""
    if plan.send_remind:
        return replace(plan.state, reminded=previous.reminded)
    return plan.state


def plan_apply(state: State, today: str, holidays: list[str] | None) -> ApplyPlan:
    """8:30pm actions. Unknown or matching holidays do nothing."""
    if holidays is None or today in holidays or state.early_date != today:
        return ApplyPlan(False, False)
    return ApplyPlan(state.blocked != today, state.cherry != today)


def status_label(state: State, today: str, holidays: list[str] | None) -> str:
    """``early`` only when today is armed and is not a holiday."""
    if holidays is None or today in holidays:
        return "normal"
    if state.early_date == today:
        return "early"
    return "normal"


def remind_notes(hours: float) -> str:
    """Body of the noon Early Bedtime email."""
    shown = f"{hours:.1f}"
    return (
        f"You slept {shown} hours last night, under 7.<br>"
        "Pi-hole blocks at 8:30pm instead of 9:30pm.<br>"
        "Cherry will remind you at 8:30pm to prepare for a 10pm bedtime."
    )


def run_apply(state: State, today: str, holidays: list[str] | None, block, cherry):
    """Run the 8:30pm side effects.

    Returns ``(state, label)``. ``label`` is ``skip``, ``applied``, or
    ``cherry-failed``. A Pi-hole error is raised before Cherry is messaged.
    """
    plan = plan_apply(state, today, holidays)
    current = state
    if plan.block:
        block()
        current = replace(current, blocked=today)
    if plan.cherry:
        try:
            cherry()
        except Exception:
            return current, "cherry-failed"
        current = replace(current, cherry=today)
    if plan.block or plan.cherry:
        return current, "applied"
    return current, "skip"


def _text_field(raw: dict, key: str) -> str:
    value = raw.get(key)
    if value is None:
        return ""
    return str(value)


def load_state(cab) -> State:
    """Read ``bedtime`` from Cabinet. A missing object is an empty state."""
    raw = cab.get("bedtime") or {}
    if not isinstance(raw, dict):
        raw = {}
    return State(
        early_date=_text_field(raw, "early_date"),
        reminded=_text_field(raw, "reminded"),
        blocked=_text_field(raw, "blocked"),
        cherry=_text_field(raw, "cherry"),
        sleep_hours=_text_field(raw, "sleep_hours"),
    )


def save_state(cab, state: State) -> None:
    """Write each bedtime field. Dates stay strings."""
    for key in ("early_date", "reminded", "blocked", "cherry", "sleep_hours"):
        cab.put("bedtime", key, value=getattr(state, key))


def load_holidays(cab) -> list[str] | None:
    """Return holiday dates, or None when Cabinet does not return a list."""
    try:
        holidays = cab.get("holidays")
    except Exception:
        return None
    if not isinstance(holidays, list):
        return None
    return [str(item) for item in holidays]


def send_early_bedtime_reminder(hours: float) -> None:
    """Send the Early Bedtime email now, through RemindMail."""
    notes = remind_notes(hours)
    remind = shutil.which("remind")
    if remind:
        command = [
            remind,
            "--save",
            "--when",
            "now",
            "--title",
            REMIND_TITLE,
            "--notes",
            notes,
        ]
    else:
        command = [
            "pipx",
            "run",
            "--spec",
            "remindmail",
            "python",
            "-m",
            "remind.__main__",
            "--save",
            "--when",
            "now",
            "--title",
            REMIND_TITLE,
            "--notes",
            notes,
        ]
    subprocess.run(command, check=True)


def send_cherry() -> None:
    """Send the 8:30pm Telegram nudge on Cherry's chat."""
    from cabinet import telegram

    if not telegram(CHERRY_MESSAGE, is_quiet=True):
        raise RuntimeError("Cherry reminder failed")


def block_pihole() -> None:
    """Block the 9:30pm distraction list. Today's holiday was already checked."""
    subprocess.run(
        [sys.executable, str(DOWNTIME), "block", BLOCK_MODE, "--force"],
        check=True,
    )


def _cabinet():
    from cabinet import Cabinet

    return Cabinet()


def _today() -> str:
    return datetime.now().astimezone().date().isoformat()


def _now() -> datetime:
    return datetime.now().astimezone()


def parse_hours_arg(raw: str) -> float:
    """Parse a manual hour count. Values outside 0–24 are rejected."""
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError("hours must be a number") from exc
    if value < 0 or value > 24:
        raise ValueError("hours must be between 0 and 24")
    return value


def hours_from_text(text: str, now: datetime) -> float | None:
    """Sleep hours for sample lines, using ``now`` as the noon reference."""
    return sleep_hours(parse_samples(text, now.tzinfo), now)


def cmd_check(hours: float | None, dry_run: bool) -> int:
    """Arm early bedtime, or clear it when the night was long enough."""
    cab = _cabinet()
    holidays = load_holidays(cab)
    previous = load_state(cab)
    today = _today()
    plan = plan_check(previous, today, hours, holidays)
    shown = "-" if plan.hours is None else f"{plan.hours:.2f}"
    print(f"{plan.outcome} {shown}")
    if dry_run:
        return 0
    save_state(cab, state_before_remind(previous, plan))
    if plan.send_remind:
        if plan.hours is None:
            print("reminder skipped: no sleep hours", file=sys.stderr)
            return 1
        try:
            send_early_bedtime_reminder(plan.hours)
        except (OSError, subprocess.CalledProcessError) as exc:
            print(f"reminder failed: {exc}", file=sys.stderr)
            return 1
        save_state(cab, plan.state)
    return 0


def cmd_apply(dry_run: bool) -> int:
    """Block Pi-hole and message Cherry when today is armed."""
    cab = _cabinet()
    holidays = load_holidays(cab)
    previous = load_state(cab)
    today = _today()
    plan = plan_apply(previous, today, holidays)
    if dry_run:
        print("block" if plan.block else "no-block")
        print("cherry" if plan.cherry else "no-cherry")
        return 0

    def save_block() -> None:
        nonlocal previous
        previous = replace(previous, blocked=today)
        save_state(cab, previous)

    if plan.block:
        try:
            block_pihole()
        except (OSError, subprocess.CalledProcessError) as exc:
            print(f"pihole failed: {exc}", file=sys.stderr)
            return 1
        save_block()
    if plan.cherry:
        try:
            send_cherry()
        except Exception as exc:  # cabinet/telegram failures are not one type
            print(f"cherry failed: {exc}", file=sys.stderr)
            return 1
        previous = replace(previous, cherry=today)
        save_state(cab, previous)
    print("applied" if plan.block or plan.cherry else "skip")
    return 0


def cmd_status() -> int:
    """Print ``early`` or ``normal`` for the Do Not Disturb shortcut."""
    cab = _cabinet()
    print(status_label(load_state(cab), _today(), load_holidays(cab)))
    return 0


def main(argv: list[str] | None = None) -> int:
    """CLI entry. ``check`` reads sample lines on stdin unless ``--hours`` is set."""
    parser = argparse.ArgumentParser(description="Early bedtime protocol")
    sub = parser.add_subparsers(dest="command", required=True)

    check = sub.add_parser("check", help="Noon decision from sleep samples or --hours")
    check.add_argument("--hours", help="Skip samples and use this asleep total")
    check.add_argument("--dry-run", action="store_true")

    apply_cmd = sub.add_parser("apply", help="8:30pm Pi-hole block and Cherry reminder")
    apply_cmd.add_argument("--dry-run", action="store_true")

    sub.add_parser("status", help="Print early or normal")

    args = parser.parse_args(argv)
    if args.command == "status":
        return cmd_status()
    if args.command == "apply":
        return cmd_apply(args.dry_run)

    hours: float | None
    if args.hours is not None:
        try:
            hours = parse_hours_arg(args.hours)
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 2
    elif sys.stdin.isatty():
        print("Pass --hours or sample lines on stdin.", file=sys.stderr)
        return 2
    else:
        hours = hours_from_text(sys.stdin.read(), _now())
    return cmd_check(hours, args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
