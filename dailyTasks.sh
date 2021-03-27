# ReadMe
# This formats my Tasks.txt file to monospace, then emails it to me. The associated cron job first pulls from Dropbox using Rclone.
# Usage: sudo bash dailyTasks.sh
#!/bin/bash

# Execute something in Python3
split() {
  readarray -d $2 -t strarr <<< "$1"

  echo "${strarr[$3]}"
}

# Read certain variables from the secure data folder
email_pi=$(</home/pi/Git/SecureData/email_pi)
email=$(</home/pi/Git/SecureData/email)

tasks="/home/pi/Notes/Tasks.txt"
cron="/var/spool/cron/crontabs/pi"

today=$(date +%Y-%m-%d)
logPath="/var/www/html/Logs/"

# copy to the Log folder to back up
mkdir -p $logPath/Tasks 			 # create in case it's not there for some reason
mkdir -p $logPath/Cron	 			 # create in case it's not there for some reason
cp -r $tasks "$logPath/Tasks/Tasks $today.txt"
cp -r $cron "$logPath/Cron/Cron $today.txt"
chmod 777 -R "$logPath/Cron"
echo "Tasks and Cron copied to Log folder."

body="Dear Tyler,<br><br>"

# Replace \n with <br> and replace ' ' with &nbsp;
tasks=$(sed -e 's|^|<br>|' -e 's|\s|\&nbsp;|g' $tasks)

# Calculate time since last log Git commit
cd /var/www/html
gitOutput=$(git show -s --format=%ct HEAD)
now=$(date +%s)
result=`expr $now - $gitOutput`
resultText="Your last Git commit to your website was before today:<br><br>"
gitStatus=$(git log -1)
gitStatus=$(echo -e ${gitStatus//$'\n'/<br>})
conclusion="<br><br>Typically, spot.py pushes logs to the website repository on a daily basis. Please double check!"

body="$body$resultText$gitStatus$conclusion"

body=${body//$\n/<br>}

# Send Email
echo "Git commit was $result seconds ago"

cd /home/pi/Git/Tools

if [ $result -gt 7200 ]
then
  python3 -c "import mail; print(mail.send('Check Git Commits $today','$body'))"
else
  python3 -c "import mail; mail.send('Git up to Date $today','$gitStatus')"
fi
