"""
Uses open-source APIs to check the weather and write to Cabinet.

Learn more about Cabinet: https://github.com/tylerjwoodfin/cabinet
"""

import sys

from datetime import datetime
from typing import Tuple, Optional
from pytz import timezone # pylint: disable=import-error # type: ignore
import requests
from cabinet import Cabinet

def get_sunrise_sunset(lat: float, lon: float) -> Tuple[Optional[str], Optional[str]]:
    """Fetch sunrise and sunset times in UTC for the given latitude and longitude."""
    url_sunrise_sunset = f"https://api.sunrise-sunset.org/json?lat={lat}&lng={lon}&formatted=0"
    response_sunrise_sunset = requests.get(url_sunrise_sunset, timeout=10)
    if response_sunrise_sunset.status_code != 200:
        return None, None
    data = response_sunrise_sunset.json()['results']
    return data['sunrise'], data['sunset']

def convert_to_local_time(utc_time_str: str, local_tz_str: str) -> str:
    """Convert a UTC time string to a local time string based on the given timezone."""
    utc_time = datetime.fromisoformat(utc_time_str)
    local_tz = timezone(local_tz_str)
    local_time = utc_time.astimezone(local_tz)
    return local_time.strftime('%Y-%m-%d %I:%M %p')

def update_weather_data():
    """Fetch weather data and update the Cabinet properties with the results."""
    cab = Cabinet()
    cab.log("Checking weather")

    # fetch latitude and longitude from the cabinet
    lat: float = cab.get("weather", "latitude", return_type=float) or -1
    lon: float = cab.get("weather", "longitude", return_type=float) or -1

    if lat == -1 or lon == -1:
        cab.log("Could not fetch lat/lon from Cabinet", level="error")
        sys.exit()

    # get grid points and local timezone
    url_request_points = f"https://api.weather.gov/points/{lat},{lon}"
    response_points = requests.get(url_request_points, timeout=10)
    if response_points.status_code != 200:
        print(f"Error: {response_points.json().get('detail', 'Unknown error')}")
        return

    response_points = response_points.json()
    grid_id: str = response_points['properties']['gridId']
    grid_x: int = response_points['properties']['gridX']
    grid_y: int = response_points['properties']['gridY']
    local_tz: str = response_points['properties']['timeZone']

    # fetch weather forecast
    url_forecast = f"https://api.weather.gov/gridpoints/{grid_id}/{grid_x},{grid_y}/forecast"
    response_forecast = requests.get(url_forecast, timeout=10)
    if response_forecast.status_code != 200:
        cab.log(f"Could not get weather: {response_forecast.json().get('detail', 'Unknown error')}",
                level="info")
        return

    response_forecast = response_forecast.json()

    # extract current weather conditions
    current_conditions = response_forecast['properties']['periods'][0]
    current_temp: int = current_conditions['temperature']
    current_condition: str = current_conditions['shortForecast']
    current_icon: str = current_conditions['icon']
    current_humidity: Optional[int] = current_conditions.get('relativeHumidity',
                                                             {}).get('value', None)

    # extract tomorrow's forecast (assume it is the second period in the list)
    forecast_tomorrow = response_forecast['properties']['periods'][1]
    high_temp: int = forecast_tomorrow['temperature']
    short_forecast: str = forecast_tomorrow['shortForecast']

    # fetch and convert sunrise and sunset times
    sunrise_utc, sunset_utc = get_sunrise_sunset(lat, lon)
    if sunrise_utc and sunset_utc:
        sunrise_local: str = convert_to_local_time(sunrise_utc, local_tz)
        sunset_local: str = convert_to_local_time(sunset_utc, local_tz)
    else:
        sunrise_local = "Unavailable"
        sunset_local = "Unavailable"
        cab.log("Unable to get sunrise/sunset data", level="error")

    # update cabinet properties with the results
    cab.put("weather", "data", "current_temperature", current_temp)
    cab.put("weather", "data", "current_conditions", current_condition)
    cab.put("weather", "data", "current_conditions_icon", current_icon)
    if current_humidity is not None:
        cab.put("weather", "data", "current_humidity", current_humidity)
    cab.put("weather", "data", "tomorrow_high", high_temp)
    cab.put("weather", "data", "tomorrow_conditions", short_forecast)
    cab.put("weather", "data", "tomorrow_sunrise", sunrise_local)
    cab.put("weather", "data", "tomorrow_sunset", sunset_local)

    # format output as HTML
    formatted_output: str = f"""
            <pre>
<strong>High:</strong>    {high_temp}° and {short_forecast}
<strong>Sunrise:</strong> {sunrise_local}
<strong>Sunset:</strong>  {sunset_local}
            </pre>
    """

    # update cabinet with formatted HTML output
    cab.put("weather", "data", "tomorrow_formatted", formatted_output)

    # update the last_checked property with the current datetime
    last_checked: str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    cab.put("weather", "data", "last_checked", last_checked)
    cab.log("Checked weather successfully")

update_weather_data()
