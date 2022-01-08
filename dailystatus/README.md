# dailystatus
- Not meant to be cloned; for educational purposes only
- Backs up logs, crontab, etc. 
- Sends me an email each day with my home automation status, the weather forecast, Spotify information, and anything else I find useful


## Dependencies
- requests (`pip install requests`)
- [securedata](https://pypi.org/project/securedata/)
- Data comes from logs or information in `securedata` produced by modules in this repo or other repos; see the code for details

# Note: weatherAPIKey should be obtained for free through openweathermap.org.