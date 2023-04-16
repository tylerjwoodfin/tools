"""
Graphing weather
"""

import sys
import json
import os
from datetime import datetime, timedelta
import pytz
import plotly
import cabinet

TODAY = str(datetime.today().strftime('%Y-%m-%d'))
TODAY_DT = datetime.today()


def get_weather_files():
    """
    Get the names of the latest weather files in the 'weather' folder of cabinet.

    Returns:
        list: A list of the names of the latest files in the format 'weather YYYY-MM-DD.json'.

    Raises:
        None.
    """
    folder_path = cab.path_cabinet + "/weather"

    # Get a list of all files in the folder
    try:
        files_in_weather_folder = os.listdir(folder_path)
    except FileNotFoundError:
        cab.log(f"No weather files found in {folder_path}")
        return []

    # Filter out any files that don't start with "weather "
    weather_files = [
        file for file in files_in_weather_folder if file.startswith("weather ")]

    # Get the names of files for last 3 days
    last_three_days = [(TODAY_DT - timedelta(days=i)
                        ).strftime("%Y-%m-%d") for i in range(3)]
    latest_files = [f"weather {date}.json" for date in last_three_days]

    # Get the latest files
    latest_files = [f for f in latest_files if f in weather_files]

    return latest_files


cab = cabinet.Cabinet()

# Load JSON data from the last 3 days
files = get_weather_files()
data = []

for file in files:
    FILE_WEATHER_ARRAY = cab.get_file_as_array(
        file, cab.path_cabinet + "/weather", ignore_not_found=True)

    if FILE_WEATHER_ARRAY is None:
        cab.log(f"Could not find `{file}`")
        sys.exit(-1)

    FILE_WEATHER = ''.join(FILE_WEATHER_ARRAY)

    # filter trailing comma, if needed
    if FILE_WEATHER.endswith(','):
        FILE_WEATHER = FILE_WEATHER[:-1]

    FILE_WEATHER = f"[{FILE_WEATHER}]"
    data.extend(json.loads(FILE_WEATHER))


# Extract data from the past 36 hours
timestamps = []
temperatures_celsius = []
humidities = []
now = datetime.now(tz=pytz.utc)
thirty_six_hours_ago = now - timedelta(hours=36)
for obs in data:
    ts = datetime.strptime(
        obs['timestamp'], '%Y-%m-%d %H:%M:%S.%f%z').replace(tzinfo=pytz.utc)
    if ts >= thirty_six_hours_ago:
        timestamps.append(ts)
        temperatures_celsius.append(obs['temperature'])
        humidities.append(obs['humidity'])

# Convert Celsius to Fahrenheit
temperatures_fahrenheit = [(temp * 1.8) + 32 for temp in temperatures_celsius]

# Sort the data by timestamp
sorted_data = sorted(zip(timestamps, temperatures_fahrenheit, humidities))

# Unpack the sorted data into separate lists
timestamps, temperatures_fahrenheit, humidities = zip(*sorted_data)

# Convert UTC timestamps to Central Time
utc_timezone = pytz.timezone('UTC')
central_timezone = pytz.timezone('US/Central')
timestamps = [ts.astimezone(central_timezone) for ts in timestamps]

# Create traces
trace1 = plotly.graph_objs.Scatter(x=timestamps, y=temperatures_fahrenheit,
                                   name='Temperature (Fahrenheit)', yaxis='y1')
trace2 = plotly.graph_objs.Scatter(
    x=timestamps, y=humidities, name='Humidity', yaxis='y2')

# Set layout
layout = plotly.graph_objs.Layout(
    title='Temperature and Humidity, Past 36 Hours',
    xaxis=dict(title='Time'),
    yaxis=dict(title='Temperature (F)', side='right',
               autorange=True, fixedrange=True),
    yaxis2=dict(title='Humidity (%)', side='left',
                overlaying='y', autorange=True, fixedrange=True),
    autosize=True,
    legend=dict(y=1, orientation='h'))

# write temperature data
data = {}
data['temperature'] = round(temperatures_fahrenheit[-1], 1)
data['humidity'] = round(humidities[-1], 1)

with open('/var/www/dashboard/html/data.json', 'w', encoding="utf-8") as outfile:
    json.dump(data, outfile)

# create fig
fig = plotly.graph_objs.Figure(data=[trace1, trace2], layout=layout)
html_graph = plotly.io.to_html(fig, include_plotlyjs=True)

html = f"""
    <head>
        <link rel="stylesheet" href="style.css">
    </head>
    <body>
        <div id="stats">
            <p>Current Temperature: <span id="current-temp">{round(temperatures_fahrenheit[-1], 1)}</span></p>
            <p>Current Humidity: <span id="current-humidity">{round(humidities[-1], 1)}</span></p>
        </div>
        <div id="graph">
        {html_graph}
        </div>
    </body>
"""

html_graph = f"<head><link rel='stylesheet' href='style.css'></head>{html_graph}"

cab.write_file("weather-graph.html", "/var/www/dashboard/html", html_graph)
