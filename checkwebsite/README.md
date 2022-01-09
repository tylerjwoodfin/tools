# checkwebsite
- My website is hosted on my Raspberry Pi 4 at 192.168.1.123. I have a second Raspberry Pi at 192.168.1.124. 
- This tool pings the sister device, and if after 3 attempts, it cannot be reached, it sends an email.
# Dependencies
- `../mail.py` should be configured using [securedata](https://pypi.org/project/securedata)
    - Otherwise, you can comment out `mail` lines and use `print`.

# Usage
- `python3 /path/to/main.py`
- I recommend putting this in your crontab (`crontab -e`)