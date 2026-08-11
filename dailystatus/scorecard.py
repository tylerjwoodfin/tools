"""
Personal SRE scorecard for the daily status email (TJW-316).

Reads existing Cabinet keys, Borg archives, and local service checks.
Missing data becomes status=unknown rather than raising.
"""

from __future__ import annotations

import datetime
import os
import re
import subprocess
from dataclasses import dataclass
from typing import Any, Callable
from urllib.parse import urlparse

_BORG_ARCHIVE_RE = re.compile(
    r"^(?P<label>.+)-(?P<ts>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})$"
)
_QUALITY_TS_RE = re.compile(
    r"^(?P<dt>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})(?:\s+\S+)?$"
)

_STATUS_STYLES = {
    "ok": "background-color: #e8f5e8; color: #2e7d32;",
    "warn": "background-color: #fff3e0; color: #ef6c00;",
    "error": "background-color: #ffebee; color: #c62828;",
    "unknown": "background-color: #f5f5f5; color: #616161;",
}


@dataclass(frozen=True)
class ScorecardRow:
    """One row in the SRE scorecard table."""

    check: str
    status: str  # ok | warn | error | unknown
    detail: str


def _safe_str(value: Any, default: str = "unknown / not configured") -> str:
    if value is None or value == "":
        return default
    return str(value)


