"""
spotipy-analytics
A tool to backup and analyze Spotify library data including title, artist, and year information.
Requires spotipy library and appropriate Spotify API credentials.
"""

import os
import sys
import errno
import atexit
import time
import datetime
import json
import subprocess
import socket
import argparse
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional, Tuple
from statistics import mean
import logging
from pathlib import Path
from collections import Counter

import re

import spotipy
from spotipy.oauth2 import SpotifyClientCredentials, SpotifyOAuth
from cabinet import Cabinet
from tyler_python_helpers import ChatGPT


@dataclass
class Track:
    """Represents a Spotify track with essential metadata."""

    index: int
    artist: str
    name: str
    release_date: str
    spotify_url: str
    added_at: Optional[str] = None
    genre: Optional[str] = None

    @classmethod
    def from_spotify_track(
        cls,
        index: int,
        track: Dict,
        added_at: Optional[str] = None,
        genre: Optional[str] = None,
    ) -> "Track":
        """Create a Track instance from Spotify API track data."""
        return cls(
            index=index,
            artist=track["artists"][0]["name"],
            name=track["name"],
            release_date=str(track["album"]["release_date"]),
            spotify_url=(track["external_urls"]["spotify"] if not track["is_local"] else ""),
            added_at=added_at,
            genre=genre,
        )


@dataclass
class PlaylistData:
    """Represents a Spotify playlist with its tracks."""

    name: str
    tracks: List[str]  # List of Spotify URLs
    playlist_id: Optional[str] = None  # Spotify playlist ID for modifications


