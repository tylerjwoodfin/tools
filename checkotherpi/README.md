# checkwebsite

- I have 2 Raspberry Pis (192.168.0.123, 192.168.0.124)
- This tool pings the sister device, and if after 3 attempts, it cannot be reached, it sends an email.

# Dependencies

- `../mail.py` should be configured using [securedata](https://pypi.org/project/securedata)
  - Otherwise, you can comment out `mail` lines and use `print`.

# Usage

- `python3 /path/to/main.py`
- I recommend putting this in your crontab (`crontab -e`)
