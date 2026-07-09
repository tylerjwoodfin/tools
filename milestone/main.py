#!/usr/bin/env python3
"""
Append a milestone to my personal 
milestones.md file for the current year and month.
"""

import os
import sys
from datetime import datetime
from pathlib import Path

MONTHS = [
    "january",
    "february",
    "march",
    "april",
    "may",
    "june",
    "july",
    "august",
    "september",
    "october",
    "november",
    "december",
]


def milestones_path() -> Path:
    notes = os.environ.get("notes")
    if notes:
        return Path(notes) / "milestones.md"
    return Path.home() / "syncthing/md/notes/milestones.md"


def year_bounds(lines: list[str], year: int) -> tuple[int, int] | None:
    header = f"# {year}"
    start = next((i for i, line in enumerate(lines) if line.strip() == header), None)
    if start is None:
        return None

    end = len(lines)
    for i in range(start + 1, len(lines)):
        line = lines[i]
        if line.startswith("# ") and not line.startswith("## "):
            end = i
            break
    return start, end


def month_bounds(
    lines: list[str], year_start: int, year_end: int, month: str
) -> tuple[int, int] | None:
    header = f"## {month}"
    start = next(
        (i for i in range(year_start + 1, year_end) if lines[i].strip() == header),
        None,
    )
    if start is None:
        return None

    end = year_end
    for i in range(start + 1, year_end):
        line = lines[i]
        if line.startswith("## ") or (
            line.startswith("# ") and not line.startswith("## ")
        ):
            end = i
            break
    return start, end


def insert_point_for_month(
    lines: list[str], year_start: int, year_end: int, month: str
) -> int:
    month_idx = MONTHS.index(month)
    for i in range(year_start + 1, year_end):
        if not lines[i].startswith("## "):
            continue
        name = lines[i].strip()[3:].lower()
        if name in MONTHS and MONTHS.index(name) > month_idx:
            return i
    return year_end


def add_milestone(text: str, path: Path) -> None:
    now = datetime.now()
    year = now.year
    month = MONTHS[now.month - 1]
    entry = f"- {text}"

    lines = path.read_text(encoding="utf-8").splitlines()
    bounds = year_bounds(lines, year)

    if bounds is None:
        if lines and lines[-1] != "":
            lines.append("")
        lines.extend([f"# {year}", f"## {month}", entry])
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"Added to {year} / {month}: {text}")
        return

    year_start, year_end = bounds
    mbounds = month_bounds(lines, year_start, year_end, month)

    if mbounds is None:
        at = insert_point_for_month(lines, year_start, year_end, month)
        block = [f"## {month}", entry]
        if at > 0 and lines[at - 1] != "":
            block.insert(0, "")
        lines[at:at] = block
    else:
        _, month_end = mbounds
        lines.insert(month_end, entry)

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Added to {year} / {month}: {text}")


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: milestone <description>", file=sys.stderr)
        sys.exit(1)

    path = milestones_path()
    if not path.is_file():
        print(f"Error: milestones file not found: {path}", file=sys.stderr)
        sys.exit(1)

    add_milestone(" ".join(sys.argv[1:]), path)


if __name__ == "__main__":
    main()
