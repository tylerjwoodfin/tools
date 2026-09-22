#!/usr/bin/env python3
"""LAN endpoint: one day's foodlog calorie total for Apple Health.

    GET http://192.168.1.101:8754/calories
    GET http://192.168.1.101:8754/calories?date=YYYY-MM-DD

``date`` is optional and defaults to yesterday (local date). The body is the
day's total only, not individual foods.
"""

from __future__ import annotations

import datetime
import json
import os
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import main as foodlog

BIND = os.environ.get("FOODLOG_HEALTH_BIND", "192.168.1.101")
PORT = int(os.environ.get("FOODLOG_HEALTH_PORT", "8754"))
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def default_day() -> str:
    """Yesterday in local time (ISO date)."""
    return (datetime.date.today() - datetime.timedelta(days=1)).isoformat()


def parse_day(raw: str | None) -> str:
    """Return an ISO date. Empty means yesterday. Invalid input raises ValueError."""
    if raw is None or raw.strip() == "":
        return default_day()
    text = raw.strip()
    if not _DATE.match(text):
        raise ValueError("date must be YYYY-MM-DD")
    try:
        datetime.date.fromisoformat(text)
    except ValueError as exc:
        raise ValueError("date must be YYYY-MM-DD") from exc
    return text


def resolve_day(path: str, query: str) -> str:
    """Read ``date`` from the query string, or a ``/YYYY-MM-DD`` path."""
    params = parse_qs(query, keep_blank_values=True)
    if "date" in params:
        return parse_day(params["date"][0] if params["date"] else None)
    segment = path.rstrip("/").rsplit("/", 1)[-1]
    if _DATE.match(segment):
        return parse_day(segment)
    return parse_day(None)


def calorie_total(day: str | None = None) -> dict:
    """Daily total for Apple Health. ``day`` defaults to yesterday."""
    status = foodlog.day_status(parse_day(day))
    return {
        "date": status["date"],
        "total_calories": status["total_calories"],
        "unit": "kcal",
    }


class HealthHandler(BaseHTTPRequestHandler):
    """GET /calories or / with an optional date."""

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path or "/"
        if path not in ("/", "/calories", "/health") and not _DATE.match(
            path.rstrip("/").rsplit("/", 1)[-1]
        ):
            self._send(404, {"error": "not found"})
            return
        try:
            day = resolve_day(path, parsed.query)
            payload = calorie_total(day)
        except ValueError as exc:
            self._send(400, {"error": str(exc)})
            return
        except Exception:  # pylint: disable=broad-exception-caught
            self._send(500, {"error": "could not read foodlog"})
            return
        self._send(200, payload)

    def log_message(self, fmt: str, *args) -> None:
        print(f"{self.address_string()} {fmt % args}")

    def _send(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    server = ThreadingHTTPServer((BIND, PORT), HealthHandler)
    print(f"foodlog health listening on http://{BIND}:{PORT}/calories")
    server.serve_forever()


if __name__ == "__main__":
    main()
