# ReadMe
# Sends an email alert if it's "nice" outside
# Dependencies: requests (pip install requests), secureData (my internal function to grab nonpublic variables from a secure folder)
# Note: weatherAPIKey should be obtained for free through openweathermap.org.

import requests
import datetime
import time
import mail
from decimal import Decimal as d
import random
import sys
import pwd
import json
import os

userDir = pwd.getpwuid(os.getuid())[0]

sys.path.insert(0, f'/home/{userDir}/Git/SecureData')
import secureData

lat = str(secureData.array("weatherLatLong")[0])
lon = str(secureData.array("weatherLatLong")[1])


def datetime_from_utc_to_local(utc_datetime):
    now_timestamp = time.time()
    offset = datetime.datetime.fromtimestamp(
        now_timestamp) - datetime.datetime.utcfromtimestamp(now_timestamp)
    return utc_datetime + offset


def shiftLocation(location):
    if(random.randrange(2) == 1):
        return d(location) + d(random.randrange(10000000)/100000000)
    else:
        return d(location) - d(random.randrange(10000000)/100000000)


def getBikeLink():
    return f"https://www.google.com/maps/dir//{shiftLocation(lat)},{shiftLocation(lon)}"


def convertTemperature(temp):
    return round((temp - 273.15) * 9/5 + 32)


# context variables
plantyStatus = secureData.variable("PLANTY_STATUS")
now = datetime.datetime.now()

# Call API
url_request = f"https://api.openweathermap.org/data/2.5/onecall?lat={lat}&lon={lon}&appid={secureData.variable('weatherAPIKey')}"
response = requests.get(url_request).json()

temperature = convertTemperature(response["current"]["temp"])
conditions_tomorrow = response["daily"][1]["weather"][0]["description"]
high_tomorrow = convertTemperature(response["daily"][0]["temp"]["max"])
low_tomorrow = convertTemperature(response["daily"][1]["temp"]["min"])
sunrise_tomorrow_formatted = time.strftime('%Y-%m-%d %H:%M AM', time.localtime(response["daily"][1]["sunrise"]))
sunset_tomorrow_formatted = time.strftime('%Y-%m-%d %I:%M PM', time.localtime(response["daily"][1]["sunset"]))

high = convertTemperature(response["daily"][0]["temp"]["max"])
wind = response["current"]["wind_speed"]
sunset = response["daily"][0]["sunset"]
timeToSunset = (sunset - time.time()) / 3600

# set WEATHER_DATA
weatherData = {"high": high_tomorrow,
    "low": low_tomorrow,
    "conditions": conditions_tomorrow,
    "sunrise": sunrise_tomorrow_formatted,
    "sunset": sunset_tomorrow_formatted}

secureData.write("WEATHER_DATA", json.dumps(weatherData))
    
if(int(secureData.variable("walkAlertSent")) < (time.time() - 43200) and now.hour >= 10):
    if(((temperature >= 65 and temperature <= 85) or (high >= 72 and high <= 90)) and wind < 10 and timeToSunset > 2):
        message = f"""\
            Hi Tyler,\
                <br><br>Get walking, biking, and moving!<br><br>
                <ul>
                    <li>It's {temperature}° right now with a high of {high}°- what a promising day to get outside!</li>
                    <li>It's not raining</li>
                    <li>The wind isn't bad</li>
                    <li>It's a nice time of day</li>
                    <br><br><h2><a href='{getBikeLink()}'>Here's a random place for you to go.</a></h2>"""

        mail.send("Particularly good weather today!", message)
        secureData.write("walkAlertSent", str(int(time.time())))
        secureData.log("Walk Alert Sent")

plantyAlertSent = secureData.variable("PLANTY_ALERT_SENT")

if(not plantyAlertSent or int(plantyAlertSent) < (time.time() - 43200)):
    secureData.log(f"Checked Planty (currently {plantyStatus}): low {low_tomorrow}, high {high}")
    if(low_tomorrow < 55 and plantyStatus == "out"):
        mail.send("Take Planty In", f"Hi Tyler,<br><br>The low tonight is {low_tomorrow}°. Please take Planty in!")
        secureData.write("PLANTY_STATUS", "in")
        secureData.write("PLANTY_ALERT_SENT", str(int(time.time())))
    if((high > 80 or low_tomorrow > 60) and plantyStatus == "in"):
        mail.send("Take Planty Out", f"Hi Tyler,<br><br>It looks like a nice day! It's going to be around {high}°. Please take Planty out.""")
        secureData.write("PLANTY_STATUS", "out")
        secureData.write("PLANTY_ALERT_SENT", str(int(time.time())))
