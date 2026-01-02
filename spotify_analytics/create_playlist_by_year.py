#!/usr/bin/env python3
"""
Create a Spotify playlist from songs with a specific release year.
Used for tracking songs by release year.
Uses spotipy with OAuth authentication (required for playlist creation).
"""

import json
import os
import re
import argparse
from pathlib import Path
from typing import List

import spotipy
from spotipy.oauth2 import SpotifyOAuth
from cabinet import Cabinet


def extract_track_id(url: str) -> str:
    """Extract track ID from Spotify URL."""
    if not url:
        return None
    # Match pattern: https://open.spotify.com/track/TRACK_ID
    match = re.search(r'track/([a-zA-Z0-9]+)', url)
    return match.group(1) if match else None


def get_songs_by_year(json_file: str, year: int) -> List[dict]:
    """Load and filter songs with the specified release year."""
    year_str = str(year)
    
    # Check if file exists
    if not Path(json_file).exists():
        raise FileNotFoundError(f"JSON file not found: {json_file}")
    
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            songs = json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in '{json_file}': {e}")
    
    filtered_songs = []
    for song in songs:
        release_date = song.get('release_date', '')
        if release_date and release_date != "None" and release_date.startswith(year_str):
            url = song.get('spotify_url', '') or ''
            track_id = extract_track_id(url)
            if track_id:
                filtered_songs.append({
                    'name': song.get('name', ''),
                    'artist': song.get('artist', '') or '',
                    'url': url,
                    'track_id': track_id
                })
    
    return filtered_songs


def initialize_spotify_client(cab: Cabinet) -> spotipy.Spotify:
    """Initialize Spotify client with OAuth authentication."""
    client_id = cab.get("spotipy", "client_id")
    client_secret = cab.get("spotipy", "client_secret")
    username = cab.get("spotipy", "username")
    
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
    
    os.environ["SPOTIPY_CLIENT_ID"] = client_id
    os.environ["SPOTIPY_CLIENT_SECRET"] = client_secret
    os.environ["SPOTIPY_REDIRECT_URI"] = redirect_uri
    
    print(f"Using redirect URI: {redirect_uri}")
    print(f"Client ID: {client_id[:10]}...")
    print("\n⚠️  IMPORTANT: Make sure this EXACT redirect URI is in your Spotify app settings:")
    print(f"   {redirect_uri}")
    print("\nIf you get an error, try adding one of these to your Spotify dashboard:")
    print("   - http://127.0.0.1:8888")
    print("   - http://127.0.0.1:8888/callback")
    print("   (Then update SPOTIPY_REDIRECT_URI environment variable to match)\n")
    
    # OAuth scope required for playlist creation
    scope = "playlist-modify-public playlist-modify-private"
    
    # Use cache file based on username (spotipy convention)
    cache_path = f".cache-{username}"
    
    # Create auth manager
    auth_manager = SpotifyOAuth(
        scope=scope,
        redirect_uri=redirect_uri,
        client_id=client_id,
        client_secret=client_secret,
        cache_path=cache_path,
        open_browser=True,  # Will open browser for authorization if needed
        show_dialog=True  # Show dialog to ensure fresh auth if needed
    )
    
    return spotipy.Spotify(auth_manager=auth_manager)


def create_playlist(sp: spotipy.Spotify, username: str, playlist_name: str, track_ids: List[str], year: int) -> str:
    """Create a playlist and add tracks to it."""
    # Create the playlist
    playlist = sp.user_playlist_create(
        user=username,
        name=playlist_name,
        description=f"Auto-generated playlist of songs released in {year} ({len(track_ids)} tracks)"
    )
    
    playlist_id = playlist['id']
    print(f"Created playlist: {playlist_name}")
    print(f"Playlist URL: {playlist['external_urls']['spotify']}")
    
    # Add tracks in batches of 100 (Spotify API limit)
    batch_size = 100
    for i in range(0, len(track_ids), batch_size):
        batch = track_ids[i:i + batch_size]
        sp.playlist_add_items(playlist_id, batch)
        print(f"Added tracks {i+1}-{min(i+batch_size, len(track_ids))} of {len(track_ids)}")
    
    return playlist['external_urls']['spotify']


