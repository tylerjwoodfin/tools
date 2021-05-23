# Dependencies
pip install miniupnpc

Email: see `mail.py`. I'm currently using msmtp.

# Description
My PiVPN needs a constant IP, and since I don't have a static IP and don't want to use ddns.net,  I have this script which checks my IP address and updates the OVPN file, then emails me.