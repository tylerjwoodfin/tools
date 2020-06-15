# ReadMe
# Sends a weekly time card reminder to my coworkers (stored in a secured file)
# Mail was installed using msmtp. sudo apt-get install msmtp msmtp-mta
# Config file: sudo nano /etc/msmtprc

import os, secureData

sentFrom = "Tyler's Raspberry Pi"
contacts = secureData.array("timecardEmails")

for i in contacts:
	if(i.split(":")[0] == "hub"):
		sentFrom = "- Oracle Austin Hub Team"

	message = "Please remember to enter your time.\n\nThanks,\n" + sentFrom + "\n\nReply STOP to unsubscribe"
	os.system("echo \"" + "Hi " + i.split(":")[1] +",\n\n" + message + "\" | mail -s \"Timecard Reminder\" " + i.split(":")[2])