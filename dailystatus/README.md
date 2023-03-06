# dailystatus
- Not meant to be cloned; for educational purposes only
- Backs up logs, crontab, etc. 
- Sends me an email each day with my home automation status, the weather forecast, Spotify information, and anything else I find useful


## Dependencies
- requests (`pip install requests`)
- [cabinet](https://pypi.org/project/cabinet/)
- Data comes from logs or information in `cabinet` produced by modules in this repo or other repos; see the code for details

# Note: weatherAPIKey should be obtained for free through openweathermap.org.