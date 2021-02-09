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

    message = "Hi " + i.split(":")[1] + ",<br><br>Please remember to enter your time. Automatic time card emails from this system will be unavailable after February 19. Please consider using <a href='https://support.microsoft.com/en-us/office/set-or-remove-reminders-7a992377-ca93-4ddd-a711-851ef3597925'>reminders in Outlook</a>.<br><br>Thanks,<br><br>- " + sentFrom + "<br><br>Reply STOP to unsubscribe"
    
    # send email <to> <subject> <message> <from (optional)>
    os.system("bash /home/pi/Tools/sendEmail.sh " + i.split(":")[2] + " \"Timecard Reminder Deprecation Notice\" \"" + message + "\" " + "\"" + sentFrom + "\"")
