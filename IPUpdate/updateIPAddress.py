import json
import os
from requests import get

msg = ''
apiIP = ''
ipFile = "/home/pi/Tools/SecureData/currentIP"

print("Updating IP Address.")

try:
    with open(ipFile) as f:
        print("Current:")
        msg = f.read()
        print(msg)
        print
except:
    print("File not found, creating.")
    f = open(ipFile,'w')
    f.close()

ip = get('https://api.ipify.org?format=json').text
apiIP = json.loads(ip)["ip"]


print("Found:")
print(apiIP)
print

# IP was updated
if(msg == apiIP):
    print("No change.")
elif(msg != apiIP):
    print("New IP! Updating and sending email.")
    f = open(ipFile, 'w')
    f.write(apiIP)
    f.close()
    
    # Replace OVPN file with new IP and email it

    newLine = "remote " + apiIP + " 1194"
    with open('Tools/IPUpdate/devices9.ovpn', 'r+') as file:
        f = file.read()
        f = f.split("remote ")[0] + newLine + f.split(" 1194")[1]
        # print("Going to use:")
        # print(f)
        file.seek(0)
        file.write(f)
        file.truncate()
    
    # Send email
    message = "Your public IP was updated from " + msg + " to " + apiIP + ". To keep tyler.cloud (including Nextcloud), update your Namecheap settings. To keep TylerVPN, please use the file on your Pi at " + os.getcwd() + ".\n\nThanks,\nTyler's Raspberry Pi"
    os.system("echo \"" + "Hi Tyler,\n\n" + message + "\" | mail -s \"IP Updated - new OVPN\" tylerjwoodfin@gmail.com")
    
    
