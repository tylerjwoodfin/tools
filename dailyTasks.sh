# ReadMe
# This formats my Tasks.txt file to monospace, then emails it to me. The associated cron job first pulls from Dropbox using Rclone.
# Usage: sudo bash dailyTasks.sh
#!/bin/bash

# Execute something in Python3
split() {
  readarray -d $2 -t strarr <<< "$1"

  echo "${strarr[$3]}"
}

# Read certain variables from secureData
email_pi=$(</home/pi/Git/SecureData/email_pi)
email=$(</home/pi/Git/SecureData/email)
dailyLog=$(</home/pi/Git/SecureData/dailyLog)
tasks="/home/pi/Notes/Tasks.txt"
getTasks=$(<$tasks)
spotify_count=$(</home/pi/Git/SecureData/SPOTIPY_SONG_COUNT)
spotify_avg_year=$(</home/pi/Git/SecureData/SPOTIPY_AVERAGE_YEAR)

# format styling
dailyLog=$(echo -e ${dailyLog//$'\n'/<br>})
dailyLog="<font face='monospace'>$dailyLog</font>"
dailyLog="<b>Daily Log:</b><br>$dailyLog"

spotifyStats="<b>Spotify Stats:</b><br>You have $spotify_count songs; the mean song is from $spotify_avg_year."

getTasks=$(echo -e ${getTasks//$'\n'/<br>})
getTasks="<font face='monospace'>$getTasks</font>"
cron="/var/spool/cron/crontabs/pi"
bash="/home/pi/.bashrc"

today=$(date +%Y-%m-%d)
logPath="/var/www/html/Logs"

# copy to the Log folder to back up
mkdir -p $logPath/tasks       # create in case it's not there for some reason
mkdir -p $logPath/Cron        # create in case it's not there for some reason
mkdir -p $logPath/Bash        # create in case it's not there for some reason

cp -r $tasks "$logPath/Tasks/Tasks $today.txt"
cp -r $cron "$logPath/Cron/Cron $today.txt"
cp -r $bash "$logPath/Bash/Bash $today.txt"

chmod 777 -R "$logPath/Tasks"
chmod 777 -R "$logPath/Cron"
chmod 777 -R "$logPath/Bash"

echo "Tasks, Cron, and Bash copied to Log folder."

# Replace \n with <br> and replace ' ' with &nbsp;
tasks=$(sed -e 's|^|<br>|' -e 's|\s|\&nbsp;|g' $tasks)

# Calculate time since last log Git commit
cd /var/www/html
gitOutput=$(git show -s --format=%ct HEAD)
now=$(date +%s)
lastGitPush=`expr $now - $gitOutput`
gitStatus=$(git log -1)
gitStatus=$(echo -e ${gitStatus//$'\n'/<br>})

# compose email
emailBody="Dear Tyler,<br><br>This is your daily status report.<br><br>"
emailBody="$emailBody$dailyLog"
emailBody="$emailBody<br><br><b>Tasks:</b><br>$getTasks<br><br>$spotifyStats"
gitErrorText="Your last Git commit to your website was before today:<br><br>${gitStatus}<br><br>Please double check spot.py."

# Send Email
echo "Git commit was $lastGitPush seconds ago"

if [ $lastGitPush -gt 7200 ]
then
  emailBody="$gitErrorText<br><br>$emailBody"
  rmail "Daily Status - Check Git Commits - $today" "$emailBody"
else
  emailBody="$emailBody<br><br><b>✔ Git Up to Date:</b><br>$gitStatus"
  rmail "Daily Status - $today" "$emailBody"
fi

# clear daily Log
echo "" > /home/pi/Git/SecureData/dailyLog