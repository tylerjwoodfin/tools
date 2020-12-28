# Dependencies
Python 3
msmtp (sudo apt-get install msmtp msmtp-mta) (config file: sudo nano /etc/msmtprc)

# Description
My website is hosted on my Raspberry Pi 4 at 192.168.1.123. I have a second Raspberry Pi as an alarm system at 192.168.1.124. 
This tool should be added to my Crontab on both devices to periodically ping each other and send an email if the other is down.

# Usage (no parameters)
python /path/to/main.py