"""
Generate a daily status email detailing key activities, back up essential files, and manage logs.
"""

import argparse
import os
import re
import shlex
import difflib
import datetime
import glob
import shutil
import subprocess
import textwrap
import json
import sys
import html
from pathlib import Path
import cabinet
from tyler_python_helpers import ChatGPT

# initialize cabinet for configuration and mail for notifications
cab = cabinet.Cabinet()
mail = cabinet.Mail()

def run_service_check():
    """Run the service check script and log any issues"""
    service_check_script = os.path.join(
        os.path.dirname(__file__), "..", "quality", "service_check.py"
    )

    if not os.path.exists(service_check_script):
        cab.log(
            f"Service check script not found: {service_check_script}", level="error"
        )
        return False

    try:
        # Run the service check script
        subprocess.run(
            [sys.executable, service_check_script],
            capture_output=True,
            text=True,
            check=True,
        )
        cab.log("Service check completed successfully")
        return True
    except subprocess.CalledProcessError as e:
        cab.log(f"Service check failed: {e.stderr}", level="error")
        return False
    except Exception as e:  # pylint: disable=broad-exception-caught
        cab.log(f"Error running service check: {str(e)}", level="error")
        return False


def append_free_space_info(email):
    """Append free space information from all devices as a table"""
    # Get all quality data from cabinet
    quality_data = cab.get("quality", force_cache_update=True) or {}

    if not quality_data:
        email += """
        <h3>Disk Space:</h3>
        <p>No disk space data available</p>
        <br>
        """
        return email

    # Build HTML table
    table_html = """
    <h3>Disk Space:</h3>
    <table border="1" style="border-collapse: collapse; width: 100%;">
        <tr style="background-color: #f2f2f2;">
            <th style="padding: 8px; text-align: left;">Device</th>
            <th style="padding: 8px; text-align: left;">Free Space (GB)</th>
        </tr>
    """

    for device_name, device_data in quality_data.items():
        # Handle nested structure from service check script
        if isinstance(device_data, dict):
            # Check if it has the nested structure from service check
            if "free_gb" in device_data:
                free_gb = device_data["free_gb"]
            else:
                # Try to get free_gb directly from device_data
                free_gb = device_data
        else:
            # Direct value
            free_gb = device_data

        # Ensure free_gb is a number
        try:
            free_gb = float(free_gb)
        except (ValueError, TypeError):
            continue

        # Color code based on available space
        if free_gb < 10:
            row_style = "background-color: #ffebee; color: #c62828;"
        elif free_gb < 50:
            row_style = "background-color: #fff3e0; color: #ef6c00;"
        else:
            row_style = "background-color: #e8f5e8; color: #2e7d32;"

        table_html += f"""
    <tr style="{row_style}">
        <td style="padding: 8px;">{device_name}</td>
        <td style="padding: 8px;">{free_gb:.2f}</td>
    </tr>
        """

    table_html += """
    </table>
    <br>
    """

    return email + table_html


def append_service_check_summary(email):
    """Append a summary of service check results only if there are errors"""
    # Get today's log to find service check results
    today_date = datetime.date.today()
    log_path = os.path.join(cab.path_dir_log, str(today_date))
    daily_log_file = (
        cab.get_file_as_array(f"LOG_DAILY_{today_date}.log", file_path=log_path) or []
    )

    # Filter for service check error entries only
    service_check_errors = [
        line for line in daily_log_file if "✗" in line or "⚠" in line
    ]

    if service_check_errors:
        # Get the most recent service check error entries (last 20 lines that match)
        recent_errors = service_check_errors[-20:]
        formatted_errors = "<br>".join(recent_errors)

        email += f"""
        <h3>Service Check Issues:</h3>
        <pre style="font-family: monospace; white-space: pre-wrap;">{formatted_errors}</pre>
        <br>
        """

    return email


def _food_log_paths():
    """Resolve food.json / food_submitted.json from Cabinet path config."""
    log_dir = cab.get("path", "cabinet", "log") or os.path.expanduser("~/syncthing/log")
    return (
        os.path.join(log_dir, "food.json"),
        os.path.join(log_dir, "food_submitted.json"),
    )