class SpotifyAnalyzer:
    """Handles Spotify playlist analysis and backup."""

    VALID_GENRES = [
        "Chill and Lofi",
        "Hip-Hop and Rap",
        "Party and EDM",
        "Pop",
        "R&B",
        "Rock",
    ]

    # Batch size for ChatGPT genre classification
    # Smaller batches reduce token usage and improve reliability
    GENRE_BATCH_SIZE = 40

    def __init__(self, cabinet: Cabinet):
        self.cab = cabinet
        self.logger = self._setup_logging()
        self.spotify_client = self._initialize_spotify_client()
        self.main_tracks: List[Track] = []
        self.playlist_data: List[PlaylistData] = []
        self.song_years: List[int] = []
        self.log_path = None
        self.is_git_repo = False
        self._playlists_cache: Optional[List[str]] = None
        self._oauth_client: Optional[spotipy.Spotify] = None
        self._oauth_port: Optional[int] = None
        self._chatgpt: Optional[ChatGPT] = None
        self._genre_cache: Dict[str, str] = {}  # Cache spotify_url -> genre
        self._pending_classifications: List[Tuple[Track, str]] = []  # Tracks needing classification

        # Register cleanup function to run on exit
        atexit.register(self._cleanup_oauth_port)

    def _setup_logging(self) -> logging.Logger:
        """Configure logging for the application."""
        logger = logging.getLogger("spotify_analyzer")
        logger.setLevel(logging.INFO)
        return logger

    def _initialize_chatgpt(self) -> ChatGPT:
        """Initialize ChatGPT client for genre classification."""
        if self._chatgpt is None:
            self._chatgpt = ChatGPT()
        return self._chatgpt

    def _classify_genre(self, artist: str, song_name: str) -> str:
        """Classify a song's genre using ChatGPT with rate limit handling.

        Args:
            artist: Artist name
            song_name: Song name

        Returns:
            One of the valid genre options or "Error"
        """
        genres_list = "\n".join(f"- {genre}" for genre in self.VALID_GENRES)
        prompt = f"""
Select exactly one label from the following enum.
The output must be one of these exact strings or the response is invalid:

{genres_list}
---
IMPORTANT DEFINITIONS:
- "Party and EDM" means electronic dance music intended for DJ club play
  (e.g., house, techno, trance, dubstep).
  It must be primarily electronic, beat-driven, and suitable for a dance club.
  DO NOT use this genre for hip-hop, rap, pop, rock, R&B, comedy, acoustic,
  or band-based songs, even if they are upbeat or popular.
- "Chill and Lofi" means songs that are slow, mellow, and relaxing, often with a focus on instrumental or acoustic elements.
  It must be primarily acoustic, instrumental, or have a slow, relaxed tempo.
  DO NOT use this genre for hip-hop, rap, pop, rock, R&B, comedy, electronic, or band-based songs, even if they are slow or mellow.

Song: "{song_name}" by {artist}

Respond with ONLY the genre name, nothing else.
You must choose one of the options above.
If the song’s true genre is not listed, choose the closest available genre from the list.
"""

        return self._retry_chatgpt_classification(
            lambda: self._execute_chatgpt_query(prompt), song_name, artist
        )

    def _classify_genres_batch(self, songs: List[Tuple[str, str]]) -> List[str]:
        """Classify multiple songs' genres in a single ChatGPT query.

        Args:
            songs: List of (artist, song_name) tuples

        Returns:
            List of genres corresponding to each song, or "Error" for failed classifications
        """
        if not songs:
            return []

        genres_list = "\n".join(f"- {genre}" for genre in self.VALID_GENRES)
        songs_list = "\n".join(
            f'{i+1}. "{song_name}" by {artist}' for i, (artist, song_name) in enumerate(songs)
        )

        prompt = f"""Classify the following songs into exactly one of these genres:
{genres_list}

Songs:
{songs_list}

Respond with a JSON array of genres, one for each song in the same order.
Each genre must be exactly one of the options above. Example: ["Pop", "Rock", "Hip-Hop and Rap"]

IMPORTANT: The array size must exactly match the number of songs provided or the response is invalid.
"""

        # Retry logic for batch classification
        max_retries = 3
        base_delay = 2
        for attempt in range(max_retries):
            try:
                response = self._execute_chatgpt_query(prompt)

                # Try to parse as JSON array
                try:
                    # Extract JSON array from response (handle markdown code blocks)
                    response_clean = response.strip()
                    if response_clean.startswith("```"):
                        # Remove markdown code blocks
                        lines = response_clean.split("\n")
                        response_clean = (
                            "\n".join(lines[1:-1]) if len(lines) > 2 else response_clean
                        )
                    elif response_clean.startswith("```json"):
                        lines = response_clean.split("\n")
                        response_clean = (
                            "\n".join(lines[1:-1]) if len(lines) > 2 else response_clean
                        )

                    genres = json.loads(response_clean)
                    if not isinstance(genres, list):
                        raise ValueError(f"Expected list of genres, got {type(genres).__name__}")

                    # Validate we got the correct number of genres
                    # If we got fewer, we can't be sure they align correctly, so retry the batch
                    if len(genres) < len(songs):
                        raise ValueError(
                            f"Got {len(genres)} genres instead of {len(songs)}. "
                            "Cannot guarantee alignment - retrying batch."
                        )
                    elif len(genres) > len(songs):
                        self.cab.log(
                            f"SPOTIFY - ChatGPT returned {len(genres)} genres "
                            f"instead of {len(songs)}. Truncating to expected length",
                            level="warning",
                        )
                        genres = genres[: len(songs)]

                    # Validate each genre
                    validated_genres = []
                    for i, genre in enumerate(genres):
                        artist, song_name = songs[i]
                        validated = self._validate_genre_response(
                            str(genre), song_name=song_name, artist=artist
                        )
                        validated_genres.append(validated)
                        if validated == "Error":
                            self.cab.log(
                                f"SPOTIFY - Batch classification failed for song "
                                f"{i+1}: '{song_name}' by {artist}",
                                level="warning",
                            )
                    return validated_genres
                except (json.JSONDecodeError, ValueError, TypeError) as e:
                    if attempt < max_retries - 1:
                        delay = base_delay * (2**attempt)
                        self.cab.log(
                            f"SPOTIFY - Failed to parse batch classification response "
                            f"(attempt {attempt + 1}/{max_retries}): {e}. "
                            f"Retrying in {delay}s...",
                            level="info",
                        )
                        time.sleep(delay)
                        continue
                    else:
                        self.cab.log(
                            f"SPOTIFY - Failed to parse batch classification response "
                            f"after {max_retries} attempts: {e}. "
                            f"Response: {response}",
                            level="info",
                        )
                        # Fallback to individual classification
                        return self._classify_genres_individually(songs, "batch classification")
            except Exception as e:  # pylint: disable=broad-except
                error_str = str(e)
                is_rate_limit = self._is_rate_limit_error(error_str)

                if attempt < max_retries - 1:
                    # Calculate exponential backoff delay
                    delay = self._calculate_exponential_backoff_delay(
                        attempt, base_delay, is_rate_limit
                    )
                    if is_rate_limit:
                        self.cab.log(
                            f"SPOTIFY - Rate limit hit during batch classification. "
                            f"Retrying in {delay}s... (attempt {attempt + 1}/{max_retries})",
                            level="warning",
                        )
                    else:
                        self.cab.log(
                            f"SPOTIFY - Batch classification failed: {error_str}. "
                            f"Retrying in {delay}s... (attempt {attempt + 1}/{max_retries})",
                            level="warning",
                        )
                    time.sleep(delay)
                else:
                    self.cab.log(
                        f"SPOTIFY - Batch classification failed after {max_retries} "
                        f"attempts: {error_str}",
                        level="error",
                    )
                    # Fallback to individual classification
                    return self._classify_genres_individually(songs, "batch classification")

        # If we somehow exit the loop without returning, fallback to individual classification
        return self._classify_genres_individually(songs, "batch classification")

    def _execute_chatgpt_query(self, prompt: str) -> str:
        """Execute a ChatGPT query and return the response."""
        chatgpt = self._initialize_chatgpt()
        return chatgpt.query(prompt).strip()

    def _is_rate_limit_error(self, error_str: str) -> bool:
        """Check if an error string indicates a rate limit error.

        Args:
            error_str: Error string to check

        Returns:
            True if error indicates rate limit, False otherwise
        """
        return (
            "429" in error_str
            or "rate limit" in error_str.lower()
            or "too many requests" in error_str.lower()
        )

    def _calculate_exponential_backoff_delay(
        self, attempt: int, base_delay: int, is_rate_limit: bool = False
    ) -> int:
        """Calculate exponential backoff delay for retries.

        Args:
            attempt: Current attempt number (0-indexed)
            base_delay: Base delay in seconds
            is_rate_limit: Whether this is a rate limit error (uses longer delays)

        Returns:
            Delay in seconds
        """
        if is_rate_limit:
            return base_delay * (2**attempt) * 2  # Longer delay for rate limits
        return base_delay * (2**attempt)

    def _classify_genres_individually(
        self, songs: List[Tuple[str, str]], context: str = "classification"
    ) -> List[str]:
        """Classify songs individually as a fallback when batch classification fails.

        Args:
            songs: List of (artist, song_name) tuples
            context: Context string for logging (e.g., "batch classification")

        Returns:
            List of genres corresponding to each song
        """
        self.cab.log(
            f"SPOTIFY - Falling back to individual {context} for {len(songs)} songs",
            level="info",
        )
        genres = []
        for artist, song_name in songs:
            genres.append(self._classify_genre(artist, song_name))
            # Small delay between individual requests to avoid rate limits
            if len(songs) > 1:
                time.sleep(0.2)
        return genres

    def _classify_tracks_batch_or_individual(
        self,
        tracks: List[Track],
        log_context: str = "classification",
        log_level: str = "info",
    ) -> None:
        """Classify tracks in batches or individually, updating cache and track objects.

        Args:
            tracks: List of Track objects to classify
            log_context: Context string for logging (e.g., "missing genres", "invalid genres")
            log_level: Log level for batch processing message
        """
        if not tracks:
            return

        # Store old genres for logging (for invalid genres case)
        old_genres = {track.spotify_url: track.genre for track in tracks if track.spotify_url}

        if len(tracks) >= 10:
            # Process in batches
            total_tracks = len(tracks)
            self.cab.log(
                f"SPOTIFY - Batch classifying {total_tracks} tracks "
                f"({log_context}) in batches of {self.GENRE_BATCH_SIZE}",
                level=log_level,
            )

            for batch_start in range(0, total_tracks, self.GENRE_BATCH_SIZE):
                batch_end = min(batch_start + self.GENRE_BATCH_SIZE, total_tracks)
                batch = tracks[batch_start:batch_end]

                songs = [(t.artist, t.name) for t in batch]
                self.cab.log(
                    f"SPOTIFY - Batch classifying tracks "
                    f"{batch_start + 1}-{batch_end} of {total_tracks}",
                    level="info",
                )
                genres = self._classify_genres_batch(songs)

                # Update tracks and cache
                for i, track in enumerate(batch):
                    genre = genres[i] if i < len(genres) else "Error"
                    self._genre_cache[track.spotify_url] = genre
                    old_genre = old_genres.get(track.spotify_url)
                    track.genre = genre
                    if log_context == "classification":
                        log_msg = (
                            f"SPOTIFY - Classified '{track.name}' by {track.artist} "
                            f"as '{genre}'"
                        )
                        log_level_msg = "info"
                    else:
                        if old_genre and log_context == "invalid genres":
                            log_msg = (
                                f"SPOTIFY - Retried classification for '{track.name}' "
                                f"by {track.artist}: '{genre}' (was '{old_genre}')"
                            )
                        else:
                            log_msg = (
                                f"SPOTIFY - Retried classification for '{track.name}' "
                                f"by {track.artist}: '{genre}'"
                            )
                        log_level_msg = "debug"
                    self.cab.log(log_msg, level=log_level_msg)

                # Small delay between batches to avoid rate limits
                if batch_end < total_tracks:
                    time.sleep(1)
        else:
            # Individual classification with small delay to avoid rate limits
            for track in tracks:
                genre = self._classify_genre(track.artist, track.name)
                self._genre_cache[track.spotify_url] = genre
                old_genre = old_genres.get(track.spotify_url)
                track.genre = genre
                if log_context == "classification":
                    log_msg = f"SPOTIFY - Classified '{track.name}' by {track.artist} as '{genre}'"
                    log_level_msg = "info"
                else:
                    if old_genre and log_context == "invalid genres":
                        log_msg = (
                            f"SPOTIFY - Retried classification for '{track.name}' "
                            f"by {track.artist}: '{genre}' (was '{old_genre}')"
                        )
                    else:
                        log_msg = (
                            f"SPOTIFY - Retried classification for '{track.name}' "
                            f"by {track.artist}: '{genre}'"
                        )
                    log_level_msg = "debug"
                self.cab.log(log_msg, level=log_level_msg)
                # Small delay between individual requests to avoid rate limits
                if len(tracks) > 1:
                    time.sleep(0.2)

    def _validate_genre_response(
        self,
        response: str,
        song_name: Optional[str] = None,
        artist: Optional[str] = None,
    ) -> str:
        """Validate and normalize a genre response from ChatGPT.

        Args:
            response: Raw response from ChatGPT
            song_name: Optional song name for logging
            artist: Optional artist name for logging

        Returns:
            Validated genre string or "Error"
        """
        response = response.strip().strip('"').strip("'")

        # Validate response matches one of the valid genres
        for genre in self.VALID_GENRES:
            if genre.lower() == response.lower():
                return genre

        # If response doesn't match exactly, try to find closest match
        response_lower = response.lower()
        for genre in self.VALID_GENRES:
            if genre.lower() in response_lower or response_lower in genre.lower():
                self.cab.log(
                    f"SPOTIFY - ChatGPT returned '{response}', mapped to '{genre}'",
                    level="debug",
                )
                return genre

        # Default fallback - return "Error" to indicate classification failure
        track_info = ""
        if song_name and artist:
            track_info = f" for '{song_name}' by {artist}"
        elif song_name:
            track_info = f" for '{song_name}'"
        self.cab.log(
            f"SPOTIFY - ChatGPT returned unexpected genre '{response}', "
            f"cannot classify{track_info}",
            level="warning",
        )
        return "Error"

    def _retry_chatgpt_classification(
        self,
        query_func,
        song_name: str,
        artist: str,
        max_retries: int = 3,
        base_delay: int = 2,
    ) -> str:
        """Retry ChatGPT classification with exponential backoff and rate limit handling.

        Args:
            query_func: Callable that executes the ChatGPT query
            song_name: Song name for logging
            artist: Artist name for logging
            max_retries: Maximum number of retry attempts
            base_delay: Base delay in seconds for exponential backoff

        Returns:
            Classified genre or "Error"
        """
        for attempt in range(max_retries):
            try:
                response = query_func()
                return self._validate_genre_response(response, song_name=song_name, artist=artist)
            except Exception as e:  # pylint: disable=broad-except
                error_str = str(e)
                is_rate_limit = self._is_rate_limit_error(error_str)

                if attempt < max_retries - 1:
                    # Calculate exponential backoff delay
                    delay = self._calculate_exponential_backoff_delay(
                        attempt, base_delay, is_rate_limit
                    )
                    if is_rate_limit:
                        self.cab.log(
                            f"SPOTIFY - Rate limit hit for '{song_name}' by {artist}. "
                            f"Retrying in {delay}s... (attempt {attempt + 1}/{max_retries})",
                            level="warning",
                        )
                    else:
                        self.cab.log(
                            f"SPOTIFY - Classification failed for '{song_name}' "
                            f"by {artist}: {error_str}. "
                            f"Retrying in {delay}s... "
                            f"(attempt {attempt + 1}/{max_retries})",
                            level="warning",
                        )
                    time.sleep(delay)
                else:
                    # Last attempt failed
                    self.cab.log(
                        f"SPOTIFY - Failed to classify genre for '{song_name}' "
                        f"by {artist} after {max_retries} attempts: {error_str}",
                        level="error",
                    )
                    return "Error"

        return "Error"

    def _initialize_spotify_client(self) -> spotipy.Spotify:
        """Initialize and return Spotify client with proper credentials."""
        try:
            client_id = self.cab.get("spotipy", "client_id")
            client_secret = self.cab.get("spotipy", "client_secret")
            if client_id is None:
                raise ValueError("Spotify client ID is not set in cabinet")
            if client_secret is None:
                raise ValueError("Spotify client secret is not set in cabinet")
            os.environ["SPOTIPY_CLIENT_ID"] = client_id
            os.environ["SPOTIPY_CLIENT_SECRET"] = client_secret
            os.environ["SPOTIPY_REDIRECT_URI"] = "http://127.0.0.1:8888"

            credentials_manager = SpotifyClientCredentials()
            return spotipy.Spotify(client_credentials_manager=credentials_manager)

        except Exception as e:
            self.cab.log(
                f"SPOTIFY - Failed to initialize Spotify client: {str(e)}",
                level="error",
            )
            raise

    def _get_playlists(self) -> List[str]:
        """Get playlist configuration from cabinet, caching the result."""
        if self._playlists_cache is None:
            self._playlists_cache = self.cab.get("spotipy", "playlists") or []
        return self._playlists_cache

    def _parse_playlist_config(self, playlist_config: str) -> Optional[Tuple[str, str]]:
        """Parse playlist configuration string into (playlist_id, playlist_name).

        Returns:
            Tuple of (playlist_id, playlist_name) if valid, None otherwise.
        """
        if not playlist_config or "," not in playlist_config:
            return None
        playlist_id, playlist_name = playlist_config.split(",", 1)
        return (playlist_id.strip(), playlist_name.strip())

    def _retry_api_call(self, api_func, max_retries=3, base_delay=1, operation_name="API call"):
        """Retry an API call with exponential backoff.

        Args:
            api_func: Callable that performs the API call
            max_retries: Maximum number of retry attempts (default: 3)
            base_delay: Base delay in seconds for exponential backoff (default: 1)
            operation_name: Name of the operation for logging (default: "API call")

        Returns:
            Result of the API call

        Raises:
            Exception: The last exception if all retries fail
        """
        for attempt in range(max_retries):
            try:
                return api_func()
            except Exception as e:  # pylint: disable=broad-except
                error_str = str(e)

                if attempt < max_retries - 1:
                    # Calculate exponential backoff delay
                    delay = base_delay * (2**attempt)
                    self.cab.log(
                        f"SPOTIFY - {operation_name} attempt "
                        f"{attempt + 1}/{max_retries} failed: {error_str}. "
                        f"Retrying in {delay}s...",
                        level="warning",
                    )
                    time.sleep(delay)
                else:
                    # Last attempt failed
                    self.cab.log(
                        f"SPOTIFY - {operation_name} failed after {max_retries} "
                        f"attempts: {error_str}",
                        level="error",
                    )
                    raise

    def _get_playlist(self, playlist_id: str) -> Optional[Dict]:
        """Fetch playlist data from Spotify."""
        return self._retry_api_call(
            lambda: self.spotify_client.playlist(playlist_id),
            operation_name=f"Fetch playlist {playlist_id}",
        )

    def _check_duplicates(self, tracks: List[str], playlist_name: str, playlist_id: str):
        """Check for duplicate tracks within a playlist and automatically remove them.

        Keeps one occurrence of each duplicate track and removes the rest.
        Only warns if removal fails.

        Args:
            tracks: List of track URLs
            playlist_name: Name of the playlist for logging
            playlist_id: Spotify playlist ID for removal operations
        """
        # Extract track IDs from URLs for reliable duplicate detection
        track_ids = []
        url_to_id_map = {}  # Map track_id -> first URL seen (for logging)
        for url in tracks:
            track_id = self._extract_track_id(url)
            if track_id:
                track_ids.append(track_id)
                if track_id not in url_to_id_map:
                    url_to_id_map[track_id] = url
            else:
                # If we can't extract track ID, fall back to URL-based detection
                track_ids.append(url)
                if url not in url_to_id_map:
                    url_to_id_map[url] = url

        track_counts = Counter(track_ids)
        duplicates = {track_id: count for track_id, count in track_counts.items() if count > 1}

        if duplicates:
            oauth_client = None
            try:
                oauth_client = self._initialize_oauth_client()
            except Exception as e:
                self.cab.log(
                    f"SPOTIFY - Failed to initialize OAuth client for duplicate "
                    f"removal in {playlist_name}: {str(e)}",
                    level="warning",
                )
                # Fall back to just logging duplicates if OAuth fails
                for track_id, count in duplicates.items():
                    url = url_to_id_map.get(track_id, track_id)
                    self.cab.log(
                        f"SPOTIFY - Duplicate found in {playlist_name}: {url} "
                        f"appears {count} times (removal failed)",
                        level="warning",
                    )
                return

            for track_id, count in duplicates.items():
                url = url_to_id_map.get(track_id, track_id)
                # Remove all occurrences of the duplicate track
                try:
                    # Use default argument to capture track_id properly
                    self._retry_api_call(
                        lambda tid=track_id: oauth_client.playlist_remove_all_occurrences_of_items(
                            playlist_id, [tid]
                        ),
                        operation_name=f"Remove duplicate track from '{playlist_name}'",
                    )
                    # Add back one occurrence
                    self._retry_api_call(
                        lambda tid=track_id: oauth_client.playlist_add_items(playlist_id, [tid]),
                        operation_name=f"Re-add track to '{playlist_name}'",
                    )
                    self.cab.log(
                        f"SPOTIFY - Removed {count - 1} duplicate(s) of {url} from {playlist_name}",
                        level="info",
                    )
                except Exception as e:
                    self.cab.log(
                        f"SPOTIFY - Failed to remove duplicate {url} from "
                        f"{playlist_name}: {str(e)}",
                        level="warning",
                    )

    def _process_tracks(
        self, tracks: Dict, playlist_name: str, playlist_index: int, total_tracks: int
    ) -> List[str]:
        """Process tracks from a playlist and return track URLs.

        Note: Classification is deferred to allow batching across all pages.
        Tracks needing classification are collected in self._pending_classifications.
        """
        track_urls = []

        for _, item in enumerate(tracks["items"]):
            track = item["track"]
            if not track:
                continue

            if not track["is_local"]:
                track_urls.append(track["external_urls"]["spotify"])

            if playlist_index == 0:  # Main playlist
                added_at = item.get("added_at")
                spotify_url = track["external_urls"]["spotify"] if not track["is_local"] else ""

                # Check if genre is cached
                genre = self._genre_cache.get(spotify_url) if spotify_url else None

                # Create track object
                if not spotify_url:
                    # Local file, default to Pop
                    genre = "Pop"

                track_obj = Track.from_spotify_track(
                    len(self.main_tracks) + 1, track, added_at, genre=genre
                )
                self.main_tracks.append(track_obj)

                # If not cached, collect for batch processing after all pages are processed
                if not genre and spotify_url:
                    if not hasattr(self, "_pending_classifications"):
                        self._pending_classifications = []
                    self._pending_classifications.append((track_obj, spotify_url))

                if track["album"]["release_date"]:
                    try:
                        year = int(track["album"]["release_date"].split("-")[0])
                        self.song_years.append(year)
                    except ValueError:
                        self.cab.log(
                            f"SPOTIFY - Invalid release date format for track: {track['name']}",
                            level="debug",
                        )

                print(f"Processed {len(self.main_tracks)} of {total_tracks} in {playlist_name}")

        return track_urls

    def _process_pending_classifications(self):
        """Process all tracks that need classification, using batching when possible.

        Chunks large batches into smaller groups to avoid token limits.
        """
        if not hasattr(self, "_pending_classifications") or not self._pending_classifications:
            return

        tracks_needing_classification = self._pending_classifications
        self._pending_classifications = []  # Clear the list

        # Extract Track objects from tuples for batch processing
        tracks_to_classify = [track_obj for track_obj, _ in tracks_needing_classification]
        self._classify_tracks_batch_or_individual(tracks_to_classify, "classification")

    def spotify_log(self, message, level="info", log_folder_path=None, log_name=None):
        """
        Wrapper function for cab.log that uses cabinet path structure for Spotify logs.
        """
        today = datetime.date.today()
        if log_folder_path is None:
            log_base_path = self.cab.get("path", "log") or "~/.cabinet/log"
            log_folder_path = os.path.join(log_base_path, str(today))
        if log_name is None:
            log_name = f"LOG_SPOTIFY_{today}"
        self.cab.log(message, level=level, log_folder_path=log_folder_path, log_name=log_name)

    def _validate_and_retry_genres(self):
        """Validate that all tracks have valid genres and retry classification for missing ones."""
        tracks_missing_genre = []
        tracks_invalid_genre = []

        for track in self.main_tracks:
            if not track.genre:
                tracks_missing_genre.append(track)
            elif track.genre not in self.VALID_GENRES:
                tracks_invalid_genre.append(track)

        # Process missing genres
        if tracks_missing_genre:
            self.cab.log(
                f"SPOTIFY - Found {len(tracks_missing_genre)} tracks missing "
                f"genre, retrying classification",
                level="info",
            )

            # Separate tracks with URLs (can be classified) from local files
            tracks_to_classify = [t for t in tracks_missing_genre if t.spotify_url]
            local_files = [t for t in tracks_missing_genre if not t.spotify_url]

            # Handle local files
            for track in local_files:
                track.genre = "Pop"
                self.cab.log(
                    f"SPOTIFY - Local file '{track.name}' by {track.artist} defaulted to 'Pop'",
                    level="debug",
                )

            # Classify tracks with URLs
            if tracks_to_classify:
                # Check cache first
                tracks_needing_api_call = []
                for track in tracks_to_classify:
                    genre = self._genre_cache.get(track.spotify_url)
                    if genre:
                        track.genre = genre
                        self.cab.log(
                            f"SPOTIFY - Found cached genre for '{track.name}' "
                            f"by {track.artist}: '{genre}'",
                            level="debug",
                        )
                    else:
                        tracks_needing_api_call.append(track)

                # Batch or individual classification (chunked to avoid token limits)
                self._classify_tracks_batch_or_individual(
                    tracks_needing_api_call, "missing genres", "info"
                )

        # Process invalid genres
        if tracks_invalid_genre:
            self.cab.log(
                f"SPOTIFY - Found {len(tracks_invalid_genre)} tracks with "
                f"invalid genres, retrying classification",
                level="warning",
            )

            tracks_with_urls = [t for t in tracks_invalid_genre if t.spotify_url]
            local_files = [t for t in tracks_invalid_genre if not t.spotify_url]

            # Handle local files
            for track in local_files:
                track.genre = "Pop"

            # Batch or individual classification for invalid genres (chunked to avoid token limits)
            self._classify_tracks_batch_or_individual(tracks_with_urls, "invalid genres", "info")

        # Final validation
        still_missing = [
            t for t in self.main_tracks if not t.genre or t.genre not in self.VALID_GENRES
        ]
        if still_missing:
            track_list = ", ".join([f"'{t.name}' by {t.artist}" for t in still_missing[:5]])
            if len(still_missing) > 5:
                track_list += f" (and {len(still_missing) - 5} more)"
            self.cab.log(
                f"SPOTIFY - Warning: {len(still_missing)} tracks still missing "
                f"valid genres after retry: {track_list}",
                level="warning",
            )
        else:
            self.cab.log("SPOTIFY - All tracks have valid genres", level="info")

    def analyze_playlists(self):
        """Main method to analyze all configured playlists."""
        # Load genre cache from existing JSON before processing
        self._load_genre_cache_from_json()

        playlists = self._get_playlists()
        if not playlists or len(playlists) < 2:
            self.cab.log("SPOTIFY - Insufficient playlist configuration", level="error")
            raise ValueError("At least two playlists must be configured")

        for index, item in enumerate(playlists):
            parsed = self._parse_playlist_config(item)
            if not parsed:
                continue

            playlist_id, playlist_name = parsed
            self.cab.log(f"SPOTIFY - Processing playlist: {playlist_name}")

            playlist_data = self._get_playlist(playlist_id)
            if not playlist_data:
                continue

            tracks = playlist_data["tracks"]
            total_tracks = tracks["total"]

            if index == 0:
                self.cab.put("spotipy", "total_tracks", total_tracks)

            playlist_tracks = []
            while True:
                if not tracks:
                    self.cab.log("SPOTIFY - No tracks found in playlist", level="warning")
                    break
                playlist_tracks.extend(
                    self._process_tracks(tracks, playlist_name, index, total_tracks)
                )
                if not tracks["next"]:
                    break
                tracks = self._retry_api_call(
                    lambda t=tracks: self.spotify_client.next(t),
                    operation_name=f"Fetch next page for playlist {playlist_name}",
                )

            # Check for duplicates in the playlist and remove them
            self._check_duplicates(playlist_tracks, playlist_name, playlist_id)

            self.playlist_data.append(
                PlaylistData(name=playlist_name, tracks=playlist_tracks, playlist_id=playlist_id)
            )

        # Process all pending classifications (batch across all pages)
        self._process_pending_classifications()

        # Validate and retry genres for all tracks
        self._validate_and_retry_genres()

        self._save_data()
        self._update_statistics()

    def _save_data(self):
        """Save processed track data to JSON file."""
        # Use existing path if already set by prepare_git_repo
        if self.log_path is None:
            log_path: str = self.cab.get("path", "log") or str(Path.home())
            self.log_path = Path(log_path)

        output_path = self.log_path
        output_path.mkdir(parents=True, exist_ok=True)

        output_file = output_path / "spotify songs.json"
        track_data = [asdict(track) for track in self.main_tracks]

        # Gracefully update existing file or create new one
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(track_data, f, indent=2, ensure_ascii=False)

        self.cab.log(f"SPOTIFY - Saved track data to {output_file}")

    def _load_genre_cache_from_json(self, json_file: Optional[Path] = None) -> None:
        """Load genre cache from existing JSON file.

        Args:
            json_file: Path to JSON file. If None, uses default location.
        """
        if json_file is None:
            if self.log_path is None:
                log_path: str = self.cab.get("path", "log") or str(Path.home())
                self.log_path = Path(log_path)
            json_file = self.log_path / "spotify songs.json"
        else:
            json_file = Path(json_file)

        if not json_file.exists():
            self.cab.log(
                f"SPOTIFY - JSON file not found for genre cache: {json_file}",
                level="debug",
            )
            return

        try:
            with open(json_file, "r", encoding="utf-8") as f:
                track_data = json.load(f)

            # Build cache: spotify_url -> genre
            # Skip "Error" genres so they get retried
            for track_dict in track_data:
                spotify_url = track_dict.get("spotify_url", "")
                genre = track_dict.get("genre")
                if spotify_url and genre and genre != "Error":
                    self._genre_cache[spotify_url] = genre

            self.cab.log(f"SPOTIFY - Loaded {len(self._genre_cache)} genres from cache")

        except json.JSONDecodeError as e:
            self.cab.log(f"SPOTIFY - Invalid JSON when loading genre cache: {e}", level="warning")
        except Exception as e:
            self.cab.log(f"SPOTIFY - Error loading genre cache: {e}", level="warning")

    def _load_tracks_from_json(self, json_file: Optional[str] = None) -> None:
        """Load tracks from existing JSON file into main_tracks.

        Args:
            json_file: Path to JSON file. If None, uses default location.
        """
        if json_file is None:
            # Use same path logic as _save_data
            if self.log_path is None:
                log_path: str = self.cab.get("path", "log") or str(Path.home())
                self.log_path = Path(log_path)
            json_file = self.log_path / "spotify songs.json"
        else:
            json_file = Path(json_file)

        if not json_file.exists():
            self.cab.log(f"SPOTIFY - JSON file not found: {json_file}", level="error")
            raise FileNotFoundError(f"JSON file not found: {json_file}")

        self.cab.log(f"SPOTIFY - Loading tracks from {json_file}")

        try:
            with open(json_file, "r", encoding="utf-8") as f:
                track_data = json.load(f)

            # Convert dicts back to Track objects
            self.main_tracks = []
            for track_dict in track_data:
                track = Track(
                    index=track_dict.get("index", 0),
                    artist=track_dict.get("artist", ""),
                    name=track_dict.get("name", ""),
                    release_date=track_dict.get("release_date", ""),
                    spotify_url=track_dict.get("spotify_url", ""),
                    added_at=track_dict.get("added_at"),
                    genre=track_dict.get("genre"),
                )
                self.main_tracks.append(track)

            self.cab.log(f"SPOTIFY - Loaded {len(self.main_tracks)} tracks from JSON")

        except json.JSONDecodeError as e:
            self.cab.log(f"SPOTIFY - Invalid JSON in {json_file}: {e}", level="error")
            raise
        except Exception as e:
            self.cab.log(f"SPOTIFY - Error loading JSON: {e}", level="error")
            raise

    def _update_statistics(self):
        """Update and log statistics about the analyzed tracks."""
        if self.song_years:
            avg_year = mean(self.song_years)
            self.cab.put("spotipy", "average_year", avg_year)

            log_path = Path(self.cab.get("path", "log") or str(Path.home()))
            log_entry = f"{datetime.datetime.now().strftime('%Y-%m-%d')},{avg_year}"

            self.spotify_log(
                log_entry,
                log_name="SPOTIPY_AVERAGE_YEAR_LOG",
                log_folder_path=str(log_path),
            )

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

    def _add_track_to_playlist(self, playlist_id: str, track_url: str, playlist_name: str) -> bool:
        """Add a track to a playlist.

        Args:
            playlist_id: Spotify playlist ID
            track_url: Spotify track URL
            playlist_name: Playlist name for logging

        Returns:
            True if successful, False otherwise
        """
        track_id = self._extract_track_id(track_url)
        if not track_id:
            self.cab.log(
                f"SPOTIFY - Cannot add track to {playlist_name}: invalid URL {track_url}",
                level="warning",
            )
            return False

        try:
            oauth_client = self._initialize_oauth_client()
            self._retry_api_call(
                lambda tid=track_id: oauth_client.playlist_add_items(playlist_id, [tid]),
                operation_name=f"Add track to '{playlist_name}'",
            )
            return True
        except Exception as e:
            self.cab.log(
                f"SPOTIFY - Failed to add track {track_url} to {playlist_name}: {str(e)}",
                level="warning",
            )
            return False

    def _remove_track_from_playlist(
        self, playlist_id: str, track_url: str, playlist_name: str
    ) -> bool:
        """Remove a track from a playlist.

        Args:
            playlist_id: Spotify playlist ID
            track_url: Spotify track URL
            playlist_name: Playlist name for logging

        Returns:
            True if successful, False otherwise
        """
        track_id = self._extract_track_id(track_url)
        if not track_id:
            self.cab.log(
                f"SPOTIFY - Cannot remove track from {playlist_name}: invalid URL {track_url}",
                level="warning",
            )
            return False

        try:
            oauth_client = self._initialize_oauth_client()
            self._retry_api_call(
                lambda: oauth_client.playlist_remove_all_occurrences_of_items(
                    playlist_id, [track_id]
                ),
                operation_name=f"Remove track from '{playlist_name}'",
            )
            return True
        except Exception as e:
            self.cab.log(
                f"SPOTIFY - Failed to remove track {track_url} from {playlist_name}: {str(e)}",
                level="warning",
            )
            return False

    def _validate_genre_assignments(self):
        """Verify that each track appears in exactly one genre playlist.
        Adds missing tracks and removes duplicates based on JSON genre assignments."""
        if len(self.playlist_data) < 8:
            self.cab.log(
                "SPOTIFY - Not enough playlists loaded for genre validation",
                level="warning",
            )
            return

        main_tracks = set(self.playlist_data[0].tracks)
        genre_playlists = self.playlist_data[2:8]  # Genre playlists

        # Create mapping: track_url -> genre from JSON
        track_genre_map = {}
        for track in self.main_tracks:
            if track.spotify_url and track.genre and track.genre in self.VALID_GENRES:
                track_genre_map[track.spotify_url] = track.genre

        # Create mapping: genre_name -> playlist
        genre_to_playlist = {}
        for playlist in genre_playlists:
            # Extract genre name from playlist name (assuming playlist names match genre names)
            genre_to_playlist[playlist.name] = playlist

        # Track which playlists each track is in
        track_playlist_map = {}  # track_url -> list of playlist names it's in
        for playlist in genre_playlists:
            for track_url in playlist.tracks:
                if track_url not in track_playlist_map:
                    track_playlist_map[track_url] = []
                track_playlist_map[track_url].append(playlist.name)

        # Process each track in main playlist
        for track_url in main_tracks:
            expected_genre = track_genre_map.get(track_url)

            if not expected_genre:
                # Track doesn't have a genre in JSON, skip it
                continue

            expected_playlist = genre_to_playlist.get(expected_genre)
            if not expected_playlist or not expected_playlist.playlist_id:
                self.cab.log(
                    f"SPOTIFY - No playlist found for genre '{expected_genre}'",
                    level="warning",
                )
                continue

            # Check if track is in the correct playlist
            is_in_correct_playlist = track_url in expected_playlist.tracks

            # Check if track is in wrong playlists
            wrong_playlists = []
            if track_url in track_playlist_map:
                for playlist_name in track_playlist_map[track_url]:
                    if playlist_name != expected_genre:
                        wrong_playlists.append(playlist_name)

            # Add to correct playlist if missing
            if not is_in_correct_playlist:
                self.cab.log(
                    f"SPOTIFY - Adding track {track_url} to '{expected_genre}' playlist",
                    level="info",
                )
                success = self._add_track_to_playlist(
                    expected_playlist.playlist_id, track_url, expected_genre
                )
                if success:
                    # Update local data structure
                    expected_playlist.tracks.append(track_url)
                else:
                    self.cab.log(
                        f"SPOTIFY - Warning: Could not add track {track_url} "
                        f"to '{expected_genre}' playlist",
                        level="warning",
                    )

            # Remove from wrong playlists
            for wrong_playlist_name in wrong_playlists:
                wrong_playlist = genre_to_playlist.get(wrong_playlist_name)
                if wrong_playlist and wrong_playlist.playlist_id:
                    self.cab.log(
                        f"SPOTIFY - Removing track {track_url} from "
                        f"'{wrong_playlist_name}' playlist (should be in "
                        f"'{expected_genre}')",
                        level="info",
                    )
                    success = self._remove_track_from_playlist(
                        wrong_playlist.playlist_id, track_url, wrong_playlist_name
                    )
                    if success:
                        # Update local data structure
                        if track_url in wrong_playlist.tracks:
                            wrong_playlist.tracks.remove(track_url)
                    else:
                        self.cab.log(
                            f"SPOTIFY - Warning: Could not remove track "
                            f"{track_url} from '{wrong_playlist_name}' playlist",
                            level="warning",
                        )

    def _check_playlist_subset(self, subset: PlaylistData, superset: PlaylistData):
        """Verify that all tracks in subset appear in superset."""
        missing = set(subset.tracks) - set(superset.tracks)
        if missing:
            self.cab.log(
                f"SPOTIFY - Tracks from {subset.name} missing from {superset.name}: {missing}",
                level="warning",
            )

    def _check_playlist_exclusion(self, excluded: PlaylistData, main_playlist: PlaylistData):
        """Verify that no tracks from excluded appear in main."""
        present = set(excluded.tracks) & set(main_playlist.tracks)
        if present:
            self.cab.log(
                f"SPOTIFY - Removed tracks still present in {main_playlist.name}: {present}",
                level="warning",
            )

    def _is_git_repo(self, path: Path) -> bool:
        """Check if a path is a Git repository."""
        try:
            result = subprocess.run(
                ["git", "-C", str(path), "rev-parse", "--git-dir"],
                capture_output=True,
                text=True,
                check=False,
            )
            return result.returncode == 0
        except (subprocess.SubprocessError, OSError) as e:
            self.cab.log(f"SPOTIFY - Error checking Git repo: {str(e)}", level="debug")
            return False

    def _get_git_branch(self, path: Path) -> Optional[str]:
        """Get the current Git branch name."""
        try:
            result = subprocess.run(
                ["git", "-C", str(path), "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            self.cab.log(f"SPOTIFY - Error getting Git branch: {str(e)}", level="error")
            return None

    def _git_has_changes(self, path: Path) -> bool:
        """Check if Git repository has uncommitted changes."""
        try:
            result = subprocess.run(
                ["git", "-C", str(path), "status", "--porcelain"],
                capture_output=True,
                text=True,
                check=True,
            )
            return bool(result.stdout.strip())
        except subprocess.CalledProcessError as e:
            self.cab.log(f"SPOTIFY - Error checking Git changes: {str(e)}", level="error")
            return False

    def _sync_with_remote(self, path: Path, context: str = "sync") -> None:
        """Sync local repository with remote, handling divergence by resetting main to origin/main.

        Args:
            path: Path to Git repository
            context: Context string for log messages (e.g., "commit", "prepare")

        Raises:
            subprocess.CalledProcessError: If sync fails and we're not on main branch
        """
        # Fetch latest changes first
        subprocess.run(
            ["git", "-C", str(path), "fetch", "origin"],
            capture_output=True,
            text=True,
            check=True,
        )

        # Try fast-forward pull first
        pull_result = subprocess.run(
            ["git", "-C", str(path), "pull", "--ff-only"],
            capture_output=True,
            text=True,
            check=False,
        )

        if pull_result.returncode != 0:
            # If fast-forward fails (divergent branches), reset to origin/main
            # This is safe for a backup repository where we want main to match remote
            current_branch = self._get_git_branch(path)
            if current_branch == "main":
                self.cab.log(
                    f"SPOTIFY - Branches diverged during {context}, "
                    f"resetting main to match origin/main",
                    level="warn",
                )
                subprocess.run(
                    ["git", "-C", str(path), "reset", "--hard", "origin/main"],
                    capture_output=True,
                    text=True,
                    check=True,
                )
                self.cab.log("SPOTIFY - Reset main branch to match origin/main")
            else:
                # Not on main, can't safely reset - raise the error
                raise subprocess.CalledProcessError(
                    pull_result.returncode, "git pull", pull_result.stderr
                )

    def _git_commit(
        self, path: Path, message: str, skip_pull: bool = False, skip_push: bool = False
    ):
        """Commit changes in Git repository.

        Args:
            path: Path to Git repository
            message: Commit message
            skip_pull: If True, skip pulling before pushing
                (useful for new branches without upstream)
            skip_push: If True, skip pushing (useful when push will be done separately with -u flag)
        """
        try:
            subprocess.run(
                ["git", "-C", str(path), "add", "-A"],
                capture_output=True,
                text=True,
                check=True,
            )
            subprocess.run(
                ["git", "-C", str(path), "commit", "-m", message],
                capture_output=True,
                text=True,
                check=True,
            )
            # Pull latest changes before pushing to avoid conflicts (skip for new branches)
            if not skip_pull:
                # Check if current branch has upstream tracking
                branch_result = subprocess.run(
                    [
                        "git",
                        "-C",
                        str(path),
                        "rev-parse",
                        "--abbrev-ref",
                        "--symbolic-full-name",
                        "@{u}",
                    ],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if branch_result.returncode == 0:
                    # Branch has upstream, safe to pull
                    self._sync_with_remote(path, context="commit")
                # If no upstream, skip pull (will be set on push with -u)
            if not skip_push:
                subprocess.run(
                    ["git", "-C", str(path), "push"],
                    capture_output=True,
                    text=True,
                    check=True,
                )
            self.cab.log(f"SPOTIFY - Git commit successful: {message}")
        except subprocess.CalledProcessError as e:
            self.cab.log(f"SPOTIFY - Git commit failed: {e.stderr}", level="error")
            raise

    def prepare_git_repo(self):
        """Prepare Git repository before script execution."""
        log_path: str = self.cab.get("path", "log") or str(Path.home())
        self.log_path = Path(log_path)

        # Check if it's a Git repo
        if not self._is_git_repo(self.log_path):
            self.cab.log(
                f"SPOTIFY - {self.log_path} is not a Git repository",
                level="info",
            )
            return

        self.is_git_repo = True
        self.cab.log(f"SPOTIFY - Git repository detected at {self.log_path}")

        # Check current branch
        current_branch = self._get_git_branch(self.log_path)
        if current_branch is None:
            return

        # If on main branch and there are unsaved changes
        if current_branch == "main" and self._git_has_changes(self.log_path):
            today = datetime.date.today().strftime("%Y-%m-%d")
            hostname = socket.gethostname()
            new_branch = f"{hostname}-unsaved-changes-{today}"

            try:
                # Check if branch already exists
                branch_check = subprocess.run(
                    [
                        "git",
                        "-C",
                        str(self.log_path),
                        "show-ref",
                        "--verify",
                        "--quiet",
                        f"refs/heads/{new_branch}",
                    ],
                    capture_output=True,
                    text=True,
                    check=False,
                )

                if branch_check.returncode == 0:
                    # Branch exists - stash changes, checkout, then commit on the branch
                    self.cab.log(
                        f"SPOTIFY - Branch {new_branch} already exists. "
                        f"Stashing changes and checking out.",
                        level="info",
                    )
                    # Stash current changes
                    subprocess.run(
                        [
                            "git",
                            "-C",
                            str(self.log_path),
                            "stash",
                            "push",
                            "-m",
                            f"Auto-stash before checkout to {new_branch}",
                        ],
                        capture_output=True,
                        text=True,
                        check=True,
                    )
                    # Checkout to existing branch
                    subprocess.run(
                        [
                            "git",
                            "-C",
                            str(self.log_path),
                            "checkout",
                            new_branch,
                        ],
                        capture_output=True,
                        text=True,
                        check=True,
                    )
                    # Apply stashed changes
                    stash_result = subprocess.run(
                        [
                            "git",
                            "-C",
                            str(self.log_path),
                            "stash",
                            "pop",
                        ],
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    if stash_result.returncode != 0:
                        self.cab.log(
                            f"SPOTIFY - No stashed changes to apply "
                            f"(or stash conflict): {stash_result.stderr}",
                            level="info",
                        )
                    # Commit changes on the branch
                    if self._git_has_changes(self.log_path):
                        self._git_commit(
                            self.log_path,
                            f"Save unsaved changes from {hostname} on {today}",
                            skip_pull=True,
                            skip_push=True,
                        )
                else:
                    # Branch doesn't exist, create it
                    self.cab.log(
                        f"SPOTIFY - Unsaved changes detected on main branch. "
                        f"Creating branch: {new_branch}",
                        level="info",
                    )
                    subprocess.run(
                        [
                            "git",
                            "-C",
                            str(self.log_path),
                            "checkout",
                            "-b",
                            new_branch,
                        ],
                        capture_output=True,
                        text=True,
                        check=True,
                    )

                    # Commit changes (skip pull and push since this is a new branch
                    # without upstream)
                    # Push will be done separately with -u flag to set upstream
                    self._git_commit(
                        self.log_path,
                        f"Save unsaved changes from {hostname} on {today}",
                        skip_pull=True,
                        skip_push=True,
                    )

                # Push branch
                subprocess.run(
                    [
                        "git",
                        "-C",
                        str(self.log_path),
                        "push",
                        "-u",
                        "origin",
                        new_branch,
                    ],
                    capture_output=True,
                    text=True,
                    check=True,
                )

                self.cab.log(
                    f"SPOTIFY - Pushed unsaved changes to branch: {new_branch}",
                    level="warn",
                )

            except subprocess.CalledProcessError as e:
                self.cab.log(
                    f"SPOTIFY - Failed to save unsaved changes: {e.stderr}",
                    level="error",
                )
                raise

        # Checkout main and pull latest
        try:
            subprocess.run(
                ["git", "-C", str(self.log_path), "checkout", "main"],
                capture_output=True,
                text=True,
                check=True,
            )
            # Sync with remote (handles divergence automatically)
            self._sync_with_remote(self.log_path, context="prepare")
            self.cab.log("SPOTIFY - Checked out main branch and pulled latest changes")
        except subprocess.CalledProcessError as e:
            self.cab.log(
                f"SPOTIFY - Failed to checkout/pull main branch: {e.stderr}",
                level="error",
            )
            raise

    def _cleanup_oauth_port(self):
        """Cleanup function registered with atexit to free OAuth port on script exit."""
        if self._oauth_port:
            self._kill_processes_on_port(self._oauth_port)

    def _check_port_available(self, port: int) -> bool:
        """Check if a port is available."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("127.0.0.1", port))
                return True
        except OSError:
            return False

    def _kill_processes_on_port(self, port: int) -> bool:
        """Kill any processes using the specified port. Returns True if processes were killed."""
        try:
            # Find processes using the port
            result = subprocess.run(
                ["lsof", "-ti", f":{port}"],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode == 0 and result.stdout.strip():
                pids = result.stdout.strip().split("\n")
                killed_any = False
                for pid in pids:
                    pid = pid.strip()
                    if pid and pid.isdigit():
                        try:
                            # Check if it's a spotify_analytics process
                            ps_result = subprocess.run(
                                ["ps", "-p", pid, "-o", "args="],
                                capture_output=True,
                                text=True,
                                check=False,
                            )
                            if "spotify_analytics" in ps_result.stdout:
                                self.cab.log(
                                    f"SPOTIFY - Killing stale process {pid} using port {port}",
                                    level="info",
                                )
                                subprocess.run(
                                    ["kill", pid],
                                    capture_output=True,
                                    text=True,
                                    check=False,
                                )
                                killed_any = True
                        except Exception:
                            pass
                if killed_any:
                    # Wait a moment for the port to be released
                    time.sleep(1)
                    return True
            return False
        except FileNotFoundError:
            # lsof not available, try alternative method
            try:
                result = subprocess.run(
                    ["fuser", f"{port}/tcp"],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if result.returncode == 0:
                    # fuser outputs PIDs, kill them
                    pids = result.stdout.strip().split()
                    for pid in pids:
                        if pid.isdigit():
                            subprocess.run(
                                ["kill", pid],
                                capture_output=True,
                                text=True,
                                check=False,
                            )
                    return True
            except FileNotFoundError:
                pass
            return False
        except Exception as e:
            self.cab.log(
                f"SPOTIFY - Error checking/killing processes on port {port}: {e}",
                level="debug",
            )
            return False

    def _initialize_oauth_client(self) -> spotipy.Spotify:
        """Initialize Spotify client with OAuth authentication for playlist modifications."""
        try:
            client_id = self.cab.get("spotipy", "client_id")
            client_secret = self.cab.get("spotipy", "client_secret")
            username = self.cab.get("spotipy", "username")

            if not client_id:
                raise ValueError("Spotify client_id is not set in cabinet")
            if not client_secret:
                raise ValueError("Spotify client_secret is not set in cabinet")
            if not username:
                raise ValueError("Spotify username is not set in cabinet")

            # Set environment variables for spotipy
            # Try common redirect URI formats - user should match one in their dashboard
            # Most common: http://127.0.0.1:8888 or http://127.0.0.1:8888/callback
            redirect_uri = os.environ.get("SPOTIPY_REDIRECT_URI", "http://127.0.0.1:8888")

            # Extract port from redirect URI
            port_match = re.search(r":(\d+)", redirect_uri)
            redirect_port = int(port_match.group(1)) if port_match else 8888
            self._oauth_port = redirect_port

            # Use cache file based on username (spotipy convention)
            # Use absolute path so it works in cron jobs
            # (which run from different working directory)
            # This matches create_playlist_by_year.py so they share the same OAuth token
            # Store cache in script directory for consistency
            script_dir = Path(__file__).parent.absolute()
            cache_path = str(script_dir / f".cache-{username}")
            cache_file = Path(cache_path)

            # Check if cache file exists and appears valid
            # If we have a cached token, spotipy shouldn't need to start a server
            has_cache = cache_file.exists() and cache_file.stat().st_size > 0

            # Check if port is in use - kill stale processes if needed
            if not self._check_port_available(redirect_port):
                self.cab.log(
                    f"SPOTIFY - Port {redirect_port} is already in use. "
                    "Attempting to kill stale spotify_analytics processes...",
                    level="info",
                )
                killed = self._kill_processes_on_port(redirect_port)
                if killed:
                    self.cab.log(
                        f"SPOTIFY - Killed stale processes. Port {redirect_port} "
                        f"should now be available.",
                        level="info",
                    )
                else:
                    self.cab.log(
                        f"SPOTIFY - Could not kill processes on port {redirect_port}. "
                        "If OAuth fails, manually kill processes with: "
                        f"lsof -ti:{redirect_port} | xargs kill",
                        level="warning",
                    )

            os.environ["SPOTIPY_CLIENT_ID"] = client_id
            os.environ["SPOTIPY_CLIENT_SECRET"] = client_secret
            os.environ["SPOTIPY_REDIRECT_URI"] = redirect_uri

            # OAuth scope required for playlist modification
            scope = "playlist-modify-public playlist-modify-private"

            # Only open browser if we don't have a cached token
            # If we have a cache, spotipy will use it and won't need to start a server
            open_browser = not has_cache

            auth_manager = SpotifyOAuth(
                scope=scope,
                redirect_uri=redirect_uri,
                client_id=client_id,
                client_secret=client_secret,
                cache_path=cache_path,
                open_browser=open_browser,  # Only open browser if no cached token exists
                show_dialog=False,  # Don't force re-auth if token is valid
            )

            oauth_client = spotipy.Spotify(auth_manager=auth_manager)
            self._oauth_client = oauth_client
            return oauth_client

        except OSError as e:
            error_str = str(e)
            error_code = getattr(e, "errno", None)
            if (
                "Address already in use" in error_str
                or "98" in error_str
                or error_code == errno.EADDRINUSE
            ):
                self.cab.log(
                    f"SPOTIFY - Port conflict detected: {error_str}",
                    level="error",
                )
                self.cab.log(
                    f"SPOTIFY - Port {redirect_port} is already in use. "
                    "This typically happens when:",
                    level="warning",
                )
                self.cab.log(
                    "  1. Another Spotify script instance is running simultaneously",
                    level="warning",
                )
                self.cab.log(
                    "  2. A previous script instance didn't clean up properly",
                    level="warning",
                )
                self.cab.log(
                    f"SPOTIFY - Solution: Wait a few seconds and try again, "
                    f"or run: lsof -ti:{redirect_port} | xargs kill",
                    level="warning",
                )
            raise
        except Exception as e:
            self.cab.log(f"SPOTIFY - Failed to initialize OAuth client: {str(e)}", level="error")
            raise

    def _extract_track_id(self, url: str) -> Optional[str]:
        """Extract track ID from Spotify URL."""
        if not url:
            return None
        # Match pattern: https://open.spotify.com/track/TRACK_ID
        match = re.search(r"track/([a-zA-Z0-9]+)", url)
        return match.group(1) if match else None

    def update_last_25_added_playlist(self):
        """Update the 'Last 25 Added' playlist with the 25 most recently added tracks.

        Returns:
            bool: True if playlist was successfully updated, False otherwise.
        """
        if not self.main_tracks:
            self.cab.log(
                "SPOTIFY - No tracks available to update Last 25 Added playlist",
                level="error",
            )
            return False

        # Get playlist configuration (uses cached value if available)
        playlists = self._get_playlists()
        if not playlists or len(playlists) < 2:
            self.cab.log("SPOTIFY - Last 25 Added playlist not configured", level="error")
            return False

        # Get playlist[1] which should be the "Last 25 Added" playlist
        parsed = self._parse_playlist_config(playlists[1])
        if not parsed:
            self.cab.log(
                "SPOTIFY - Invalid playlist configuration for Last 25 Added",
                level="error",
            )
            return False

        playlist_id, playlist_name = parsed
        self.cab.log(f"SPOTIFY - Updating '{playlist_name}' with 25 most recently added tracks")

        # Filter tracks that have added_at timestamps and valid Spotify URLs
        # Note: Local files (empty spotify_url) cannot be added via API and are excluded
        local_file_count = sum(
            1 for track in self.main_tracks if track.added_at and not track.spotify_url
        )
        if local_file_count > 0:
            self.cab.log(
                f"SPOTIFY - Skipping {local_file_count} local file(s) (cannot be added via API)",
                level="info",
            )

        tracks_with_added_at = [
            track for track in self.main_tracks if track.added_at and track.spotify_url
        ]

        if not tracks_with_added_at:
            self.cab.log("SPOTIFY - No tracks with added_at timestamps found", level="error")
            return False

        # Sort by added_at (most recent first) - parse ISO 8601 timestamps
        def parse_timestamp(timestamp_str: str) -> datetime.datetime:
            try:
                # Handle ISO 8601 format with Z timezone
                return datetime.datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
            except ValueError:
                # Fallback for different formats
                return datetime.datetime.min

        tracks_with_added_at.sort(
            key=lambda t: (parse_timestamp(t.added_at) if t.added_at else datetime.datetime.min),
            reverse=True,
        )

        # Get the 25 most recent tracks
        top_25_tracks = tracks_with_added_at[:25]

        # Extract track IDs from URLs
        track_ids = []
        for track in top_25_tracks:
            track_id = self._extract_track_id(track.spotify_url)
            if track_id:
                track_ids.append(track_id)
            else:
                self.cab.log(
                    f"SPOTIFY - Could not extract track ID from URL: {track.spotify_url}",
                    level="warning",
                )

        if not track_ids:
            self.cab.log(
                "SPOTIFY - No valid track IDs found for Last 25 Added playlist",
                level="error",
            )
            return False

        self.cab.log(f"SPOTIFY - Found {len(track_ids)} tracks to add to '{playlist_name}'")

        # Initialize OAuth client for playlist modification
        try:
            oauth_client = self._initialize_oauth_client()

            # Replace all items in the playlist with the new tracks (with retry logic)
            self._retry_api_call(
                lambda tids=track_ids: oauth_client.playlist_replace_items(playlist_id, tids),
                operation_name=f"Update playlist '{playlist_name}'",
            )

            self.cab.log(
                f"SPOTIFY - Successfully updated '{playlist_name}' with {len(track_ids)} tracks"
            )
            return True

        except Exception as e:
            self.cab.log(
                f"SPOTIFY - Failed to update Last 25 Added playlist: {str(e)}",
                level="error",
            )
            # Don't raise - allow script to continue even if playlist update fails
            self.cab.log("SPOTIFY - Continuing with remaining operations", level="info")
            return False

    def commit_updated_data(self):
        """Commit the updated spotify songs.json file."""
        if not self.is_git_repo:
            # Double-check if it's a Git repo (in case prepare_git_repo wasn't called)
            if self.log_path and self._is_git_repo(self.log_path):
                self.is_git_repo = True
            else:
                self.cab.log(
                    "SPOTIFY - Not a Git repository, skipping commit",
                    level="info",
                )
                return

        if not self._git_has_changes(self.log_path):
            self.cab.log("SPOTIFY - No changes to commit", level="info")
            return

        today = datetime.date.today().strftime("%Y-%m-%d")
        commit_message = f"Update spotify songs.json for {today}"

        try:
            self._git_commit(self.log_path, commit_message)
            self.cab.log("SPOTIFY - Successfully committed and pushed! 🎉")
        except subprocess.CalledProcessError as e:
            self.cab.log(
                f"SPOTIFY - Failed to commit changes: {str(e)}",
                level="error",
            )
            raise


def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(description="Spotify playlist analysis and backup tool")
    parser.add_argument(
        "--update-last-25-only",
        action="store_true",
        help="Only update the 'Last 25 Added' playlist (loads tracks from existing JSON)",
    )
    parser.add_argument(
        "--json-file",
        type=str,
        help=("Path to JSON file (only used with --update-last-25-only " "or --genres-only)"),
    )
    parser.add_argument(
        "--genres-only",
        action="store_true",
        help=(
            "Only update genres for tracks in existing JSON file "
            "(loads, validates/retries genres, saves, commits)"
        ),
    )
    parser.add_argument(
        "--reclassify-genre",
        type=str,
        help=(
            "Reclassify all tracks with the specified genre (e.g., 'Party and EDM'). "
            "Loads from JSON, reclassifies matching tracks, saves, commits."
        ),
    )

    args = parser.parse_args()

    cab = Cabinet()
    analyzer = SpotifyAnalyzer(cab)

    try:
        playlist_update_success = False
        if args.reclassify_genre:
            # Reclassify tracks with a specific genre
            target_genre = args.reclassify_genre
            cab.log(f"SPOTIFY - Running in reclassify-genre mode for '{target_genre}'")

            # Validate the genre is valid
            if target_genre not in SpotifyAnalyzer.VALID_GENRES:
                valid_genres_str = ", ".join(SpotifyAnalyzer.VALID_GENRES)
                cab.log(
                    f"SPOTIFY - Invalid genre '{target_genre}'. "
                    f"Valid genres: {valid_genres_str}",
                    level="error",
                )
                sys.exit(1)

            # Prepare Git repository
            analyzer.prepare_git_repo()

            # Load genre cache from existing JSON (to avoid re-classifying other tracks)
            analyzer._load_genre_cache_from_json()  # pylint: disable=protected-access

            # Load tracks from existing JSON file
            analyzer._load_tracks_from_json(args.json_file)  # pylint: disable=protected-access

            # Find tracks with the target genre
            tracks_to_reclassify = [
                t for t in analyzer.main_tracks if t.genre == target_genre and t.spotify_url
            ]

            if not tracks_to_reclassify:
                cab.log(
                    f"SPOTIFY - No tracks found with genre '{target_genre}'",
                    level="info",
                )
                sys.exit(0)

            cab.log(
                f"SPOTIFY - Found {len(tracks_to_reclassify)} tracks with genre "
                f"'{target_genre}' to reclassify",
                level="info",
            )

            # Clear their genres and remove from cache so they get reclassified
            for track in tracks_to_reclassify:
                track.genre = None
                if track.spotify_url in analyzer._genre_cache:  # pylint: disable=protected-access
                    del analyzer._genre_cache[track.spotify_url]  # pylint: disable=protected-access

            # Reclassify using the existing validation/retry logic
            analyzer._validate_and_retry_genres()  # pylint: disable=protected-access

            # Save updated data
            analyzer._save_data()  # pylint: disable=protected-access

            # Commit updated data
            analyzer.commit_updated_data()

            cab.log(f"SPOTIFY - Reclassification of '{target_genre}' tracks completed successfully")
        elif args.genres_only:
            # Only update genres, skip all playlist processing
            cab.log("SPOTIFY - Running in genres-only mode")

            # Prepare Git repository before starting
            analyzer.prepare_git_repo()

            # Load genre cache from existing JSON
            analyzer._load_genre_cache_from_json()  # pylint: disable=protected-access

            # Load tracks from existing JSON file
            analyzer._load_tracks_from_json(args.json_file)  # pylint: disable=protected-access

            # Validate and retry genres for all tracks
            analyzer._validate_and_retry_genres()  # pylint: disable=protected-access

            # Save updated data
            analyzer._save_data()  # pylint: disable=protected-access

            # Commit updated data
            analyzer.commit_updated_data()

            cab.log("SPOTIFY - Genres-only update completed successfully")
        elif args.update_last_25_only:
            # Only update the playlist, skip all processing
            cab.log("SPOTIFY - Running in update-last-25-only mode")

            # Load tracks from existing JSON file
            analyzer._load_tracks_from_json(args.json_file)  # pylint: disable=protected-access

            # Update the playlist
            playlist_update_success = analyzer.update_last_25_added_playlist()

            if not playlist_update_success:
                cab.log(
                    "SPOTIFY - Playlist update failed in update-last-25-only mode",
                    level="error",
                )
                sys.exit(1)
        else:
            # Full processing mode
            # Prepare Git repository before starting
            analyzer.prepare_git_repo()

            # Run analysis and validation
            analyzer.analyze_playlists()
            analyzer.validate_playlists()

            # Update the "Last 25 Added" playlist with most recently added tracks
            playlist_update_success = analyzer.update_last_25_added_playlist()

            if not playlist_update_success:
                cab.log(
                    "SPOTIFY - Playlist update failed, but continuing with commit",
                    level="error",
                )

            # Commit updated data after validation
            analyzer.commit_updated_data()
    except Exception as e:
        logging.error("Analysis failed: %s", str(e))
        cab.log(f"SPOTIFY - Analysis failed: {str(e)}", level="error")
        raise


if __name__ == "__main__":
    main()
