#!/usr/bin/env python3
"""
Download every track in `spotify songs.json` into ~/syncthing/music/music_new (TJW-328).

For each catalog row:
  1. Skip blank / placeholder titles or artists
  2. Skip if the planned filename already exists in the dest folder
  3. Optionally copy a unique match from the existing ~/syncthing/music library
  4. Otherwise duration-match a YouTube upload (same rules as replace_unplayable.py)
     and save via music-stack `mp3` with beets disabled so files stay in dest

Spotify-local rows (no URL) fall back to an `mp3` artist+title search.
Resume by re-running: existing dest files are skipped.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from cabinet import Cabinet

from replace_unplayable import (
    extract_track_id,
    is_placeholder,
    process_row,
    resolve_mp3_exec,
    resolve_ytdlp,
    spotify_client_credentials,
)

AUDIO_EXTS = {".mp3", ".flac", ".m4a", ".opus", ".ogg", ".wav"}
DEFAULT_JSON = Path.home() / "syncthing" / "log" / "spotify songs.json"
DEFAULT_DEST = Path.home() / "syncthing" / "music" / "music_new"
DEFAULT_LIBRARY = Path.home() / "syncthing" / "music"
DEFAULT_SLEEP_SEC = 1.0


def _load_clean_track_title():
    path = (
        Path.home()
        / "git"
        / "docker"
        / "music-stack"
        / "scripts"
        / "clean_track_title.py"
    )
    spec = importlib.util.spec_from_file_location("clean_track_title", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.clean_track_title  # type: ignore[attr-defined]


try:
    clean_track_title = _load_clean_track_title()
except Exception:  # noqa: BLE001

    def clean_track_title(name: str) -> str:
        return (name or "").strip()


def fold_alnum(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (value or "").lower())


def sanitize_segment(text: str) -> str:
    """Match music-stack `mp3` sanitize_segment (single path component)."""
    s = text or ""
    for char in '\\/<>":|?*':
        s = s.replace(char, "_")
    s = s.strip()
    return s or "untitled"


def load_songs(path: Path) -> List[Dict[str, Any]]:
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError(f"Expected a JSON array in {path}")
    return [row for row in data if isinstance(row, dict)]


def row_index(row: Dict[str, Any], fallback: int) -> int:
    idx = row.get("index")
    if isinstance(idx, int):
        return idx
    if isinstance(idx, str) and idx.strip().isdigit():
        return int(idx.strip())
    return fallback


def filter_start_at(rows: List[Dict[str, Any]], start_at: int) -> List[Dict[str, Any]]:
    if start_at <= 0:
        return rows
    return [row for i, row in enumerate(rows, start=1) if row_index(row, i) >= start_at]


def title_stem(name: str) -> str:
    cleaned = clean_track_title(name) or (name or "").strip()
    return sanitize_segment(cleaned)


def planned_stem(artist: str, name: str, existing_stems: Set[str]) -> str:
    """Filename stem `mp3` would choose given files already in dest."""
    title = title_stem(name)
    artist_stem = sanitize_segment(artist)
    if fold_alnum(title) in existing_stems:
        return f"{title} ({artist_stem})"
    return title


def first_artist_by_title(jobs: Iterable[Dict[str, Any]]) -> Dict[str, str]:
    """First catalog row for each title owns `Title.ext` in dest (mp3 naming)."""
    mapping: Dict[str, str] = {}
    for job in jobs:
        key = fold_alnum(title_stem(str(job.get("name") or "")))
        if key and key not in mapping:
            mapping[key] = str(job.get("artist") or "")
    return mapping


def dest_already_has(
    existing_stems: Set[str],
    artist: str,
    name: str,
    *,
    first_artist: str = "",
) -> bool:
    title = title_stem(name)
    artist_stem = sanitize_segment(artist)
    if fold_alnum(f"{title} ({artist_stem})") in existing_stems:
        return True
    if fold_alnum(title) not in existing_stems:
        return False
    # Title.ext exists: only the first catalog artist for that title owns it.
    if first_artist and fold_alnum(artist) == fold_alnum(first_artist):
        return True
    return False


def index_audio_stems(folder: Path, *, exclude: Optional[Path] = None) -> Set[str]:
    stems: Set[str] = set()
    if not folder.is_dir():
        return stems
    for path in folder.iterdir():
        if exclude is not None and path.resolve() == exclude.resolve():
            continue
        if not path.is_file():
            continue
        if path.suffix.lower() not in AUDIO_EXTS:
            continue
        folded = fold_alnum(path.stem)
        if folded:
            stems.add(folded)
    return stems


def index_library_files(
    library: Path, dest: Path
) -> Dict[str, List[Path]]:
    """Map folded filename stems to files in the existing library (max depth 1)."""
    by_stem: Dict[str, List[Path]] = {}
    if not library.is_dir():
        return by_stem
    dest_resolved = dest.resolve() if dest.exists() else dest
    skip_names = {".library-staging", dest.name, "Excluded from Main Library"}
    for path in library.iterdir():
        if path.name in skip_names or path.name.startswith("."):
            continue
        try:
            if dest.exists() and path.resolve() == dest_resolved:
                continue
        except OSError:
            continue
        if not path.is_file() or path.suffix.lower() not in AUDIO_EXTS:
            continue
        folded = fold_alnum(path.stem)
        if not folded:
            continue
        by_stem.setdefault(folded, []).append(path)
    return by_stem


def find_library_copy(
    by_stem: Dict[str, List[Path]],
    artist: str,
    name: str,
    *,
    first_artist: str = "",
) -> Optional[Path]:
    """Return a unique existing-library file for this title, if one is safe to copy."""
    title = fold_alnum(title_stem(name))
    artist_f = fold_alnum(artist)
    if not title:
        return None

    titled = by_stem.get(title) or []
    with_artist = by_stem.get(fold_alnum(f"{title_stem(name)} ({artist})")) or []
    if len(with_artist) == 1:
        return with_artist[0]
    if len(titled) == 1:
        only = titled[0]
        stem_f = fold_alnum(only.stem)
        if artist_f and artist_f in stem_f:
            return only
        # Unique Title.mp3 belongs to the first catalog artist for that title.
        if first_artist and fold_alnum(artist) == fold_alnum(first_artist):
            return only
        return None
    if len(titled) > 1 and artist_f:
        artist_hits = [p for p in titled if artist_f in fold_alnum(p.stem)]
        if len(artist_hits) == 1:
            return artist_hits[0]
    return None


def copy_to_dest(
    src: Path,
    dest: Path,
    artist: str,
    name: str,
    existing_stems: Set[str],
    dry_run: bool,
) -> Path:
    stem = planned_stem(artist, name, existing_stems)
    target = dest / f"{stem}{src.suffix.lower()}"
    if dry_run:
        print(f"  DRY-RUN: copy {src} -> {target}", file=sys.stderr)
        return target
    dest.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, target)
    print(f"  Copied {src.name} -> {target.name}", file=sys.stderr)
    return target


def ensure_dest(dest: Path, hide_from_navidrome: bool) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    if not hide_from_navidrome:
        return
    ndignore = dest / ".ndignore"
    if not ndignore.exists():
        ndignore.write_text("", encoding="utf-8")


def songs_to_jobs(rows: Iterable[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], int, int]:
    jobs: List[Dict[str, Any]] = []
    skipped_artist = 0
    skipped_name = 0
    for row in rows:
        artist = str(row.get("artist") or "").strip()
        name = str(row.get("name") or "").strip()
        if is_placeholder(artist):
            skipped_artist += 1
            continue
        if is_placeholder(name):
            skipped_name += 1
            continue
        jobs.append(
            {
                "name": name,
                "artist": artist,
                "url": str(row.get("spotify_url") or "").strip(),
                "playlists": [],
                "index": row.get("index"),
            }
        )
    return jobs, skipped_artist, skipped_name


def download_by_query(
    mp3_exec: List[str],
    artist: str,
    name: str,
    dry_run: bool,
) -> str:
    env = os.environ.copy()
    env["MP3_STEM_TITLE"] = name
    env["MP3_STEM_ARTIST"] = artist
    cmd = [*mp3_exec]
    if dry_run:
        cmd.append("--dry-run")
    cmd.extend([artist, name])
    if dry_run:
        print(
            "  DRY-RUN: "
            + subprocess.list2cmdline(cmd),
            file=sys.stderr,
        )
        return "ok"
    print(f"  mp3 query {artist!r} {name!r}", file=sys.stderr)
    rc = subprocess.run(cmd, env=env).returncode
    if rc != 0:
        print(f"  FAIL: mp3 exited {rc}", file=sys.stderr)
        return "fail"
    return "ok"


def _set_env(overrides: Dict[str, str]) -> Dict[str, Optional[str]]:
    previous: Dict[str, Optional[str]] = {}
    for key, value in overrides.items():
        previous[key] = os.environ.get(key)
        os.environ[key] = value
    return previous


def _restore_env(previous: Dict[str, Optional[str]]) -> None:
    for key, value in previous.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


def append_log(log_path: Path, record: Dict[str, Any]) -> None:
    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Download every Spotify catalog track into ~/syncthing/music/music_new"
        )
    )
    parser.add_argument(
        "--json",
        type=Path,
        default=DEFAULT_JSON,
        help="Path to spotify songs.json",
    )
    parser.add_argument(
        "--dest",
        type=Path,
        default=DEFAULT_DEST,
        help="Output folder (default: ~/syncthing/music/music_new)",
    )
    parser.add_argument(
        "--library",
        type=Path,
        default=DEFAULT_LIBRARY,
        help="Existing library to copy unique matches from (default: ~/syncthing/music)",
    )
    parser.add_argument(
        "--no-copy",
        action="store_true",
        help="Do not copy existing library files; always download",
    )
    parser.add_argument(
        "--mp3",
        default="mp3",
        help="mp3 helper on PATH or path to docker/music-stack/scripts/mp3",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        metavar="N",
        help="Process at most N tracks (0 = all)",
    )
    parser.add_argument(
        "--start-at",
        type=int,
        default=0,
        metavar="N",
        help="Only rows whose JSON index >= N",
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=DEFAULT_SLEEP_SEC,
        metavar="SEC",
        help=f"Pause between downloads (default {DEFAULT_SLEEP_SEC:g})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Plan only; do not copy or download",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Required when processing more than 10 tracks without --dry-run",
    )
    parser.add_argument(
        "--index-in-navidrome",
        action="store_true",
        help="Do not write dest/.ndignore (Navidrome will pick up files)",
    )
    parser.add_argument(
        "--tolerance",
        type=float,
        default=15.0,
        metavar="SEC",
        help="Max |YouTube−Spotify| duration delta (default 15)",
    )
    parser.add_argument(
        "--search-results",
        type=int,
        default=12,
        metavar="N",
        help="ytsearchN depth for duration matching (default 12)",
    )
    args = parser.parse_args()

    json_path = args.json.expanduser()
    dest = args.dest.expanduser()
    library = args.library.expanduser()

    if not json_path.is_file():
        print(f"ERROR: JSON not found: {json_path}", file=sys.stderr)
        return 1

    mp3_exec = resolve_mp3_exec(args.mp3)
    if mp3_exec is None:
        return 1

    try:
        rows = load_songs(json_path)
        rows = filter_start_at(rows, args.start_at)
        jobs, skipped_artist, skipped_name = songs_to_jobs(rows)
        ytdlp = resolve_ytdlp()
        cab = Cabinet()
        sp = spotify_client_credentials(cab)
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if args.limit and args.limit > 0:
        jobs = jobs[: args.limit]

    print(
        f"Tracks to process: {len(jobs)} "
        f"(skipped blank artist: {skipped_artist}, blank name: {skipped_name})",
        file=sys.stderr,
    )

    if len(jobs) > 10 and not args.yes and not args.dry_run:
        print(
            f"Refusing to process {len(jobs)} tracks without --yes "
            "(use --dry-run, --limit N, or --yes).",
            file=sys.stderr,
        )
        return 1

    if not args.dry_run:
        ensure_dest(dest, hide_from_navidrome=not args.index_in_navidrome)

    existing_stems = index_audio_stems(dest)
    first_by_title = first_artist_by_title(jobs)
    library_index = (
        {} if args.no_copy else index_library_files(library, dest)
    )
    log_path = dest / ".download_library.jsonl"

    env_prev = _set_env(
        {
            "MUSIC_ROOT": str(dest),
            "MP3_STAGING": str(dest),
            "MP3_BEETS_IMPORT": "0",
        }
    )

    counts = {
        "ok": 0,
        "copy": 0,
        "skip": 0,
        "fail": 0,
    }
    try:
        for i, job in enumerate(jobs, 1):
            artist = job["artist"]
            name = job["name"]
            label = f"{name} — {artist}"
            print(f"\n[{i}/{len(jobs)}] {label}", file=sys.stderr)

            first_artist = first_by_title.get(fold_alnum(title_stem(name)), "")
            if dest_already_has(
                existing_stems, artist, name, first_artist=first_artist
            ):
                print("  SKIP: already in dest", file=sys.stderr)
                counts["skip"] += 1
                continue

            src = None if args.no_copy else find_library_copy(
                library_index, artist, name, first_artist=first_artist
            )
            if src is not None:
                target = copy_to_dest(
                    src, dest, artist, name, existing_stems, dry_run=args.dry_run
                )
                existing_stems.add(fold_alnum(target.stem))
                counts["copy"] += 1
                if not args.dry_run:
                    append_log(
                        log_path,
                        {
                            "status": "copy",
                            "artist": artist,
                            "name": name,
                            "src": str(src),
                            "dest": str(target),
                        },
                    )
                continue

            track_id = extract_track_id(job["url"])
            status = "fail"
            try:
                if track_id:
                    status = process_row(
                        job,
                        sp=sp,
                        ytdlp=ytdlp,
                        mp3_exec=mp3_exec,
                        search_results=max(1, args.search_results),
                        tolerance_sec=args.tolerance,
                        dry_run=args.dry_run,
                        update_spotify=False,
                        oauth=None,
                        name_to_id={},
                    )
                if status != "ok":
                    reason = "no Spotify URL" if not track_id else status
                    print(
                        f"  Falling back to mp3 artist+title search ({reason})",
                        file=sys.stderr,
                    )
                    status = download_by_query(
                        mp3_exec, artist, name, dry_run=args.dry_run
                    )
            except Exception as exc:  # noqa: BLE001
                print(f"  FAIL: {exc}", file=sys.stderr)
                status = "fail"

            if status == "ok":
                existing_stems.add(fold_alnum(title_stem(name)))
                existing_stems.add(
                    fold_alnum(f"{title_stem(name)} ({sanitize_segment(artist)})")
                )
                counts["ok"] += 1
            elif status == "skip":
                counts["skip"] += 1
            else:
                counts["fail"] += 1

            if not args.dry_run:
                append_log(
                    log_path,
                    {
                        "status": status,
                        "artist": artist,
                        "name": name,
                        "url": job["url"],
                    },
                )
                if args.sleep > 0 and status == "ok":
                    time.sleep(args.sleep)
    finally:
        _restore_env(env_prev)

    print(
        f"\nDone. downloaded={counts['ok']} copied={counts['copy']} "
        f"skip={counts['skip']} fail={counts['fail']}",
        file=sys.stderr,
    )
    print(f"Dest: {dest}", file=sys.stderr)
    return 0 if counts["fail"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
