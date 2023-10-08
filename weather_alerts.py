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
        now_timestamp
    ) - datetime.datetime.utcfromtimestamp(now_timestamp)
    return utc_datetime + offset


def shift_location(location):
    """
    generates a random offset from the current location to find a place to walk/bike
    """
    if random.randrange(2) == 1:
        return float(location) * (0.9999) + (random.randrange(1, 100) / 10000)

    return float(location) * (0.9999) - (random.randrange(1, 100) / 10000)


def get_location_link():
    """
    returns a Google Maps URL for the shifted location
    """
    return (
        f"https://www.google.com/maps/dir/{shift_location(lat)},{shift_location(lon)}"
    )


def convert_temperature_c_to_f(temp):
    """
    converts from celsius to fahrenheit
    """
    return round((temp - 273.15) * 9 / 5 + 32)

def get_air_quality_advice(aqi_components):
    """
    Gets advice based on air quality
    """

    # Setting some basic thresholds (µg/m³)
    pm25_threshold = 12
    pm10_threshold = 20
    o3_threshold = 70
    no2_threshold = 25

    components = aqi_components

    advice = []
    if components["pm2_5"] > pm25_threshold:
        advice.append("High PM2.5 levels. Consider an N95 mask outdoors.")
    if components["pm10"] > pm10_threshold:
        advice.append("Elevated PM10. Consider short walks with an N95 mask.")
    if components["o3"] > o3_threshold:
        advice.append("High Ozone levels. Limit outdoor time & strenuous activities.")
    if components["no2"] > no2_threshold:
        advice.append("High NO2 levels. Maybe stay indoors or limit exposure.")
    return advice


# context variables
planty_status = cab.get("planty", "status")
now = datetime.datetime.now()

# Call API

# ... weather
url_request_weather = (
    f"https://api.openweathermap.org/data/2.5/onecall"
    f"?lat={lat}&lon={lon}&appid={cab.get('weather', 'api_key')}"
)
print(f"Calling API at {url_request_weather}")

# ... air quality
url_request_air = (
    f"http://api.openweathermap.org/data/2.5/air_pollution"
    f"?lat={lat}&lon={lon}&appid={cab.get('weather', 'api_key')}"
)


response_weather = requests.get(url_request_weather, timeout=30).json()

print(f"Calling API at {url_request_air}")
response_air = requests.get(url_request_air, timeout=30).json()
response_air_components = response_air["list"][0]["components"]

temperature = convert_temperature_c_to_f(response_weather["current"]["temp"])
conditions_now = response_weather["current"]["weather"][0]["description"]
conditions_now_icon = response_weather["current"]["weather"][0]["icon"]
conditions_tomorrow = response_weather["daily"][1]["weather"][0]["description"]
high_tomorrow = convert_temperature_c_to_f(response_weather["daily"][1]["temp"]["max"])
low_tomorrow = convert_temperature_c_to_f(response_weather["daily"][1]["temp"]["min"])
sunrise_tomorrow_formatted = time.strftime(
    "%Y-%m-%d %H:%M AM", time.localtime(response_weather["daily"][1]["sunrise"])
)
sunset_tomorrow_formatted = time.strftime(
    "%Y-%m-%d %I:%M PM", time.localtime(response_weather["daily"][1]["sunset"])
)
humidity = response_weather["current"]["humidity"]

high = convert_temperature_c_to_f(response_weather["daily"][0]["temp"]["max"])
wind = response_weather["current"]["wind_speed"]
sunset = response_weather["daily"][0]["sunset"]
time_to_sunset = (sunset - time.time()) / 3600

weather_data = {
    "current_temperature": temperature,
    "current_conditions": conditions_now,
    "current_conditions_icon": conditions_now_icon,
    "current_humidity": humidity,
    "tomorrow_high": high_tomorrow,
    "tomorrow_low": low_tomorrow,
    "tomorrow_conditions": conditions_tomorrow,
    "tomorrow_sunrise": sunrise_tomorrow_formatted,
    "tomorrow_sunset": sunset_tomorrow_formatted,
}

cab.put("weather", "data", weather_data)

if (
    cab.get("weather", "alert_walk_sent") < (time.time() - 43200)
    and 10 <= now.hour < 19
):
    # send air quality alerts
    air_quality_advice = get_air_quality_advice(response_air_components)
    if len(air_quality_advice) > 0:
        AIR_QUALITY_ADVICE = '\n'.join([f"<li>{item}</li>" for item in air_quality_advice])
        message = f"""\
            Hi Tyler,\
            <br><br>Take a look at today's air quality:<br><br>
            <ul>{AIR_QUALITY_ADVICE}</ul>"""
        mail.send("Air Quality Alert", message)

    # air quality is fine
    GOOD_TEMP = (65 <= temperature <= 85) or (72 <= temperature <= 90)
    if GOOD_TEMP and wind < 10 and time_to_sunset > 2:
        message = f"""\
            Hi Tyler,\
                <br><br>It's very specifically nice outside!<br><br>
                <ul>
                    <li>It's {temperature}° right now with a high of {high}°- your future self will thank you for going out today!</li>
                    <li>It's not raining</li>
                    <li>The wind isn't bad</li>
                    <li>It's a nice time of day</li>
                    <li>The air quality is fine</li>
                    <br><br><h2><a href='{get_location_link()}'>
                    Here's a close place for you to walk to.</a></h2>"""

        mail.send("Here's a close place to walk today!", message)
        cab.put("weather", "alert_walk_sent", int(time.time()))
        cab.put("Walk Alert Sent")

planty_alert_sent = cab.get("weather", "alert_planty_sent")
planty_alert_checked = cab.get("weather", "alert_planty_checked")

if (
    len(sys.argv) > 1
    and sys.argv[1] == "force"
    or (
        not planty_alert_sent
        or not planty_alert_checked
        or (
            int(planty_alert_sent) < (time.time() - 43200)
            and int(planty_alert_checked) < (time.time() - 21600)
        )
    )
):
    cab.log(f"Checked Planty ({planty_status}): low {low_tomorrow}, high {high}")
    cab.put("weather", "alert_planty_checked", int(time.time()))
    
    if low_tomorrow < 55 and planty_status == "out":
        try:
            mail.send(
                "Take Planty In This Afternoon",
                (
                    f"Hi Tyler,<br><br>The low tonight is {low_tomorrow}°."
                    f" Please take Planty in!"
                ),
                to_addr=cab.get("weather", "alert_planty_emails"),
            )
            cab.put("weather", "alert_planty_sent", int(time.time()))
        except IOError as e:
            cab.log(f"Could not send Planty email: {e}", level="error")
        cab.put("planty", "status", "in")
    if (high > 80 or low_tomorrow >= 56) and planty_status == "in":
        try:
            EMAIL = (
                f"Hi Tyler,<br><br>It looks like a nice day!"
                f" It's going to be around {high}°. Please take Planty out."
            )

            mail.send(
                "Take Planty Out This Afternoon",
                EMAIL,
                to_addr=cab.get("weather", "alert_planty_emails"),
            )
            cab.put("weather", "alert_planty_sent", int(time.time()))
        except IOError as e:
            cab.log(f"Could not send Planty email: {e}", level="error")
        cab.put("planty", "status", "out")
