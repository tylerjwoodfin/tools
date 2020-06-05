# ReadMe
# Sends a weekly time card reminder to my coworkers (stored in a secured file)
# Mail was installed using msmtp. sudo apt-get install msmtp msmtp-mta
# Config file: sudo nano /etc/msmtprc

import os, secureData

message = "Please remember to enter your time.\n\nThanks,\nTyler's Raspberry Pi\n\nReply STOP to unsubscribe"

contacts = secureData.array("timecardEmails")

for i in contacts:
	os.system("echo \"" + "Hi " + i.split(":")[0] +",\n\n" + message + "\" | mail -s \"Timecard Reminder\" " + i.split(":")[1])