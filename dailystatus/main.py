"""
Generate a daily status email detailing key activities, back up essential files, and manage logs.
"""

import os
import pwd
import datetime
import glob
import subprocess
import json
import textwrap
import cabinet

# pylint: disable=invalid-name

# initialize cabinet for configuration and mail for notifications
cab = cabinet.Cabinet()
mail = cabinet.Mail()


def get_paths_and_config():
    """retrieve and configure paths"""
    today = datetime.date.today()
    user_home = pwd.getpwuid(os.getuid())[0]
    path_dot_cabinet = os.path.join(f"/home/{user_home}/.cabinet")
    path_backend = cab.get("path", "cabinet", "log-backup") or f"{path_dot_cabinet}/log-backup"
    path_zshrc = os.path.join(f"/home/{user_home}/.zshrc")
    path_notes = cab.get("path", "notes") or f"{path_dot_cabinet}/notes"
    log_path_today = os.path.join(cab.path_dir_log, str(today))
    log_path_backups = cab.get("path", "backups") or f"{path_dot_cabinet}/backups"
    log_backups_location = os.path.join(log_path_backups, "log")
    bedtime_key = os.path.join(path_backend, "log", "keys", "BEDTIME")

    return {
        "today": today,
        "user_home": user_home,
        "path_backend": path_backend,
        "path_zshrc": path_zshrc,
        "path_notes": path_notes,
        "log_path_today": log_path_today,
        "log_backups_location": log_backups_location,
        "bedtime_key": bedtime_key,
    }


def backup_files(paths):
    """back up essential files"""
    backup_commands = [
        f"/usr/bin/crontab -l > '{os.path.join(paths['path_backend'],
        'cron',
        f'Cron {paths['today']}.md')}'",
        f"cp -r {paths['path_zshrc']} '{os.path.join(paths['path_backend'],
        'bash',
        f'Bash {paths['today']}.md')}'",
        f"zip -r '{os.path.join(paths['path_backend'],
        'notes',
        f'notes {paths['today']}.zip')}' {paths['path_notes']}",
        f"zip -r '{os.path.join(paths['log_backups_location'],
        f'log folder backup {paths['today']}.zip')}'\
            {paths['path_backend']} --exclude='{os.path.join(paths['path_backend'],
            'songs', '*')}'",
    ]

    try:
        for command in backup_commands:
            subprocess.run(command, shell=True, check=True)
    except subprocess.CalledProcessError as error:
        cab.log(f"command failed: {command} with error: {str(error)}", level="error")
    except OSError as error:
        cab.log(f"os error for: {command} with error: {str(error)}", level="error")


def prune_old_backups(paths, max_backups=14):
    """prune log folder backups exceeding the limit"""
    cab.log(f"pruning {paths['log_backups_location']}...")
    zip_files = glob.glob(f"{paths['log_backups_location']}/*.zip")
    zip_files.sort(key=os.path.getmtime)
    excess_count = len(zip_files) - max_backups
    for i in range(excess_count):
        os.remove(zip_files[i])


def manage_bedtime_key(paths):
    """publish bedtime limit"""
    bedtime_output = json.dumps(cab.get("bedtime", "limit"))
    os.makedirs(os.path.dirname(paths["bedtime_key"]), exist_ok=True)

    try:
        with open(paths["bedtime_key"], "x", encoding="utf-8") as file:
            file.write(bedtime_output)
    except FileExistsError:
        with open(paths["bedtime_key"], "w", encoding="utf-8") as file:
            file.write(bedtime_output)
    except (IOError, OSError) as error:
        cab.log(f"could not write bedtime key: {error}", level="error")


def analyze_logs(paths, email):
    """append daily log analysis"""
    daily_log_file = cab.get_file_as_array(f"LOG_DAILY_{paths['today']}.log",
                                           file_path=paths["log_path_today"]) or []

    daily_log_issues = [line for line in daily_log_file if \
        "ERROR" in line or "WARN" in line or "CRITICAL" in line]
    is_warnings = any("WARN" in issue for issue in daily_log_issues)
    is_errors = any("ERROR" in issue or "CRITICAL" in issue for issue in daily_log_issues)

    if daily_log_issues:
        daily_log_filtered = "<br>".join(daily_log_issues)
        email += textwrap.dedent(f"""
            <b>Warning/Error/Critical Log:</b><br>
            <pre style="font-family: monospace; white-space: pre-wrap;">{daily_log_filtered}</pre>
            <br>
            """)

    return email, is_warnings, is_errors


def append_spotify_info(paths, email):
    """append spotify issues and stats"""
    spotify_log = cab.get_file_as_array("LOG_SPOTIFY.log", file_path=paths["log_path_today"]) or []
    spotify_stats = cab.get("spotipy") or {}

    spotify_issues = "No Data"
    if spotify_log:
        issues = [log for log in spotify_log if \
            "WARNING" in log or "ERROR" in log or "CRITICAL" in log]
        if issues:
            spotify_issues = "<br>".join(issues)
            email += f"<b>Spotify Issues:</b><br>{spotify_issues}<br><br>"

    total_tracks = spotify_stats.get("total_tracks", "No Data")
    average_year = spotify_stats.get("average_year", "No Data")

    email += f"""
    <b>Spotify Stats:</b><br>
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
            <b>Weather Tomorrow:</b><br>
            {weather_tomorrow_formatted}
        """
    return email


def send_status_email(email, is_warnings, is_errors, today):
    """determine and send status email"""
    email_subject = f"Daily Status - {today}"
    if is_errors and is_warnings:
        email_subject += " - Check Errors/Warnings"
    elif is_errors:
        email_subject += " - Check Errors"
    elif is_warnings:
        email_subject += " - Check Warnings"

    mail.send(email_subject, email)


if __name__ == "__main__":
    # retrieve paths and configuration
    config_data = get_paths_and_config()

    # set up email content
    status_email = "Dear Tyler,<br><br>This is your daily status report.<br><br>"

    # back up files
    backup_files(config_data)

    # prune old backups
    prune_old_backups(config_data)

    # manage bedtime key
    manage_bedtime_key(config_data)

    # analyze logs
    status_email, has_warnings, has_errors = analyze_logs(config_data, status_email)

    # add spotify info
    status_email = append_spotify_info(config_data, status_email)

    # append weather info
    status_email = append_weather_info(status_email)

    # send the email
    send_status_email(status_email, has_warnings, has_errors, config_data["today"])