def is_foodlog_submitted(day: str, submitted_data: dict | None = None) -> bool:
    """True when ``foodlog submit`` has marked ``day`` (ISO date)."""
    if submitted_data is None:
        _, submitted_file = _food_log_paths()
        if not os.path.exists(submitted_file):
            return False
        try:
            with open(submitted_file, "r", encoding="utf-8") as f:
                submitted_data = json.load(f)
        except (json.JSONDecodeError, OSError):
            return False
    value = submitted_data.get(day)
    if isinstance(value, dict):
        return bool(value.get("submitted"))
    return bool(value)


def append_food_log(email, dry_run=False):
    """
    Append today's calorie total when food was logged.

    Sends the foodlog reminder email only if ``foodlog submit`` has not been
    run for today (logging alone does not suppress the reminder).
    """
    log_file, _submitted_file = _food_log_paths()
    today_str = datetime.date.today().isoformat()

    if not is_foodlog_submitted(today_str):
        if not dry_run:
            mail.send(
                "🍊 Log food for today!",
                "Food log not submitted for today. "
                "Log your food, then run `foodlog submit` when done.",
            )

    if not os.path.exists(log_file):
        cab.log("Food log file does not exist.", level="error")
        return email

    try:
        with open(log_file, "r", encoding="utf-8") as f:
            log_data = json.load(f)

        if today_str in log_data and log_data[today_str]:
            total_calories = sum(entry["calories"] for entry in log_data[today_str])
            submitted_note = " (submitted)" if is_foodlog_submitted(today_str) else ""
            return email + textwrap.dedent(
                f"""
            <h3>Calories Eaten Today:</h3>
            <pre style="font-family: monospace; white-space: pre-wrap;"
            >{total_calories} calories{submitted_note}</pre>
            <br>
            """
            )
        return email

    except (json.JSONDecodeError, OSError):
        cab.log("Error reading food log file.", level="error")
        return email


# English month names for goal date parsing (locale-independent).
_MONTH_NAME_TO_NUM = {
    "january": 1,
    "jan": 1,
    "february": 2,
    "feb": 2,
    "march": 3,
    "mar": 3,
    "april": 4,
    "apr": 4,
    "may": 5,
    "june": 6,
    "jun": 6,
    "july": 7,
    "jul": 7,
    "august": 8,
    "aug": 8,
    "september": 9,
    "sep": 9,
    "sept": 9,
    "october": 10,
    "oct": 10,
    "november": 11,
    "nov": 11,
    "december": 12,
    "dec": 12,
}

_MONTH_DAY_RE = re.compile(
    r"(?i)^\s*("
    r"january|february|march|april|may|june|july|august|"
    r"september|october|november|december|"
    r"jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec"
    r")\.?\s+(\d{1,2})(?:st|nd|rd|th)?(?:,?\s*(\d{4}))?\s*$"
)
_ISO_DATE_RE = re.compile(r"^\s*(\d{4})-(\d{1,2})-(\d{1,2})\s*$")
_MDY_SLASH_RE = re.compile(r"^\s*(\d{1,2})/(\d{1,2})(?:/(\d{4}))?\s*$")

# Health goals are for "next week"; reject remind roll-forwards like april→next year.
_FOODLOG_GOAL_MAX_DAYS_AHEAD = 14


def _next_week_date_context(today: datetime.date | None = None) -> str:
    """
    Explicit calendar bounds so ChatGPT does not copy stale example months
    (e.g. April) that remind would roll into the following year.
    """
    today = today or datetime.date.today()
    start = today + datetime.timedelta(days=1)
    end = today + datetime.timedelta(days=7)
    return (
        f"Today is {today.strftime('%A, %B')} {today.day}, {today.year} "
        f"({today.isoformat()}). "
        f'"Next week" means {start.isoformat()} through {end.isoformat()}. '
        "All goal dates MUST fall in that range. Prefer ISO dates YYYY-MM-DD. "
        "Do not copy example months (e.g. April) unless they fall in that range."
    )


