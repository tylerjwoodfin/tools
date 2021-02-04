#!/bin/bash
# ReadMe: Fetches Pi's Gmail and displays it in the format: senderEmail \n email_content \n senderEmail2, etc.

username=$(</home/pi/Tools/SecureData/email_pi)
password=$(</home/pi/Tools/SecureData/email_pi_pw)

SHOW_COUNT=5 # No of recent unread mails to be shown

echo

curl  -u $username:$password --silent "https://mail.google.com/mail/feed/atom" | \
tr -d '\n' | sed 's:</entry>:\n:g' |\
 sed 's/.*<summary>\(.*\)<\/summary.*<author><name>\([^<]*\)<\/name><email>\([^<]*\).*/\3\n\1\n/' | \
head -n $(( $SHOW_COUNT * 3 ))
