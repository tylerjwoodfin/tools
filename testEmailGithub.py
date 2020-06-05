# ReadMe
# Mail was installed using msmtp. sudo apt-get install msmtp msmtp-mta
# Config file: sudo nano /etc/msmtprc

import os, secureData

os.system("echo \"" + "This is a test file used to test email, network, and Git functionality\"")
os.system("echo \"Testing Email:\"")

os.system("echo \"" + "Hi Tyler,\n\nThis is a test email from your Raspberry Pi." + "\" | mail -s \"Raspberry Pi Test Email\" " + secureData.variable("email"))

os.system("echo \"Email Sent.\"")