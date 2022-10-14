"""
checkipstatus - see README
"""

import json
from requests import get
from securedata import securedata, mail

currentIP = securedata.getItem("currentIP")

print("Updating IP Address")

ip = get('https://api.ipify.org?format=json', timeout=30).text
discovered_IP = json.loads(ip)["ip"]

print(f"Found {discovered_IP}, currently {currentIP}")

# IP was updated
if currentIP == discovered_IP:
    print("No change.")
else:
    print("New IP! Updating and sending email.")
    securedata.setItem("currentIP", discovered_IP)

    # Replace OVPN file with new IP
    newLine = f"remote {discovered_IP} 1194"

    try:
        FILE_VPN = '\n'.join(securedata.getFileAsArray(
            "tyler.cloud.ovpn", "/home/tyler/ovpns/"))
        FILE_VPN = FILE_VPN.split("remote ", maxsplit=1)[
            0] + newLine + FILE_VPN.split(" 1194")[1]
        securedata.writeFile("tyler.cloud.ovpn",
                             "/home/tyler/ovpns/", FILE_VPN)
    except IOError as e:
        securedata.log(f"Could not update VPN: {e}", level="error")

    # Send email
    message = (f"Your public IP was updated from {currentIP} to {discovered_IP}."
               "To keep tyler.cloud, update your Namecheap settings.<br><br>"
               "To keep TylerVPN, please switch your OVPN file to the one located in"
               " (probably) Dropbox/securedata.")

    mail.send("IP Updated - new OVPN file", message)
