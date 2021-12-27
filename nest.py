# ReadMe
# Pulls the current humidity and sends an email to turn humidifier on if humidity is low
# You need a Google Device Access Console account.
# Reference as of 23 JAN 2021: https://www.wouternieuwerth.nl/controlling-a-google-nest-thermostat-with-python/
# Make sure redirect_uri is the same in this file as in the Google Device Access Console account.

import requests
import mail
import os
import datetime
import sys

sys.path.insert(0, '/home/pi/Git/SecureData')
from securedata import securedata

# Use only to log in manually
# url = 'https://nestservices.google.com/partnerconnections/'+project_id+'/auth?redirect_uri='+redirect_uri+'&access_type=offline&prompt=consent&client_id='+client_id+'&response_type=code&scope=https://www.googleapis.com/auth/sdm.service'
# print("Go to this URL to log in:")
# print(url)

# Constants
project_id = securedata.getItem("nest", "project_id")
client_id = securedata.getItem("nest", "client_id")
client_secret = securedata.getItem("nest", "client_secret")
code = securedata.getItem("nest", "code")
redirect_uri = 'https://www.tyler.cloud'

# Access token- do we need to refresh?
access_token = securedata.getItem("nest", "access_token")

# Get new Access Token by Passing the Refresh Token
def renewAccessToken():
    params = (
        ('client_id', client_id),
        ('client_secret', client_secret),
        ('refresh_token', securedata.getItem("nest", "refresh_token")),
        ('grant_type', 'refresh_token')
    )

    response = requests.post('https://www.googleapis.com/oauth2/v4/token', params=params)

    response_json = response.json()

    print(response.json())

    access_token = response_json['token_type'] + ' ' + response_json['access_token']
    print('Access token: ' + access_token)
      
    securedata.setItem("nest", "refresh_token", access_token)

# Get structures

url_structures = 'https://smartdevicemanagement.googleapis.com/v1/enterprises/' + project_id + '/structures'

headers = {
    'Content-Type': 'application/json',
    'Authorization': access_token,
}

response = requests.get(url_structures, headers=headers)

# print(response.json())

# Get devices

url_get_devices = 'https://smartdevicemanagement.googleapis.com/v1/enterprises/' + project_id + '/devices'

headers = {
    'Content-Type': 'application/json',
    'Authorization': access_token,
}

response = requests.get(url_get_devices, headers=headers)

# print(response.json())

response_json = response.json()
device_0_name = response_json['devices'][0]['name']

# Get device stats

url_get_device = 'https://smartdevicemanagement.googleapis.com/v1/' + device_0_name

headers = {
    'Content-Type': 'application/json',
    'Authorization': access_token,
}

response = requests.get(url_get_device, headers=headers)

response_json = response.json()
humidity = response_json['traits']['sdm.devices.traits.Humidity']['ambientHumidityPercent']
print('Humidity:', humidity)
temperature = response_json['traits']['sdm.devices.traits.Temperature']['ambientTemperatureCelsius']
print('Temperature:', temperature)

renewAccessToken()

# Log to File
with open('/var/www/html/Logs/Humidity/humidity.csv','a') as fd:
    fd.write("\n" + str(datetime.datetime.now()) + "," + str(humidity))

if(humidity < 35):
    # Email Variables
    message = """\
    Hi Tyler,<br><br>
    Your humidity at home is %s%%. I recommend turning on your humidifier."""
    
    message = message % str(humidity)
    mail.send("Low Humidity", message)
