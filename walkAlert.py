# ReadMe
# Sends an email alert if it's "nice" outside
# Dependencies: requests (pip install requests), secureData (my internal function to grab nonpublic variables from a secure folder)
# Note: weatherAPIKey should be obtained for free through openweathermap.org.

import os
import requests
import datetime
import time
import json
import secureData

def datetime_from_utc_to_local(utc_datetime):
    now_timestamp = time.time()
    offset = datetime.datetime.fromtimestamp(now_timestamp) - datetime.datetime.utcfromtimestamp(now_timestamp)
    return utc_datetime + offset

# Email Variables
sentFrom = "Raspberry Pi"
email = secureData.variable("email")
now = datetime.datetime.now()

response = requests.get("https://api.openweathermap.org/data/2.5/weather?zip=" + secureData.variable("zipCode") + '&appid=' + secureData.variable("weatherAPIKey"))

lat = response.json()["coord"]["lat"]
long = response.json()["coord"]["lon"]
temperature = round((response.json()["main"]["temp"] - 273.15) * 9/5 + 32)
wind = response.json()["wind"]["speed"]

if(temperature >= 65 and temperature <= 85 and wind < 10 and now.hour >= 15):
    response = requests.get("https://api.sunrise-sunset.org/json?lat=" + str(lat) + "&lng=" + str(long) + "&date=today&formatted=0")

    hrs = response.json()["results"]["sunset"].split("T")[1].split(":")[0]
    mns = response.json()["results"]["sunset"].split("T")[1].split(":")[1]

    sunsetTime = now.replace(hour=int(hrs), minute=int(mns), second=0, microsecond=0)
    timeToSunset = (datetime_from_utc_to_local(sunsetTime) - now).seconds / 3600

    if(timeToSunset < 5):
        message = "Hi Tyler,<br><br>You should really take a walk!<br><br><ul><li>It's between 65 and 85 degrees (actually " + str(temperature) + ")</li><li>It's not raining</li><li>The wind isn't bad</li><li>It's a nice time of day</li><br><br>Thanks,<br><br>- " + sentFrom
        os.system("bash /home/pi/Tools/sendEmail.sh " + email + " \"Take a walk, please!\" \"" + message + "\" " + "\"" + sentFrom + "\"")
