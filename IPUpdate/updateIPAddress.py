import json
import os
import sys
from requests import get

currentdir = os.path.dirname(os.path.realpath(__file__))
parentdir = os.path.dirname(currentdir)
sys.path.append(parentdir)
sys.path.append('/home/pi/Git/SecureData')

import secureData, mail

currentIP = secureData.variable("currentIP")
email = secureData.variable("email")

print("Updating IP Address, " + email)

ip = get('https://api.ipify.org?format=json').text
discoveredIP = json.loads(ip)["ip"]

print ("Found " + discoveredIP + ", currently " + currentIP + ".")

# IP was updated
if(currentIP == discoveredIP):
    print("No change.")
else:
    print("New IP! Updating and sending email.")
    secureData.write("currentIP", discoveredIP)
    
    # Replace OVPN file with new IP and email it
    newLine = "remote " + discoveredIP + " 1194"
    vpnFile = secureData.file("tyler.cloud.ovpn")
    
    vpnFile = vpnFile.split("remote ")[0] + newLine + vpnFile.split(" 1194")[1]
    secureData.write("tyler.cloud.ovpn", vpnFile)
    
    # Send email
    message = """
    Your public IP was updated from %s to %s. To keep tyler.cloud, update your Namecheap settings.<br><br>
    To keep TylerVPN, please switch your OVPN file to the one located in SecureData.""" % (currentIP, discoveredIP)
    
    mail.send("IP Updated - new OVPN file", message)