def _parse_goal_calendar_date(
    when: str, today: datetime.date
) -> datetime.date | None:
    """
    Parse a concrete calendar date from a foodlog goal `when` string.

    Month/day without a year uses ``today.year``, then rolls forward one year if
    that date is already past (same rule remind uses). Returns None if ``when``
    is relative language (tomorrow, in 2 days, monday, …) or unparseable.
    """
    text = when.strip()
    if match := _ISO_DATE_RE.match(text):
        try:
            return datetime.date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
        except ValueError:
            return None

    if match := _MDY_SLASH_RE.match(text):
        month, day = int(match.group(1)), int(match.group(2))
        year = int(match.group(3)) if match.group(3) else today.year
        try:
            proposed = datetime.date(year, month, day)
        except ValueError:
            return None
        if match.group(3) is None and proposed < today:
            proposed = datetime.date(proposed.year + 1, month, day)
        return proposed

    if match := _MONTH_DAY_RE.match(text):
        month_word = match.group(1).lower().rstrip(".")
        month = _MONTH_NAME_TO_NUM.get(month_word)
        if month is None:
            return None
        day = int(match.group(2))
        year = int(match.group(3)) if match.group(3) else today.year
        try:
            proposed = datetime.date(year, month, day)
        except ValueError:
            return None
        if match.group(3) is None and proposed < today:
            proposed = datetime.date(proposed.year + 1, month, day)
        return proposed

    return None


def _normalize_foodlog_goal_when(
    when: str,
    today: datetime.date | None = None,
    max_days_ahead: int = _FOODLOG_GOAL_MAX_DAYS_AHEAD,
) -> str | None:
    """
    Return a ``--when`` value safe for near-term health goals, or None to skip.

    Absolute calendar dates more than ``max_days_ahead`` days out (typical when
    ChatGPT copies April examples and remind rolls them to next year) are
    rejected. Relative phrases are passed through unchanged.
    """
    today = today or datetime.date.today()
    text = when.strip()
    if not text:
        return None

    parsed = _parse_goal_calendar_date(text, today)
    if parsed is None:
        # Relative / weekday / day-of-month language — leave for remind.
        return text

    delta_days = (parsed - today).days
    if delta_days < 0 or delta_days > max_days_ahead:
        return None
    return parsed.isoformat()


def _apply_foodlog_goals_response(
    goals_response: str, today: datetime.date | None = None
) -> None:
    """
    Parse ChatGPT output from foodlog_goals: either the literal NO GOALS, or
    line-separated `rmmy when, "title"` commands; run each via `remind --save`.
    """
    today = today or datetime.date.today()
    text = goals_response.strip()
    if not text or text.upper() == "NO GOALS":
        cab.log("No foodlog goals to apply.", level="info")
        return

    remind_exe = shutil.which("remind")
    if not remind_exe:
        cab.log(
            "remind executable not found in PATH; skipping foodlog goal reminders",
            level="error",
        )
        return

    for raw_line in goals_response.splitlines():
        line = raw_line.strip()
        match = re.match(r"rmmy\s+", line, flags=re.IGNORECASE)
        if not match:
            continue
        rest = line[match.end() :].strip()
        comma = rest.find(",")
        if comma == -1:
            cab.log(f"Skipping invalid rmmy line (no comma): {raw_line!r}", level="warning")
            continue
        when = rest[:comma].strip()
        title = rest[comma + 1 :].strip()
        if (title.startswith('"') and title.endswith('"')) or (
            title.startswith("'") and title.endswith("'")
        ):
            title = title[1:-1]
        if not when or not title:
            cab.log(f"Skipping empty when/title in rmmy line: {raw_line!r}", level="warning")
            continue
        normalized_when = _normalize_foodlog_goal_when(when, today=today)
        if normalized_when is None:
            cab.log(
                f"Skipping foodlog goal with out-of-range date {when!r} "
                f"(expected within {_FOODLOG_GOAL_MAX_DAYS_AHEAD} days of {today.isoformat()})",
                level="warning",
                tags=["dailystatus", "remind", "foodlog_goal"],
            )
            continue
        cmd = [remind_exe, "--save", "--when", normalized_when, "--title", *title.split()]
        try:
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            cab.log(
                f"remind foodlog goal OK\ncommand: {shlex.join(cmd)}\n"
                f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}",
                level="debug",
                tags=["dailystatus", "remind", "foodlog_goal"],
            )
        except subprocess.CalledProcessError as e:
            cab.log(
                f"remind failed for foodlog goal ({normalized_when!r}, {title!r}): "
                f"{e.stderr or e}",
                level="error",
            )
            cab.log(
                f"remind foodlog goal FAILED\ncommand: {shlex.join(cmd)}\n"
                f"stdout: {e.stdout!r}\nstderr: {e.stderr!r}",
                level="debug",
                tags=["dailystatus", "remind", "foodlog_goal"],
            )


