# dailystatus
- Feel free to clone, but this is very custom to my setup and backup process
- Backs up logs, crontab, etc. 
- Sends me an email each day with my home automation status, the weather forecast, Spotify information, and anything else I find useful


## dependencies
- requests (`pip install requests`)
- [cabinet](https://pypi.org/project/cabinet/)
- Data comes from logs or information in `cabinet` produced by `../weather.py`