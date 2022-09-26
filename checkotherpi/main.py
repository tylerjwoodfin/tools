"""
checkotherpi - see README.md
"""
import os
import sys
import socket

from securedata import mail

s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.connect(("8.8.8.8", 80))
MY_IP = s.getsockname()[0]
s.close()

HOSTNAME = "192.168.0.123"

if MY_IP == "192.168.0.123":
    HOSTNAME = "192.168.0.124"

RESPONSE = -1

for i in range(2):
    RESPONSE = os.system("ping -c 1 " + HOSTNAME)

    if RESPONSE == 0:
        sys.exit(0)

# sister device not found
print(RESPONSE)
mail.send(f"{HOSTNAME} is Down", f"Your server at {HOSTNAME} is down.")
