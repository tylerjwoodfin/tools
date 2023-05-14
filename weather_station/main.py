"""
Imp
"""

import json
from datetime import datetime
import smbus2
import bme280
import requests
import time
from cabinet import Cabinet

def is_jsonable(item):
    """
    Check if the given object is JSON serializable.

    Args:
        x: Any object.

    Returns:
        bool: True if the object is JSON serializable, False otherwise.
    """
    try:
        json.dumps(item)
        return True
    except (TypeError, OverflowError):
        return False

class UUIDEncoder(json.JSONEncoder):
    """
    A custom JSON encoder that handles UUID objects.

    This encoder is used to convert non-serializable objects (such as UUIDs)
    to a serializable form when encoding JSON.

    Attributes:
        None
    """

    def default(self, o):
        """
        Override the default JSONEncoder method to handle UUID objects.

        Args:
            obj: Any object.

        Returns:
            Any: A serializable representation of the object, if possible.
        """

        if not is_jsonable(o):
            if hasattr(o, "hex"):
                return o.hex

            return str(o)
        return json.JSONEncoder.default(self, o)

def main():
    """
    Main function that reads weather data from a BME280 sensor and writes it to a file.

    Args:
        None

    Returns:
        None
    """
    cab = Cabinet()
    port = 1
    address = 0x77 # change this as needed
    bus = smbus2.SMBus(port)
    calibration_params = bme280.load_calibration_params(bus, address)
    today = datetime.today().strftime('%Y-%m-%d')
    
    lat = cab.get("latitude")
    lon = cab.get("longitude")

    # the sample method will take a single reading and return a
    # compensated_reading object
    compensated_data = bme280.sample(bus, address, calibration_params)
    data = compensated_data.__dict__

    # weather API for outdoor temps
    url_request = (f"https://api.openweathermap.org/data/2.5/onecall"
               f"?lat={lat}&lon={lon}&appid={cab.get('weather', 'api_key')}")
    print(f"Calling API at {url_request}")

    response = requests.get(url_request, timeout=30).json()

    temperature = (response["current"]["temp"])
    conditions_now = response["current"]["weather"][0]["description"]
    conditions_now_icon = response["current"]["weather"][0]["icon"]
    conditions_tomorrow = response["daily"][1]["weather"][0]["description"]
    high_tomorrow = (response["daily"][1]["temp"]["max"])
    low_tomorrow = (response["daily"][1]["temp"]["min"])
    sunrise_tomorrow_formatted = time.strftime(
        '%Y-%m-%d %H:%M AM', time.localtime(response["daily"][1]["sunrise"]))
    sunset_tomorrow_formatted = time.strftime(
        '%Y-%m-%d %I:%M PM', time.localtime(response["daily"][1]["sunset"]))
    humidity = response["current"]["humidity"]

    high = (response["daily"][0]["temp"]["max"])
    wind = response["current"]["wind_speed"]
    sunset = response["daily"][0]["sunset"]
    timeToSunset = (sunset - time.time()) / 3600

    weather_data = {
    "current_temperature": temperature,
    "current_conditions": conditions_now,
    "current_conditions_icon": conditions_now_icon,
    "current_humidity": humidity,
    "tomorrow_high": high_tomorrow,
    "tomorrow_low": low_tomorrow,
    "tomorrow_conditions": conditions_tomorrow,
    "tomorrow_sunrise": sunrise_tomorrow_formatted,
    "tomorrow_sunset": sunset_tomorrow_formatted}

    data["weather_data"] = weather_data 
    data_json = json.dumps(data, cls=UUIDEncoder, indent=4) + ","
    
    print(data_json)

    # write data_json to cabinet 
    cab.write_file(f"weather {today}.json", cab.path_cabinet + "/weather", data_json, append=True)


if __name__ == "__main__":
    main()

