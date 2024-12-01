"""
spotipy-analytics
- takes a backup of my Spotify library, including title/artist/year

"""

import os
import datetime
import sys
from statistics import mean
from typing import Dict, List
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from tqdm import tqdm
from cabinet import Cabinet

cab = Cabinet()

# environment variables needed by Spotipy

spotipy_env = cab.get("spotipy")
required_keys = ['client_id', 'client_secret', 'username']

if not spotipy_env:
    cab.log("Could not determine Spotipy env.")
    sys.exit()

# Check for the presence of each required attribute
for key in required_keys:
    if not spotipy_env.get(key):
        cab.log(f"Could not determine Spotipy {key}.")
        sys.exit()

os.environ['SPOTIPY_CLIENT_ID'] = spotipy_env["client_id"]
os.environ['SPOTIPY_CLIENT_SECRET'] = spotipy_env["client_secret"]
os.environ['SPOTIPY_REDIRECT_URI'] = 'http://localhost:8888'
spotipy_username = cab.get("spotipy", "username")

csv_main_playlist = []
PATH_LOG = cab.get("path", "log") or "~/.cabinet/log"

def initialize_spotify_client() -> spotipy.Spotify:
    """
    initializes and returns a Spotipy client instance.
    """

    try:
        client_credentials_manager = SpotifyClientCredentials()
        return spotipy.Spotify(client_credentials_manager=client_credentials_manager)
    except Exception as e:
        cab.log(f"Could not initialize Spotify: {str(e)}", level="error")
        raise

def get_playlist_tracks(client: spotipy.Spotify, playlist_id: str) -> List[str]:
    """
    retrieves tracks from a specified playlist.
    """

    playlist_tracks = []
    results = client.playlist_tracks(playlist_id)

    if not results:
        cab.log("Could not determine playlist tracks", level="error")
        sys.exit()
    count = results['total']

    progress_bar = tqdm(total=count, unit='track')

    while results:
        for item in results['items']:
            if item['track']:
                track = item['track']
                track_info = (
                    f"{track['artists'][0]['name']}::"
                    f"{track['name']}::"
                    f"{track['album']['release_date']}::"
                    f"{track['external_urls']['spotify'] if not track['is_local'] else ''}"
                )
                playlist_tracks.append(track_info)
                progress_bar.update(1)
        results = client.next(results)

    progress_bar.close()
    return playlist_tracks

def extract_playlists_tracks(client: spotipy.Spotify, playlists: List[str]) -> Dict[str, List[str]]:
    """
    extracts tracks from all specified playlists.
    """
    extracted_tracks = {}
    for plist in playlists:
        if ',' not in plist:
            continue
        playlist_id, playlist_name = plist.split(',', 1)
        cab.log(f"Getting tracks in {playlist_name}")
        extracted_tracks[playlist_name] = get_playlist_tracks(client, playlist_id)
    return extracted_tracks

def log_and_save(tracks_to_save: Dict[str, List[str]]):
    """
    Logs all songs to a daily CSV
    """

    all_tracks = [track for playlist in tracks_to_save.values() for track in playlist]
    # Updated to filter out 'None' or invalid date strings
    song_years = [
        int(track.split('::')[-2].split('-')[0])
        for track in all_tracks
        if track.split('::')[-2] and track.split('::')[-2] != 'None'
            and track.split('::')[-2].split('-')[0].isdigit()
    ]

    content = '\n'.join(
        [f"{playlist}: {', '.join(tracks)}" for playlist, tracks in tracks_to_save.items()])
    file_name = f"{datetime.date.today()}.csv"
    file_path = f"{cab.get('path', 'cabinet', 'log-backup')}/songs/{file_name}"

    cab.write_file(content=content, file_name=file_name, path_file=file_path)

    cab.log("Updated Spotify Log")
    average_year = mean(song_years) if song_years else 0
    cab.put("spotipy", "average_year", str(average_year))

    if tracks_to_save['Tyler Radio']:
        cab.put("spotipy", "total_tracks", len(tracks_to_save['Tyler Radio']))
    cab.log(f"Setting average year to {average_year}")
    cab.log(f"{datetime.datetime.now().strftime('%Y-%m-%d')},{average_year}",
            log_name="SPOTIPY_AVERAGE_YEAR_LOG", log_folder_path=cab.get("path", "log"),
            is_quiet=True)

def extract():
    """
    main function to extract and process Spotify playlists.
    """

    playlists = cab.get("spotipy", "playlists")
    if not playlists or len(playlists) < 2:
        cab.log("Could not resolve Spotify playlists", level="error")
        return

    client = initialize_spotify_client()
    extracted_tracks = extract_playlists_tracks(client, playlists)
    log_and_save(extracted_tracks)

    return extracted_tracks

def check_for_a_in_b(a_tracks, b_tracks, inverse=False, a_name='', b_name=''):
    """
    checks whether the item from Playlist A is in Playlist B
    logs an error or a success message depending on the results and "inverse"
    """

    cab.log(
        f"Checking that every track in {a_name} is {'' if not inverse else 'not '}in {b_name}",
        log_name="LOG_SPOTIFY")

    is_success = True
    for track in a_tracks:
        if (track in b_tracks) == inverse:
            is_success = False
            cab.log(
                f"{track} {'' if inverse else 'not '}in {b_name}",
                    log_name="LOG_SPOTIFY", level="error")
    if is_success:
        cab.log("Looks good!", log_name="LOG_SPOTIFY")


def check_for_one_match_in_playlists(tracks_array: List[List[str]], playlist_names: List[str]):
    """
    checks whether every track is in exactly one genre playlist (hardcoded).
    genre playlists start from index 2 of tracks_array to account for 'Last 25 Added'
    at index 1.
    """

    main_playlist = tracks_array[0]
    genre_playlists = tracks_array[2:]

    track_genre_count = {track: 0 for track in main_playlist}

    cab.log(f"Checking that each track in {playlist_names[0]} is in exactly one genre.")
    for track in main_playlist:
        for genre_playlist in genre_playlists:
            if track in genre_playlist:
                track_genre_count[track] += 1

    issues = []

    for track, count in track_genre_count.items():
        if count != 1:
            issues.append(f"Track '{track}' appears in {count} genre playlists.")

    if issues:
        for issue in issues:
            cab.log(issue, level="error")
    else:
        cab.log("Looks good!")

if __name__ == "__main__":
    playlists_tracks = extract()

    if not playlists_tracks:
        cab.log("Spotipy Unable to Extract Tracks", level="error")
        sys.exit()

    for playlist, tracks in playlists_tracks.items():
        if len(tracks) > 0:
            cab.write_file(content=str(playlists_tracks),
                file_name="LOG_SPOTIPY_PLAYLIST_DATA", path_file=PATH_LOG)

    # caution- this code is necessarily fragile and assumes the data in the `SPOTIPY_PLAYLISTS` file
    # matches the example file in README.md.

    tracks_list = list(playlists_tracks.values())
    tracks_names_list = list(playlists_tracks.keys())

    # 1. check `Last 25 Added` and songs from each genre playlist are in `Tyler Radio`
    for i, _ in enumerate(tracks_list[1:8]):
        check_for_a_in_b(tracks_list[i+1], tracks_list[0],
            False, tracks_names_list[i+1], tracks_names_list[0])

    # 2. check that any song from `Removed` is not in `Tyler Radio`
    check_for_a_in_b(tracks_list[8], tracks_list[0],
        True, tracks_names_list[8], tracks_names_list[0])

    # 3. check that songs from `Tyler Radio` have exactly one genre playlist
    check_for_one_match_in_playlists(tracks_list, tracks_names_list[0:7])
