import os, sys, socket

currentdir = os.path.dirname(os.path.realpath(__file__))
parentdir = os.path.dirname(currentdir)
sys.path.append(parentdir)

import secureData, mail

s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.connect(("8.8.8.8", 80))
myIP = s.getsockname()[0]
s.close()

hostname = "192.168.1.123"

if myIP == "192.168.1.123":
    hostname = "192.168.1.124"

response = os.system("ping -c 1 " + hostname)

if response != 0:
    email = secureData.getItem("email")
    message = "Your server at " + hostname + " is down."
    mail.send(hostname + " is down", message)
