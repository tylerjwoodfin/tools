''' Used to send daily weather/Spotify updates '''

import pwd
import os
import datetime
import sys
from securedata import securedata, mail
sys.path.insert(0, securedata.getItem("path", "openai"))
import main as openai

securedata.log("Started Daily Tasks")

GREETING = ""
try:
    GREETING = openai.submit("give me a cute greeting for an email")
except Exception as error:
    securedata.log(f"Error fetching daily status greeting: {error}", level="warn")
status_email_alerts = []

STATUS_EMAIL = f"Dear Tyler,<br><br>{GREETING} This is your daily status report.<br><br>"

DIR_USER = pwd.getpwuid(os.getuid())[0]
TODAY = datetime.date.today()
PATH_BACKEND = securedata.getItem("path", "securedata", "log-backup")
PATH_LOG_BACKEND = f"{PATH_BACKEND}/log"
PATH_BASHRC = f"/home/{DIR_USER}/.bashrc"
PATH_LOG_TODAY = f"{securedata.getItem('path', 'log')}/{TODAY}/"

# get steps
STEPS_COUNT = -1
STEPS_COUNT_FILE = securedata.getFileAsArray(
    "securedata/steps.md", filePath=PATH_BACKEND)

if STEPS_COUNT_FILE:
    STEPS_COUNT = STEPS_COUNT_FILE[0].split(" ")[0].replace(",", "")

# log steps
with open(f"{PATH_LOG_BACKEND}/log_steps.csv", "a+", encoding="utf-8") as file_steps:
    file_steps.write(f"\n{TODAY},{STEPS_COUNT}")

# get reminders sent
REMINDERS_COUNT = securedata.getItem("remindmail", "sent_today") or 0

securedata.log("Setting remindmail -> sent_today to 0", level="debug")
securedata.setItem("remindmail", "sent_today", 0)
securedata.log(f"""remindmail -> sent_today is {securedata.getItem("remindmail", "sent_today")}""")

# log reminders
with open(f"{PATH_LOG_BACKEND}/log_reminders.csv", "a+", encoding="utf-8") as file_rmm:
    file_rmm.write(f"\n{TODAY},{REMINDERS_COUNT}")


# create backend folders
print(f"\nCreating folders in {PATH_LOG_BACKEND}, if necessary")
os.system(f"mkdir -p {PATH_LOG_BACKEND}/tasks")
os.system(f"mkdir -p {PATH_LOG_BACKEND}/cron")
os.system(f"mkdir -p {PATH_LOG_BACKEND}/bash")
os.system(f"mkdir -p {PATH_LOG_BACKEND}/securedata")

# copy key files to backend
print("Copying files to backend\n")
remind_src = f"{securedata.getItem('path', 'notes', 'local')}/remind.md"
remind_dst = f"{PATH_LOG_BACKEND}/tasks/remind {TODAY}.md"
os.system(f"cp -r {remind_src} '{remind_dst}'")

# copy cron to backup
os.system(f"crontab -l > '{PATH_LOG_BACKEND}/cron/Cron {TODAY}.md'")
os.system(f"cp -r {PATH_BASHRC} '{PATH_LOG_BACKEND}/bash/Bash {TODAY}.md'")

securedata.log(f"Cron, Bash, and remind.md copied to {PATH_LOG_BACKEND}.")

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

STATUS_EMAIL += f"""<b>Reminders:</b><br>{REMINDERS_COUNT} reminders were sent today.<br><br>"""

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
        Sunset:  {weather_data['tomorrow_sunset']}
        <br><br></font>
        """

STATUS_EMAIL += WEATHER_DATA_TEXT

STATUS_EMAIL.replace("<br><br><br><br>", "<br><br>")

STATUS_EMAIL_WARNINGS_TEXT = "- Check " + \
    ', '.join(status_email_alerts) + \
    " " if len(status_email_alerts) > 0 else ""

mail.send(f"Daily Status {STATUS_EMAIL_WARNINGS_TEXT}- {TODAY}", STATUS_EMAIL)
