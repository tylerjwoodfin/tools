#!/usr/bin/env python3
"""
Filter songs from spotify songs.json by release year.
Outputs filtered songs in a simple format.
"""

import json
import sys
import argparse
from pathlib import Path


def main():
    """Filter songs by release year and print results."""
    parser = argparse.ArgumentParser(
        description='Filter songs from spotify songs.json by release year'
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

    args = parser.parse_args()
    year = str(args.year)
    json_file = args.json_file

    # Check if file exists
    if not Path(json_file).exists():
        print(f"Error: File '{json_file}' not found", file=sys.stderr)
        sys.exit(1)

    # Load the JSON file
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            songs = json.load(f)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in '{json_file}': {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error reading '{json_file}': {e}", file=sys.stderr)
        sys.exit(1)

    # Filter songs with the specified year release_date
    filtered_songs = []
    for song in songs:
        release_date = song.get('release_date', '')
        # Check if release_date starts with the year (handles dates like "2025-01-01")
        if release_date and release_date != "None" and release_date.startswith(year):
            name = song.get('name', '')
            artist = song.get('artist', '') or ''
            url = song.get('spotify_url', '') or ''
            filtered_songs.append((name, artist, url))

    # Output in format "name // artist // url"
    if filtered_songs:
        for name, artist, url in filtered_songs:
            print(f"{name} \n {artist} \n {url}\n\n")
    else:
        print(f"No songs found with {year} release_date", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