def append_nutrition_summary(email):
    """Append a bulleted summary of nutritional quality from the past 7 days via ChatGPT."""
    log_file = _food_log_paths()[0]

    if not os.path.exists(log_file):
        cab.log("Food log file does not exist for nutrition summary.", level="error")
        return email

    try:
        with open(log_file, "r", encoding="utf-8") as f:
            log_data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        cab.log(f"Error reading food log for nutrition summary: {e}", level="error")
        return email

    # Build food log for past 7 days
    today_day = datetime.date.today()
    week_entries = []
    for i in range(7):
        date = today_day - datetime.timedelta(days=i)
        date_str = date.isoformat()
        if date_str in log_data and log_data[date_str]:
            day_foods = [
                f"  - {e.get('food', 'unknown')}: {e.get('calories', 0)} cal"
                for e in log_data[date_str]
            ]
            day_total = sum(e.get("calories", 0) for e in log_data[date_str])
            week_entries.append(
                f"{date_str} ({day_total} cal total):\n" + "\n".join(day_foods)
            )

    if not week_entries:
        cab.log("No food log data in the past 7 days for nutrition summary.")
        return email

    food_log_text = "\n\n".join(week_entries)
    date_context = _next_week_date_context(today_day)

    prompt = textwrap.dedent(f"""
        {cab.get("ai", "prompts", "foodlog")}

        {date_context}

        Food log:
        {food_log_text}
    """).strip()

    try:
        chatgpt = ChatGPT()
        summary = chatgpt.query(prompt)
        cab.log(
            f"ChatGPT foodlog response:\n{summary}",
            level="debug",
            tags=["dailystatus", "chatgpt", "foodlog"],
        )

        goals_prompt_base = cab.get("ai", "prompts", "foodlog_goals")
        if goals_prompt_base:
            try:
                goals_prompt = (
                    f"{goals_prompt_base}\n\n{date_context}\n\n{summary}"
                )
                goals_response = chatgpt.query(goals_prompt)
                cab.log(
                    f"ChatGPT foodlog_goals response:\n{goals_response}",
                    level="debug",
                    tags=["dailystatus", "chatgpt", "foodlog_goals"],
                )
                _apply_foodlog_goals_response(goals_response, today=today_day)
            except Exception as e:  # pylint: disable=broad-exception-caught
                cab.log(f"ChatGPT foodlog goals or remind step failed: {e}", level="error")

        # foodlog prompt asks for HTML: opening sentence, then <h3> + <ul><li> sections.
        return email + textwrap.dedent(f"""
            <h3>Weekly Nutrition Summary:</h3>
            {summary.strip()}
            <br>
        """)
    except Exception as e:  # pylint: disable=broad-exception-caught
        cab.log(f"ChatGPT nutrition summary failed: {e}", level="error")
        return email


