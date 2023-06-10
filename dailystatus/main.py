"""
This script generates a daily status email with key information and sends it to me each evening.

The script performs the following tasks:
- Collects various data and statistics related to my activities
- Backs up important files such as cron, bash, and notes
- Prunes excess log backups
- Retrieves and includes Spotify statistics
- Retrieves and includes the daily log file
- Retrieves and includes weather information for tomorrow
- Sends the generated status email

The script relies on the following external modules:
- `remindmail_utils` from the `remind` package for handling reminders
- `Cabinet` for accessing configuration settings and file utilities
- `Mail` for sending email notifications

Note: This code snippet is a personal script intended only for the developer.
Additional configuration is required to run successfully on your machine.
"""


import os
import pwd
import datetime
import glob
import subprocess

from remind import remindmail_utils
from cabinet import Cabinet, Mail

# Add the openai directory to the sys path
cab = Cabinet()
mail = Mail()
status_email_alerts = []

STATUS_EMAIL = "Dear Tyler,<br><br> This is your daily status report.<br><br>"

DIR_USER = pwd.getpwuid(os.getuid())[0]
TODAY = datetime.date.today()
PATH_BACKEND = cab.get("path", "cabinet", "log-backup")
PATH_LOG_BACKEND = f"{PATH_BACKEND}/log"
PATH_BASHRC = f"/home/{DIR_USER}/.bashrc"
PATH_NOTES = cab.get('path', 'notes')
PATH_LOG_TODAY = f"{cab.path_log}{TODAY}/"

LOG_BACKUPS_MAX = cab.get("backups", "log_backup_limit") or 14
LOG_BACKUPS_LOCATION = f"{cab.get('path', 'backups')}/log"

# get steps
STEPS_COUNT = -1
STEPS_COUNT_FILE = cab.get_file_as_array(
    "cabinet/steps.md", file_path=PATH_BACKEND)

if STEPS_COUNT_FILE:
    STEPS_COUNT = STEPS_COUNT_FILE[0].split(" ")[0].replace(",", "")

# log steps
with open(f"{PATH_LOG_BACKEND}/log_steps.csv", "a+", encoding="utf-8") as file_steps:
    file_steps.write(f"\n{TODAY},{STEPS_COUNT}")

# get reminders sent
REMINDERS_COUNT = remindmail_utils.RemindMailUtils().get_sent_today() or -1

# log reminders
with open(f"{PATH_LOG_BACKEND}/log_reminders.csv", "a+", encoding="utf-8") as file_rmm:
    file_rmm.write(f"\n{TODAY},{REMINDERS_COUNT}")


# create backend folders
print(f"\nCreating folders in {PATH_LOG_BACKEND}, if necessary")

directories = ["cron", "bash", "cabinet", "notes"]
for directory in directories:
    os.system(f"mkdir -p {os.path.join(PATH_LOG_BACKEND, directory)}")

# Backup cron, bash, notes
cab.log("Backing up key files...\n")

try:
    subprocess.run(
        f"crontab -l > '{PATH_LOG_BACKEND}/cron/Cron {TODAY}.md'", shell=True, check=True)
    subprocess.run(
        f"cp -r {PATH_BASHRC} '{PATH_LOG_BACKEND}/bash/Bash {TODAY}.md'", shell=True, check=True)
    subprocess.run(
        f"zip -r '{PATH_LOG_BACKEND}/notes/notes {TODAY}.zip' {PATH_NOTES}", shell=True, check=True)
    subprocess.run(
        f"zip -r '{LOG_BACKUPS_LOCATION}/log folder backup {TODAY}.zip' \
{PATH_LOG_BACKEND} --exclude='{PATH_LOG_BACKEND}/songs/*'",
        shell=True, check=True)
except subprocess.CalledProcessError as error:
    cab.log(f"Could not create ZIP: {str(error)}", level="error")

# delete log folder backups above a certain size (default: 14)
cab.log(f"Pruning {LOG_BACKUPS_LOCATION}...")
zip_files = glob.glob(f"{LOG_BACKUPS_LOCATION}/*.zip")
zip_files.sort(key=os.path.getmtime)
excess_count = len(zip_files) - LOG_BACKUPS_MAX

if excess_count > 0:
    for i in range(excess_count):
        os.remove(zip_files[i])

cab.log(f"Cron, Bash, Notes, and remind.md copied to {PATH_LOG_BACKEND}.")

# spotify stats
spotify_count = cab.get("spotipy", "total_tracks")
spotify_avg_year = cab.get("spotipy", "average_year")
SPOTIFY_STATS = "<b>Spotify Stats:</b><br>"


spotify_log_array = cab.get_file_as_array(
    "LOG_SPOTIFY.log", file_path=PATH_LOG_TODAY)

if spotify_log_array is not None:
    SPOTIFY_LOG = "<font face='monospace'>" + \
        '<br>'.join(cab.get_file_as_array(
            "LOG_SPOTIFY.log", file_path=PATH_LOG_TODAY)) + "</font><br><br>"

    if "ERROR —" in SPOTIFY_LOG:
        status_email_alerts.append('Spotify')
        SPOTIFY_STATS += "Please review your songs! We found some errors.<br><br>"

SPOTIFY_STATS += f"""
    You have {spotify_count} songs; the mean song is from {spotify_avg_year}.<br><br>
    """

if 'Spotify' in status_email_alerts and spotify_log_array is not None:
    SPOTIFY_STATS += SPOTIFY_LOG

# daily log
daily_log_file_array = cab.get_file_as_array(
    f"LOG_DAILY_{TODAY}.log", file_path=PATH_LOG_TODAY)
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

SENT_TODAY = " was" if REMINDERS_COUNT == 1 else "s were"
STATUS_EMAIL += f"<b>Reminders:</b><br>{REMINDERS_COUNT} reminder{SENT_TODAY} sent today.<br><br>"

# weather
weather_data = cab.get("weather", "data")
WEATHER_DATA_TEXT = "Unavailable"
if weather_data:
    WEATHER_DATA_TEXT = f"""
        <b>Weather Tomorrow:</b><br><font face='monospace'>
        {weather_data['tomorrow_high']}° and {weather_data['tomorrow_conditions']}.
        <br> 
        Sunrise:
        {weather_data['tomorrow_sunrise']}
        <br>
        Sunset:&nbsp;&nbsp;{weather_data['tomorrow_sunset']}
        <br><br></font>
        """

STATUS_EMAIL += WEATHER_DATA_TEXT

STATUS_EMAIL.replace("<br><br><br><br>", "<br><br>")

STATUS_EMAIL_WARNINGS_TEXT = "- Check " + \
    ', '.join(status_email_alerts) + \
    " " if len(status_email_alerts) > 0 else ""

mail.send(f"Daily Status {STATUS_EMAIL_WARNINGS_TEXT}- {TODAY}", STATUS_EMAIL)
