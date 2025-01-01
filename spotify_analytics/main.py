"""
spotipy-analytics
A tool to backup and analyze Spotify library data including title, artist, and year information.
Requires spotipy library and appropriate Spotify API credentials.
"""

import os
import datetime
import json
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional
from statistics import mean
import logging
from pathlib import Path

import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from cabinet import Cabinet

@dataclass
class Track:
    """Represents a Spotify track with essential metadata."""
    index: int
    artist: str
    name: str
    release_date: str
    spotify_url: str

    @classmethod
    def from_spotify_track(cls, index: int, track: Dict) -> 'Track':
        """Create a Track instance from Spotify API track data."""
        return cls(
            index=index,
            artist=track['artists'][0]['name'],
            name=track['name'],
            release_date=str(track['album']['release_date']),
            spotify_url=track['external_urls']['spotify'] if not track['is_local'] else ''
        )

@dataclass
class PlaylistData:
    """Represents a Spotify playlist with its tracks."""
    name: str
    tracks: List[str]  # List of Spotify URLs

class SpotifyAnalyzer:
    """Handles Spotify playlist analysis and backup."""

    def __init__(self, cabinet: Cabinet):
        self.cab = cabinet
        self.logger = self._setup_logging()
        self.spotify_client = self._initialize_spotify_client()
        self.main_tracks: List[Track] = []
        self.playlist_data: List[PlaylistData] = []
        self.song_years: List[int] = []

    def _setup_logging(self) -> logging.Logger:
        """Configure logging for the application."""
        logger = logging.getLogger('spotify_analyzer')
        logger.setLevel(logging.INFO)
        return logger

    def _initialize_spotify_client(self) -> spotipy.Spotify:
        """Initialize and return Spotify client with proper credentials."""
        try:
            client_id = self.cab.get("spotipy", "client_id")
            client_secret = self.cab.get("spotipy", "client_secret")
            if client_id is None:
                raise ValueError("Spotify client ID is not set in cabinet")
            if client_secret is None:
                raise ValueError("Spotify client secret is not set in cabinet")
            os.environ['SPOTIPY_CLIENT_ID'] = client_id
            os.environ['SPOTIPY_CLIENT_SECRET'] = client_secret
            os.environ['SPOTIPY_REDIRECT_URI'] = 'http://localhost:8888'

            credentials_manager = SpotifyClientCredentials()
            return spotipy.Spotify(client_credentials_manager=credentials_manager)

        except Exception as e:
            self.cab.log(f"Failed to initialize Spotify client: {str(e)}", level="error")
            raise

    def _get_playlist(self, playlist_id: str) -> Optional[Dict]:
        """Fetch playlist data from Spotify."""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                return self.spotify_client.playlist(playlist_id)
            except Exception as e: # pylint: disable=broad-except
                self.cab.log(f"Attempt {attempt + 1} failed: {str(e)}", level="warning")
                if attempt == max_retries - 1:
                    self.cab.log(f"Failed to fetch playlist {playlist_id} after 3 attempts",
                                 level="error")
                    raise

    def _process_tracks(self, tracks: Dict, playlist_name: str,
                        playlist_index: int, total_tracks: int) -> List[str]:
        """Process tracks from a playlist and return track URLs."""
        track_urls = []

        for _, item in enumerate(tracks['items']):
            track = item['track']
            if not track:
                continue

            if not track['is_local']:
                track_urls.append(track['external_urls']['spotify'])

            if playlist_index == 0:  # Main playlist
                track_obj = Track.from_spotify_track(len(self.main_tracks) + 1, track)
                self.main_tracks.append(track_obj)

                if track['album']['release_date']:
                    try:
                        year = int(track['album']['release_date'].split("-")[0])
                        self.song_years.append(year)
                    except ValueError:
                        self.cab.log(f"Invalid release date format for track: {track['name']}",
                                     level="warning")

                print(f"Processed {len(self.main_tracks)} of {total_tracks} in {playlist_name}")

        return track_urls

    def analyze_playlists(self):
        """Main method to analyze all configured playlists."""
        playlists = self.cab.get("spotipy", "playlists")
        if not playlists or len(playlists) < 2:
            self.cab.log("Insufficient playlist configuration")
            raise ValueError("At least two playlists must be configured")

        for index, item in enumerate(playlists):
            if ',' not in item:
                continue

            playlist_id, playlist_name = item.split(',')
            self.cab.log(f"Processing playlist: {playlist_name}")

            playlist_data = self._get_playlist(playlist_id)
            if not playlist_data:
                continue

            tracks = playlist_data['tracks']
            total_tracks = tracks['total']

            if index == 0:
                self.cab.put("spotipy", "total_tracks", total_tracks)

            playlist_tracks = []
            while True:
                if not tracks:
                    self.cab.log("No tracks found in playlist", level="warning")
                    break
                playlist_tracks.extend(self._process_tracks(tracks,
                                                            playlist_name,
                                                            index,
                                                            total_tracks))
                if not tracks['next']:
                    break
                tracks = self.spotify_client.next(tracks)

            self.playlist_data.append(PlaylistData(name=playlist_name, tracks=playlist_tracks))

        self._save_data()
        self._update_statistics()

    def _save_data(self):
        """Save processed track data to JSON file."""

        log_backup_path: str = self.cab.get('path', 'cabinet', 'log-backup') or str(Path.home())
        output_path = Path(log_backup_path) / "songs"
        output_path.mkdir(parents=True, exist_ok=True)

        output_file = output_path / f"{datetime.date.today()}.json"
        track_data = [asdict(track) for track in self.main_tracks]

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(track_data, f, indent=2, ensure_ascii=False)

        self.cab.log(f"Saved track data to {output_file}")

    def _update_statistics(self):
        """Update and log statistics about the analyzed tracks."""
        if self.song_years:
            avg_year = mean(self.song_years)
            self.cab.put("spotipy", "average_year", avg_year)

            log_path = Path(self.cab.get('path', 'log') or str(Path.home()))
            log_entry = f"{datetime.datetime.now().strftime('%Y-%m-%d')},{avg_year}"

            self.cab.log(log_entry, log_name="SPOTIPY_AVERAGE_YEAR_LOG",
                         log_folder_path=str(log_path))

    def validate_playlists(self):
        """Validate playlist contents according to business rules."""
        self._validate_playlist_inclusion()
        self._validate_removed_tracks()
        self._validate_genre_assignments()

    def _validate_playlist_inclusion(self):
        """Verify that tracks from each genre playlist are in the main playlist."""
        main_playlist = self.playlist_data[0]
        for playlist in self.playlist_data[1:8]:  # Genre playlists
            self._check_playlist_subset(playlist, main_playlist)

    def _validate_removed_tracks(self):
        """Verify that removed tracks are not in the main playlist."""
        if len(self.playlist_data) > 8:
            self._check_playlist_exclusion(self.playlist_data[8], self.playlist_data[0])

    def _validate_genre_assignments(self):
        """Verify that each track appears in exactly one genre playlist."""
        main_tracks = set(self.playlist_data[0].tracks)
        genre_assignments = {}

        for playlist in self.playlist_data[2:8]:  # Genre playlists
            for track in playlist.tracks:
                if track in genre_assignments:
                    genres = f"{playlist.name} and {genre_assignments[track]}"
                    self.cab.log(f"Track {track} found in multiple genres: {genres}",
                                 level="warning")
                genre_assignments[track] = playlist.name

        for track in main_tracks:
            if track not in genre_assignments:
                self.cab.log(f"Track {track} missing genre assignment", level="warning")

    def _check_playlist_subset(self, subset: PlaylistData, superset: PlaylistData):
        """Verify that all tracks in subset appear in superset."""
        missing = set(subset.tracks) - set(superset.tracks)
        if missing:
            self.cab.log(f"Tracks from {subset.name} missing from {superset.name}: {missing}")

    def _check_playlist_exclusion(self, excluded: PlaylistData, main_playlist: PlaylistData):
        """Verify that no tracks from excluded appear in main."""
        present = set(excluded.tracks) & set(main_playlist.tracks)
        if present:
            self.cab.log(f"Removed tracks still present in {main_playlist.name}: {present}")

def main():
    """Main entry point for the script."""
    cab = Cabinet()
    analyzer = SpotifyAnalyzer(cab)

    try:
        analyzer.analyze_playlists()
        analyzer.validate_playlists()
    except Exception as e:
        logging.error("Analysis failed: %s", str(e))
        raise

if __name__ == '__main__':
    main()
