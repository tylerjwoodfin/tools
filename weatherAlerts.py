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
    
def convertTemperature(temp):
    return round((temp - 273.15) * 9/5 + 32)
    
# context variables
plantyStatus = secureData.variable("plantyStatus")
lat = str(secureData.array("weatherLatLong")[0])
lon = str(secureData.array("weatherLatLong")[1])
now = datetime.datetime.now()

if(int(secureData.variable("walkAlertSent")) < (time.time() - 43200) and now.hour >= 10):
    # Call API
    url_request = "https://api.openweathermap.org/data/2.5/onecall?lat={}&lon={}&appid={}".format(lat, lon, secureData.variable("weatherAPIKey"))
    response = requests.get(url_request).json()
    
    # print(response)
    
    temperature = convertTemperature(response["current"]["temp"])
    low = convertTemperature(response["daily"][1]["temp"]["min"])
    high = convertTemperature(response["daily"][1]["temp"]["max"])
    wind = response["current"]["wind_speed"]

    if(((temperature >= 65 and temperature <= 85) or (high >= 65 and high <=90)) and wind < 10):

        # Get Sunset
        url_sunset = "https://api.sunrise-sunset.org/json?lat=%s&lng=%s&date=today&formatted=0" % (lat,lon)
        response = requests.get(url_sunset).json()

        hrs = response["results"]["sunset"].split("T")[1].split(":")[0]
        mns = response["results"]["sunset"].split("T")[1].split(":")[1]

        sunsetTime = now.replace(hour=int(hrs), minute=int(mns), second=0, microsecond=0)
        timeToSunset = (datetime_from_utc_to_local(sunsetTime) - now).seconds / 3600

        if(timeToSunset > 2):
            message = """\
                Hi Tyler,\
                    <br><br>I hope you try to take a walk today!<br><br>
                    <ul>
                        <li>It's {}° right now with a high of {}°- what a promising day to get outside!</li>
                        <li>It's not raining</li>
                        <li>The wind isn't bad</li>
                        <li>It's a nice time of day</li>""".format(temperature,high)
            
            mail.send("Take a walk today, please!", message)
            secureData.write("walkAlertSent",str(int(time.time())))
            
# Planty Alerts
if(int(secureData.variable("plantyAlertSent")) < (time.time() - 43200)):
    if(low < 55 and plantyStatus == "out"):
        mail.send("Take Planty In", "Hi Tyler,<br><br>The low tonight is {}°. Please take Planty in!".format(low))
        secureData.write("plantyStatus", "in")
        secureData.write("plantyAlertSent", str(int(time.time())))
    if(high > 80 and plantyStatus == "in"):
        mail.send("Take Planty Out", "Hi Tyler,<br><br>It looks like a nice day! It's going to be around {}°. Please take Planty out.".format(high))
        secureData.write("plantyStatus", "out")
        secureData.write("plantyAlertSent", str(int(time.time())))
