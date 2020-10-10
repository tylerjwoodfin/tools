# ReadMe
# Sends a weekly time card reminder to my coworkers (stored in a secured file)
# Mail was installed using msmtp. sudo apt-get install msmtp msmtp-mta
# Config file: sudo nano /etc/msmtprc

import os, secureData

sentFrom = "Raspberry Pi"
contacts = secureData.array("timecardEmails")

for i in contacts:
    if(i.split(":")[0] == "hub"):
        sentFrom = "Oracle Austin Hub Team"

    message = "Hi " + i.split(":")[1] + ",<br><br>Please remember to enter your time.<br><br>Thanks,<br><br>- " + sentFrom + "<br><br>Reply STOP to unsubscribe"
    
    # send email <to> <subject> <message> <from (optional)>
    os.system("bash /home/pi/Tools/sendEmail.sh " + i.split(":")[2] + " \"Timecard Reminder\" \"" + message + "\" " + "\"" + sentFrom + "\"")
