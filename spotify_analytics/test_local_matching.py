#!/usr/bin/env python3
"""Unit tests for local/catalog title matching (TJW-334)."""

import unittest

from main import SpotifyAnalyzer


class TestLocalMatching(unittest.TestCase):
    """Artist/title similarity used for local song genre + duplicate checks."""

    def setUp(self):
        self.analyzer = object.__new__(SpotifyAnalyzer)

    def test_red_balloons_matches_luftballons(self):
        self.assertTrue(
            self.analyzer._tracks_are_same_song(
                "Nena", "99 Red Balloons", "Nena", "99 Luftballoons"
            )
        )

    def test_different_artists_do_not_match(self):
        self.assertFalse(
            self.analyzer._tracks_are_same_song(
                "Goldfinger", "99 Red Balloons", "Nena", "99 Luftballoons"
            )
        )

    def test_album_version_suffix_matches(self):
        self.assertTrue(
            self.analyzer._tracks_are_same_song(
                "Drake",
                "Hate Sleeping Alone",
                "Drake",
                "Hate Sleeping Alone (Album Version)",
            )
        )

    def test_local_genre_key_stable(self):
        key_a = self.analyzer._local_genre_key("Nena", "99 Red Balloons")
        key_b = self.analyzer._local_genre_key("nena", "99 Red Balloons")
        self.assertEqual(key_a, key_b)
        self.assertTrue(key_a.startswith("local:"))

    def test_extract_track_id_uri_and_url(self):
        self.assertEqual(
            self.analyzer._extract_track_id("spotify:track:4ZhPLoMzZwewHLLjV1J15c"),
            "4ZhPLoMzZwewHLLjV1J15c",
        )
        self.assertEqual(
            self.analyzer._extract_track_id(
                "https://open.spotify.com/track/4ZhPLoMzZwewHLLjV1J15c"
            ),
            "4ZhPLoMzZwewHLLjV1J15c",
        )
        self.assertIsNone(
            self.analyzer._extract_track_id("spotify:local:Nena::99+Red+Balloons:230")
        )


if __name__ == "__main__":
    unittest.main()
