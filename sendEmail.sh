# ReadMe
# Sends emails using msmtp
# This script is used to avoid having to pass parameters every time
# Usage: bash sendEmail.sh <to> <subject> <message in HTML format> <sender name (optional)>
#!/bin/bash

# Assign variables
to=$1
subject=$2
message=$3
sender=$4

if [ -z "$4" ]; then
	sender="Raspberry Pi"
fi

# Log to syslog
logger "Sending Email: to $to, sub $subject, from $sender"

if echo $message | mail \
-a "From: $sender" \
-a "MIME-Version: 1.0" \
-a "Content-Type: text/html" \
-s "$subject" \
$to; then
	echo "Sent Email"
#	echo "to: $to"
#	echo "subject: $subject"
#	echo "message: $message"
#	echo "from: $sender"
else
	echo; echo "Usage: bash sendEmail.sh <to> <subject> <message in HTML format> <sender name (optional)>"
fi
