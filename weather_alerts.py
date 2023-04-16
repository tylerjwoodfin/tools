"""
Sends an email alert if it's "nice" outside

Dependencies:
- requests (pip install requests)
- cabinet (my internal function to grab nonpublic variables from a JSON file)

Note: the API key should be obtained for free through openweathermap.org.
"""

import datetime
import time
import random
import sys
import requests
from cabinet import Cabinet, Mail

cab = Cabinet()
mail = Mail()

lat = cab.get("latitude")
lon = cab.get("longitude")


def datetime_from_utc_to_local(utc_datetime):
    """
    converts utc datetime to local timezone on system
    """
    now_timestamp = time.time()
    offset = datetime.datetime.fromtimestamp(
        now_timestamp) - datetime.datetime.utcfromtimestamp(now_timestamp)
    return utc_datetime + offset


def shift_location(location):
    """
    generates a random offset from the current location to find a place to walk/bike
    """
    if random.randrange(2) == 1:
        return float(location) * (.9999) + (random.randrange(1, 100) / 10000)

    return float(location) * (.9999) - (random.randrange(1, 100) / 10000)


def get_location_link():
    """
    returns a Google Maps URL for the shifted location
    """
    return f"https://www.google.com/maps/dir/{shift_location(lat)},{shift_location(lon)}"


def convert_temperature_c_to_f(temp):
    """
    converts from celsius to fahrenheit
    """
    return round((temp - 273.15) * 9/5 + 32)


# context variables
plantyStatus = cab.get("planty", "status")
now = datetime.datetime.now()

# Call API
url_request = (f"https://api.openweathermap.org/data/2.5/onecall"
               f"?lat={lat}&lon={lon}&appid={cab.get('weather', 'api_key')}")
print(f"Calling API at {url_request}")

response = requests.get(url_request, timeout=30).json()

temperature = convert_temperature_c_to_f(response["current"]["temp"])
conditions_now = response["current"]["weather"][0]["description"]
conditions_now_icon = response["current"]["weather"][0]["icon"]
conditions_tomorrow = response["daily"][1]["weather"][0]["description"]
high_tomorrow = convert_temperature_c_to_f(response["daily"][1]["temp"]["max"])
low_tomorrow = convert_temperature_c_to_f(response["daily"][1]["temp"]["min"])
sunrise_tomorrow_formatted = time.strftime(
    '%Y-%m-%d %H:%M AM', time.localtime(response["daily"][1]["sunrise"]))
sunset_tomorrow_formatted = time.strftime(
    '%Y-%m-%d %I:%M PM', time.localtime(response["daily"][1]["sunset"]))

high = convert_temperature_c_to_f(response["daily"][0]["temp"]["max"])
wind = response["current"]["wind_speed"]
sunset = response["daily"][0]["sunset"]
timeToSunset = (sunset - time.time()) / 3600

# set WEATHER_DATA
weatherData = {
    "current_temperature": temperature,
    "current_conditions": conditions_now,
    "current_conditions_icon": conditions_now_icon,
    "tomorrow_high": high_tomorrow,
    "tomorrow_low": low_tomorrow,
    "tomorrow_conditions": conditions_tomorrow,
    "tomorrow_sunrise": sunrise_tomorrow_formatted,
    "tomorrow_sunset": sunset_tomorrow_formatted}

cab.put("weather", "data", weatherData)

if cab.get("weather", "alert_walk_sent") < (time.time() - 43200) and now.hour >= 10:
    GOOD_TEMP = (65 <= temperature <= 85) or (72 <= temperature <= 90)
    if GOOD_TEMP and wind < 10 and timeToSunset > 2:
        message = f"""\
            Hi Tyler,\
                <br><br>It's very specifically nice outside!<br><br>
                <ul>
                    <li>It's {temperature}° right now with a high of {high}°- your future self will thank you for going out today!</li>
                    <li>It's not raining</li>
                    <li>The wind isn't bad</li>
                    <li>It's a nice time of day</li>
                    <br><br><h2><a href='{get_location_link()}'>
                    Here's a close place for you to walk to.</a></h2>"""

        mail.send("Here's a close place to walk today!", message)
        cab.put("weather", "alert_walk_sent", int(time.time()))
        cab.put("Walk Alert Sent")

plantyAlertSent = cab.get("weather", "alert_planty_sent")
plantyAlertChecked = cab.get("weather", "alert_planty_checked")

if len(sys.argv) > 1 and sys.argv[1] == 'force' or \
    (not plantyAlertSent or not plantyAlertChecked or
     (int(plantyAlertSent) < (time.time() - 43200) and
        int(plantyAlertChecked) < (time.time() - 21600))):
    cab.log(
        f"Checked Planty ({plantyStatus}): low {low_tomorrow}, high {high}")
    cab.put("weather", "alert_planty_checked", int(time.time()))
    if low_tomorrow < 55 and plantyStatus == "out":
        try:
            mail.send("Take Planty In This Afternoon",
                      (f"Hi Tyler,<br><br>The low tonight is {low_tomorrow}°."
                       f" Please take Planty in!"),
                      to_addr=cab.get("weather", "alert_planty_emails"))
            cab.put(
                "weather", "alert_planty_sent", int(time.time()))
        except IOError as e:
            cab.log(f"Could not send Planty email: {e}", level="error")
        cab.put("planty", "status", "in")
    if (high > 80 or low_tomorrow >= 56) and plantyStatus == "in":
        try:
            EMAIL = (f"Hi Tyler,<br><br>It looks like a nice day!"
                     f" It's going to be around {high}°. Please take Planty out.")

            mail.send("Take Planty Out This Afternoon", EMAIL,
                      to_addr=cab.get("weather", "alert_planty_emails"))
            cab.put(
                "weather", "alert_planty_sent", int(time.time()))
        except IOError as e:
            cab.log(f"Could not send Planty email: {e}", level="error")
        cab.put("planty", "status", "out")
