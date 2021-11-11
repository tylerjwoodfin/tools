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

status_email_warnings = []
status_email = "Dear Tyler,<br><br>This is your daily status report.<br><br>"

# Run Backups
logPath="/var/www/html/Logs"
cron=f"/var/spool/cron/crontabs/{userDir}"
bash=f"/home/{userDir}/.bashrc"
today = os.popen("date +%Y-%m-%d").read().strip()

os.system(f"mkdir -p {logPath}/Tasks")
os.system(f"mkdir -p {logPath}/Cron")
os.system(f"mkdir -p {logPath}/Bash")

os.system(f"cp -r {secureData.piTasksNotesPath + 'Tasks.txt'} '{logPath}/Tasks/Tasks {today}.txt'")
os.system(f"cp -r {cron} '{logPath}/Cron/Cron {today}.txt'")
os.system(f"cp -r {bash} '{logPath}/Bash/Bash {today}.txt'")

secureData.log(f"Tasks, Cron, and Bash copied to {logPath}.")

# Push today's Log files to Github
os.system("cd /var/www/html; git pull; git add -A; git commit -m 'Updated Logs'; git push")
secureData.log("Updated Git")

# Spotify Stats
spotify_count = secureData.variable("SPOTIPY_SONG_COUNT")
spotify_avg_year = secureData.variable("SPOTIPY_AVERAGE_YEAR")
spotify_log = "<font face='monospace'>" + '<br>'.join(secureData.array("LOG_SPOTIFY")) + "</font><br><br>"
spotify_stats = "<b>Spotify Stats:</b><br>"

if "Error: " in spotify_log:
    status_email_warnings.append('Spotify')
    spotify_stats += "Please review your songs! We found some errors.<br><br>"

spotify_stats += spotify_log
spotify_stats += f"You have {spotify_count} songs; the mean song is from {spotify_avg_year}.<br><br>"

# Daily Log
daily_log = "<b>Daily Log:</b><br><font face='monospace'>" + '<br>'.join(secureData.array("LOG_DAILY")) + "</font><br><br>"


status_email += daily_log
status_email += spotify_stats

# Git Status
git_status = os.popen('cd /var/www/html; git log -1').read().replace("\n", "<br>")

lastCommitTime = int(os.popen('cd /var/www/html; git log -1 --format="%at"').read())
now = int(os.popen("date +%s").read())

if(now - lastCommitTime > 7200):
    status_email_warnings.append("Git")
    status_email = f"<b>❌ Check Git:</b><br>Your last Git commit to your website was before today:<br><br>{git_status}<br><hr><br><br>{status_email}"
else:
    status_email += f"<br><br><br><b>✔ Git Up to Date:</b><br>{git_status}"

status_email_warnings_text = "- Check " + ', '.join(status_email_warnings) + " " if len(status_email_warnings) else ""

mail.send(f"Daily Status {status_email_warnings_text}- {today}", status_email)

# clear daily log
secureData.log(clear=True)
secureData.log(clear=True, logName="LOG_SPOTIFY")
