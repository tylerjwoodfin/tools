"""Retrieve previous diary entries for prompt personalization."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


ENTRY_SPLIT = re.compile(r"(?=^## \d{4}-\d{2}-\d{2}\s*$)", re.MULTILINE)


@dataclass
class RetrievedEntry:
    date: str
    title: str
    body: str
    tags: list[str]
    path: Path
    score: float = 0.0

    @property
    def text(self) -> str:
        tags = f"\nTags: {' '.join(self.tags)}" if self.tags else ""
        return f"### {self.title}\n{self.body.strip()}{tags}"


class DiaryHistory(Protocol):
    """Swap-friendly retrieval interface (files now, embeddings later)."""

    def recent(self, limit: int = 5) -> list[RetrievedEntry]:
        ...

    def search(self, query: str, limit: int = 3) -> list[RetrievedEntry]:
        ...


class MarkdownDiaryHistory:
    """Simple filesystem search over diary Markdown files."""

    def __init__(self, diary_dir: Path) -> None:
        self.diary_dir = diary_dir

    def _iter_files(self) -> list[Path]:
        if not self.diary_dir.exists():
            return []
        files = [
            p
            for p in self.diary_dir.rglob("*.md")
            if p.is_file() and "conversations" not in p.parts
        ]
        return sorted(files, key=lambda p: p.stat().st_mtime, reverse=True)

    def _parse_file(self, path: Path) -> list[RetrievedEntry]:
        try:
            content = path.read_text(encoding="utf-8")
        except OSError:
            return []
        chunks = [c.strip() for c in ENTRY_SPLIT.split(content) if c.strip()]
        entries: list[RetrievedEntry] = []
        for chunk in chunks:
            lines = chunk.splitlines()
            if not lines or not lines[0].startswith("## "):
                continue
            date = lines[0][3:].strip()
            title = "Untitled"
            body_lines: list[str] = []
            tags: list[str] = []
            for line in lines[1:]:
                if line.startswith("### ") and title == "Untitled":
                    title = line[4:].strip()
                    continue
                if line.startswith("Tags:"):
                    tags = re.findall(r"#?[\w/-]+", line[5:])
                    tags = [t if t.startswith("#") else f"#{t}" for t in tags]
                    continue
                body_lines.append(line)
            body = "\n".join(body_lines).strip()
            if body or title != "Untitled":
                entries.append(
                    RetrievedEntry(
                        date=date,
                        title=title,
                        body=body,
                        tags=tags,
                        path=path,
                    )
                )
        return entries

    def all_entries(self) -> list[RetrievedEntry]:
        entries: list[RetrievedEntry] = []
        for path in self._iter_files():
            entries.extend(self._parse_file(path))
        # Prefer newer dates when present
        entries.sort(key=lambda e: e.date, reverse=True)
        return entries

    def recent(self, limit: int = 5) -> list[RetrievedEntry]:
        return self.all_entries()[: max(0, limit)]

    def search(self, query: str, limit: int = 3) -> list[RetrievedEntry]:
        tokens = [t.lower() for t in re.findall(r"[\w']+", query) if len(t) > 2]
        if not tokens:
            return self.recent(limit)
        scored: list[RetrievedEntry] = []
        for entry in self.all_entries():
            hay = f"{entry.title}\n{entry.body}\n{' '.join(entry.tags)}".lower()
            score = sum(1.0 for t in tokens if t in hay)
            if score > 0:
                scored.append(
                    RetrievedEntry(
                        date=entry.date,
                        title=entry.title,
                        body=entry.body,
                        tags=entry.tags,
                        path=entry.path,
                        score=score,
                    )
                )
        scored.sort(key=lambda e: (e.score, e.date), reverse=True)
        return scored[: max(0, limit)]
