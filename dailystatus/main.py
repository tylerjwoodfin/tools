import pwd
import os
import datetime
from securedata import securedata, mail
from sys import exit


securedata.log("Started Daily Tasks")

status_email_alerts = []
status_email = "Dear Tyler,<br><br>This is your daily status report.<br><br>"

DIR_USER = pwd.getpwuid(os.getuid())[0]
TODAY = datetime.date.today()
PATH_BACKEND = securedata.getItem("path", "securedata", "log-backup")
PATH_LOG_BACKEND = f"{PATH_BACKEND}/log"
PATH_CRON = f"/var/spool/cron/crontabs/{DIR_USER}"
PATH_BASHRC = f"/home/{DIR_USER}/.bashrc"
PATH_LOG_TODAY = f"{securedata.getItem('path', 'log')}/{TODAY}/"

# copy settings.json to root
os.system(f"cp {securedata.getConfigItem('path_securedata')}/settings.json {securedata.getItem('path', 'securedata', 'all-users')}/settings.json")

os.system(f"mkdir -p {PATH_LOG_BACKEND}/tasks")
os.system(f"mkdir -p {PATH_LOG_BACKEND}/cron")
os.system(f"mkdir -p {PATH_LOG_BACKEND}/bash")

os.system(
    f"cp -r {securedata.getItem('path', 'notes', 'local') + '/remind.md'} '{PATH_LOG_BACKEND}/tasks/remind {TODAY}.md'")
os.system(f"cp -r {PATH_CRON} '{PATH_LOG_BACKEND}/cron/Cron {TODAY}.md'")
os.system(f"cp -r {PATH_BASHRC} '{PATH_LOG_BACKEND}/bash/Bash {TODAY}.md'")

securedata.log(f"Cron, Bash, and remind.md copied to {PATH_LOG_BACKEND}.")

# push daily log to github
os.system(
    f"cd {PATH_BACKEND}; git pull; git add -A; git commit -m 'Updated Logs'; git push")
securedata.log("Updated Git")

# spotify stats
spotify_count = securedata.getItem("spotipy", "total_tracks")
spotify_avg_year = securedata.getItem("spotipy", "average_year")
spotify_log = "<font face='monospace'>" + \
    '<br>'.join(securedata.getFileAsArray(
        f"LOG_SPOTIFY.log", filePath=PATH_LOG_TODAY)) + "</font><br><br>"
spotify_stats = "<b>Spotify Stats:</b><br>"

if "ERROR —" in spotify_log:
    status_email_alerts.append('Spotify')
    spotify_stats += "Please review your songs! We found some errors.<br><br>"

spotify_stats += f"You have {spotify_count} songs; the mean song is from {spotify_avg_year}.<br><br>"

if 'Spotify' in status_email_alerts:
    spotify_stats += spotify_log

# daily log
daily_log_file_array = securedata.getFileAsArray(
    f"LOG_DAILY {TODAY}.log", filePath=PATH_LOG_TODAY)
daily_log_file = '<br>'.join(daily_log_file_array)

if "ERROR —" in daily_log_file or "CRITICAL —" in daily_log_file:
    status_email_alerts.append("Errors")
if "WARNING —" in daily_log_file:
    status_email_alerts.append("Warnings")

daily_log_filtered = '<br>'.join([item for item in daily_log_file_array if (
    "ERROR" in item or "WARN" in item or "CRITICAL" in item)])

if len(daily_log_filtered) > 0:
    status_email += f"<b>Warning/Error/Critical Log:</b><br><font face='monospace'>{daily_log_filtered}</font><br><br>"

status_email += spotify_stats

# weather
weather_data = securedata.getItem("weather", "data")
weather_data_text = "Unavailable"
if weather_data:
    weather_data_text = f""" <b>Weather Tomorrow:</b><br>{weather_data['tomorrow_high']}° and {weather_data['tomorrow_conditions']}.<br> Sunrise:
                        {weather_data['tomorrow_sunrise']}<br>Sunset: {weather_data['tomorrow_sunset']}<br><br>"""

status_email += weather_data_text

# git status
git_status = os.popen(
    f"cd {PATH_BACKEND}; git log -1; git log -1 --pretty=%B").read().replace("\n", "<br>")

try:
    lastCommitTime = int(
        os.popen(f'cd {PATH_BACKEND}; git log -1 --format="%at"').read())
except Exception as e:
    lastCommitTime = 0

now = int(os.popen("date +%s").read())

if now - lastCommitTime > 7200:
    status_email_alerts.append("Git")
    status_email = f"<b>❌ Check Git:</b><br>Your last Git commit to the backend was before today:<br><br>{git_status}<br><hr><br><br>{status_email}"
else:
    status_email += f"<br><br><br><b>✔ Git Up to Date:</b><br>{git_status}"

status_email.replace("<br><br><br><br>", "<br><br>")

status_email_warnings_text = "- Check " + \
    ', '.join(status_email_alerts) + \
    " " if len(status_email_alerts) else ""

mail.send(f"Daily Status {status_email_warnings_text}- {TODAY}", status_email)
