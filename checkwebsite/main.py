import os, sys, socket

currentdir = os.path.dirname(os.path.realpath(__file__))
parentdir = os.path.dirname(currentdir)
sys.path.append(parentdir)

from securedata import securedata
import mail

s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.connect(("8.8.8.8", 80))
myIP = s.getsockname()[0]
s.close()

hostname = "192.168.1.123"

if myIP == "192.168.1.123":
    hostname = "192.168.1.124"

response = -1

for i in range(2):
    response = os.system("ping -c 1 " + hostname)

    if response == 0:
        sys.exit(0)

print(response)
mail.send(f"{hostname} is Down", f"Your server at " + hostname + " is down.")