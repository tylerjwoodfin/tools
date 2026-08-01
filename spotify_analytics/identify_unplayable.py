#!/usr/bin/env python3
"""
Identify Spotify tracks that are unplayable in the US market.

Default: read `spotify unplayable.json` written by the daily spotify_analytics run.
Use --live to scan configured playlists via Spotipy (market=US / is_playable).

Output is suitable as input for replacing unplayable tracks with local copies.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import spotipy
from cabinet import Cabinet
from spotipy.oauth2 import SpotifyClientCredentials

MARKET = "US"
DEFAULT_FILENAME = "spotify unplayable.json"


def default_unplayable_path(cab: Cabinet) -> Path:
    log_path = cab.get("path", "log") or str(Path.home())
    return Path(log_path) / DEFAULT_FILENAME


def load_from_file(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError(f"Expected a JSON array in {path}")
    return [row for row in data if isinstance(row, dict)]


def _track_record(
    playlist_name: str,
    track: Optional[Dict[str, Any]],
    reason: str,
) -> Dict[str, Any]:
    if not track:
        return {
            "name": "",
            "artist": "",
            "url": "",
            "reason": reason,
            "playlists": [playlist_name] if playlist_name else [],
        }

    artists = track.get("artists") or []
    artist = (artists[0].get("name") or "") if artists else ""
    name = track.get("name") or "(unknown)"
    external_urls = track.get("external_urls") or {}
    url = external_urls.get("spotify") or track.get("uri") or track.get("id") or ""
    restrictions = track.get("restrictions") or {}
    restriction_reason = restrictions.get("reason")
    detail = reason
    if restriction_reason:
        detail = f"{reason}; restrictions.reason={restriction_reason}"
    return {
        "name": name,
        "artist": artist,
        "url": url,
        "reason": detail,
        "playlists": [playlist_name] if playlist_name else [],
    }


def _merge_records(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    by_key: Dict[str, Dict[str, Any]] = {}
    for record in records:
        url = (record.get("url") or "").strip()
        name = record.get("name") or ""
        artist = record.get("artist") or ""
        key = url or f"{name}\0{artist}"
        existing = by_key.get(key)
        playlists = list(record.get("playlists") or [])
        if existing is None:
            by_key[key] = {
                "name": name,
                "artist": artist,
                "url": url,
                "reason": record.get("reason") or "",
                "playlists": playlists,
            }
            continue
        for playlist in playlists:
            if playlist and playlist not in existing["playlists"]:
                existing["playlists"].append(playlist)
        reason = record.get("reason") or ""
        if reason and reason not in (existing.get("reason") or ""):
            existing["reason"] = (
                f"{existing['reason']}; {reason}" if existing.get("reason") else reason
            )
    return list(by_key.values())


def scan_live(cab: Cabinet) -> List[Dict[str, Any]]:
    client_id = cab.get("spotipy", "client_id")
    client_secret = cab.get("spotipy", "client_secret")
    playlists = cab.get("spotipy", "playlists") or []
    if not client_id or not client_secret:
        raise RuntimeError("Missing spotipy.client_id / spotipy.client_secret in Cabinet")
    if not playlists:
        raise RuntimeError("Missing spotipy.playlists in Cabinet")

    sp = spotipy.Spotify(
        client_credentials_manager=SpotifyClientCredentials(
            client_id=client_id,
            client_secret=client_secret,
        )
    )

    found: List[Dict[str, Any]] = []
    for entry in playlists:
        if not isinstance(entry, str) or "," not in entry:
            continue
        playlist_id, playlist_name = entry.split(",", 1)
        playlist_id = playlist_id.strip()
        playlist_name = playlist_name.strip()
        results = sp.playlist_items(playlist_id, market=MARKET)
        while results:
            for item in results.get("items") or []:
                track = item.get("track")
                if not track:
                    found.append(
                        _track_record(playlist_name, None, reason="null track entry")
                    )
                    continue
                if track.get("is_local"):
                    continue
                if track.get("is_playable") is False:
                    found.append(
                        _track_record(playlist_name, track, reason="is_playable=false")
                    )
            if not results.get("next"):
                break
            results = sp.next(results)

    return _merge_records(found)


def format_text(rows: List[Dict[str, Any]]) -> str:
    lines: List[str] = []
    for row in rows:
        name = row.get("name") or "(unknown)"
        artist = row.get("artist") or ""
        url = row.get("url") or ""
        playlists = ", ".join(row.get("playlists") or [])
        reason = row.get("reason") or ""
        label = f"{name} — {artist}" if artist else name
        bits = [label]
        if url:
            bits.append(url)
        if playlists:
            bits.append(f"playlists: {playlists}")
        if reason:
            bits.append(f"[{reason}]")
        lines.append(" | ".join(bits))
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Identify Spotify tracks unplayable in the US market"
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Scan playlists via Spotipy instead of reading the daily JSON file",
    )
    parser.add_argument(
        "--json-file",
        type=str,
        default=None,
        help=f"Path to {DEFAULT_FILENAME} (default: $cabinet path.log / {DEFAULT_FILENAME})",
    )
    parser.add_argument(
        "--write",
        type=str,
        default=None,
        metavar="PATH",
        help="Write the identified list to PATH as JSON (also prints summary)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the full JSON array to stdout instead of a text summary",
    )
    args = parser.parse_args()

    cab = Cabinet()
    try:
        if args.live:
            rows = scan_live(cab)
        else:
            path = Path(args.json_file) if args.json_file else default_unplayable_path(cab)
            try:
                rows = load_from_file(path)
            except FileNotFoundError:
                print(
                    f"Error: {path} not found. Run daily spotify_analytics first, "
                    "or pass --live to scan now.",
                    file=sys.stderr,
                )
                return 1
    except Exception as exc:  # noqa: BLE001
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if args.write:
        write_path = Path(args.write).expanduser()
        write_path.parent.mkdir(parents=True, exist_ok=True)
        with write_path.open("w", encoding="utf-8") as f:
            json.dump(rows, f, indent=2, ensure_ascii=False)
        print(f"Wrote {len(rows)} unplayable track(s) to {write_path}", file=sys.stderr)

    if args.json:
        json.dump(rows, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
    else:
        if not rows:
            print("No unplayable tracks found.")
        else:
            print(f"{len(rows)} unplayable track(s):\n")
            print(format_text(rows))

    return 0


if __name__ == "__main__":
    sys.exit(main())
