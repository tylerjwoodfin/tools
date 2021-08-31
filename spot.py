# ReadMe
# Takes a backup of my Spotify music library, including title, artist, and year, and places the csv in a log folder in my Dropbox directory.
# Uses "Spotipy", a great tool to use the Spotify APIs.
# Mail was installed using msmtp. sudo apt-get install msmtp msmtp-mta
# Config file: /etc/msmtprc

from spotipy.oauth2 import SpotifyClientCredentials
import os
from os import path
import datetime
import sys
import subprocess
import spotipy
import codecs
from statistics import mean

sys.path.insert(0, '/home/pi/Git/SecureData')
import secureData


# set environment variables needed by Spotipy
os.environ['SPOTIPY_CLIENT_ID'] = secureData.variable("SPOTIPY_CLIENT_ID")
os.environ['SPOTIPY_CLIENT_SECRET'] = secureData.variable("SPOTIPY_CLIENT_SECRET")
os.environ['SPOTIPY_REDIRECT_URI'] = 'http://localhost:8888'
spotipy_username = secureData.variable("SPOTIPY_USERNAME")
spotipy_playlist_id = secureData.variable("SPOTIPY_PLAYLIST_ID")

songYears = []
totalTracks = -1
index = 0

def show_tracks(tracks):
    global index
    toReturn = u""

    for i, item in enumerate(tracks['items']):
        track = item['track']
        index+=1
        print(f"{index} of {totalTracks}...")
        line = f"{str(index)}::{track['artists'][0]['name']}::{track['name']}::{str(track['album']['release_date'])}::{(track['external_urls']['spotify'] if track['is_local'] == False else '')}\n"
        toReturn += line

        if(track['album']['release_date']):
            songYears.append(int(track['album']['release_date'].split("-")[0]))
    
    return toReturn

if __name__ == '__main__':

    secureData.log("Started spot.py")

    try:
        client_credentials_manager = SpotifyClientCredentials()
        sp = spotipy.Spotify(client_credentials_manager=client_credentials_manager)
        filePath = f"/var/www/html/Logs/Songs/{str(datetime.date.today())}.csv"
        f = open(filePath, 'w+')
    except Exception as e:
        secureData.log(f"Caught Spotify Initialization Error: {str(e)}")

    try:
        # parse playlist by ID
        results = sp.playlist(spotipy_playlist_id)
        tracks = results['tracks']
        totalTracks = results['tracks']['total']
        secureData.write("SPOTIPY_SONG_COUNT", str(totalTracks))

        # go through each set of songs, 100 at a time (due to API limits)
        f.write(str(show_tracks(tracks)))
        while tracks['next']:
            tracks = sp.next(tracks)
            f.write(str(show_tracks(tracks)))

        print(f"Average Year: {str(mean(songYears))}")

        secureData.log("Updated Spotify Log")
        secureData.write("SPOTIPY_AVERAGE_YEAR", str(mean(songYears)))
    except Exception as e:
        secureData.log(f"Caught Spotify error when creating csv: {str(e)}")

    print("\n\nDone. Updating Git:")
    f.close()

    # Push the new log file (and anything else from today) to Github
    os.system("cd /var/www/html; git pull; git add -A; git commit -m 'Updated Logs'; git push")
    secureData.log("Updated Git")
