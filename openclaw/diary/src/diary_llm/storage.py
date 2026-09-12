"""Markdown diary entry storage."""

from __future__ import annotations

from pathlib import Path

from .atomic import atomic_write_text
from .models import DiaryEntry


def day_file_path(diary_dir: Path, date: str) -> Path:
    year, month, _day = date.split("-")
    return diary_dir / year / month / f"{date}.md"


def append_entry(diary_dir: Path, entry: DiaryEntry) -> Path:
    """Append an entry to the day's Markdown file (create if needed)."""
    path = day_file_path(diary_dir, entry.date)
    path.parent.mkdir(parents=True, exist_ok=True)
    block = entry.to_markdown().rstrip() + "\n"
    if path.exists():
        existing = path.read_text(encoding="utf-8").rstrip()
        if existing:
            content = existing + "\n\n" + block
        else:
            content = block
    else:
        content = block
    atomic_write_text(path, content if content.endswith("\n") else content + "\n")
    return path