def parse_quality_updated_at(
    value: Any, now: datetime.datetime | None = None
) -> datetime.datetime | None:
    """Parse ``quality.<host>.updated_at`` (``YYYY-MM-DD HH:MM:SS TZ``)."""
    if not value:
        return None
    text = str(value).strip()
    match = _QUALITY_TS_RE.match(text)
    if not match:
        return None
    try:
        return datetime.datetime.strptime(match.group("dt"), "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None


def parse_borg_archive_name(name: str) -> datetime.datetime | None:
    """Parse ``cloud-2026-08-10T03:05:37`` style Borg archive names."""
    match = _BORG_ARCHIVE_RE.match(name.strip())
    if not match:
        return None
    try:
        return datetime.datetime.strptime(match.group("ts"), "%Y-%m-%dT%H:%M:%S")
    except ValueError:
        return None


def parse_spotify_last_success(value: Any) -> datetime.datetime | None:
    """Parse ``spotipy.last_success`` (``YYYY-MM-DD HH:mm``)."""
    if not value:
        return None
    try:
        return datetime.datetime.strptime(str(value), "%Y-%m-%d %H:%M")
    except (TypeError, ValueError):
        return None


def expand_borg_repo_path(raw: str | None) -> str | None:
    """Expand ``$HOME`` / ``~`` in a Cabinet Borg repo path."""
    if not raw:
        return None
    text = str(raw).strip()
    if not text:
        return None
    home = os.path.expanduser("~")
    text = text.replace("$HOME", home)
    return os.path.expanduser(text)


def rainbow_host_from_borg_path(raw: str | None) -> str | None:
    """
    Extract SSH host from ``path.rainbow-borg`` (``ssh://user@host:port/path``).
    """
    if not raw:
        return None
    text = str(raw).strip()
    if not text.startswith("ssh://"):
        return None
    parsed = urlparse(text)
    return parsed.hostname


def age_hours(then: datetime.datetime, now: datetime.datetime) -> float:
    return (now - then).total_seconds() / 3600.0


def format_age_hours(hours: float) -> str:
    if hours < 1:
        return f"{hours * 60:.0f}m ago"
    if hours < 48:
        return f"{hours:.0f}h ago"
    return f"{hours / 24:.1f}d ago"


def collect_log_issues(cab) -> tuple[list[str], str]:
    """
    Return (issue lines, source label).

    Prefer Loki (cross-host, post-Mongo log migration) when ``logging.loki_url``
    is configured; fall back to local daily files.

    If the configured Loki URL fails (common on the Loki host when config uses a
    Tailscale DNS name), retry ``http://127.0.0.1:3100``.
    """
    loki_url = getattr(cab, "logging_loki_url", None) or ""
    candidates: list[str] = []
    if isinstance(loki_url, str) and loki_url.strip():
        candidates.append(loki_url.strip().rstrip("/"))
    localhost = "http://127.0.0.1:3100"
    if localhost not in candidates:
        candidates.append(localhost)

    original = getattr(cab, "logging_loki_url", loki_url)
    for url in candidates:
        try:
            cab.logging_loki_url = url
            lines = cab.log_query_issues_loki() or []
            return list(lines), "loki"
        except Exception:  # pylint: disable=broad-exception-caught
            continue
        finally:
            try:
                cab.logging_loki_url = original
            except Exception:  # pylint: disable=broad-exception-caught
                pass

    try:
        lines = cab.log_query_issues() or []
        return list(lines), "local"
    except Exception:  # pylint: disable=broad-exception-caught
        return [], "unavailable"


def _list_borg_archives(cab, timeout_s: float = 45.0) -> list[str] | None:
    """Return short archive names newest-last, or None if Borg is unavailable."""
    try:
        repo = expand_borg_repo_path(cab.get("keys", "borg", "repo"))
        passphrase = cab.get("keys", "borg", "passphrase")
    except Exception:  # pylint: disable=broad-exception-caught
        return None
    if not repo or not passphrase:
        return None
    if not os.path.isdir(repo) and not str(repo).startswith("ssh://"):
        return None

    env = os.environ.copy()
    env["BORG_REPO"] = repo
    env["BORG_PASSPHRASE"] = str(passphrase)
    # Avoid interactive prompts hanging cron/email.
    env.setdefault("BORG_UNKNOWN_UNENCRYPTED_REPO_ACCESS_IS_OK", "yes")
    env.setdefault("BORG_RELOCATED_REPO_ACCESS_IS_OK", "yes")

    try:
        result = subprocess.run(
            ["borg", "list", "--short"],
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return None

    if result.returncode != 0:
        return None
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def _recent_borg_error_files(max_age_days: int = 7) -> list[str]:
    """Basenames of recent files under ``~/.cabinet/log/borg-errors``."""
    err_dir = os.path.expanduser("~/.cabinet/log/borg-errors")
    if not os.path.isdir(err_dir):
        return []
    cutoff = datetime.datetime.now() - datetime.timedelta(days=max_age_days)
    found: list[str] = []
    try:
        for name in os.listdir(err_dir):
            if "error" not in name.lower():
                continue
            path = os.path.join(err_dir, name)
            try:
                mtime = datetime.datetime.fromtimestamp(os.path.getmtime(path))
            except OSError:
                continue
            if mtime >= cutoff:
                found.append(name)
    except OSError:
        return []
    found.sort(reverse=True)
    return found


def check_borg(cab, now: datetime.datetime) -> ScorecardRow:
    archives = _list_borg_archives(cab)
    error_files = _recent_borg_error_files()
    if archives is None:
        detail = "unknown / not configured (borg list unavailable)"
        if error_files:
            detail += f"; recent error logs: {', '.join(error_files[:3])}"
        return ScorecardRow("Borg backups", "unknown", detail)

    if not archives:
        return ScorecardRow("Borg backups", "error", "no archives found")

    last_name = archives[-1]
    last_dt = parse_borg_archive_name(last_name)
    if last_dt is None:
        return ScorecardRow(
            "Borg backups",
            "warn",
            f"latest archive {last_name!r} (unparseable timestamp)",
        )

    hours = age_hours(last_dt, now)
    detail = f"last success {last_name} ({format_age_hours(hours)})"
    if error_files:
        detail += f"; recent failures logged: {', '.join(error_files[:2])}"

    if hours > 72:
        status = "error"
    elif hours > 36 or error_files:
        status = "warn"
    else:
        status = "ok"
    return ScorecardRow("Borg backups", status, detail)


def check_disk_summary(quality_data: dict) -> ScorecardRow:
    if not isinstance(quality_data, dict) or not quality_data:
        return ScorecardRow("Disk free space", "unknown", "unknown / not configured")

    parts: list[str] = []
    worst = "ok"
    for name, device in quality_data.items():
        free_gb = None
        if isinstance(device, dict):
            free_gb = device.get("free_gb", device)
        else:
            free_gb = device
        try:
            free_gb_f = float(free_gb)
        except (TypeError, ValueError):
            parts.append(f"{name}: unknown")
            if worst == "ok":
                worst = "unknown"
            continue
        parts.append(f"{name} {free_gb_f:.1f} GB")
        if free_gb_f < 10:
            worst = "error"
        elif free_gb_f < 50 and worst == "ok":
            worst = "warn"
    return ScorecardRow("Disk free space", worst, "; ".join(parts) or "unknown / not configured")


def check_pihole(
    *,
    run_command: Callable[[list[str]], tuple[int, str, str]] | None = None,
) -> ScorecardRow:
    """Check local Pi-hole container / blocking status when Docker is available."""

    def _run(cmd: list[str]) -> tuple[int, str, str]:
        if run_command is not None:
            return run_command(cmd)
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=15, check=False
            )
            return result.returncode, result.stdout.strip(), result.stderr.strip()
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as exc:
            return 127, "", str(exc)

    code, out, _ = _run(
        ["docker", "ps", "--filter", "name=pihole", "--format", "{{.Names}} {{.Status}}"]
    )
    if code != 0:
        return ScorecardRow(
            "Pi-hole",
            "unknown",
            "unknown / not configured (docker unavailable)",
        )
    if not out or "pihole" not in out.lower():
        return ScorecardRow("Pi-hole", "error", "container not running")

    status_line = out.splitlines()[0]
    healthy = "up" in status_line.lower()
    # Best-effort block health
    b_code, b_out, _ = _run(["docker", "exec", "pihole", "pihole", "status"])
    blocking = None
    if b_code == 0 and b_out:
        lower = b_out.lower()
        if "blocking is enabled" in lower or "enabled" in lower:
            blocking = True
        elif "disabled" in lower:
            blocking = False

    if not healthy:
        return ScorecardRow("Pi-hole", "error", status_line)
    if blocking is False:
        return ScorecardRow("Pi-hole", "warn", f"{status_line}; blocking disabled")
    if blocking is True:
        return ScorecardRow("Pi-hole", "ok", f"{status_line}; blocking enabled")
    return ScorecardRow("Pi-hole", "ok", status_line)


def ping_host(hostname: str, timeout_s: int = 3) -> bool:
    try:
        result = subprocess.run(
            ["ping", "-c", "1", f"-W{timeout_s}", hostname],
            capture_output=True,
            text=True,
            timeout=timeout_s + 2,
            check=False,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return False


def check_rainbow(cab, quality_data: dict, now: datetime.datetime) -> ScorecardRow:
    """Reachability + uptime; disk free lives in the Disk free space row."""
    host = rainbow_host_from_borg_path(cab.get("path", "rainbow-borg"))
    reachable = None
    if host:
        reachable = ping_host(host)

    device = quality_data.get("rainbow") if isinstance(quality_data, dict) else None
    parts: list[str] = []
    status = "ok"

    if host:
        if reachable is True:
            parts.append("reachable")
        elif reachable is False:
            parts.append("unreachable")
            status = "error"
    else:
        parts.append("host unknown / not configured")
        status = "unknown"

    if isinstance(device, dict):
        updated = parse_quality_updated_at(device.get("updated_at"), now=now)
        if updated is not None:
            hours = age_hours(updated, now)
            # service_check writes quality.rainbow.updated_at on rainbow
            parts.append(f"last health check {format_age_hours(hours)}")
            if hours > 72 and status != "error":
                status = "error"
            elif hours > 36 and status == "ok":
                status = "warn"
        else:
            parts.append("last health check unknown")
            if status == "ok":
                status = "unknown"
    else:
        parts.append("no recent health check")
        if status == "ok":
            status = "unknown"

    # Local uptime when this host *is* rainbow
    try:
        if os.uname().nodename.lower() == "rainbow":
            with open("/proc/uptime", "r", encoding="utf-8") as fh:
                seconds = float(fh.read().split()[0])
            days = seconds / 86400.0
            parts.append(f"uptime {days:.0f}d")
    except (OSError, ValueError, AttributeError):
        pass

    return ScorecardRow("Rainbow", status, "; ".join(parts))


def check_spotify(cab, now: datetime.datetime) -> ScorecardRow:
    try:
        stats = cab.get("spotipy") or {}
    except Exception:  # pylint: disable=broad-exception-caught
        stats = {}
    if not isinstance(stats, dict):
        stats = {}
    raw = stats.get("last_success")
    parsed = parse_spotify_last_success(raw)
    tracks = stats.get("total_tracks")
    try:
        tracks_n = int(tracks) if tracks is not None else None
    except (TypeError, ValueError):
        tracks_n = None
    songs_bit = f"{tracks_n} songs" if tracks_n is not None else "song count unknown"

    if parsed is None:
        return ScorecardRow(
            "Spotify analytics",
            "error" if raw else "unknown",
            f"Checked unknown; {songs_bit}."
            if not raw
            else f"Checked unknown ({_safe_str(raw)}); {songs_bit}.",
        )
    hours = age_hours(parsed, now)
    detail = f"Checked {format_age_hours(hours)}; {songs_bit}."
    if hours > 48:
        status = "error"
    elif hours > 24:
        status = "warn"
    else:
        status = "ok"
    return ScorecardRow("Spotify analytics", status, detail)


def check_warnings_summary(issue_lines: list[str], source: str) -> ScorecardRow:
    if source == "unavailable":
        return ScorecardRow(
            "Warnings / errors (24h)",
            "unknown",
            "unknown / not configured (log query failed)",
        )
    errors = [
        line
        for line in issue_lines
        if "ERROR" in line.upper() or "CRITICAL" in line.upper()
    ]
    warnings = [line for line in issue_lines if "WARN" in line.upper()]
    detail = (
        f"{len(errors)} error(s), {len(warnings)} warning(s) via {source}"
    )
    if errors:
        status = "error"
    elif warnings:
        status = "warn"
    else:
        status = "ok"
        detail = f"none via {source}"
    return ScorecardRow("Warnings / errors (24h)", status, detail)


def build_scorecard_rows(
    cab,
    *,
    now: datetime.datetime | None = None,
    quality_data: dict | None = None,
    issue_lines: list[str] | None = None,
    issue_source: str | None = None,
) -> tuple[list[ScorecardRow], list[str], str]:
    """
    Collect scorecard rows plus the issue lines used for the warnings section.

    Returns ``(rows, issue_lines, issue_source)``.
    """
    now = now or datetime.datetime.now()
    if quality_data is None:
        try:
            quality_data = cab.get("quality", force_cache_update=True) or {}
        except TypeError:
            quality_data = cab.get("quality") or {}
        except Exception:  # pylint: disable=broad-exception-caught
            quality_data = {}
    if not isinstance(quality_data, dict):
        quality_data = {}

    if issue_lines is None or issue_source is None:
        issue_lines, issue_source = collect_log_issues(cab)

    rows = [
        check_borg(cab, now),
        check_disk_summary(quality_data),
        check_pihole(),
        check_rainbow(cab, quality_data, now),
        check_spotify(cab, now),
        check_warnings_summary(issue_lines, issue_source),
    ]
    return rows, issue_lines, issue_source


def render_scorecard_html(rows: list[ScorecardRow]) -> str:
    """Compact HTML table for the daily status email."""
    table = [
        "<h3>Personal SRE Scorecard</h3>",
        '<table border="1" style="border-collapse: collapse; width: 100%;">',
        '<tr style="background-color: #f2f2f2;">',
        '<th style="padding: 8px; text-align: left;">Check</th>',
        '<th style="padding: 8px; text-align: left;">Status</th>',
        '<th style="padding: 8px; text-align: left;">Detail</th>',
        "</tr>",
    ]
    for row in rows:
        style = _STATUS_STYLES.get(row.status, _STATUS_STYLES["unknown"])
        table.append(f'<tr style="{style}">')
        table.append(f'<td style="padding: 8px;">{_escape(row.check)}</td>')
        table.append(
            f'<td style="padding: 8px; text-transform: uppercase;">'
            f"{_escape(row.status)}</td>"
        )
        table.append(f'<td style="padding: 8px;">{_escape(row.detail)}</td>')
        table.append("</tr>")
    table.append("</table>")
    table.append("<br>")
    return "\n".join(table)


def render_issues_html(issue_lines: list[str], source: str, limit: int = 40) -> str:
    """Visually cleaned-up warnings/errors section (replaces raw pre dump)."""
    if not issue_lines:
        return (
            "<h3>Warnings / Errors (24h)</h3>"
            f"<p>None detected via { _escape(source) }.</p><br>"
        )

    shown = issue_lines[-limit:]
    rows_html: list[str] = []
    for line in shown:
        level = "info"
        upper = line.upper()
        if "CRITICAL" in upper:
            level = "critical"
        elif "ERROR" in upper:
            level = "error"
        elif "WARN" in upper:
            level = "warning"
        style = _STATUS_STYLES.get(
            {"critical": "error", "error": "error", "warning": "warn"}.get(level, "unknown"),
            _STATUS_STYLES["unknown"],
        )
        rows_html.append(
            f'<tr style="{style}">'
            f'<td style="padding: 6px; white-space: nowrap;">{_escape(level)}</td>'
            f'<td style="padding: 6px; font-family: monospace; font-size: 12px;">'
            f"{_escape(line)}</td></tr>"
        )

    omitted = max(0, len(issue_lines) - len(shown))
    note = ""
    if omitted:
        note = f"<p>Showing latest {len(shown)} of {len(issue_lines)} (source: {_escape(source)}).</p>"
    else:
        note = f"<p>Source: {_escape(source)}.</p>"

    return (
        "<h3>Warnings / Errors (24h)</h3>"
        f"{note}"
        '<table border="1" style="border-collapse: collapse; width: 100%;">'
        '<tr style="background-color: #f2f2f2;">'
        '<th style="padding: 6px; text-align: left;">Level</th>'
        '<th style="padding: 6px; text-align: left;">Message</th>'
        "</tr>"
        + "".join(rows_html)
        + "</table><br>"
    )


def _escape(text: str) -> str:
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
