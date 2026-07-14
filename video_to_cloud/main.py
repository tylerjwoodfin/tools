#!/usr/bin/env python3
"""
Watch ~/syncthing/documents/video-to-cloud and move completed files into
~/syncthing/video, then email a success notice via Cabinet Mail.

Syncthing-friendly behavior:
  - Only moves files (never removes parent folders during a move).
  - Waits until a file's size/mtime are stable before moving, so mid-sync
    transfers are not cut short.
  - Leaves empty directories behind; a daily 4am sweep removes empty parents
    under the watch root (never the watch root itself).
"""

from __future__ import annotations

import argparse
import shutil
import time
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from cabinet import Cabinet, Mail

WATCH_DIR = Path.home() / "syncthing" / "documents" / "video-to-cloud"
DEST_DIR = Path.home() / "syncthing" / "video"

# How long size+mtime must stay unchanged before we consider a file done.
STABLE_SECONDS = 30
# How often the watcher scans for new/ready files.
POLL_SECONDS = 10
# Local hour (24h) for the empty-directory sweep.
CLEANUP_HOUR = 4

IGNORE_NAMES = {
    ".ds_store",
    "thumbs.db",
    "desktop.ini",
    ".stfolder",
    ".stignore",
    ".stversions",
}
IGNORE_PREFIXES = (".syncthing.", ".~", ".sync-conflict-")
IGNORE_SUFFIXES = (".tmp", ".part", ".partial", ".download", ".crdownload")


@dataclass
class FileSnapshot:
    """Last observed size and mtime for stability checks."""

    size: int
    mtime: float
    first_seen: float


cabinet = Cabinet()
mail = Mail()


def should_ignore(path: Path) -> bool:
    """Return True for Syncthing temp/conflict files and junk metadata."""
    name = path.name
    lowered = name.lower()

    if lowered in IGNORE_NAMES:
        return True
    if any(name.startswith(prefix) for prefix in IGNORE_PREFIXES):
        return True
    if any(lowered.endswith(suffix) for suffix in IGNORE_SUFFIXES):
        return True
    return False


def unique_destination(dest: Path) -> Path:
    """
    If dest already exists, return a non-colliding sibling path.

    Example: show.mkv -> show.conflict-20260713-160530.mkv
    """
    if not dest.exists():
        return dest

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    candidate = dest.with_name(f"{dest.stem}.conflict-{stamp}{dest.suffix}")
    counter = 2
    while candidate.exists():
        candidate = dest.with_name(
            f"{dest.stem}.conflict-{stamp}-{counter}{dest.suffix}"
        )
        counter += 1
    return candidate


def iter_candidate_files(watch_dir: Path) -> list[Path]:
    """All non-ignored files under the watch directory."""
    if not watch_dir.is_dir():
        return []

    files: list[Path] = []
    for path in watch_dir.rglob("*"):
        if not path.is_file():
            continue
        if should_ignore(path):
            continue
        files.append(path)
    return files


def move_file(src: Path, watch_dir: Path, dest_dir: Path) -> Path | None:
    """
    Move src into dest_dir, preserving relative path under watch_dir.

    Parent folders under watch_dir are left in place (even if empty).
    """
    try:
        relative = src.relative_to(watch_dir)
    except ValueError:
        cabinet.log(f"Skipping path outside watch dir: {src}", level="warn")
        return None

    dest = unique_destination(dest_dir / relative)
    dest.parent.mkdir(parents=True, exist_ok=True)

    cabinet.log(f"Moving {src} -> {dest}")
    try:
        shutil.move(str(src), str(dest))
    except OSError as exc:
        cabinet.log(f"Failed to move {src}: {exc}", level="error")
        return None

    return dest


def send_success_email(moved: Path) -> None:
    """Email a short success notice naming the moved file."""
    subject = f"Video moved: {moved.name}"
    body = (
        f"<p>Moved to cloud video library:</p>"
        f"<p><code>{moved}</code></p>"
    )
    if mail.send(subject, body):
        cabinet.log(f"Success email sent for {moved.name}")
    else:
        cabinet.log(f"Failed to send success email for {moved.name}", level="error")


def cleanup_empty_dirs(watch_dir: Path) -> int:
    """
    Remove empty directories under watch_dir (deepest first).

    Never removes watch_dir itself. Returns the number of directories removed.
    """
    if not watch_dir.is_dir():
        return 0

    removed = 0
    # Bottom-up so nested empties clear before parents.
    for path in sorted(
        (p for p in watch_dir.rglob("*") if p.is_dir()),
        key=lambda p: len(p.parts),
        reverse=True,
    ):
        if should_ignore(path):
            continue
        try:
            # Only remove truly empty dirs (ignore is already filtered above).
            if any(path.iterdir()):
                continue
            path.rmdir()
            removed += 1
            cabinet.log(f"Removed empty directory: {path}")
        except OSError as exc:
            cabinet.log(f"Could not remove {path}: {exc}", level="warn")

    return removed


