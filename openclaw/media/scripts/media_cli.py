#!/usr/bin/env python3
"""Narrow media control for Cherry.

Movies go to Radarr, shows to Sonarr, torrent status to qBittorrent, and music
to the Sockseek daemon. The stack runs on this machine. The CLI calls the
loopback HTTP APIs and does not shell into the download clients.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

SONARR_PORT = 8989
RADARR_PORT = 7878
QBIT_PORT = 8080
SOCKSEEK_PORT = 5030

OUTCOMES = (
    "added",
    "already_monitored",
    "downloading",
    "completed",
    "no_results",
    "backend_unavailable",
    "vpn_unavailable",
)


def latest_season(series: dict) -> dict | None:
    seasons = [
        season
        for season in series.get("seasons") or []
        if int(season.get("seasonNumber") or 0) > 0
    ]
    if not seasons:
        return None
    return max(seasons, key=lambda season: int(season["seasonNumber"]))


def season_stats(season: dict | None) -> tuple[bool, int, int]:
    if not season:
        return False, 0, 0
    stats = season.get("statistics") or {}
    return (
        bool(season.get("monitored")),
        int(stats.get("episodeCount") or stats.get("totalEpisodeCount") or 0),
        int(stats.get("episodeFileCount") or 0),
    )


def plan_series_action(
    existing: dict | None,
    *,
    in_queue: bool,
) -> tuple[str, str]:
    """Return (outcome, action). action is add, search, or none."""
    if existing is None:
        return "added", "add"
    if in_queue:
        return "downloading", "none"
    monitored, episodes, files = season_stats(latest_season(existing))
    if episodes and files >= episodes:
        return "completed", "none"
    if monitored and files < episodes:
        return "downloading", "search"
    if monitored:
        return "already_monitored", "none"
    return "added", "search"


def plan_movie_action(existing: dict | None, *, in_queue: bool) -> tuple[str, str]:
    if existing is None:
        return "added", "add"
    if in_queue:
        return "downloading", "none"
    if existing.get("hasFile"):
        return "completed", "none"
    if existing.get("monitored"):
        return "already_monitored", "search"
    return "added", "search"


def pick_best(items: list[dict], query: str, title_key: str = "title") -> dict | None:
    if not items:
        return None
    wanted = query.casefold().strip()
    exact = [
        item
        for item in items
        if str(item.get(title_key) or "").casefold().strip() == wanted
    ]
    return exact[0] if exact else items[0]


def parse_music_query(query: str) -> tuple[str | None, str]:
    if " - " in query:
        artist, rest = query.split(" - ", 1)
        return artist.strip() or None, rest.strip()
    return None, query.strip()


class ApiError(Exception):
    def __init__(self, outcome: str, message: str):
        super().__init__(message)
        self.outcome = outcome
        self.message = message


class Api:
    def __init__(self, sonarr: str, radarr: str, qbit: str, sockseek: str):
        self.sonarr = sonarr.rstrip("/")
        self.radarr = radarr.rstrip("/")
        self.qbit = qbit.rstrip("/")
        self.sockseek_url = sockseek.rstrip("/")
        self._qbit_cookie: str | None = None

    def _key(self, kind: str) -> str:
        filename = "sonarr" if kind == "sonarr" else "radarr"
        path = Path.home() / f"git/docker/media/config/{filename}/config.xml"
        if not path.exists():
            raise ApiError("backend_unavailable", f"{kind} config is missing")
        text = path.read_text(encoding="utf-8")
        match = re.search(r"<ApiKey>([^<]+)</ApiKey>", text or "")
        if not match:
            raise ApiError("backend_unavailable", f"{kind} API key is missing")
        return match.group(1).strip()

    def _json(self, method: str, url: str, payload: dict | None = None, headers: dict | None = None):
        data = None
        hdrs = {"Accept": "application/json"}
        if headers:
            hdrs.update(headers)
        if payload is not None:
            data = json.dumps(payload).encode()
            hdrs["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
        try:
            with urllib.request.urlopen(req, timeout=45) as resp:
                body = resp.read().decode()
                return json.loads(body) if body else None
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode(errors="replace")[:300]
            raise ApiError("backend_unavailable", f"{method} {url} failed ({exc.code}): {detail}") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise ApiError("backend_unavailable", f"could not reach {url}") from exc

    def sonarr_get(self, path: str, params: dict | None = None):
        query = f"?{urllib.parse.urlencode(params)}" if params else ""
        return self._json(
            "GET",
            f"{self.sonarr}/api/v3{path}{query}",
            headers={"X-Api-Key": self._key("sonarr")},
        )

    def sonarr_send(self, method: str, path: str, payload: dict):
        return self._json(
            method,
            f"{self.sonarr}/api/v3{path}",
            payload,
            headers={"X-Api-Key": self._key("sonarr")},
        )

    def radarr_get(self, path: str, params: dict | None = None):
        query = f"?{urllib.parse.urlencode(params)}" if params else ""
        return self._json(
            "GET",
            f"{self.radarr}/api/v3{path}{query}",
            headers={"X-Api-Key": self._key("radarr")},
        )

    def radarr_send(self, method: str, path: str, payload: dict):
        return self._json(
            method,
            f"{self.radarr}/api/v3{path}",
            payload,
            headers={"X-Api-Key": self._key("radarr")},
        )

    def qbit_login(self) -> None:
        password = _cabinet_value("media", "qbit_password")
        if not password:
            raise ApiError("backend_unavailable", "qBittorrent password is not in Cabinet")
        form = urllib.parse.urlencode({"username": "admin", "password": password}).encode()
        req = urllib.request.Request(f"{self.qbit}/api/v2/auth/login", data=form, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                body = resp.read().decode().strip()
                cookie = resp.headers.get("Set-Cookie", "").split(";", 1)[0]
                status = resp.status
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise ApiError(self._download_outcome(), "qBittorrent is not reachable") from exc
        # qBittorrent 4 returned "Ok."; 5 returns 204 with an empty body.
        if status not in (200, 204) or (body and body != "Ok.") or not cookie:
            raise ApiError("backend_unavailable", "qBittorrent login failed")
        self._qbit_cookie = cookie

    def qbit_torrents(self) -> list[dict]:
        if not self._qbit_cookie:
            self.qbit_login()
        req = urllib.request.Request(
            f"{self.qbit}/api/v2/torrents/info",
            headers={"Cookie": self._qbit_cookie or ""},
        )
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                return json.loads(resp.read().decode() or "[]")
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise ApiError(self._download_outcome(), "qBittorrent is not reachable") from exc

    def sockseek(self, method: str, path: str, payload: dict | None = None):
        try:
            return self._json(method, f"{self.sockseek_url}{path}", payload)
        except ApiError as exc:
            if exc.outcome == "backend_unavailable":
                raise ApiError(self._download_outcome(), "Sockseek is not reachable") from exc
            raise

    def _download_outcome(self) -> str:
        health = gluetun_health()
        if health in {"missing", "unhealthy", "exited", "dead"}:
            return "vpn_unavailable"
        return "backend_unavailable"


def _cabinet_value(*path: str) -> str:
    try:
        from cabinet import Cabinet

        value = Cabinet().get(*path, return_type=str) or ""
    except Exception:
        return ""
    return str(value).strip()


def gluetun_health() -> str:
    command = [
        "docker",
        "inspect",
        "-f",
        "{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}",
        "media-gluetun",
    ]
    try:
        proc = subprocess.run(command, capture_output=True, text=True, timeout=20, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return "unknown"
    if proc.returncode != 0:
        return "missing"
    return (proc.stdout or "").strip() or "unknown"


def local_api() -> Api:
    return Api(
        f"http://127.0.0.1:{SONARR_PORT}",
        f"http://127.0.0.1:{RADARR_PORT}",
        f"http://127.0.0.1:{QBIT_PORT}",
        f"http://127.0.0.1:{SOCKSEEK_PORT}",
    )


def _quality_profile_id(profiles: list[dict]) -> int:
    if not profiles:
        raise ApiError("backend_unavailable", "no quality profile is configured")
    return int(profiles[0]["id"])


def _root_folder(folders: list[dict]) -> str:
    if not folders:
        raise ApiError("backend_unavailable", "no root folder is configured")
    return str(folders[0]["path"])


def _queue_has(records: list[dict], key: str, value) -> bool:
    return any(row.get(key) == value for row in records)


def add_series(api: Api, query: str) -> dict:
    found = api.sonarr_get("/series/lookup", {"term": query}) or []
    chosen = pick_best(found, query)
    if not chosen:
        return _result("no_results", f'no series matched "{query}"')
    library = api.sonarr_get("/series") or []
    existing = next((row for row in library if row.get("tvdbId") == chosen.get("tvdbId")), None)
    queue = (api.sonarr_get("/queue") or {}).get("records") or []
    in_queue = bool(existing and _queue_has(queue, "seriesId", existing.get("id")))
    outcome, action = plan_series_action(existing, in_queue=in_queue)
    title = chosen.get("title") or query
    season = latest_season(existing or chosen)
    season_no = int(season["seasonNumber"]) if season else None
    if action == "add":
        body = dict(chosen)
        body.pop("id", None)
        body["qualityProfileId"] = _quality_profile_id(api.sonarr_get("/qualityprofile") or [])
        body["rootFolderPath"] = _root_folder(api.sonarr_get("/rootfolder") or [])
        body["monitored"] = True
        body["seasonFolder"] = True
        body["addOptions"] = {"monitor": "lastSeason", "searchForMissingEpisodes": True}
        api.sonarr_send("POST", "/series", body)
        label = f"season {season_no}" if season_no else "the current season"
        return _result("added", f"added: {title} ({label}) is monitored and searching")
    if action == "search" and existing and season_no:
        _monitor_season(api, existing, season_no)
        api.sonarr_send(
            "POST",
            "/command",
            {"name": "SeasonSearch", "seriesId": existing["id"], "seasonNumber": season_no},
        )
        if outcome == "added":
            return _result("added", f"added: {title} season {season_no} is now monitored and searching")
        return _result("downloading", f"downloading: searching {title} season {season_no}")
    if outcome == "completed":
        return _result("completed", f"completed: {title} current season is already on disk")
    if outcome == "downloading":
        return _result("downloading", f"downloading: {title} is already in the queue")
    return _result("already_monitored", f"already monitored: {title}")


def _monitor_season(api: Api, series: dict, season_no: int) -> None:
    for season in series.get("seasons") or []:
        if int(season.get("seasonNumber") or 0) == season_no:
            season["monitored"] = True
    series["monitored"] = True
    api.sonarr_send("PUT", f"/series/{series['id']}", series)


def add_movie(api: Api, query: str) -> dict:
    found = api.radarr_get("/movie/lookup", {"term": query}) or []
    chosen = pick_best(found, query)
    if not chosen:
        return _result("no_results", f'no movie matched "{query}"')
    library = api.radarr_get("/movie") or []
    existing = next((row for row in library if row.get("tmdbId") == chosen.get("tmdbId")), None)
    queue = (api.radarr_get("/queue") or {}).get("records") or []
    in_queue = bool(existing and _queue_has(queue, "movieId", existing.get("id")))
    outcome, action = plan_movie_action(existing, in_queue=in_queue)
    title = chosen.get("title") or query
    if action == "add":
        body = dict(chosen)
        body.pop("id", None)
        body["qualityProfileId"] = _quality_profile_id(api.radarr_get("/qualityprofile") or [])
        body["rootFolderPath"] = _root_folder(api.radarr_get("/rootfolder") or [])
        body["monitored"] = True
        body["addOptions"] = {"searchForMovie": True}
        api.radarr_send("POST", "/movie", body)
        return _result("added", f"added: {title} is monitored and searching")
    if action == "search" and existing:
        existing["monitored"] = True
        api.radarr_send("PUT", f"/movie/{existing['id']}", existing)
        api.radarr_send("POST", "/command", {"name": "MoviesSearch", "movieIds": [existing["id"]]})
        if outcome == "already_monitored":
            return _result("downloading", f"downloading: searching {title}")
        return _result("added", f"added: {title} is now monitored and searching")
    if outcome == "completed":
        return _result("completed", f"completed: {title} is already on disk")
    if outcome == "downloading":
        return _result("downloading", f"downloading: {title} is already in the queue")
    return _result("already_monitored", f"already monitored: {title}")


def search_series(api: Api, query: str) -> dict:
    found = api.sonarr_get("/series/lookup", {"term": query}) or []
    if not found:
        return _result("no_results", f'no series matched "{query}"', matches=[])
    matches = [_title_year(item) for item in found[:8]]
    return _result("matches", "series matches: " + "; ".join(matches), matches=matches)


def search_movie(api: Api, query: str) -> dict:
    found = api.radarr_get("/movie/lookup", {"term": query}) or []
    if not found:
        return _result("no_results", f'no movie matched "{query}"', matches=[])
    matches = [_title_year(item) for item in found[:8]]
    return _result("matches", "movie matches: " + "; ".join(matches), matches=matches)


def _title_year(item: dict) -> str:
    title = item.get("title") or item.get("sortTitle") or "unknown"
    year = item.get("year")
    return f"{title} ({year})" if year else str(title)


def add_music(api: Api, query: str, *, album: bool) -> dict:
    if query.startswith("http://") or query.startswith("https://"):
        payload = {"songQuery": {"uri": query}} if not album else {"albumQuery": {"uri": query}}
        path = "/api/jobs/downloads/album" if album else "/api/jobs/downloads/song"
    else:
        artist, rest = parse_music_query(query)
        if album:
            payload = {"albumQuery": {"artist": artist, "album": rest}}
            path = "/api/jobs/downloads/album"
        else:
            payload = {"songQuery": {"artist": artist, "title": rest}}
            path = "/api/jobs/downloads/song"
    created = api.sockseek("POST", path, payload)
    label = "album" if album else "song"
    return _result("added", f"added: {label} download submitted for {query}", job=created)


def status(api: Api) -> dict:
    parts = []
    details: dict = {}
    try:
        queue = (api.sonarr_get("/queue") or {}).get("records") or []
        details["sonarr"] = [row.get("title") for row in queue]
        parts.append(f"sonarr queue: {len(queue)}")
    except ApiError as exc:
        details["sonarr_error"] = exc.outcome
        parts.append(f"sonarr: {exc.outcome}")
    try:
        queue = (api.radarr_get("/queue") or {}).get("records") or []
        details["radarr"] = [row.get("title") for row in queue]
        parts.append(f"radarr queue: {len(queue)}")
    except ApiError as exc:
        details["radarr_error"] = exc.outcome
        parts.append(f"radarr: {exc.outcome}")
    try:
        torrents = api.qbit_torrents()
        details["qbittorrent"] = [
            {"name": row.get("name"), "progress": row.get("progress"), "state": row.get("state")}
            for row in torrents
        ]
        parts.append(f"qbittorrent: {len(torrents)}")
    except ApiError as exc:
        details["qbittorrent_error"] = exc.outcome
        parts.append(f"qbittorrent: {exc.outcome}")
    try:
        jobs = api.sockseek("GET", "/api/jobs") or []
        details["sockseek"] = len(jobs) if isinstance(jobs, list) else jobs
        parts.append("sockseek: up")
    except ApiError as exc:
        details["sockseek_error"] = exc.outcome
        parts.append(f"sockseek: {exc.outcome}")
    vpn = gluetun_health()
    details["vpn"] = vpn
    outcome = "downloading" if details.get("qbittorrent") else "already_monitored"
    if vpn in {"missing", "unhealthy", "exited", "dead"}:
        outcome = "vpn_unavailable"
    return _result(outcome, "status: " + "; ".join(parts), **details)


def health(api: Api) -> dict:
    report = status(api)
    vpn = report.get("vpn")
    errors = [key for key in report if key.endswith("_error")]
    if vpn in {"missing", "unhealthy", "exited", "dead"}:
        report["outcome"] = "vpn_unavailable"
        report["ok"] = False
        report["message"] = "vpn unavailable; " + report["message"]
    elif errors:
        report["outcome"] = "backend_unavailable"
        report["ok"] = False
        report["message"] = "backend unavailable; " + report["message"]
    else:
        report["outcome"] = "completed"
        report["ok"] = True
        report["message"] = "vpn: up; " + report["message"]
    return report


def _result(outcome: str, message: str, **extra) -> dict:
    body = {"ok": outcome not in {"no_results", "backend_unavailable", "vpn_unavailable"}, "outcome": outcome, "message": message}
    body.update(extra)
    return body


def emit(result: dict, as_json: bool) -> int:
    if as_json:
        print(json.dumps(result))
    else:
        print(result["message"])
    return 0 if result.get("ok") else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Control Radarr, Sonarr, qBittorrent, and Sockseek")
    parser.add_argument("--json", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("health")
    sub.add_parser("status")

    for name in ("movie", "series"):
        search = sub.add_parser(f"search-{name}")
        search.add_argument("query")
        add = sub.add_parser(f"add-{name}")
        add.add_argument("query")
        if name == "series":
            add.add_argument("--season", default="current", choices=["current"])

    music = sub.add_parser("add-music")
    music.add_argument("query")
    mode = music.add_mutually_exclusive_group()
    mode.add_argument("--song", action="store_true")
    mode.add_argument("--album", action="store_true")
    return parser


def run(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    as_json = args.json
    try:
        api = local_api()
        if args.command == "health":
            result = health(api)
        elif args.command == "status":
            result = status(api)
        elif args.command == "search-movie":
            result = search_movie(api, args.query)
        elif args.command == "search-series":
            result = search_series(api, args.query)
        elif args.command == "add-movie":
            result = add_movie(api, args.query)
        elif args.command == "add-series":
            result = add_series(api, args.query)
        elif args.command == "add-music":
            result = add_music(api, args.query, album=bool(args.album))
        else:
            parser.error(f"unknown command {args.command}")
            return 2
    except ApiError as exc:
        result = _result(exc.outcome, f"{exc.outcome.replace('_', ' ')}: {exc.message}")
    return emit(result, as_json)


def main() -> None:
    raise SystemExit(run())


if __name__ == "__main__":
    main()
