#!/usr/bin/env python3
"""Unit tests for Spotify library dump into music_new (TJW-328)."""

import tempfile
import unittest
from pathlib import Path

import download_library as dl


class SongsToJobsTests(unittest.TestCase):
    def test_skips_blank_artist_and_name(self):
        jobs, skipped_artist, skipped_name = dl.songs_to_jobs(
            [
                {"artist": "", "name": "22 Bath", "spotify_url": ""},
                {"artist": "Polo G", "name": "", "spotify_url": "https://x"},
                {
                    "artist": "Polo G",
                    "name": "Martin & Gina",
                    "spotify_url": "https://open.spotify.com/track/1VLtjHwRWOVJiE5Py7JxoQ",
                },
            ]
        )
        self.assertEqual(skipped_artist, 1)
        self.assertEqual(skipped_name, 1)
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["name"], "Martin & Gina")
        self.assertIn("1VLtjHwRWOVJiE5Py7JxoQ", jobs[0]["url"])

    def test_skips_unknown_placeholders(self):
        jobs, skipped_artist, skipped_name = dl.songs_to_jobs(
            [
                {"artist": "(unknown)", "name": "Song"},
                {"artist": "A", "name": "N/A"},
            ]
        )
        self.assertEqual(len(jobs), 0)
        self.assertEqual(skipped_artist, 1)
        self.assertEqual(skipped_name, 1)


class DestNamingTests(unittest.TestCase):
    def test_planned_stem_uses_title_when_free(self):
        self.assertEqual(dl.planned_stem("The 1975", "Chocolate", set()), "Chocolate")

    def test_planned_stem_disambiguates_when_title_exists(self):
        stems = {dl.fold_alnum("Chocolate")}
        self.assertEqual(
            dl.planned_stem("The 1975", "Chocolate", stems),
            "Chocolate (The 1975)",
        )

    def test_dest_already_has_title_only_owned_by_first_artist(self):
        stems = {dl.fold_alnum("Chocolate")}
        self.assertTrue(
            dl.dest_already_has(
                stems, "The 1975", "Chocolate", first_artist="The 1975"
            )
        )
        self.assertFalse(
            dl.dest_already_has(
                stems, "Other Band", "Chocolate", first_artist="The 1975"
            )
        )

    def test_dest_already_has_disambiguated_name(self):
        stems = {dl.fold_alnum("Chocolate (The 1975)")}
        self.assertTrue(
            dl.dest_already_has(
                stems, "The 1975", "Chocolate", first_artist="The 1975"
            )
        )

    def test_sanitize_replaces_path_chars(self):
        self.assertEqual(dl.sanitize_segment('A/B:C'), "A_B_C")

    def test_index_audio_stems_case_insensitive_ext(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / "Chocolate.MP3").write_bytes(b"x")
            (folder / "notes.txt").write_text("nope")
            stems = dl.index_audio_stems(folder)
            self.assertEqual(stems, {dl.fold_alnum("Chocolate")})


class LibraryCopyTests(unittest.TestCase):
    def test_unique_title_copy(self):
        with tempfile.TemporaryDirectory() as tmp:
            library = Path(tmp) / "music"
            dest = library / "music_new"
            library.mkdir()
            dest.mkdir()
            src = library / "Chocolate.mp3"
            src.write_bytes(b"x")
            (dest / "other.mp3").write_bytes(b"y")
            by_stem = dl.index_library_files(library, dest)
            found = dl.find_library_copy(
                by_stem, "The 1975", "Chocolate", first_artist="The 1975"
            )
            self.assertEqual(found, src)
            self.assertIsNone(
                dl.find_library_copy(
                    by_stem, "Other", "Chocolate", first_artist="The 1975"
                )
            )

    def test_ambiguous_title_requires_artist(self):
        with tempfile.TemporaryDirectory() as tmp:
            library = Path(tmp)
            a = library / "All Night Long (Lionel Richie).mp3"
            b = library / "All Night Long (Faith Evans).mp3"
            a.write_bytes(b"a")
            b.write_bytes(b"b")
            by_stem = {
                dl.fold_alnum("All Night Long (Lionel Richie)"): [a],
                dl.fold_alnum("All Night Long (Faith Evans)"): [b],
            }
            found = dl.find_library_copy(
                by_stem, "Lionel Richie", "All Night Long", first_artist="Lionel Richie"
            )
            self.assertEqual(found, a)
            self.assertIsNone(
                dl.find_library_copy(
                    by_stem, "Unknown", "All Night Long", first_artist="Lionel Richie"
                )
            )

    def test_copy_to_dest_uses_disambiguated_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp)
            src = dest / "src.mp3"
            src.write_bytes(b"x")
            (dest / "Chocolate.mp3").write_bytes(b"y")
            stems = dl.index_audio_stems(dest)
            target = dl.copy_to_dest(
                src, dest, "The 1975", "Chocolate", stems, dry_run=False
            )
            self.assertEqual(target.name, "Chocolate (The 1975).mp3")
            self.assertTrue(target.is_file())


class FilterStartAtTests(unittest.TestCase):
    def test_filter_by_json_index(self):
        rows = [{"index": 1, "name": "a"}, {"index": 5, "name": "b"}]
        out = dl.filter_start_at(rows, 5)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["name"], "b")


if __name__ == "__main__":
    unittest.main()
