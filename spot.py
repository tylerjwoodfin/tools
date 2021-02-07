# ReadMe
# Uses Spotipy.
# Mail was installed using msmtp. sudo apt-get install msmtp msmtp-mta
# Config file: sudo nano /etc/msmtprc

from spotipy.oauth2 import SpotifyClientCredentials
import os
from os import path
import datetime
from datetime import timedelta
import sys
import subprocess
import spotipy
import codecs
import secureData


# set environment variables needed by Spotipy
os.environ['SPOTIPY_CLIENT_ID'] = secureData.variable("SPOTIPY_CLIENT_ID")
os.environ['SPOTIPY_CLIENT_SECRET'] = secureData.variable("SPOTIPY_CLIENT_SECRET")
os.environ['SPOTIPY_REDIRECT_URI'] = 'http://localhost:8888'

# /

inc = 0
yesterdayCount = 0

def show_tracks(tracks):
    global inc
    global yesterdayCount
    toReturn = u""

    for i, item in enumerate(tracks['items']):
        track = item['track']
        inc+=1
        line = str(inc) + "::" + (track['artists'][0]['name']) + "::" + track['name'] + "::" + str(track['album']['release_date']) + "::" + (track['external_urls']['spotify'] if track['is_local'] == False else "") + "\n"
        toReturn += line
        if(inc > yesterdayCount):
                print(line.encode("utf-8"))
    
    return toReturn


# this if statement prevents the code from running if it's imported instead of run directly
if __name__ == '__main__':

    yesterday = str(datetime.date.today() - timedelta(days=1))
    newSongs = bytes("", "utf-8")
    client_credentials_manager = SpotifyClientCredentials()
    sp = spotipy.Spotify(client_credentials_manager=client_credentials_manager)

    filePath = "/var/www/html/Logs/Songs/"
    fullPath = filePath + "Songs " + str(datetime.date.today()) + ".csv"

    # get number of songs from yesterday
    if (path.exists(os.getcwd() + os.path.join(filePath, "Songs " + yesterday + ".csv"))):
        print("Path Exists")
        with codecs.open(filePath + "Songs " + yesterday + ".csv", 'r', encoding='Latin-1', errors='ignore') as f:
            for line in f:
                yesterdayCount += 1
            print("Yesterday Count: " + str(yesterdayCount))
    
    f = open(fullPath, 'w+')

    playlists = sp.user_playlists(secureData.variable("username"))
    for playlist in playlists['items']:
        if playlist['name'] == "Tyler Radio":
            print(playlist['name'])
            print ('  total tracks', playlist['tracks']['total'])
            results = sp.playlist(playlist['id'])
            tracks = results['tracks']
            f.write(str(show_tracks(tracks)))
            while tracks['next']:
                tracks = sp.next(tracks)
                f.write(str(show_tracks(tracks)))
    print("\n\nDone. Updating Git:")
    f.close()

    # Push the new log file (and anything else from today) to Github
    os.system("cd /var/www/html; git pull; git add -A; git commit -m 'Updated Logs'; git push")
    
    # gitOutput = os.popen("git push").read()
    gitOutput = os.popen("cd /var/www/html; git log -1").read().replace("\n","<br>")
    
    sentFrom = "Raspberry Pi"
    email = secureData.variable("email")
    # message = "Hi Tyler,<br><br>Your humidity at home is " + str(humidity) + "%. I recommend turning on your humidifier.<br><br>Thanks,<br><br>- " + sentFrom
    os.system("bash /home/pi/Tools/sendEmail.sh " + email + " \"Git Log\" \"" + str(gitOutput) + "\" " + "\"" + sentFrom + "\"")
