# YouTube Downloader

## Install

Install the required packages from `requirements.md`:
```bash
pip3 install -r requirements.md
```

## Usage

### Download a specific video

To download a specific video or audio, specify the `audio` or `video` type and the YouTube URL:

```bash
python3 main.py {audio | video} {url} [-d <destination, optional>]
```

Examples:
```bash
python3 main.py audio https://www.youtube.com/watch?v=dQw4w9WgXcQ
python3 main.py video https://www.youtube.com/watch?v=dQw4w9WgXcQ -d ~/Downloads
```

### Download all videos from Watch Later playlist

To download all videos from your "Watch Later" playlist, use the `--watch-later` flag. This requires YouTube API credentials (see below).

```bash
python3 main.py --watch-later -d <destination, optional>
```

Example:
```bash
python3 main.py --watch-later -d ~/syncthing/videos/youtube
```

Each downloaded video will be removed from the "Watch Later" playlist after successful download.

## YouTube API Setup

To download from your "Watch Later" playlist, set up YouTube API access:

1. Go to [Google Cloud Console](https://console.cloud.google.com/) and create a new project.
2. Enable the **YouTube Data API v3** for your project.
3. Create OAuth 2.0 credentials and download the `client_secret.json` file to the same directory as `main.py`.
4. The first time you run the script with `--watch-later`, you will be prompted to authenticate.

## Notes

- The script saves authentication details in `token.json` for future use.
- When using `--watch-later`, ensure `client_secret.json` is in the same directory as the script.