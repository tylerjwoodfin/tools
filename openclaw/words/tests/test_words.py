import random
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import words_cli

TZ = ZoneInfo("America/Los_Angeles")


def evening(day: int = 23, hour: int = 19) -> datetime:
    return datetime(2026, 9, day, hour, 0, tzinfo=TZ)


@pytest.fixture
def paths(tmp_path: Path):
    return tmp_path / "words_to_remember.md", tmp_path / "state.json"


def test_parse_and_render_roundtrip():
    text = """# Words to remember

## Active

- **ephemeral** — lasting for a very short time
- **laconic** - using very few words

## Completed

- **serendipity** — a happy accident
"""
    preamble, items = words_cli.parse_words(text)
    assert [item.word for item in items] == ["ephemeral", "laconic", "serendipity"]
    assert items[2].section == "completed"
    rendered = words_cli.render_words(preamble, items)
    _, again = words_cli.parse_words(rendered)
    assert [(item.word, item.section) for item in again] == [
        ("ephemeral", "active"),
        ("laconic", "active"),
        ("serendipity", "completed"),
    ]


def test_three_correct_moves_to_completed(paths):
    notes, state_path = paths
    words_cli.save_notes(
        notes,
        "",
        [words_cli.WordItem("ephemeral", "lasting for a very short time", "active")],
    )
    moment = evening()
    asked = words_cli.start_quiz(
        notes_path=notes,
        state_path=state_path,
        moment=moment,
        rng=random.Random(0),
        force=True,
        source="manual",
    )
    assert "lasting for a very short time" in asked["message"]
    assert "ephemeral" not in asked["message"].lower()

    last = None
    for guess in ("ephemeral", "It's ephemeral", "ephemerel"):
        last = words_cli.cmd_handle(guess, notes_path=notes, state_path=state_path, moment=moment)
        words_cli.start_quiz(
            notes_path=notes,
            state_path=state_path,
            moment=moment,
            rng=random.Random(0),
            force=True,
            source="manual",
        )
    _, items = words_cli.load_notes(notes)
    assert items[0].section == "completed"
    assert "moving it to completed" in last["message"]


def test_wrong_answer_does_not_increment(paths):
    notes, state_path = paths
    words_cli.save_notes(notes, "", [words_cli.WordItem("laconic", "using very few words", "active")])
    words_cli.start_quiz(
        notes_path=notes,
        state_path=state_path,
        moment=evening(),
        rng=random.Random(0),
        force=True,
        source="manual",
    )
    result = words_cli.cmd_handle("chatty", notes_path=notes, state_path=state_path, moment=evening())
    assert "laconic" in result["message"]
    state = words_cli.load_state(state_path)
    assert state["words"]["laconic"]["correct"] == 0
    assert state["pending"] is None


def test_empty_list_uses_generated_word(paths):
    notes, state_path = paths

    def fake_infer(_prompt: str) -> str:
        return '{"word":"pragmatic","definition":"dealing with things sensibly and realistically"}'

    result = words_cli.start_quiz(
        notes_path=notes,
        state_path=state_path,
        moment=evening(),
        rng=random.Random(0),
        force=True,
        source="manual",
        infer_fn=fake_infer,
    )
    assert result["generated"] is True
    assert "sensibly" in result["message"]
    _, items = words_cli.load_notes(notes)
    assert items[0].word == "pragmatic"
    assert items[0].section == "active"


def test_completed_words_wait_for_revisit_window(paths):
    notes, state_path = paths
    words_cli.save_notes(
        notes,
        "",
        [words_cli.WordItem("serendipity", "a happy accident", "completed")],
    )
    state = words_cli.load_state(state_path)
    state["words"]["serendipity"] = {
        "correct": 3,
        "last_asked": evening(day=20).isoformat(),
    }
    words_cli.save_state(state_path, state)
    moment = evening(day=23)
    assert words_cli.proactive_due(words_cli.load_state(state_path), moment)
    skipped = words_cli.cmd_tick(
        notes_path=notes,
        state_path=state_path,
        moment=moment,
        rng=random.Random(0),
        send=False,
    )
    assert skipped["action"] == "skip"

    forced = words_cli.cmd_handle("/words", notes_path=notes, state_path=state_path, moment=moment)
    assert forced["action"] == "asked"
    assert "happy accident" in forced["message"]


def test_proactive_respects_hour_and_delay(paths):
    notes, state_path = paths
    words_cli.save_notes(notes, "", [words_cli.WordItem("ephemeral", "brief", "active")])
    morning = evening(hour=9)
    assert not words_cli.proactive_due(words_cli.load_state(state_path), morning)
    night_tick = words_cli.cmd_tick(
        notes_path=notes,
        state_path=state_path,
        moment=morning,
        rng=random.Random(0),
        send=False,
    )
    assert night_tick["action"] == "skip"

    first = words_cli.cmd_tick(
        notes_path=notes,
        state_path=state_path,
        moment=evening(),
        rng=random.Random(1),
        send=False,
    )
    assert first["action"] == "asked"
    state = words_cli.load_state(state_path)
    state["pending"] = None
    words_cli.save_state(state_path, state)
    too_soon = words_cli.cmd_tick(
        notes_path=notes,
        state_path=state_path,
        moment=evening(day=24),
        rng=random.Random(1),
        send=False,
    )
    assert too_soon["action"] == "skip"


def test_add_and_unrelated_chat_is_ignored(paths):
    notes, state_path = paths
    added = words_cli.cmd_handle(
        "/words add laconic — using very few words",
        notes_path=notes,
        state_path=state_path,
        moment=evening(),
    )
    assert added["action"] == "added"
    ignored = words_cli.cmd_handle(
        "anyway, about that pull request",
        notes_path=notes,
        state_path=state_path,
        moment=evening(),
    )
    assert ignored["action"] == "skip"
    assert ignored["message"] is None
