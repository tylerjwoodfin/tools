# ReadMe
# Pulls the current humidity and sends an email to turn humidifier on if humidity is low
# You need a Google Device Access Console account. Instructions for registering as of 23 JAN 2021: https://www.wouternieuwerth.nl/controlling-a-google-nest-thermostat-with-python/
# Make sure redirect_uri is the same in this file as in the Google Device Access Console account.

import requests
import secureData
import os

# create 'SecureData/NestIDs' and place these variables in the first 4 lines
project_id = secureData.array("NestIDs")[0]
client_id = secureData.array("NestIDs")[1]
client_secret = secureData.array("NestIDs")[2]
redirect_uri = 'https://www.tyler.cloud'
code = secureData.array("NestIDs")[3]

url = 'https://nestservices.google.com/partnerconnections/'+project_id+'/auth?redirect_uri='+redirect_uri+'&access_type=offline&prompt=consent&client_id='+client_id+'&response_type=code&scope=https://www.googleapis.com/auth/sdm.service'
# print("Go to this URL to log in:")
# print(url)

params = (
    ('client_id', client_id),
    ('client_secret', client_secret),
    ('code', code),
    ('grant_type', 'authorization_code'),
    ('redirect_uri', redirect_uri),
)

access_token = secureData.variable("NestAccessToken")
refresh_token = secureData.variable("NestRefreshToken")

params = (
    ('client_id', client_id),
    ('client_secret', client_secret),
    ('refresh_token', refresh_token),
    ('grant_type', 'refresh_token'),
)

response = requests.post('https://www.googleapis.com/oauth2/v4/token', params=params)

response_json = response.json()
access_token = response_json['token_type'] + ' ' + response_json['access_token']
secureData.write("NestAccessToken", access_token)
print('Access token: ' + access_token)

# Get structures

url_structures = 'https://smartdevicemanagement.googleapis.com/v1/enterprises/' + project_id + '/structures'

headers = {
    'Content-Type': 'application/json',
    'Authorization': access_token,
}

response = requests.get(url_structures, headers=headers)

print(response.json())

# Get devices

url_get_devices = 'https://smartdevicemanagement.googleapis.com/v1/enterprises/' + project_id + '/devices'

headers = {
    'Content-Type': 'application/json',
    'Authorization': access_token,
}

response = requests.get(url_get_devices, headers=headers)

print(response.json())

response_json = response.json()
device_0_name = response_json['devices'][0]['name']
print(device_0_name)

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

if(humidity < 35):
    # Email Variables
    sentFrom = "Raspberry Pi"
    email = secureData.variable("email")
    message = "Hi Tyler,<br><br>Your humidity at home is " + humidity + "%. I recommend turning on your humidifier.<br><br>Thanks,<br><br>- " + sentFrom
    os.system("bash /home/pi/Tools/sendEmail.sh " + email + " \"Low Humidity\" \"" + message + "\" " + "\"" + sentFrom + "\"")