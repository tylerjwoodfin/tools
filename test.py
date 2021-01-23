import requests
import datetime, time

def datetime_from_utc_to_local(utc_datetime):
    now_timestamp = time.time()
    offset = datetime.datetime.fromtimestamp(now_timestamp) - datetime.datetime.utcfromtimestamp(now_timestamp)
    return utc_datetime + offset

now = datetime.datetime.now()
response = requests.get("https://api.sunrise-sunset.org/json?lat=30.5145&lng=-97.668&date=today&formatted=0")

hrs = response.json()["results"]["sunset"].split("T")[1].split(":")[0]
mns = response.json()["results"]["sunset"].split("T")[1].split(":")[1]

sunsetTime = now.replace(hour=int(hrs), minute=int(mns), second=0, microsecond=0)

print(response.json())
print(datetime_from_utc_to_local(sunsetTime))
print((datetime_from_utc_to_local(sunsetTime) - now).seconds / 3600)
