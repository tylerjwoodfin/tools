#!/usr/bin/env python

"""
youtube downloader - see README.md
"""
import sys
from os import system
import yt_dlp


def help_usage():
    """
    describes how to use this script
    """
    print("Usage: main.py {audio/video} {url}")
    sys.exit(0)


IS_VIDEO = True
URL = ''

if len(sys.argv) < 3:
    help_usage()
else:
    if not sys.argv[2].startswith('http'):
        help_usage()

    URL = sys.argv[2]
    IS_VIDEO = sys.argv[1].lower() == 'video'

ydl_opts = {
    'format': 'mp3/bestaudio/best',
    'postprocessors': [{  # Extract audio using ffmpeg
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'mp3',
    }]
}

with yt_dlp.YoutubeDL(ydl_opts if not IS_VIDEO else None) as ydl:
    ERROR_CODE = ydl.download(URL)

# move all downloads to desktop
system("mv *.webm ~/Desktop; mv *.mp3 ~/Desktop")
