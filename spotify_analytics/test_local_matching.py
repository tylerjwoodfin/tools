#!/usr/bin/env python3
"""Unit tests for local duplicate identity and genre membership (TJW-334)."""

import unittest

from main import PlaylistData, PlaylistTrackRef, SpotifyAnalyzer, Track


class FakeCab:
    """Capture Cabinet log messages."""

    def __init__(self):
        self.msgs = []

    def log(self, msg, level="info", **_kwargs):
        self.msgs.append((level, msg))


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


class TestGenreAssignmentNoPolicing(unittest.TestCase):
    """Exactly one genre playlist is enough; AI must not reassign."""

    def setUp(self):
        self.analyzer = object.__new__(SpotifyAnalyzer)
        self.analyzer._genre_cache = {}
        self.analyzer.cab = FakeCab()
        self.analyzer.VALID_GENRES = SpotifyAnalyzer.VALID_GENRES
        self.analyzer.playlist_data = [
            PlaylistData("Tyler Radio", [], None, []),
            PlaylistData("Last 25", [], None, []),
            PlaylistData("Chill and Lofi", [], "c", []),
            PlaylistData("Hip-Hop and Rap", [], "h", []),
            PlaylistData("Party and EDM", [], "p", []),
            PlaylistData("Pop", [], "o", []),
            PlaylistData("R&B", [], "r", []),
            PlaylistData("Rock", [], "k", []),
        ]

    def test_cookie_cutter_in_rnb_not_moved_to_ai_genre(self):
        track = Track(
            1,
            "Quasian",
            "Cookie Cutter",
            "",
            "",
            genre="Hip-Hop and Rap",
            is_local=True,
            album="[standalone recordings]",
        )
        self.analyzer.main_tracks = [track]
        self.analyzer.playlist_data[6] = PlaylistData(
            "R&B",
            [],
            "r",
            [
                PlaylistTrackRef(
                    "spotify:local:Quasian:[standalone recordings]:Cookie+Cutter:180",
                    "Cookie Cutter",
                    "Quasian",
                    "[standalone recordings]",
                    True,
                )
            ],
        )

        self.analyzer._validate_genre_assignments()

        self.assertEqual(track.genre, "R&B")
        joined = " ".join(msg for _, msg in self.analyzer.cab.msgs)
        self.assertNotIn("should be in", joined)
        self.assertNotIn("missing from", joined)

    def test_sparse_metadata_still_counts_as_one_genre(self):
        track = Track(
            1,
            "",
            "Cookie Cutter",
            "",
            "",
            genre="Chill and Lofi",
            is_local=True,
            album="",
            local_uri="spotify:local:::Cookie+Cutter:180",
        )
        self.analyzer.main_tracks = [track]
        self.analyzer.playlist_data[6] = PlaylistData(
            "R&B",
            [],
            "r",
            [PlaylistTrackRef("spotify:local:x", "Cookie Cutter", "Quasian", "Alb", True)],
        )

        self.assertEqual(self.analyzer._find_genre_playlists_for_track(track), ["R&B"])
        self.analyzer._validate_genre_assignments()
        self.assertEqual(track.genre, "R&B")
        self.assertFalse(
            any("should be in" in msg or "missing from" in msg for _, msg in self.analyzer.cab.msgs)
        )

    def test_catalog_already_in_one_genre_is_not_moved(self):
        url = "https://open.spotify.com/track/abc123abc123abc123abc1"
        track = Track(
            1,
            "Artist",
            "Song",
            "",
            url,
            genre="Rock",
            is_local=False,
            album="Album",
        )
        self.analyzer.main_tracks = [track]
        self.analyzer.playlist_data[5] = PlaylistData("Pop", [url], "o", [])

        self.analyzer._validate_genre_assignments()

        self.assertEqual(track.genre, "Pop")
        self.assertEqual(self.analyzer.playlist_data[5].tracks, [url])
        self.assertEqual(self.analyzer.playlist_data[7].tracks, [])
        joined = " ".join(msg for _, msg in self.analyzer.cab.msgs)
        self.assertNotIn("Adding track", joined)
        self.assertNotIn("Removing track", joined)
        self.assertNotIn("should be in", joined)

    def test_local_missing_all_genre_playlists_is_flagged(self):
        track = Track(
            1,
            "Quasian",
            "Cookie Cutter",
            "",
            "",
            genre="Hip-Hop and Rap",
            is_local=True,
            album="[standalone recordings]",
        )
        self.analyzer.main_tracks = [track]

        self.analyzer._validate_genre_assignments()

        self.assertTrue(
            any("missing from 'Hip-Hop and Rap'" in msg for _, msg in self.analyzer.cab.msgs)
        )


if __name__ == "__main__":
    unittest.main()
