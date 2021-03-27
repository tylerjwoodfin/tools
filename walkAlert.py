# ReadMe
# Sends an email alert if it's "nice" outside
# Dependencies: requests (pip install requests), secureData (my internal function to grab nonpublic variables from a secure folder)
# Note: weatherAPIKey should be obtained for free through openweathermap.org.

import requests
import datetime
import time
import secureData
import mail

def datetime_from_utc_to_local(utc_datetime):
    now_timestamp = time.time()
    offset = datetime.datetime.fromtimestamp(now_timestamp) - datetime.datetime.utcfromtimestamp(now_timestamp)
    return utc_datetime + offset

# Call API
url_request = "https://api.openweathermap.org/data/2.5/weather?zip=%s&appid=%s" % (secureData.variable("zipCode"), secureData.variable("weatherAPIKey"))
response = requests.get(url_request)

# Context Variables
now = datetime.datetime.now()
lat = str(response.json()["coord"]["lat"])
lon = str(response.json()["coord"]["lon"])
temperature = round((response.json()["main"]["temp"] - 273.15) * 9/5 + 32)
wind = response.json()["wind"]["speed"]

if(int(secureData.variable("walkAlertSent")) < (time.time() - 43200) and temperature >= 65 and temperature <= 85 and wind < 10 and now.hour >= 16):

    # Get Sunset
    url_sunset = "https://api.sunrise-sunset.org/json?lat=%s&lng=%s&date=today&formatted=0" % (lat,lon)
    response = requests.get(url_sunset)

    hrs = response.json()["results"]["sunset"].split("T")[1].split(":")[0]
    mns = response.json()["results"]["sunset"].split("T")[1].split(":")[1]

    sunsetTime = now.replace(hour=int(hrs), minute=int(mns), second=0, microsecond=0)
    timeToSunset = (datetime_from_utc_to_local(sunsetTime) - now).seconds / 3600

    if(timeToSunset < 5):
        message = """\
            Hi Tyler,\
                <br><br>You should really take a walk!<br><br>
                <ul>
                    <li>It's """ + str(temperature) + """°- a perfectly nice temperature!</li>
                    <li>It's not raining</li>
                    <li>The wind isn't bad</li>
                    <li>It's a nice time of day</li>"""
        
        mail.send("Take a walk today, please!", message)
        secureData.write("walkAlertSent",str(int(time.time())))