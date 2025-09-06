"""
Generate a daily status email detailing key activities, back up essential files, and manage logs.
"""

import os
import difflib
import pwd
import datetime
import glob
import subprocess
import textwrap
import socket
import json
import sys
from pathlib import Path
import cabinet

# pylint: disable=invalid-name

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
        result = subprocess.run(
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
    except Exception as e:
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
    today = datetime.date.today()
    log_path_today = os.path.join(cab.path_dir_log, str(today))
    daily_log_file = (
        cab.get_file_as_array(f"LOG_DAILY_{today}.log", file_path=log_path_today) or []
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


def get_paths_and_config():
    """retrieve and configure paths"""
    today = datetime.date.today()
    device_name = socket.gethostname()
    user_home = pwd.getpwuid(os.getuid())[0]
    path_dot_cabinet = os.path.join(f"/home/{user_home}/.cabinet")
    path_backend = (
        cab.get("path", "cabinet", "log-backup") or f"{path_dot_cabinet}/log-backup"
    )
    path_zshrc = os.path.join(f"/home/{user_home}/.zshrc")
    path_notes = cab.get("path", "notes") or f"{path_dot_cabinet}/notes"
    log_path_today = os.path.join(cab.path_dir_log, str(today))
    log_path_backups = cab.get("path", "backups") or f"{path_dot_cabinet}/backups"
    log_backups_location = os.path.join(log_path_backups, "log")

    return {
        "today": today,
        "device_name": device_name,
        "user_home": user_home,
        "path_backend": path_backend,
        "path_zshrc": path_zshrc,
        "path_notes": path_notes,
        "log_path_today": log_path_today,
        "log_backups_location": log_backups_location,
    }


def append_food_log(email):
    """check if food has been logged today, print total calories or an error if none found."""
    log_file = os.path.expanduser("~/syncthing/log/food.json")
    today = datetime.date.today().isoformat()

    if not os.path.exists(log_file):
        cab.log("Food log file does not exist.", level="error")
        return email

    try:
        with open(log_file, "r", encoding="utf-8") as f:
            log_data = json.load(f)

        if today not in log_data or not log_data[today]:
            cab.log("No food logged for today.", level="error")
            return email
        else:
            total_calories = sum(entry["calories"] for entry in log_data[today])
            return email + textwrap.dedent(
                f"""
            <h3>Calories Eaten Today:</h3>
            <pre style="font-family: monospace; white-space: pre-wrap;"
            >{total_calories} calories</pre>
            <br>
            """
            )

    except (json.JSONDecodeError, OSError):
        cab.log("Error reading food log file.", level="error")
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


def backup_files(paths: dict) -> None:
    """
    Back up essential files.

    Args:
        paths (dict): A dictionary containing paths and other related configuration values.

    Returns:
        None
    """

    def build_backup_path(category):
        """Helper function to construct backup file paths."""
        return os.path.join(
            paths["path_backend"],
            paths["device_name"],
            category,
            f"{category} {paths['today']}.md",
        )

    # Construct backup file paths
    path_cron_today = build_backup_path("cron")
    path_bash_today = build_backup_path("zsh")
    path_notes_today = os.path.join(
        paths["path_backend"],
        paths["device_name"],
        "notes",
        f"notes {paths['today']}.zip",
    )
    path_log_backup = os.path.join(
        paths["log_backups_location"], f"log folder backup {paths['today']}.zip"
    )

    # define backup commands
    backup_commands = [
        f"/usr/bin/crontab -l > '{path_cron_today}'",
        f"cp -r {paths['path_zshrc']} '{path_bash_today}'",
        f"zip -r '{path_notes_today}' {paths['path_notes']}",
        f"zip -r '{path_log_backup}' {paths['path_backend']} "
        f"--exclude='{os.path.join(paths['path_backend'], 'songs', '*')}'",
    ]

    # execute each backup command
    try:
        for command in backup_commands:
            subprocess.run(command, shell=True, check=True)
    except subprocess.CalledProcessError as error:
        cab.log(f"Command failed: {command} with error: {str(error)}", level="error")
    except OSError as error:
        cab.log(f"OS error for: {command} with error: {str(error)}", level="error")


def prune_old_backups(paths, max_backups=14):
    """prune log folder backups exceeding the limit"""
    cab.log(f"pruning {paths['log_backups_location']}...")
    zip_files = glob.glob(f"{paths['log_backups_location']}/*.zip")
    zip_files.sort(key=os.path.getmtime)
    excess_count = len(zip_files) - max_backups
    for i in range(excess_count):
        os.remove(zip_files[i])


def analyze_logs(paths, email):
    """append daily log analysis"""
    daily_log_file = (
        cab.get_file_as_array(
            f"LOG_DAILY_{paths['today']}.log", file_path=paths["log_path_today"]
        )
        or []
    )

    daily_log_issues = [
        line
        for line in daily_log_file
        if "ERROR" in line or "WARN" in line or "CRITICAL" in line
    ]
    is_warnings = any("WARN" in issue for issue in daily_log_issues)
    is_errors = any(
        "ERROR" in issue or "CRITICAL" in issue for issue in daily_log_issues
    )

    # Check if the only error is the food log error
    error_lines = [
        line for line in daily_log_issues if "ERROR" in line or "CRITICAL" in line
    ]
    is_only_food_log_error = len(error_lines) == 1 and any(
        "No food logged for today." in line for line in error_lines
    )

    if daily_log_issues:
        daily_log_filtered = "<br>".join(daily_log_issues)
        email += textwrap.dedent(
            f"""
            <h3>Warning/Error/Critical Log:</h3>
            <pre style="font-family: monospace; white-space: pre-wrap;">{daily_log_filtered}</pre>
            <br>
            """
        )

    return email, is_warnings, is_errors, is_only_food_log_error


def append_spotify_info(paths, email):
    """append spotify issues and stats"""
    spotify_log = (
        cab.get_file_as_array("LOG_SPOTIFY.log", file_path=paths["log_path_today"])
        or []
    )
    spotify_stats = cab.get("spotipy") or {}

    spotify_issues = "No Data"
    if spotify_log:
        issues = [
            log
            for log in spotify_log
            if "WARNING" in log or "ERROR" in log or "CRITICAL" in log
        ]
        if issues:
            spotify_issues = "<br>".join(issues)
            email += f"<h3>Spotify Issues:</h3>{spotify_issues}<br><br>"

    total_tracks = spotify_stats.get("total_tracks", "No Data")
    average_year = spotify_stats.get("average_year", "No Data")

    email += f"""
    <h3>Spotify Stats:</h3>
    <ul><b>Song Count:</b> {total_tracks}</ul>
    <ul><b>Average Year:</b> {average_year}</ul>
    <br>
    """

    return email


def append_weather_info(email):
    """append weather data"""
    weather_tomorrow_formatted = cab.get("weather", "data", "tomorrow_formatted") or {}
    if weather_tomorrow_formatted:
        email += f"""
            <h3>Weather Tomorrow:</h3>
            {weather_tomorrow_formatted}
        """
    return email


def send_status_email(email, is_warnings, is_errors, is_only_food_log_error, today):
    """determine and send status email"""
    email_subject = f"Daily Status - {today}"
    if is_errors and is_warnings:
        email_subject += " - Check Errors/Warnings"
    elif is_errors:
        if is_only_food_log_error:
            email_subject += " - Check Food Log"
        else:
            email_subject += " - Check Errors"
    elif is_warnings:
        email_subject += " - Check Warnings"

    mail.send(email_subject, email)


if __name__ == "__main__":
    # retrieve paths and configuration
    config_data = get_paths_and_config()

    # set up email content
    status_email = "Dear Tyler,<br><br>This is your daily status report.<br><br>"

    # run service check first to gather latest data
    run_service_check()

    # check if food has been logged today
    status_email = append_food_log(status_email)

    # back up files
    backup_files(config_data)

    # prune old backups
    prune_old_backups(config_data)

    # analyze logs
    status_email, has_warnings, has_errors, is_only_food_log_error = analyze_logs(
        config_data, status_email
    )

    # add syncthing conflict check
    status_email = append_syncthing_conflict_check(status_email)

    # add spotify info
    status_email = append_spotify_info(config_data, status_email)

    # append weather info
    status_email = append_weather_info(status_email)

    # append free space info
    status_email = append_free_space_info(status_email)

    # append service check summary
    status_email = append_service_check_summary(status_email)

    # send the email
    send_status_email(
        status_email,
        has_warnings,
        has_errors,
        is_only_food_log_error,
        config_data["today"],
    )
