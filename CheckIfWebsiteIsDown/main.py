import os, sys, socket

currentdir = os.path.dirname(os.path.realpath(__file__))
parentdir = os.path.dirname(currentdir)
sys.path.append(parentdir)

import secureData

myIP = socket.gethostbyname(socket.gethostname())
hostname = "192.168.1.123"

if myIP == "192.168.1.123":
    hostname = "192.168.1.124"

response = os.system("ping -c 1 " + hostname)

if response != 0:
  email = secureData.variable("email")
  message = "Your server at " + hostname + " is down."
  os.system("bash /home/pi/Tools/sendEmail.sh " + email + " \"" + hostname + " is Down\" \"" + message + "\" " + "\"" + "Raspberry Pi" + "\"")