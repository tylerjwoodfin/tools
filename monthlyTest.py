# ReadMe
# Mail was installed using msmtp. sudo apt-get install msmtp msmtp-mta
# Config file: sudo nano /etc/msmtprc

import os, secureData

os.system("echo \"" + "This is a test file used to test email, network, and Git functionality\"")
os.system("echo \"Testing Email:\"")

os.system("sudo bash sendEmail.sh " + secureData.variable("email") + "\"Monthly Raspberry Pi Test\" \"This is a monthly system test for the Raspberry Pi.\"")