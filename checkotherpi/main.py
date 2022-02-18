import os
import sys
import socket

from securedata import mail

s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.connect(("8.8.8.8", 80))
myIP = s.getsockname()[0]
s.close()

hostname = "192.168.0.123"

if myIP == "192.168.0.123":
    hostname = "192.168.0.124"

response = -1

for i in range(2):
    response = os.system("ping -c 1 " + hostname)

    if response == 0:
        sys.exit(0)

print(response)
mail.send(f"{hostname} is Down", f"Your server at " + hostname + " is down.")
