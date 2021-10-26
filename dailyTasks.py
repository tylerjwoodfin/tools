# ReadMe
# Sends an email alert if it's "nice" outside
# Dependencies: requests (pip install requests), secureData (my internal function to grab nonpublic variables from a secure folder)
# Note: weatherAPIKey should be obtained for free through openweathermap.org.

import requests
import datetime
import time
import mail
from decimal import Decimal as d
import random
import sys
import pwd
import os

userDir = pwd.getpwuid(os.getuid())[0]

sys.path.insert(0, f'/home/{userDir}/Git/SecureData')
import secureData

secureData.log("Started Daily Tasks")

spotify_count = secureData.variable("SPOTIPY_SONG_COUNT")
spotify_avg_year = secureData.variable("SPOTIPY_AVERAGE_YEAR")

daily_log = '<br>'.join(secureData.array("dailyLog"))
daily_log = f"<font face='monospace'>{daily_log}</font>"
daily_log = f"<b>Daily Log:</b><br>{daily_log}<br><br>"
daily_log = "Dear Tyler,<br><br>This is your daily status report.<br><br>" + daily_log

daily_log += f"<b>Spotify Stats:</b><br>You have {spotify_count} songs; the mean song is from {spotify_avg_year}.<br><br>"

logPath="/var/www/html/Logs"

today = os.popen("date +%Y-%m-%d").read()

# create these folders in case they don't exist for some reason
os.system(f"mkdir -p {logPath}/tasks")
os.system(f"mkdir -p {logPath}/Cron")
os.system(f"mkdir -p {logPath}/Bash")

secureData.log("Tasks, Cron, and Bash copied to Log folder.")

# chmod 777 -R "$logPath/Tasks"
# chmod 777 -R "$logPath/Cron"
# chmod 777 -R "$logPath/Bash"

# Git Status
git_status = os.popen('cd /var/www/html; git log -1').read().replace("\n", "<br>")

lastCommitTime = int(os.popen('cd /var/www/html; git log -1 --format="%at"').read())
now = int(os.popen("date +%s").read())

if(now - lastCommitTime > 7200):
    daily_log = f"Your last Git commit to your website was before today:<br><br>{git_status}<br><br>Please double check spot.py.<br><br>" + daily_log
    mail.send(f"Daily Status - Check Git Commits - {today}", daily_log)
else:
    daily_log += f"<br><br><br><b>✔ Git Up to Date:</b><br>{git_status}"
    mail.send(f"Daily Status - {today}", daily_log)

# clear daily log
secureData.write("dailyLog", "")
secureData.log("Cleared Daily Log")