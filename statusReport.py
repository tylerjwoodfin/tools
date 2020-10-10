# ReadMe
# Sends a weekly time card reminder to my coworkers (stored in a secured file)
# Mail was installed using msmtp. sudo apt-get install msmtp msmtp-mta
# Config file: sudo nano /etc/msmtprc

import os, secureData

sentFrom = "Raspberry Pi"
email = secureData.variable("email_work")

message = "Hi Tyler,<br><br>Please remember to send your weekly status report to Mark in the form:<br><br><ul><li>Customer Projects %</li><li>Internal Projects %</li><li>Training/Overhead/Unutilized</li><li>PTO/vacation/time off</li><br><br>Thanks,<br><br>- " + sentFrom + "<br><br>Reply STOP to unsubscribe"
    
# send email <to> <subject> <message> <from (optional)>
os.system("bash /home/pi/Tools/sendEmail.sh " + email + " \"Status Report Reminder\" \"" + message + "\" " + "\"" + sentFrom + "\"")

