#!/usr/bin/env python3
"""Email when the SFPL DIY Digital Archive Lab has an open appointment.

Cron runs this every 3 hours. It reads the LibCal widget endpoints behind
https://sfpl.libcal.com/appointments/diydigilab, emails one message listing any
timeslots not emailed before, and records their ISO start times in Cabinet
``sfpl_digilab.sent``. Each run first drops recorded starts more than 48 hours
in the past, so the list stays short.
"""

from __future__ import annotations

import html
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import requests

BASE_URL = "https://sfpl.libcal.com"
PAGE_URL = f"{BASE_URL}/appointments/diydigilab"
WIDGET = f"{BASE_URL}/widget/appointments"
IID = 6098
LID = 8464
TIMEZONE = "America/Los_Angeles"
TZ = ZoneInfo(TIMEZONE)
KEEP_PAST = timedelta(hours=48)
CABINET_KEY = ("sfpl_digilab", "sent")
HEADERS = {"User-Agent": "Mozilla/5.0 (sfpl-digilab-check)"}


@dataclass(frozen=True)
class Slot:
    """One open timeslot."""

    begins: datetime
    ends: datetime | None

    @property
    def key(self) -> str:
        """The ISO start time stored in Cabinet."""
        return self.begins.isoformat()


def parse_time(value: str) -> datetime:
    """Parse a LibCal time (ISO or ``YYYY-MM-DD HH:MM:SS``) as Pacific when naive."""
    parsed = datetime.fromisoformat(value.strip().replace(" ", "T", 1))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=TZ)


def get_json(path: str, **params: object) -> dict:
    """GET a LibCal widget endpoint and return its JSON."""
    response = requests.get(
        f"{WIDGET}/{path}",
        params={"iid": IID, "lid": LID, **params},
        headers=HEADERS,
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()
    if isinstance(data, dict) and data.get("success") is False:
        raise RuntimeError(f"LibCal {path} refused the request: {data.get('error')}")
    return data


def find_service() -> tuple[int, int]:
    """Return (gid, cid) for the DIY Digi Lab service from the staff widget."""
    page = get_json("staff", uid=0, gid=0, cid=0).get("html", "")
    gid = re.search(r'data-gid="(\d+)"', page)
    cid = re.search(r'class="form-control-static groupcat_filtering"[^>]*data-value="(\d+)"', page)
    if not gid or not cid:
        raise RuntimeError("Could not find the DIY Digi Lab service on the LibCal page")
    return int(gid.group(1)), int(cid.group(1))


def parse_slots(times: list[dict] | None) -> list[Slot]:
    """Turn LibCal ``times`` rows into slots."""
    slots = []
    for row in times or []:
        start = str(row.get("start") or "")
        if not start:
            continue
        ends = row.get("endDisplay") or row.get("end")
        slots.append(
            Slot(
                begins=parse_time(str(row.get("startDisplay") or start)),
                ends=parse_time(str(ends)) if ends else None,
            )
        )
    return slots


def fetch_slots() -> list[Slot]:
    """Every open timeslot across every available date."""
    gid, cid = find_service()
    common = {"uid": 0, "gid": gid, "cid": cid, "timezone": TIMEZONE}
    dates = get_json("datetime", **common).get("dates") or []
    slots: list[Slot] = []
    for day in dates:
        slots.extend(parse_slots(get_json("times", date=day, **common).get("times")))
    return sorted(slots, key=lambda slot: slot.begins)


def prune(sent: list[str], now: datetime) -> list[str]:
    """Drop recorded starts more than 48 hours before ``now``, and any that do not parse."""
    kept = []
    for start in sent:
        try:
            if parse_time(start) >= now - KEEP_PAST:
                kept.append(start)
        except ValueError:
            continue
    return kept


def describe(slot: Slot) -> str:
    """``Tue, Dec 2 · 10:00 AM – 1:00 PM``."""
    text = slot.begins.strftime("%a, %b %-d · %-I:%M %p")
    if slot.ends:
        text += slot.ends.strftime(" – %-I:%M %p")
    return text


def email_body(slots: list[Slot]) -> str:
    """HTML list of new slots with a booking link."""
    items = "".join(f"<li>{html.escape(describe(slot))}</li>" for slot in slots)
    return f"<ul>{items}</ul><p><a href='{PAGE_URL}'>Book at SFPL</a></p>"


def main() -> int:
    """Check LibCal, email new slots, and record them."""
    from cabinet import Cabinet, Mail  # pylint: disable=import-outside-toplevel

    cab = Cabinet()
    now = datetime.now(TZ)
    stored = cab.get(*CABINET_KEY) or []
    sent = prune(stored, now)
    if sent != stored:
        cab.put(*CABINET_KEY, value=sent)

    new = [slot for slot in fetch_slots() if slot.key not in sent]
    if not new:
        print("No new DIY Digi Lab appointments")
        return 0

    count = len(new)
    subject = f"SFPL DIY Digi Lab: {count} new appointment{'s' if count != 1 else ''}"
    if not Mail().send(subject, email_body(new)):
        print("Email failed; will retry these slots next run", file=sys.stderr)
        return 1

    cab.put(*CABINET_KEY, value=sent + [slot.key for slot in new])
    print(f"Emailed {count} new DIY Digi Lab appointment(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
