#!/usr/bin/env python3
"""Unit tests for local duplicate identity (TJW-334)."""

import unittest

from main import SpotifyAnalyzer


class TestLocalMatching(unittest.TestCase):
    """Local files are compared by title + artist + album; catalog by URL."""

    def setUp(self):
        self.analyzer = object.__new__(SpotifyAnalyzer)

    def test_local_identity_case_insensitive(self):
        a = self.analyzer._local_identity("Song", "Artist", "Album")
        b = self.analyzer._local_identity("song", "artist", "album")
        self.assertEqual(a, b)

    def test_local_identity_requires_same_album(self):
        a = self.analyzer._local_identity("99 Red Balloons", "Nena", "Album A")
        b = self.analyzer._local_identity("99 Red Balloons", "Nena", "Album B")
        self.assertNotEqual(a, b)

    def test_local_identity_different_title_not_equal(self):
        a = self.analyzer._local_identity("99 Red Balloons", "Nena", "99 Luftballons")
        b = self.analyzer._local_identity("99 Luftballoons", "Nena", "99 Luftballons")
        self.assertNotEqual(a, b)

    def test_local_genre_key_includes_album(self):
        key = self.analyzer._local_genre_key("Song", "Artist", "Album")
        self.assertTrue(key.startswith("local:"))
        self.assertIn("album", key)

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
