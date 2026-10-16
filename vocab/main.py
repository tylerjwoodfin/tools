#!/usr/bin/env python3
"""Add words to Cherry's vocabulary list.

The list is a JSON array at ~/syncthing/network/vocab.json. Each entry has
name, times_asked, and times_correct. The first run copies words from
~/syncthing/notes/words_to_remember.md and recall counts from the word-recall
state file when that file is present.
"""

from __future__ import annotations

import json
import os
import re
import sys
import tempfile
from pathlib import Path

VOCAB_PATH = Path.home() / "syncthing/network/vocab.json"
NOTES_PATH = Path.home() / "syncthing/notes/words_to_remember.md"
STATE_PATH = Path.home() / ".local/share/word-recall/state.json"

ITEM_RE = re.compile(r"^[-*]\s+\*\*(?P<word>.+?)\*\*")
SECTION_RE = re.compile(r"^##\s+")


def clean_name(raw: str) -> str:
    """Collapse whitespace and trim a word the user typed."""
    return re.sub(r"\s+", " ", raw).strip()


def words_from_notes(text: str) -> list[str]:
    """Return word names under any ## section, skipping the preamble example."""
    in_section = False
    words: list[str] = []
    seen: set[str] = set()
    for line in text.splitlines():
        if SECTION_RE.match(line.strip()):
            in_section = True
            continue
        if not in_section:
            continue
        match = ITEM_RE.match(line.strip())
        if not match:
            continue
        word = clean_name(match.group("word"))
        key = word.casefold()
        if not word or key in seen:
            continue
        seen.add(key)
        words.append(word)
    return words


def counters_from_stats(stats: dict | None) -> tuple[int, int]:
    """Map word-recall state onto times_asked and times_correct.

    The recall file stores a correct streak, not a full ask count. A recorded
    miss adds one ask beyond that streak. A word that was asked and never
    marked correct counts as one ask.
    """
    if not isinstance(stats, dict):
        return 0, 0
    try:
        times_correct = int(stats.get("correct") or 0)
    except (TypeError, ValueError):
        times_correct = 0
    if times_correct < 0:
        times_correct = 0
    times_asked = times_correct
    if stats.get("last_result") == "wrong":
        times_asked += 1
    elif stats.get("last_asked") and times_asked == 0:
        times_asked = 1
    return times_asked, times_correct


def load_state(path: Path) -> dict:
    """Return the word-recall state map, or an empty map when it is missing."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    words = data.get("words") if isinstance(data, dict) else None
    return words if isinstance(words, dict) else {}


def entries_from_notes(notes_path: Path, state_path: Path) -> list[dict]:
    """Build vocab entries from the existing markdown list and recall state."""
    try:
        text = notes_path.read_text(encoding="utf-8")
    except OSError:
        return []
    state = load_state(state_path)
    entries = []
    for name in words_from_notes(text):
        times_asked, times_correct = counters_from_stats(state.get(name.casefold()))
        entries.append(
            {
                "name": name,
                "times_asked": times_asked,
                "times_correct": times_correct,
            }
        )
    return entries


def load_vocab(path: Path) -> list[dict]:
    """Read the vocab array. A missing file is an empty list."""
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path} is not valid JSON") from exc
    if not isinstance(data, list):
        raise ValueError(f"{path} must be a JSON array")
    entries: list[dict] = []
    for item in data:
        if not isinstance(item, dict) or not str(item.get("name") or "").strip():
            raise ValueError(f"{path} has an entry without a name")
        try:
            times_asked = int(item.get("times_asked") or 0)
            times_correct = int(item.get("times_correct") or 0)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{path} has a non-numeric count") from exc
        entries.append(
            {
                "name": clean_name(str(item["name"])),
                "times_asked": times_asked,
                "times_correct": times_correct,
            }
        )
    return entries


def save_vocab(path: Path, entries: list[dict]) -> None:
    """Write the vocab array atomically."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(entries, indent=2, ensure_ascii=False) + "\n"
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(payload)
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def ensure_vocab(path: Path, notes_path: Path, state_path: Path) -> int | None:
    """Create the vocab file from the existing list when it does not exist.

    Returns the number of migrated words, or None when the file was already there.
    """
    if path.exists():
        return None
    entries = entries_from_notes(notes_path, state_path)
    save_vocab(path, entries)
    return len(entries)


def add_word(entries: list[dict], name: str) -> bool:
    """Append a word with zero counts. Return False when it is already listed."""
    key = name.casefold()
    if any(str(entry["name"]).casefold() == key for entry in entries):
        return False
    entries.append({"name": name, "times_asked": 0, "times_correct": 0})
    return True


def main(
    argv: list[str] | None = None,
    *,
    vocab_path: Path | None = None,
    notes_path: Path | None = None,
    state_path: Path | None = None,
) -> int:
    """Add one word, creating the list from the old notes file on first use."""
    args = list(sys.argv[1:] if argv is None else argv)
    path = vocab_path or VOCAB_PATH
    notes = notes_path or NOTES_PATH
    state = state_path or STATE_PATH
    try:
        migrated = ensure_vocab(path, notes, state)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if migrated is not None:
        print(f"Migrated {migrated} words to {path}")

    name = clean_name(" ".join(args))
    if not name:
        print("Usage: vocab <word>", file=sys.stderr)
        return 1

    try:
        entries = load_vocab(path)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if not add_word(entries, name):
        print(f"{name} is already on the list.")
        return 0
    save_vocab(path, entries)
    print(f"Added {name}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
