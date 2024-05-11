"""
Generate a daily status email detailing key activities, back up essential files, and manage logs.

This script is specific to the developer's environment.

Adjust settings and paths for different setups.
"""

import os
import pwd
import datetime
import glob
import subprocess
import json
import cabinet

# pylint: disable=invalid-name

# initialize cabinet for configuration and mail for notifications
cab = cabinet.Cabinet()
mail = cabinet.Mail()

# email content setup
_status_email: str = "Dear Tyler,<br><br>This is your daily status report.<br><br>"

# paths and configuration retrieval
_today: datetime.date = datetime.date.today()
_path_user_home: str = pwd.getpwuid(os.getuid())[0]
_path_dot_cabinet: str = os.path.join(f"/home/{_path_user_home}/.cabinet")
_path_backend: str = cab.get("path", "cabinet", "log-backup") or f"{_path_dot_cabinet}/log-backup"
_path_zshrc: str = os.path.join(f"/home/{_path_user_home}/.zshrc")
_path_notes: str = cab.get("path", "notes") or f"{_path_dot_cabinet}/notes"
_log_path_today: str = os.path.join(cab.path_log, str(_today))
_log_path_backend: str = os.path.join(_path_backend, "log")
_log_path_backups: str = cab.get("path", "backups") or f"{_path_dot_cabinet}/backups"
_log_backups_max: int = cab.get("backups", "log_backup_limit", return_type=int) or 14
_log_backups_location: str = os.path.join(_log_path_backups, "log")
_bedtime_key: str = os.path.join(_path_backend, "log", "keys", "BEDTIME")

# retrieve reminders count
_reminders_count = cab.get("remindmail", "sent_today", return_type=int) or -1

# log the reminders count
with open(os.path.join(_log_path_backend, "log_reminders.csv"), "a+", encoding="utf-8") as file_rmm:
    file_rmm.write(f"\n{_today},{_reminders_count}")

# ensure backend directories exist
directories = ["cron", "bash", "cabinet", "notes"]
for directory in directories:
    os.makedirs(os.path.join(_log_path_backend, directory), exist_ok=True)

# back up key files
backup_commands = [
    f"crontab -l > '{os.path.join(_log_path_backend, 'cron', f'Cron {_today}.md')}'",
    f"cp -r {_path_zshrc} '{os.path.join(_log_path_backend, 'bash', f'Bash {_today}.md')}'",
    f"zip -r '{os.path.join(_log_path_backend, 'notes', f'notes {_today}.zip')}' {_path_notes}",
    f"zip -r '{os.path.join(_log_backups_location, f'log folder backup {_today}.zip')}'\
        {_log_path_backend} --exclude='{os.path.join(_log_path_backend, 'songs', '*')}'",
]

try:
    for command in backup_commands:
        subprocess.run(command, shell=True, check=True)
except subprocess.CalledProcessError as error:
    cab.log(f"Command failed: {command} with error: {str(error)}", level="error")
except OSError as error:
    cab.log(f"OS error for: {command} with error: {str(error)}", level="error")

# prune log folder backups exceeding the limit (currently 14)
cab.log(f"Pruning {_log_backups_location}...")
zip_files = glob.glob(f"{_log_backups_location}/*.zip")
zip_files.sort(key=os.path.getmtime)
excess_count = len(zip_files) - _log_backups_max
for i in range(excess_count):
    os.remove(zip_files[i])

# publish bedtime limit
bedtime_output = json.dumps(cab.get("bedtime", "limit"))
os.makedirs(os.path.dirname(_bedtime_key), exist_ok=True)

try:
    with open(_bedtime_key, "x", encoding="utf-8") as file:
        file.write(bedtime_output)
except FileExistsError:
    with open(_bedtime_key, "w", encoding="utf-8") as file:
        file.write(bedtime_output)
except (IOError, OSError) as error:
    cab.log(f"Could not write bedtime key: {error}", level="error")

# append Spotify statistics
_spotify_log: list = cab.get_file_as_array("LOG_SPOTIFY.log", file_path=_log_path_today) or []
_spotify_log_formatted: str = "No Data"

if _spotify_log:
    # Filter out only WARNING, ERROR, or CRITICAL messages
    issues = [log for log in _spotify_log \
        if "WARNING" in log or "ERROR" in log or "CRITICAL" in log]

    if issues:
        _spotify_log_formatted = "<br>".join(issues)
    else:
        _spotify_log_formatted = "Looks good!"

_status_email += f"<b>Spotify Stats:</b><br>{_spotify_log_formatted}<br><br>"

# append daily log analysis
_daily_log_file = cab.get_file_as_array(f"LOG_DAILY_{_today}.log", file_path=_log_path_today) or []

_daily_log_issues: list = [line for line in _daily_log_file \
    if "ERROR" in line or "WARN" in line or "CRITICAL" in line]
if _daily_log_issues:
    _daily_log_filtered: str = "<br>".join(_daily_log_issues)
    _status_email += f"<b>Warning/Error/Critical Log:</b><br>{_daily_log_filtered}<br><br>"

# append weather data
weather_data = cab.get("weather", "data") or {}
if weather_data:
    _status_email += f"""
        <b>Weather Tomorrow:</b><br>
        <font face='monospace'>
            High: {weather_data.get('tomorrow_high', 'N/A')}°
            and {weather_data.get('tomorrow_conditions', 'No data')}
            <br>
                Sunrise: {weather_data.get('tomorrow_sunrise', 'No data')}
            <br>
                Sunset:  {weather_data.get('tomorrow_sunset', 'No data')}
            <br><br>
        </font>
    """

# send the email
mail.send(f"Daily Status - {_today}", _status_email)