def main():
    """Main function to create playlist from songs by year."""
    parser = argparse.ArgumentParser(
        description='Create a Spotify playlist from songs with a specific release year'
    )
    parser.add_argument(
        'year',
        type=int,
        help='Year to filter songs by (e.g., 2026)'
    )
    parser.add_argument(
        '--json-file',
        type=str,
        default='spotify songs.json',
        help='Path to the JSON file (default: spotify songs.json)'
    )
    parser.add_argument(
        '--playlist-name',
        type=str,
        help='Name for the playlist (default: "{year} Releases")'
    )
    
    args = parser.parse_args()
    year = args.year
    json_file = args.json_file
    playlist_name = args.playlist_name or f"{year} Releases"
    
    # Load songs from JSON
    print(f"Loading songs from {json_file}...")
    try:
        songs = get_songs_by_year(json_file, year)
    except FileNotFoundError as e:
        print(f"Error: {e}")
        return
    except ValueError as e:
        print(f"Error: {e}")
        return
    
    if not songs:
        print(f"No songs found with {year} release_date")
        return
    
    print(f"Found {len(songs)} songs with {year} release_date")
    
    # Initialize Spotify client
    cab = Cabinet()
    print("Initializing Spotify client...")
    
    # Check for and potentially clear old cache files with wrong redirect URI
    username = cab.get("spotipy", "username")
    if username:
        cache_path = f".cache-{username}"
        if os.path.exists(cache_path):
            print(f"Found existing cache file: {cache_path}")
            print("If you're getting redirect URI errors, try deleting this file and re-authenticating.")
    
    try:
        sp = initialize_spotify_client(cab)
        username = cab.get("spotipy", "username")
        
        # Test the connection by getting current user (this will trigger auth if needed)
        print("Testing authentication...")
        try:
            # Try to get a token first - this will show us the exact redirect URI being used
            token_info = sp.auth_manager.get_access_token(as_dict=False)
            if token_info:
                print("✓ Got access token successfully")
            current_user = sp.current_user()
            print(f"Authenticated as: {current_user.get('display_name', username)}")
        except Exception as auth_error:
            error_msg = str(auth_error)
            print(f"\n⚠️  Authentication error: {error_msg}")
            
            # Check if it's a redirect URI error
            if "INVALID_CLIENT" in error_msg or "redirect" in error_msg.lower() or "invalid redirect" in error_msg.lower():
                redirect_uri = os.environ.get("SPOTIPY_REDIRECT_URI", "http://127.0.0.1:8888")
                print(f"\n❌ Redirect URI Error!")
                print(f"The script is using: {redirect_uri}")
                print(f"\nPlease verify in your Spotify Dashboard:")
                print(f"1. Go to https://developer.spotify.com/dashboard")
                print(f"2. Click on your app")
                print(f"3. Click 'Edit Settings'")
                print(f"4. Check the 'Redirect URIs' section")
                print(f"5. Make sure '{redirect_uri}' is EXACTLY listed there")
                print(f"   - No trailing slashes")
                print(f"   - Exact match including http://")
                print(f"   - If it's not there, add it and click Save")
                print(f"\nIf you need to use a different redirect URI, set it as:")
                print(f"   export SPOTIPY_REDIRECT_URI='http://127.0.0.1:8888/callback'")
                print(f"   (or whatever matches your dashboard)")
                raise Exception("INVALID_CLIENT: Redirect URI mismatch") from auth_error
            raise
        
    except Exception as e:
        error_msg = str(e)
        print(f"\n❌ Error details: {error_msg}")
        if "INVALID_CLIENT" in error_msg or "redirect" in error_msg.lower() or "insecure" in error_msg.lower():
            print("\n❌ Error: Redirect URI not configured correctly in Spotify app settings.")
            print("\nTo fix this:")
            print("1. Go to https://developer.spotify.com/dashboard")
            print("2. Select your app")
            print("3. Click 'Edit Settings'")
            print("4. In 'Redirect URIs', make sure you have EXACTLY: http://127.0.0.1:8888")
            print("   - Remove 'http://localhost:8888' if present")
            print("   - Remove any trailing slashes")
            print("   - Must be exactly: http://127.0.0.1:8888")
            print("5. Click 'Add' and then 'Save'")
            print("\nIf you still get errors after updating:")
            username = cab.get("spotipy", "username")
            if username:
                cache_path = f".cache-{username}"
                print(f"- Delete the cache file: {cache_path}")
            print("- Wait a few minutes for changes to propagate")
            print("- Then run this script again")
        else:
            print(f"\n❌ Error initializing Spotify client: {e}")
        return
    
    # Extract track IDs
    track_ids = [song['track_id'] for song in songs]
    
    # Create playlist
    try:
        playlist_url = create_playlist(sp, username, playlist_name, track_ids, year)
        print(f"\n✅ Successfully created playlist!")
        print(f"Playlist URL: {playlist_url}")
        print(f"Total tracks: {len(track_ids)}")
    except Exception as e:
        print(f"\n❌ Error creating playlist: {e}")
        return


if __name__ == "__main__":
    main()