def process_stable_files(
    watch_dir: Path,
    dest_dir: Path,
    snapshots: dict[Path, FileSnapshot],
    *,
    stable_seconds: float,
    dry_run: bool,
) -> int:
    """Move files that have been size/mtime-stable for stable_seconds."""
    now = time.time()
    moved_count = 0
    seen: set[Path] = set()

    for src in iter_candidate_files(watch_dir):
        seen.add(src)
        try:
            stat = src.stat()
        except OSError:
            snapshots.pop(src, None)
            continue

        snap = snapshots.get(src)
        if (
            snap is None
            or snap.size != stat.st_size
            or snap.mtime != stat.st_mtime
        ):
            snapshots[src] = FileSnapshot(
                size=stat.st_size,
                mtime=stat.st_mtime,
                first_seen=now,
            )
            continue

        if now - snap.first_seen < stable_seconds:
            continue

        if dry_run:
            relative = src.relative_to(watch_dir)
            cabinet.log(f"[dry-run] would move {src} -> {dest_dir / relative}")
            snapshots.pop(src, None)
            moved_count += 1
            continue

        dest = move_file(src, watch_dir, dest_dir)
        snapshots.pop(src, None)
        if dest is None:
            continue

        send_success_email(dest)
        moved_count += 1

    # Drop snapshots for files that disappeared (moved elsewhere / deleted).
    for stale in list(snapshots):
        if stale not in seen:
            snapshots.pop(stale, None)

    return moved_count


def maybe_run_daily_cleanup(
    watch_dir: Path,
    last_cleanup_day: date | None,
    *,
    cleanup_hour: int,
    dry_run: bool,
    force: bool = False,
) -> date | None:
    """Run empty-dir cleanup once per day at cleanup_hour (or immediately if force)."""
    today = date.today()
    now = datetime.now()

    if not force:
        if now.hour != cleanup_hour:
            return last_cleanup_day
        if last_cleanup_day == today:
            return last_cleanup_day

    if dry_run:
        cabinet.log(f"[dry-run] would clean empty dirs under {watch_dir}")
        return today

    cabinet.log(f"Running empty-directory cleanup under {watch_dir}")
    removed = cleanup_empty_dirs(watch_dir)
    cabinet.log(f"Empty-directory cleanup removed {removed} folder(s)")
    return today


def run_watcher(
    watch_dir: Path,
    dest_dir: Path,
    *,
    poll_seconds: float,
    stable_seconds: float,
    cleanup_hour: int,
    dry_run: bool,
) -> None:
    """Long-running poll loop: move stable files + daily empty-dir sweep."""
    watch_dir.mkdir(parents=True, exist_ok=True)
    dest_dir.mkdir(parents=True, exist_ok=True)

    cabinet.log(
        f"Watching {watch_dir} -> {dest_dir} "
        f"(stable={stable_seconds}s, poll={poll_seconds}s, cleanup={cleanup_hour}:00)"
    )

    snapshots: dict[Path, FileSnapshot] = {}
    last_cleanup_day: date | None = None

    while True:
        process_stable_files(
            watch_dir,
            dest_dir,
            snapshots,
            stable_seconds=stable_seconds,
            dry_run=dry_run,
        )
        last_cleanup_day = maybe_run_daily_cleanup(
            watch_dir,
            last_cleanup_day,
            cleanup_hour=cleanup_hour,
            dry_run=dry_run,
        )
        time.sleep(poll_seconds)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Move Syncthing drop-folder videos into the cloud video library."
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Process currently stable files once and exit (no watch loop).",
    )
    parser.add_argument(
        "--cleanup",
        action="store_true",
        help="Only run the empty-directory cleanup, then exit.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Log actions without moving files or removing directories.",
    )
    parser.add_argument(
        "--watch-dir",
        type=Path,
        default=WATCH_DIR,
        help=f"Source drop folder (default: {WATCH_DIR})",
    )
    parser.add_argument(
        "--dest-dir",
        type=Path,
        default=DEST_DIR,
        help=f"Destination library (default: {DEST_DIR})",
    )
    parser.add_argument(
        "--stable-seconds",
        type=float,
        default=STABLE_SECONDS,
        help=f"Seconds a file must stay unchanged before moving (default: {STABLE_SECONDS})",
    )
    parser.add_argument(
        "--poll-seconds",
        type=float,
        default=POLL_SECONDS,
        help=f"Watcher poll interval in seconds (default: {POLL_SECONDS})",
    )
    parser.add_argument(
        "--cleanup-hour",
        type=int,
        default=CLEANUP_HOUR,
        help=f"Local hour (0-23) for daily empty-dir cleanup (default: {CLEANUP_HOUR})",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    watch_dir = args.watch_dir.expanduser().resolve()
    dest_dir = args.dest_dir.expanduser().resolve()

    if args.cleanup:
        maybe_run_daily_cleanup(
            watch_dir,
            None,
            cleanup_hour=args.cleanup_hour,
            dry_run=args.dry_run,
            force=True,
        )
        return

    if args.once:
        # Treat already-present files as immediately stable for one-shot runs.
        snapshots: dict[Path, FileSnapshot] = {}
        now = time.time() - args.stable_seconds - 1
        for src in iter_candidate_files(watch_dir):
            try:
                stat = src.stat()
            except OSError:
                continue
            snapshots[src] = FileSnapshot(
                size=stat.st_size,
                mtime=stat.st_mtime,
                first_seen=now,
            )
        moved = process_stable_files(
            watch_dir,
            dest_dir,
            snapshots,
            stable_seconds=args.stable_seconds,
            dry_run=args.dry_run,
        )
        cabinet.log(f"--once complete; moved {moved} file(s)")
        return

    run_watcher(
        watch_dir,
        dest_dir,
        poll_seconds=args.poll_seconds,
        stable_seconds=args.stable_seconds,
        cleanup_hour=args.cleanup_hour,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
