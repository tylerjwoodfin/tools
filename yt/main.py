from sys import argv
from sys import exit
from os import system

#!/usr/bin/env python

import yt_dlp


def help():
    print("Usage: main.py {audio/video} {url}")
    exit(0)


is_video = True
url = ''

if len(argv) < 3:
    help()
else:
    if not argv[2].startswith('http'):
        help()

    url = argv[2]
    is_video = argv[1].lower() == 'video'

ydl_opts = {
    'format': 'mp3/bestaudio/best',
    'postprocessors': [{  # Extract audio using ffmpeg
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'mp3',
    }]
}

with yt_dlp.YoutubeDL(ydl_opts if not is_video else None) as ydl:
    error_code = ydl.download(url)

# move all downloads to desktop
system("mv *.webm ~/Desktop; mv *.mp3 ~/Desktop")
