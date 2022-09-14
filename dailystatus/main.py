''' Used to send daily weather/Spotify/Git updates '''

import pwd
import os
import datetime
import subprocess
from securedata import securedata, mail


securedata.log("Started Daily Tasks")

status_email_alerts = []
STATUS_EMAIL = "Dear Tyler,<br><br>This is your daily status report.<br><br>"

DIR_USER = pwd.getpwuid(os.getuid())[0]
TODAY = datetime.date.today()
PATH_BACKEND = securedata.getItem("path", "securedata", "log-backup")
PATH_LOG_BACKEND = f"{PATH_BACKEND}/log"
PATH_CRON = f"/var/spool/cron/crontabs/{DIR_USER}"
PATH_BASHRC = f"/home/{DIR_USER}/.bashrc"
PATH_LOG_TODAY = f"{securedata.getItem('path', 'log')}/{TODAY}/"

# copy settings.json to root
CMD_COPY = f"""
    cp {securedata.getConfigItem('path_securedata')}/settings.json
    {securedata.getItem('path', 'securedata', 'all-users')}/settings.json
    """
os.system(CMD_COPY)

os.system(f"mkdir -p {PATH_LOG_BACKEND}/tasks")
os.system(f"mkdir -p {PATH_LOG_BACKEND}/cron")
os.system(f"mkdir -p {PATH_LOG_BACKEND}/bash")

# copy key files to backend
CMD_COPY_TASKS = f"""
    cp -r {securedata.getItem('path', 'notes', 'local') + '/remind.md'}
    '{PATH_LOG_BACKEND}/tasks/remind {TODAY}.md'
    """
os.system(CMD_COPY_TASKS)
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
SPOTIFY_STATS = "<b>Spotify Stats:</b><br>"
SPOTIFY_LOG = "<font face='monospace'>" + \
    '<br>'.join(securedata.getFileAsArray(
        "LOG_SPOTIFY.log", filePath=PATH_LOG_TODAY)) + "</font><br><br>"

if "ERROR —" in SPOTIFY_LOG:
    status_email_alerts.append('Spotify')
    SPOTIFY_STATS += "Please review your songs! We found some errors.<br><br>"

SPOTIFY_STATS += f"""
    You have {spotify_count} songs; the mean song is from {spotify_avg_year}.<br><br>
    """

if 'Spotify' in status_email_alerts:
    SPOTIFY_STATS += SPOTIFY_LOG

# daily log
daily_log_file_array = securedata.getFileAsArray(
    f"LOG_DAILY {TODAY}.log", filePath=PATH_LOG_TODAY)
DAILY_LOG_FILE = '<br>'.join(daily_log_file_array)

if "ERROR —" in DAILY_LOG_FILE or "CRITICAL —" in DAILY_LOG_FILE:
    status_email_alerts.append("Errors")
if "WARNING —" in DAILY_LOG_FILE:
    status_email_alerts.append("Warnings")

DAILY_LOG_FILTERED = '<br>'.join([item for item in daily_log_file_array if (
    "ERROR" in item or "WARN" in item or "CRITICAL" in item)])

if len(DAILY_LOG_FILTERED) > 0:
    STATUS_EMAIL += f"""
        <b>Warning/Error/Critical Log:</b><br>
        <font face='monospace'>
        {DAILY_LOG_FILTERED}
        </font><br><br>
        """

STATUS_EMAIL += SPOTIFY_STATS

# weather
weather_data = securedata.getItem("weather", "data")
WEATHER_DATA_TEXT = "Unavailable"
if weather_data:
    WEATHER_DATA_TEXT = f"""
        <b>Weather Tomorrow:</b><br><font face='monospace'>
        {weather_data['tomorrow_high']}° and {weather_data['tomorrow_conditions']}.
        <br> 
        Sunrise:
        {weather_data['tomorrow_sunrise']}
        <br>
        Sunset: {weather_data['tomorrow_sunset']}
        <br><br></font>
        """

STATUS_EMAIL += WEATHER_DATA_TEXT

# git status
git_status = os.popen(
    f"cd {PATH_BACKEND}; git log -1 --pretty='format:%cD<br>%s'").read().replace("\n", "<br>")
git_status = f"<font face='monospace'>{git_status}</font>"

try:
    CMD_GLOG = subprocess.check_output(
        f'cd {PATH_BACKEND}; git log -1 --format="%at"', stderr=subprocess.STDOUT)
    LAST_COMMIT_TIME = int(CMD_GLOG)
except subprocess.CalledProcessError as e:
    LAST_COMMIT_TIME = 0

NOW = int(os.popen("date +%s").read())

if NOW - LAST_COMMIT_TIME > 7200:
    status_email_alerts.append("Git")
    STATUS_EMAIL = f"""
    <b>❌ Check Git:</b><br>
    Your last Git commit to the backend was before today:
    <br><br>
    {git_status}
    <br>
    <hr>
    <br><br>
    {STATUS_EMAIL}
    """
else:
    STATUS_EMAIL += f"<br><b>✔ Backend Up to Date:</b><br>{git_status}"


STATUS_EMAIL.replace("<br><br><br><br>", "<br><br>")

STATUS_EMAIL_WARNINGS_TEXT = "- Check " + \
    ', '.join(status_email_alerts) + \
    " " if len(status_email_alerts) > 0 else ""

mail.send(f"Daily Status {STATUS_EMAIL_WARNINGS_TEXT}- {TODAY}", STATUS_EMAIL)
