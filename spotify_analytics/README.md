# spotify-analytics
Checks for duplicate songs, unplayable songs (US market via Spotify `is_playable` /
track relinking), and songs missing from playlists.

Local files:
- Genres are classified with ChatGPT (OpenAI), same as catalog tracks — not hard-defaulted to Pop.
- Spotify Web API cannot add/move `spotify:local:` URIs; rule breaks (e.g. in Tyler Radio
  but missing from the genre playlist) are **flagged only**, not auto-fixed via catalog search.
- Duplicate detection: catalog tracks by Spotify URL/ID; local files by title + artist + album.

Unplayable detection:
- Playlist fetches use `market=US`.
- A track is reported when the playlist item's `track` is `null`, or when `is_playable` is explicitly `false`.
- Empty `available_markets` alone is **not** treated as unplayable (that field is unreliable without a market).
- Unplayable tracks are logged as warnings; they are not removed automatically.
- The **Removed** playlist is never reported (unplayable tracks there are expected).
- `spotify unplayable.json` (next to `spotify songs.json`) lists **Tyler Radio only** (first Cabinet `spotipy.playlists` entry). Other playlists (except Removed) are still warned about in logs.

List / refresh unplayable tracks (Phase 1):

```bash
python3 identify_unplayable.py              # read daily spotify unplayable.json
python3 identify_unplayable.py --live       # scan Tyler Radio via Spotipy
python3 identify_unplayable.py --live --json
python3 identify_unplayable.py --live --write ~/syncthing/log/spotify\ unplayable.json
python3 identify_unplayable.py --live --all-playlists   # include Removed / genres
```

Replace with local YouTube audio (Phase 2 — prefers duration-matched uploads, not long music videos):

```bash
# Preview selection only (no download) — Tyler Radio only by default
python3 replace_unplayable.py --dry-run --limit 5

# Download into ~/syncthing/music via music-stack `mp3` (beets/Navidrome path)
python3 replace_unplayable.py --limit 3 --yes

# After download, also remove greyed-out Spotify URIs from playlists
python3 replace_unplayable.py --limit 3 --yes --update-spotify

# Include Removed / other playlists (not just Tyler Radio)
python3 replace_unplayable.py --all-playlists --dry-run --limit 5
```

Matching rules:
- **Default scope: Tyler Radio only** (first Cabinet `spotipy.playlists` entry). Use `--all-playlists` or `--playlist NAME` to change.
- Skip placeholder titles/artists (`(unknown)`, `N/A`, empty, etc.)
- YouTube hit must include the Spotify artist in the video title or channel
- Prefer closest duration within ±15s (`--tolerance`), penalize clean/censored/live/cover/karaoke
- If Spotify marks the track explicit, further penalize clean/censored uploads
- Search tries `"Artist" Title` before looser queries (avoids same-title wrong-artist hits)

Spotify cannot add local files via API — `--update-spotify` only removes the unplayable URI once a local copy exists.

## dependencies
- [Spotify API access](https://stevesie.com/docs/pages/spotify-client-id-secret-developer-api)
- [Cabinet](https://github.com/tylerjwoodfin/cabinet)
- [Spotipy](https://spotipy.readthedocs.io)

## setup
1. `pip3 install -r requirements.md`
2. Obtain [Spotify API access](https://stevesie.com/docs/pages/spotify-client-id-secret-developer-api). Make note of the client ID and secret.
3. Install [Cabinet](https://github.com/tylerjwoodfin/cabinet)
4. Setup `Spotipy`
    - Configure `spotipy` in Cabinet using the `Example` below as a template.
    - Find your `playlist IDs` by going to Spotify, right-clicking on a playlist, then clicking "Share".
        - The ID is the last part of the URL, for instance: https://open.spotify.com/playlist/6hywO4jlkShcGKdTrez9yr
    - The first column in `playlists` is the `playlist ID`. The second column is just a label- make it anything you want. Mine are named after my playlists.
5. Adjust the code as you see fit. Your musical tastes are your own. My code is specific to my own music setup, which is:
    - Each new song is added to `Tyler Radio`, `Last 25 Added`, and the appropriate `genre playlist`
    - No song should be in multiple `genre playlists`
    - No song should exist in `Tyler Radio` but not in a `genre playlist`
    - No song should exist in a `genre playlist` but not in `Tyler Radio`
    - No song should exist in `Last 25 Added` but not in `Tyler Radio`
    - No song should exist in `Removed` and `Tyler Radio` simultaneously.

## usage
```python3 main.py```
(Note: this will take a minute. Spotipy limits you to 100 songs at a time.)

## example
```bash
{
    "spotipy": {
        "playlists": [
            "6oqyTmCc2uf3aTDvZRk1T2,Tyler Radio",
            "3ZDXHUzUcW6rLqOFpfK7QO,Last 25 Added",
            "09jNP5fuQesZoC7xiIj5I4,Chill",
            "2OFLLecfoHrlwvJtfCJQoP,Hip Hop and Rap",
            "3e691JWNU3anPtZgNfmFss,Party and EDM",
            "2Aop8CO3DC7K9qyM1WgloX,Pop",
            "4E8EyyhmbBUCAh9tNIYMv0,R&B",
            "6hywO4jlkShcGKdTrez9yr,Rock",
            "3zr0wmZocFR6nD6teH0dlm,Removed"
        ],
        "client_secret": "your_secret_here",
        "client_id": "your_id_here",
        "username": "your_spotify_username"
    }
}
```
