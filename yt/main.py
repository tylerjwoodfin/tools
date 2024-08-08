#!/usr/bin/env python

"""
youtube downloader - see README.md
"""
import sys
import os
import argparse
import yt_dlp


def parse_arguments():
    """parse command line arguments"""
    parser = argparse.ArgumentParser(description="YouTube Downloader")
    parser.add_argument("media_type", choices=["audio", "video"], help="Type of media to download")
    parser.add_argument("url", help="YouTube URL to download from")
    parser.add_argument("-d", "--destination", default=".",
                        help="Destination directory for downloaded files")
    return parser.parse_args()


def download_media(url, is_video, destination):
    """download media from youtube"""
    # set options for audio download
    ydl_opts = {
        'format': 'mp3/bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
        }],
        'outtmpl': os.path.join(destination, '%(title)s.%(ext)s'),
    }

    # use default options for video download
    options = ydl_opts if not is_video else \
        {'outtmpl': os.path.join(destination, '%(title)s.%(ext)s')}

    # perform the download
    with yt_dlp.YoutubeDL(options) as ydl:
        return ydl.download([url])


def main():
    """main function to run the script"""
    args = parse_arguments()

    # create destination directory if it doesn't exist
    os.makedirs(args.destination, exist_ok=True)

    # download the media
    error_code = download_media(args.url, args.media_type == "video", args.destination)

    # check for errors
    if error_code:
        print(f"An error occurred. Error code: {error_code}")
        sys.exit(1)

    print(f"Download completed successfully. Files saved to: {args.destination}")


if __name__ == "__main__":
    main()
