# YouTube Downloader

A simple Python script to download YouTube videos and audio using the `yt_dlp` library.

Install the required packages from `requirements.md`:
```bash
pip3 install -r requirements.md
```

# Usage

## Download a specific video

To download a specific video or audio, specify the `audio` or `video` type and the YouTube URL:

```bash
python3 main.py {audio | video} {url} [-d <destination, optional>]
```

Examples:
```bash
python3 main.py audio https://www.youtube.com/watch?v=dQw4w9WgXcQ
python3 main.py video https://www.youtube.com/watch?v=dQw4w9WgXcQ -d ~/Downloads
```