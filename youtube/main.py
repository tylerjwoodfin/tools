#!/usr/bin/env python

"""
YouTube downloader - see README.md
"""
import sys
import os
import argparse
import time
import json
import yt_dlp
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from cabinet import Cabinet

# Initialize Cabinet
cab = Cabinet()

# Retrieve configuration data from Cabinet
youtube_keys = cab.get("keys", "youtube")
if not youtube_keys or "client_secret" not in youtube_keys or "token" not in youtube_keys:
    cab.log("Error: YouTube API keys not found in Cabinet.", level="error")

if youtube_keys:
    CLIENT_SECRET = youtube_keys["client_secret"]  # OAuth client configuration
    TOKEN = youtube_keys["token"]  # OAuth token details
else:
    cab.log("Error: YouTube API keys are missing or incomplete.", level="error")
    sys.exit(1)

SCOPES = ['https://www.googleapis.com/auth/youtube']
WATCH_LATER_PLAYLIST_ID = 'WL'

def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description="YouTube Downloader")
    parser.add_argument("media_type",
                        choices=["audio", "video"],
                        nargs="?",
                        help="Type of media to download")
    parser.add_argument("url",
                        nargs="?",
                        help="YouTube URL to download from")
    parser.add_argument("-d", "--destination",
                        default=".",
                        help="Destination directory for downloaded files")
    parser.add_argument("--watch-later",
                        action="store_true",
                        help="Download all videos from Watch Later playlist")
    return parser.parse_args()

def authenticate_youtube():
    """Authenticate with the YouTube API."""
    creds = None
    if TOKEN:
        creds = Credentials.from_authorized_user_info(TOKEN, SCOPES)
    if not creds or not creds.valid:
        # Use the client secret directly from Cabinet instead of a file
        flow = InstalledAppFlow.from_client_config(CLIENT_SECRET, SCOPES)
        creds = flow.run_local_server(port=0)
        # Save the token back to Cabinet for future use
        cab.put("keys", "youtube",
                {"client_secret": CLIENT_SECRET, "token": json.loads(creds.to_json())})
    return build('youtube', 'v3', credentials=creds)


def download_media(url, is_video, destination):
    """Download media from YouTube"""
    ydl_opts = {
        'format': 'mp3/bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
        }],
        'outtmpl': os.path.join(destination, '%(title)s.%(ext)s'),
    }

    options = ydl_opts if not is_video else \
        {'outtmpl': os.path.join(destination, '%(title)s.%(ext)s')}

    with yt_dlp.YoutubeDL(options) as ydl:
        return ydl.download([url])

def download_watch_later(youtube, destination):
    """Download videos from the Watch Later playlist and remove them once downloaded."""
    request = youtube.playlistItems().list(
        part='snippet', playlistId=WATCH_LATER_PLAYLIST_ID, maxResults=10)
    response = request.execute()

    for item in response['items']:
        video_id = item['snippet']['resourceId']['videoId']
        video_title = item['snippet']['title']
        video_url = f'https://www.youtube.com/watch?v={video_id}'

        print(f'Downloading: {video_title}')

        error_code = download_media(video_url, is_video=True, destination=destination)
        if error_code:
            print(f"Error downloading {video_title}")
            continue

        print(f'Removing {video_title} from Watch Later')
        youtube.playlistItems().delete(id=item['id']).execute()
        time.sleep(1)

def main():
    """Main function to run the script."""
    args = parse_arguments()

    # Ensure destination directory exists
    os.makedirs(args.destination, exist_ok=True)

    # Check if downloading Watch Later playlist
    if args.watch_later:
        youtube = authenticate_youtube()
        download_watch_later(youtube, args.destination)
    else:
        # Download individual audio or video
        if not args.url:
            print("Error: URL is required unless --watch-later is specified.")
            sys.exit(1)

        is_video = args.media_type == "video"
        error_code = download_media(args.url, is_video, args.destination)

        if error_code:
            print(f"An error occurred. Error code: {error_code}")
            sys.exit(1)

    print(f"Download completed successfully. Files saved to: {args.destination}")

if __name__ == "__main__":
    main()
