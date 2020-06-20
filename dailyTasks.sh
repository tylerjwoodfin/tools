# ReadMe
# This formats my Tasks.txt file to monospace, then emails it to me. The associated cron job first pulls from Dropbox using Rclone.
# Usage: sudo bash dailyTasks.sh
#!/bin/bash

# Read certain variables from the secure data folder
tasks="/home/pi/Notes/Tasks.txt"
email_pi=$(</home/pi/Tools/SecureData/email_pi)
email=$(</home/pi/Tools/SecureData/email)

today=$(date +%Y-%m-%d)
tasksCopy="/var/www/html/Logs/Tasks"

# copy to the Log folder to back up
mkdir -p $tasksCopy # in case it's not there for some reason
cp -r $tasks "$tasksCopy/Tasks $today.txt"
echo "Tasks copied to Log folder."

body="
<!DOCTYPE HTML PUBLIC \"-//W3C//DTD HTML 4.01 Transitional//EN\" \"http://www.w3.org/TR/html4/loose.dtd\">
<html>
<head><title></title>
</head>
<body>
Dear Tyler,<br><br>
Please review the following tasks:<br><font face='monospace'>"

# Replace \n with <br> and replace ' ' with &nbsp;
tasks=$(sed -e 's|^|<br>|' -e 's|\s|\&nbsp;|g' $tasks)

body="$body$tasks"

# Email the Tasks file
bash sendEmail.sh $email "Daily Tasks Review" "$body"
