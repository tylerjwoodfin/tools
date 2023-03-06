# checkipstatus
My PiVPN needs a constant IP, and since I don't have a static IP and don't want to use ddns.net, I have this script which checks my IP address and updates the OVPN file, then emails me.

# dependencies
- [cabinet](https://pypi.org/project/cabinet/)
    - set up mail per the `cabinet` README