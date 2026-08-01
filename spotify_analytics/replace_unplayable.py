#!/usr/bin/env python3
"""
Replace unplayable Spotify tracks with local YouTube downloads (TJW-328 phase 2).

For each entry in `spotify unplayable.json`:
  1. Fetch Spotify track duration
  2. Search YouTube and pick the candidate whose length is closest to that duration
     (rejects long music-video / mix uploads outside the tolerance)
  3. Download via the music-stack `mp3` helper into ~/syncthing/music
  4. Optionally remove the unplayable Spotify URI from playlists (--update-spotify)

Spotify's Web API cannot add local files to playlists; removal clears greyed-out
entries once a Navidrome/local copy exists.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import spotipy
from cabinet import Cabinet
from spotipy.oauth2 import SpotifyClientCredentials, SpotifyOAuth

MARKET = "US"
DEFAULT_UNPLAYABLE = "spotify unplayable.json"
DEFAULT_SEARCH_RESULTS = 8
DEFAULT_TOLERANCE_SEC = 15.0


def default_unplayable_path(cab: Cabinet) -> Path:
    log_path = cab.get("path", "log") or str(Path.home())
    return Path(log_path) / DEFAULT_UNPLAYABLE


def resolve_mp3_exec(mp3_cmd: str) -> Optional[List[str]]:
    expanded = Path(mp3_cmd).expanduser()
    if expanded.is_file():
        return [str(expanded)]
    found = shutil.which(mp3_cmd)
    if found:
        return [found]
    fallback = (
        Path.home() / "git" / "docker" / "music-stack" / "scripts" / "mp3"
    )
    if fallback.is_file():
        return [str(fallback)]
    print(
        f"ERROR: `{mp3_cmd}` not found (tried PATH and {fallback}).",
        file=sys.stderr,
    )
    return None


def resolve_ytdlp() -> List[str]:
    if shutil.which("yt-dlp"):
        return ["yt-dlp"]
    local = Path.home() / ".local" / "bin" / "yt-dlp"
    if local.is_file():
        return [str(local)]
    try:
        subprocess.run(
            [sys.executable, "-m", "yt_dlp", "--version"],
            capture_output=True,
            check=True,
        )
        return [sys.executable, "-m", "yt_dlp"]
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        raise RuntimeError("yt-dlp not found") from exc


def extract_track_id(url: str) -> Optional[str]:
    if not url:
        return None
    match = re.search(r"track/([a-zA-Z0-9]+)", url)
    if match:
        return match.group(1)
    if re.fullmatch(r"[a-zA-Z0-9]{22}", url.strip()):
        return url.strip()
    return None


def load_unplayable(path: Path) -> List[Dict[str, Any]]:
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError(f"Expected JSON array in {path}")
    return [row for row in data if isinstance(row, dict)]


def playlist_name_to_id(cab: Cabinet) -> Dict[str, str]:
    mapping: Dict[str, str] = {}
    for entry in cab.get("spotipy", "playlists") or []:
        if not isinstance(entry, str) or "," not in entry:
            continue
        playlist_id, name = entry.split(",", 1)
        mapping[name.strip()] = playlist_id.strip()
    return mapping


def spotify_client_credentials(cab: Cabinet) -> spotipy.Spotify:
    client_id = cab.get("spotipy", "client_id")
    client_secret = cab.get("spotipy", "client_secret")
    if not client_id or not client_secret:
        raise RuntimeError("Missing spotipy.client_id / client_secret in Cabinet")
    return spotipy.Spotify(
        client_credentials_manager=SpotifyClientCredentials(
            client_id=client_id,
            client_secret=client_secret,
        )
    )


def spotify_oauth_client(cab: Cabinet) -> spotipy.Spotify:
    """OAuth client for playlist modifications (reuse analytics cache path)."""
    client_id = cab.get("spotipy", "client_id")
    client_secret = cab.get("spotipy", "client_secret")
    username = cab.get("spotipy", "username") or "user"
    if not client_id or not client_secret:
        raise RuntimeError("Missing spotipy.client_id / client_secret in Cabinet")

    cache_path = str(
        Path(__file__).resolve().parent / f".cache-{username}"
    )
    auth = SpotifyOAuth(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri="http://127.0.0.1:8888/callback",
        scope="playlist-modify-public playlist-modify-private",
        cache_path=cache_path,
        open_browser=False,
    )
    token = auth.get_cached_token()
    if not token:
        raise RuntimeError(
            "No Spotify OAuth cache. Run: python3 main.py --reauthorize"
        )
    return spotipy.Spotify(auth=token["access_token"])


def fetch_duration_ms(sp: spotipy.Spotify, track_id: str) -> Optional[int]:
    track = sp.track(track_id, market=MARKET)
    duration = track.get("duration_ms")
    if isinstance(duration, int) and duration > 0:
        return duration
    return None


def youtube_search(
    ytdlp: List[str],
    query: str,
    results: int,
) -> List[Dict[str, Any]]:
    """Return flat search hits with id/title/duration (seconds)."""
    search = f"ytsearch{results}:{query}"
    proc = subprocess.run(
        [
            *ytdlp,
            "--flat-playlist",
            "--dump-json",
            "--no-download",
            search,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0 and not proc.stdout.strip():
        err = (proc.stderr or "").strip().splitlines()
        detail = err[-1] if err else f"exit {proc.returncode}"
        raise RuntimeError(f"yt-dlp search failed: {detail}")

    candidates: List[Dict[str, Any]] = []
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        video_id = row.get("id")
        duration = row.get("duration")
        if not video_id or duration is None:
            continue
        try:
            duration_f = float(duration)
        except (TypeError, ValueError):
            continue
        if duration_f <= 0:
            continue
        candidates.append(
            {
                "id": str(video_id),
                "title": row.get("title") or "",
                "duration": duration_f,
                "url": f"https://www.youtube.com/watch?v={video_id}",
            }
        )
    return candidates


def pick_closest_duration(
    candidates: List[Dict[str, Any]],
    target_sec: float,
    tolerance_sec: float,
) -> Optional[Tuple[Dict[str, Any], float]]:
    best: Optional[Dict[str, Any]] = None
    best_diff = float("inf")
    for cand in candidates:
        diff = abs(float(cand["duration"]) - target_sec)
        if diff < best_diff:
            best = cand
            best_diff = diff
    if best is None or best_diff > tolerance_sec:
        return None
    return best, best_diff


def download_with_mp3(
    mp3_exec: List[str],
    youtube_url: str,
    artist: str,
    title: str,
    dry_run: bool,
) -> int:
    env = os.environ.copy()
    env["MP3_STEM_TITLE"] = title
    env["MP3_STEM_ARTIST"] = artist
    cmd = [*mp3_exec]
    if dry_run:
        cmd.append("--dry-run")
    cmd.append(youtube_url)
    if dry_run:
        print(
            f"  DRY-RUN: MP3_STEM_TITLE={title!r} MP3_STEM_ARTIST={artist!r} "
            + subprocess.list2cmdline(cmd),
            file=sys.stderr,
        )
        return 0
    print(f"  mp3 {youtube_url}", file=sys.stderr)
    return subprocess.run(cmd, env=env).returncode


def remove_from_playlists(
    oauth: Optional[spotipy.Spotify],
    track_id: str,
    playlist_names: List[str],
    name_to_id: Dict[str, str],
    dry_run: bool,
) -> List[str]:
    removed: List[str] = []
    for name in playlist_names:
        playlist_id = name_to_id.get(name)
        if not playlist_id:
            print(f"  WARN: unknown playlist {name!r}, skip remove", file=sys.stderr)
            continue
        if dry_run:
            print(
                f"  DRY-RUN: would remove {track_id} from {name} ({playlist_id})",
                file=sys.stderr,
            )
            removed.append(name)
            continue
        if oauth is None:
            print(f"  WARN: no OAuth; cannot remove from {name}", file=sys.stderr)
            continue
        try:
            oauth.playlist_remove_all_occurrences_of_items(playlist_id, [track_id])
            print(f"  Removed from {name}", file=sys.stderr)
            removed.append(name)
        except Exception as exc:  # noqa: BLE001
            print(f"  WARN: failed to remove from {name}: {exc}", file=sys.stderr)
    return removed


def process_row(
    row: Dict[str, Any],
    *,
    sp: spotipy.Spotify,
    ytdlp: List[str],
    mp3_exec: List[str],
    search_results: int,
    tolerance_sec: float,
    dry_run: bool,
    update_spotify: bool,
    oauth: Optional[spotipy.Spotify],
    name_to_id: Dict[str, str],
) -> str:
    """Return status: ok | skip | fail."""
    name = (row.get("name") or "").strip()
    artist = (row.get("artist") or "").strip()
    url = (row.get("url") or "").strip()
    playlists = list(row.get("playlists") or [])

    if not name or name == "(unknown)":
        print("  SKIP: missing/unknown title", file=sys.stderr)
        return "skip"
    if not artist:
        print("  SKIP: missing artist", file=sys.stderr)
        return "skip"

    track_id = extract_track_id(url)
    if not track_id:
        print(f"  SKIP: cannot parse Spotify track id from {url!r}", file=sys.stderr)
        return "skip"

    duration_ms = fetch_duration_ms(sp, track_id)
    if duration_ms is None:
        print("  SKIP: Spotify duration unavailable", file=sys.stderr)
        return "skip"
    target_sec = duration_ms / 1000.0

    query = f"{artist} {name} audio"
    print(
        f"  Spotify duration={target_sec:.1f}s; searching YouTube: {query!r}",
        file=sys.stderr,
    )
    candidates = youtube_search(ytdlp, query, search_results)
    picked = pick_closest_duration(candidates, target_sec, tolerance_sec)
    if not picked:
        preview = ", ".join(
            f"{c['duration']:.0f}s:{c['title'][:40]}" for c in candidates[:5]
        ) or "(none)"
        print(
            f"  FAIL: no YouTube hit within ±{tolerance_sec:g}s "
            f"(target {target_sec:.1f}s); candidates: {preview}",
            file=sys.stderr,
        )
        return "fail"

    cand, diff = picked
    print(
        f"  Picked {cand['id']} ({cand['duration']:.1f}s, Δ{diff:.1f}s) "
        f"{cand['title']!r}",
        file=sys.stderr,
    )

    rc = download_with_mp3(mp3_exec, cand["url"], artist, name, dry_run=dry_run)
    if rc != 0:
        print(f"  FAIL: mp3 exited {rc}", file=sys.stderr)
        return "fail"

    if update_spotify and playlists:
        if not dry_run and oauth is None:
            print("  WARN: OAuth unavailable; skipped Spotify remove", file=sys.stderr)
        else:
            remove_from_playlists(
                oauth,
                track_id,
                playlists,
                name_to_id,
                dry_run=dry_run,
            )

    return "ok"


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Download YouTube audio for unplayable Spotify tracks, "
            "preferring videos closest in length to the Spotify duration"
        )
    )
    parser.add_argument(
        "--json-file",
        type=str,
        default=None,
        help=f"Path to {DEFAULT_UNPLAYABLE} (default: Cabinet path.log)",
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
        "--dry-run",
        action="store_true",
        help="Search and select only; do not download or modify Spotify",
    )
    parser.add_argument(
        "--update-spotify",
        action="store_true",
        help=(
            "After a successful download, remove the unplayable track from "
            "its Spotify playlists (API cannot add local files)"
        ),
    )
    parser.add_argument(
        "--tolerance",
        type=float,
        default=DEFAULT_TOLERANCE_SEC,
        metavar="SEC",
        help=f"Max |YouTube−Spotify| duration delta in seconds (default {DEFAULT_TOLERANCE_SEC:g})",
    )
    parser.add_argument(
        "--search-results",
        type=int,
        default=DEFAULT_SEARCH_RESULTS,
        metavar="N",
        help=f"ytsearchN depth (default {DEFAULT_SEARCH_RESULTS})",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Required when processing more than 10 tracks without --dry-run",
    )
    args = parser.parse_args()

    cab = Cabinet()
    path = Path(args.json_file) if args.json_file else default_unplayable_path(cab)
    if not path.is_file():
        print(
            f"ERROR: {path} not found. Run identify_unplayable.py --live --write … first.",
            file=sys.stderr,
        )
        return 1

    mp3_exec = resolve_mp3_exec(args.mp3)
    if mp3_exec is None:
        return 1

    try:
        rows = load_unplayable(path)
        ytdlp = resolve_ytdlp()
        sp = spotify_client_credentials(cab)
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if args.limit and args.limit > 0:
        rows = rows[: args.limit]

    if len(rows) > 10 and not args.yes and not args.dry_run:
        print(
            f"Refusing to process {len(rows)} tracks without --yes "
            "(use --dry-run, --limit N, or --yes).",
            file=sys.stderr,
        )
        return 1

    oauth: Optional[spotipy.Spotify] = None
    name_to_id = playlist_name_to_id(cab)
    if args.update_spotify and not args.dry_run:
        try:
            oauth = spotify_oauth_client(cab)
        except Exception as exc:  # noqa: BLE001
            print(f"ERROR: Spotify OAuth required for --update-spotify: {exc}", file=sys.stderr)
            return 1

    print(f"Processing {len(rows)} unplayable track(s) from {path}", file=sys.stderr)
    counts = {"ok": 0, "skip": 0, "fail": 0}
    for i, row in enumerate(rows, 1):
        label = f"{row.get('name') or '?'} — {row.get('artist') or '?'}"
        print(f"\n[{i}/{len(rows)}] {label}", file=sys.stderr)
        try:
            status = process_row(
                row,
                sp=sp,
                ytdlp=ytdlp,
                mp3_exec=mp3_exec,
                search_results=max(1, args.search_results),
                tolerance_sec=args.tolerance,
                dry_run=args.dry_run,
                update_spotify=args.update_spotify,
                oauth=oauth,
                name_to_id=name_to_id,
            )
        except Exception as exc:  # noqa: BLE001
            print(f"  FAIL: {exc}", file=sys.stderr)
            status = "fail"
        counts[status] = counts.get(status, 0) + 1

    print(
        f"\nDone. ok={counts['ok']} skip={counts['skip']} fail={counts['fail']}",
        file=sys.stderr,
    )
    return 0 if counts["fail"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