def append_syncthing_conflict_check(email):
    """
    If there are conflicts (files with `.sync-conflict` in their name) for remind.md
    (cabinet -> remindmail -> path -> file),
    return a merge conflict-style difference between the conflicting files
    with HTML formatting.
    """
    # Get the absolute path to the file from Cabinet
    target_file = cab.get("remindmail", "path", "file")

    if not target_file or not os.path.isfile(target_file):
        return email

    # Find files with `.sync-conflict` in the same directory as the target file
    target_dir = os.path.dirname(target_file)
    base_name = Path(target_file).stem
    conflict_pattern = os.path.join(target_dir, f"{base_name}.sync-conflict*")
    conflict_files = glob.glob(conflict_pattern)

    if not conflict_files:
        return email

    # Read the contents of the original file
    try:
        with open(target_file, "r", encoding="utf-8") as f:
            original_content = f.readlines()
    except (OSError, IOError) as e:
        cab.log(f"Error reading original file: {str(e)}", level="error")
        return email + f"Error reading original file: {str(e)}"

    # Read and compare each conflict file
    html_diffs = []
    for conflict_file in conflict_files:
        try:
            with open(conflict_file, "r", encoding="utf-8") as f:
                conflict_content = f.readlines()
        except (OSError, IOError) as e:
            cab.log(
                f"Error reading conflict file {conflict_file}: {str(e)}", level="error"
            )
            return email + f"Error reading conflict file {conflict_file}: {str(e)}"

        # Generate a unified diff and convert to HTML
        diff = difflib.unified_diff(
            original_content,
            conflict_content,
            fromfile=base_name,
            tofile=os.path.basename(conflict_file),
            lineterm="",
        )
        formatted_diff = "<br>".join(
            [
                (
                    f"<span style='color: green;'>+{line[1:]}</span>"
                    if line.startswith("+") and not line.startswith("+++")
                    else (
                        f"<span style='color: red;'>-{line[1:]}</span>"
                        if line.startswith("-") and not line.startswith("---")
                        else f"<span>{line}</span>"
                    )
                )
                for line in diff
            ]
        )
        html_diffs.append(
            f"<h3>remind.md has a conflict:</h3>"
            f"<pre style='font-family: monospace; white-space: pre-wrap;'>"
            f"{formatted_diff}</pre>"
        )

    # Combine all diffs into a single HTML string
    return email + "<br>".join(html_diffs)


def analyze_logs(email):
    """Append warning/error/critical log lines from the last 24h via ``cab.log_query_issues()``."""
    daily_log_issues = cab.log_query_issues()
    is_warnings = any("WARN" in issue for issue in daily_log_issues)
    is_errors = any(
        "ERROR" in issue or "CRITICAL" in issue for issue in daily_log_issues
    )

    error_lines = [
        line for line in daily_log_issues if "ERROR" in line or "CRITICAL" in line
    ]
    only_food_log_error = len(error_lines) == 1 and any(
        "No food logged for today." in line for line in error_lines
    )

    if daily_log_issues:
        daily_log_filtered = "<br>".join(daily_log_issues)
        email += textwrap.dedent(
            f"""
            <h3>Warning/Error/Critical Log (24h):</h3>
            <pre style="font-family: monospace; white-space: pre-wrap;">{daily_log_filtered}</pre>
            <br>
            """
        )

    return email, is_warnings, is_errors, only_food_log_error


def _parse_spotify_last_success(value) -> datetime.datetime | None:
    """Parse spotipy.last_success (YYYY-MM-DD HH:mm). Returns None if missing/invalid."""
    if not value:
        return None
    try:
        return datetime.datetime.strptime(str(value), "%Y-%m-%d %H:%M")
    except (TypeError, ValueError):
        return None


def append_spotify_info(today, log_path_today, email):  # pylint: disable=redefined-outer-name
    """append spotify issues and stats

    Returns:
        tuple: (email_html, last_success_stale) where last_success_stale is True when
        spotipy.last_success is missing or older than 24 hours.
    """
    # Read from daily log and filter for SPOTIFY entries
    daily_log = (
        cab.get_file_as_array(
            f"LOG_DAILY_{today}.log", file_path=log_path_today
        )
        or []
    )
    spotify_log = [line for line in daily_log if "SPOTIFY" in line]
    spotify_stats = cab.get("spotipy") or {}

    issue_lines = []
    if spotify_log:
        issue_lines.extend(
            log
            for log in spotify_log
            if "WARNING" in log or "ERROR" in log or "CRITICAL" in log
        )

    last_success_raw = spotify_stats.get("last_success")
    last_success_dt = _parse_spotify_last_success(last_success_raw)
    last_success_stale = False
    if last_success_dt is None:
        last_success_stale = True
        issue_lines.append(
            "SPOTIFY - last_success missing or invalid "
            f"(value={last_success_raw!r})"
        )
    else:
        age = datetime.datetime.now() - last_success_dt
        if age > datetime.timedelta(hours=24):
            last_success_stale = True
            hours = age.total_seconds() / 3600
            issue_lines.append(
                f"SPOTIFY - last_success stale ({last_success_raw}, "
                f"{hours:.0f}h ago; expected within 24h)"
            )

    if issue_lines:
        email += f"<h3>Spotify Issues:</h3>{'<br>'.join(issue_lines)}<br><br>"

    total_tracks = spotify_stats.get("total_tracks", "No Data")
    average_year = spotify_stats.get("average_year", "No Data")
    last_success_display = last_success_raw or "No Data"

    email += f"""
    <h3>Spotify Stats:</h3>
    <ul><b>Song Count:</b> {total_tracks}</ul>
    <ul><b>Average Year:</b> {average_year}</ul>
    <ul><b>Last Success:</b> {last_success_display}</ul>
    <br>
    """

    return email, last_success_stale


