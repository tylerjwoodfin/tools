import json
from requests import get
from securedata import securedata, mail

currentIP = securedata.getItem("currentIP")

print("Updating IP Address")

ip = get('https://api.ipify.org?format=json').text
discoveredIP = json.loads(ip)["ip"]

print(f"Found {discoveredIP}, currently {currentIP}")

# IP was updated
if currentIP == discoveredIP:
    print("No change.")
else:
    print("New IP! Updating and sending email.")
    securedata.setItem("currentIP", discoveredIP)
    
    # Replace OVPN file with new IP
    newLine = f"remote {discoveredIP} 1194"

    try:
        vpnFile = '\n'.join(securedata.getFileAsArray("tyler.cloud.ovpn", "/home/pi/ovpns/"))
        vpnFile = vpnFile.split("remote ")[0] + newLine + vpnFile.split(" 1194")[1]
        securedata.writeFile("tyler.cloud.ovpn", "/home/pi/ovpns/", vpnFile )
    except Exception as e:
        securedata.log(f"Could not update VPN: {e}", level="error")
    
    # Send email
    message = f"""
    Your public IP was updated from {currentIP} to {discoveredIP}. To keep tyler.cloud, update your Namecheap settings.<br><br>
    To keep TylerVPN, please switch your OVPN file to the one located in (probably) Dropbox/securedata."""
    
    mail.send("IP Updated - new OVPN file", message)