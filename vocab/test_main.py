"""Tests for the Cherry vocab list."""

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

import main as vocab


NOTES = """# Words to remember

Example (this line is not quizzed):

- **ephemeral** — lasting for a very short time

## Active

- **pragmatic** — Focused on practical results.
- **nuance** — A subtle distinction.

## Completed

- **ambivalent** — Having mixed feelings.
"""


class VocabTests(unittest.TestCase):
    def test_words_from_notes_skips_preamble_example(self):
        self.assertEqual(
            vocab.words_from_notes(NOTES),
            ["pragmatic", "nuance", "ambivalent"],
        )

    def test_counters_from_stats(self):
        self.assertEqual(vocab.counters_from_stats(None), (0, 0))
        self.assertEqual(
            vocab.counters_from_stats({"correct": 3, "last_result": "correct"}),
            (3, 3),
        )
        self.assertEqual(
            vocab.counters_from_stats(
                {"correct": 0, "last_result": "wrong", "last_asked": "2026-10-15T18:00:00"}
            ),
            (1, 0),
        )
        self.assertEqual(
            vocab.counters_from_stats({"correct": 0, "last_asked": "2026-10-15T18:00:00"}),
            (1, 0),
        )

    def test_migrate_copies_names_and_counts(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            notes = root / "words_to_remember.md"
            state = root / "state.json"
            dest = root / "vocab.json"
            notes.write_text(NOTES, encoding="utf-8")
            state.write_text(
                json.dumps(
                    {
                        "words": {
                            "pragmatic": {
                                "correct": 0,
                                "last_result": "wrong",
                                "last_asked": "t",
                            },
                            "ambivalent": {
                                "correct": 3,
                                "last_result": "correct",
                                "last_asked": "t",
                            },
                        }
                    }
                ),
                encoding="utf-8",
            )

            self.assertEqual(vocab.ensure_vocab(dest, notes, state), 3)
            self.assertIsNone(vocab.ensure_vocab(dest, notes, state))
            data = json.loads(dest.read_text(encoding="utf-8"))
            self.assertEqual(
                data,
                [
                    {"name": "pragmatic", "times_asked": 1, "times_correct": 0},
                    {"name": "nuance", "times_asked": 0, "times_correct": 0},
                    {"name": "ambivalent", "times_asked": 3, "times_correct": 3},
                ],
            )

    def test_add_word_sets_counts_to_zero_and_rejects_duplicates(self):
        with TemporaryDirectory() as tmp:
            dest = Path(tmp) / "network" / "vocab.json"
            notes = Path(tmp) / "missing.md"
            state = Path(tmp) / "missing-state.json"

            code = vocab.main(
                ["luminous"], vocab_path=dest, notes_path=notes, state_path=state
            )
            self.assertEqual(code, 0)
            added = json.loads(dest.read_text(encoding="utf-8"))
            self.assertEqual(
                added, [{"name": "luminous", "times_asked": 0, "times_correct": 0}]
            )

            code = vocab.main(
                ["Luminous"], vocab_path=dest, notes_path=notes, state_path=state
            )
            self.assertEqual(code, 0)
            again = json.loads(dest.read_text(encoding="utf-8"))
            self.assertEqual(again, added)

    def test_add_joins_arguments_and_rejects_blank(self):
        with TemporaryDirectory() as tmp:
            dest = Path(tmp) / "vocab.json"
            notes = Path(tmp) / "missing.md"
            state = Path(tmp) / "missing-state.json"

            with mock.patch("sys.stderr") as err:
                code = vocab.main([], vocab_path=dest, notes_path=notes, state_path=state)
            self.assertEqual(code, 1)
            printed = "".join(call.args[0] for call in err.write.call_args_list)
            self.assertIn("Usage: vocab <word>", printed)

            code = vocab.main(
                ["ice", "cream"], vocab_path=dest, notes_path=notes, state_path=state
            )
            self.assertEqual(code, 0)
            data = json.loads(dest.read_text(encoding="utf-8"))
            self.assertEqual(data[0]["name"], "ice cream")
            self.assertEqual(data[0]["times_asked"], 0)
            self.assertEqual(data[0]["times_correct"], 0)

    def test_load_rejects_non_array(self):
        with TemporaryDirectory() as tmp:
            dest = Path(tmp) / "vocab.json"
            dest.write_text("{}", encoding="utf-8")
            with self.assertRaises(ValueError):
                vocab.load_vocab(dest)


if __name__ == "__main__":
    unittest.main()