def append_weather_info(email):
    """append weather data"""
    weather_tomorrow_formatted = cab.get("weather", "data", "tomorrow_formatted") or {}
    if weather_tomorrow_formatted:
        email += f"""
            <h3>Weather Tomorrow:</h3>
            {weather_tomorrow_formatted}
        """
    return email


def send_status_email(
    email,
    is_warnings,
    is_errors,
    only_food_log_error,
    today,
    dry_run=False,
):  # pylint: disable=redefined-outer-name
    """determine and send status email (or print to terminal if dry_run)"""
    email_subject = f"Daily Status - {today}"
    if is_errors and is_warnings:
        email_subject += " - Check Errors/Warnings"
    elif is_errors:
        if only_food_log_error:
            email_subject += " - Check Food Log"
        else:
            email_subject += " - Check Errors"
    elif is_warnings:
        email_subject += " - Check Warnings"

    if today.weekday() == 5:  # Saturday
        email_subject = f"🍎 {email_subject}"

    if dry_run:
        plain = html_to_plain_text(email)
        print(f"Subject: {email_subject}\n")
        print(plain)
        return

    mail.send(email_subject, email)


def html_to_plain_text(html_content):
    """Convert HTML email content to readable plain text for terminal display."""
    text = html_content.replace("<br>", "\n").replace("<br/>", "\n").replace("<br />", "\n")
    # Convert list items to bullets before stripping other tags
    text = re.sub(r"<li[^>]*>", "\n• ", text, flags=re.IGNORECASE)
    # Add newlines after block elements
    text = re.sub(r"</(?:h[1-6]|p|li|tr|pre|div)>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<(?:h[1-6]|p|li|tr|pre|div)[^>]*>", "\n", text, flags=re.IGNORECASE)
    # Strip remaining tags
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    # Collapse excessive newlines, trim
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate daily status email")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the full email to terminal without sending",
    )
    args = parser.parse_args()

    # set up paths
    today = datetime.date.today()
    log_path_today = os.path.join(cab.path_dir_log, str(today))

    # set up email content
    status_email = "Dear Tyler,<br><br>This is your daily status report.<br><br>"

    # run service check first to gather latest data
    run_service_check()

    # check if food has been logged today
    status_email = append_food_log(status_email, dry_run=args.dry_run)

    # weekly nutrition summary (Saturdays only)
    if today.weekday() == 5:
        status_email = append_nutrition_summary(status_email)

    # add syncthing conflict check
    status_email = append_syncthing_conflict_check(status_email)

    # add spotify info
    status_email, spotify_last_success_stale = append_spotify_info(
        today, log_path_today, status_email
    )

    # analyze logs (24h via cab.log_query when Mongo enabled, else log files)
    status_email, has_warnings, has_errors, is_only_food_log_error = analyze_logs(
        status_email
    )

    if spotify_last_success_stale:
        has_errors = True
        # Stale Spotify success is not a food-log-only failure
        is_only_food_log_error = False

    # append weather info
    status_email = append_weather_info(status_email)

    # append free space info
    status_email = append_free_space_info(status_email)

    # append service check summary
    status_email = append_service_check_summary(status_email)

    # send the email (or print to terminal if --dry-run)
    send_status_email(
        status_email,
        has_warnings,
        has_errors,
        is_only_food_log_error,
        today,
        dry_run=args.dry_run,
    )
