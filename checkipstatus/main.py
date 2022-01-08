import json
import os
import sys
from requests import get

# for `mail`
currentdir = os.path.dirname(os.path.realpath(__file__))
parentdir = os.path.dirname(currentdir)
sys.path.append(parentdir)

from securedata import securedata
import mail

currentIP = securedata.variable("currentIP")
email = securedata.variable("email")

print("Updating IP Address, " + email)

ip = get('https://api.ipify.org?format=json').text
discoveredIP = json.loads(ip)["ip"]

print ("Found " + discoveredIP + ", currently " + currentIP + ".")

# IP was updated
if(currentIP == discoveredIP):
    print("No change.")
else:
    print("New IP! Updating and sending email.")
    securedata.write("currentIP", discoveredIP)
    
    # Replace OVPN file with new IP
    newLine = "remote " + discoveredIP + " 1194"
    vpnFile = securedata.file("tyler.cloud.ovpn", "/home/pi/ovpns")
    
    vpnFile = vpnFile.split("remote ")[0] + newLine + vpnFile.split(" 1194")[1]
    securedata.write("tyler.cloud.ovpn", vpnFile, "/home/pi/ovpns")
    
    # Send email
    message = """
    Your public IP was updated from %s to %s. To keep tyler.cloud, update your Namecheap settings.<br><br>
    To keep TylerVPN, please switch your OVPN file to the one located in (probably) Dropbox/Backups/securedata.""" % (currentIP, discoveredIP)
    
    mail.send("IP Updated - new OVPN file", message)
