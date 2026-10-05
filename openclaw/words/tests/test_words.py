import random
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import words_cli

TZ = ZoneInfo("America/Los_Angeles")


class ScriptedRng(random.Random):
    """Always returns the same roll so list-vs-generated picks stay deterministic."""

    def __init__(self, roll: float) -> None:
        super().__init__()
        self._roll = roll

    def random(self) -> float:
        return self._roll


def evening(day: int = 23, hour: int = 19) -> datetime:
    return datetime(2026, 9, day, hour, 0, tzinfo=TZ)


def fake_pragmatic(_prompt: str) -> str:
    return '{"word":"pragmatic","definition":"dealing with things sensibly and realistically"}'


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
        rng=ScriptedRng(0.99),
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
            rng=ScriptedRng(0.99),
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
        rng=ScriptedRng(0.99),
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

    result = words_cli.start_quiz(
        notes_path=notes,
        state_path=state_path,
        moment=evening(),
        rng=ScriptedRng(0.0),
        force=True,
        source="manual",
        infer_fn=fake_pragmatic,
    )
    assert result["generated"] is True
    assert "sensibly" in result["message"]
    _, items = words_cli.load_notes(notes)
    assert items == []
    assert "pragmatic" not in words_cli.load_state(state_path)["words"]


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
        rng=ScriptedRng(0.99),
        send=False,
    )
    assert skipped["action"] == "skip"

    forced = words_cli.cmd_handle(
        "/words",
        notes_path=notes,
        state_path=state_path,
        moment=moment,
        rng=ScriptedRng(0.99),
    )
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
        rng=ScriptedRng(0.99),
        send=False,
    )
    assert night_tick["action"] == "skip"

    first = words_cli.cmd_tick(
        notes_path=notes,
        state_path=state_path,
        moment=evening(),
        rng=ScriptedRng(0.99),
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
        rng=ScriptedRng(0.99),
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


def test_generated_pick_chance_matches_list_length():
    assert words_cli.generated_pick_chance(0) == 1
    assert words_cli.generated_pick_chance(8) == pytest.approx(0.2)
    assert words_cli.generated_pick_chance(9) == pytest.approx(0.1)
    assert words_cli.generated_pick_chance(10) == 0
    assert words_cli.generated_pick_chance(12) == 0


def test_short_list_can_quiz_a_new_word_without_saving_it(paths):
    notes, state_path = paths
    words_cli.save_notes(
        notes,
        "",
        [words_cli.WordItem(f"word{i}", f"definition {i}", "active") for i in range(8)],
    )
    result = words_cli.start_quiz(
        notes_path=notes,
        state_path=state_path,
        moment=evening(),
        rng=ScriptedRng(0.0),
        force=True,
        source="manual",
        infer_fn=fake_pragmatic,
    )
    assert result["generated"] is True
    assert result["word"] == "pragmatic"
    _, items = words_cli.load_notes(notes)
    assert [item.word for item in items] == [f"word{i}" for i in range(8)]


def test_short_list_roll_above_chance_keeps_a_list_word(paths):
    notes, state_path = paths
    words_cli.save_notes(
        notes,
        "",
        [words_cli.WordItem(f"word{i}", f"definition {i}", "active") for i in range(8)],
    )

    def fail_if_called(_prompt: str) -> str:
        raise AssertionError("should quiz a list word")

    result = words_cli.start_quiz(
        notes_path=notes,
        state_path=state_path,
        moment=evening(),
        rng=ScriptedRng(0.2),
        force=True,
        source="manual",
        infer_fn=fail_if_called,
    )
    assert result["generated"] is False
    assert result["word"] == "word0"


def test_full_list_never_generates(paths):
    notes, state_path = paths
    words_cli.save_notes(
        notes,
        "",
        [words_cli.WordItem(f"word{i}", f"definition {i}", "active") for i in range(10)],
    )

    def fail_if_called(_prompt: str) -> str:
        raise AssertionError("list of 10 should not generate")

    result = words_cli.start_quiz(
        notes_path=notes,
        state_path=state_path,
        moment=evening(),
        rng=ScriptedRng(0.0),
        force=True,
        source="manual",
        infer_fn=fail_if_called,
    )
    assert result["generated"] is False
    assert result["word"] == "word0"


def test_generated_word_correct_on_first_try_is_completed(paths):
    notes, state_path = paths
    words_cli.start_quiz(
        notes_path=notes,
        state_path=state_path,
        moment=evening(),
        rng=ScriptedRng(0.0),
        force=True,
        source="manual",
        infer_fn=fake_pragmatic,
    )
    graded = words_cli.cmd_handle("pragmatic", notes_path=notes, state_path=state_path, moment=evening())
    assert "moving it to completed" in graded["message"]
    _, items = words_cli.load_notes(notes)
    assert [(item.word, item.section) for item in items] == [("pragmatic", "completed")]
    stats = words_cli.load_state(state_path)["words"]["pragmatic"]
    assert stats["correct"] == 3


def test_generated_word_miss_is_added_at_zero(paths):
    notes, state_path = paths
    words_cli.start_quiz(
        notes_path=notes,
        state_path=state_path,
        moment=evening(),
        rng=ScriptedRng(0.0),
        force=True,
        source="manual",
        infer_fn=fake_pragmatic,
    )
    graded = words_cli.cmd_handle("nope", notes_path=notes, state_path=state_path, moment=evening())
    assert "pragmatic" in graded["message"]
    _, items = words_cli.load_notes(notes)
    assert [(item.word, item.section) for item in items] == [("pragmatic", "active")]
    stats = words_cli.load_state(state_path)["words"]["pragmatic"]
    assert stats["correct"] == 0
    assert "(0/3)" in words_cli.list_message(items, words_cli.load_state(state_path))


def test_skipped_generated_word_is_not_saved(paths):
    notes, state_path = paths
    words_cli.start_quiz(
        notes_path=notes,
        state_path=state_path,
        moment=evening(),
        rng=ScriptedRng(0.0),
        force=True,
        source="manual",
        infer_fn=fake_pragmatic,
    )
    skipped = words_cli.cmd_handle("/words skip", notes_path=notes, state_path=state_path, moment=evening())
    assert skipped["action"] == "skipped"
    _, items = words_cli.load_notes(notes)
    assert items == []
    assert words_cli.load_state(state_path)["words"] == {}


def test_repeated_completed_word_can_be_replaced_by_a_generated_one(paths):
    notes, state_path = paths
    words_cli.save_notes(
        notes,
        "",
        [words_cli.WordItem("ambivalent", "having mixed feelings", "completed")],
    )
    result = words_cli.start_quiz(
        notes_path=notes,
        state_path=state_path,
        moment=evening(),
        rng=ScriptedRng(0.0),
        force=True,
        source="manual",
        infer_fn=fake_pragmatic,
    )
    assert result["generated"] is True
    assert result["word"] == "pragmatic"
    _, items = words_cli.load_notes(notes)
    assert [item.word for item in items] == ["ambivalent"]


def test_generated_word_already_on_the_list_is_retried(paths):
    notes, state_path = paths
    words_cli.save_notes(
        notes,
        "",
        [words_cli.WordItem("ambivalent", "having mixed feelings", "active")],
    )
    calls = {"n": 0}

    def infer(_prompt: str) -> str:
        calls["n"] += 1
        if calls["n"] == 1:
            return '{"word":"ambivalent","definition":"having mixed feelings about something"}'
        return '{"word":"pragmatic","definition":"dealing with things sensibly and realistically"}'

    result = words_cli.start_quiz(
        notes_path=notes,
        state_path=state_path,
        moment=evening(),
        rng=ScriptedRng(0.0),
        force=True,
        source="manual",
        infer_fn=infer,
    )
    assert calls["n"] == 2
    assert result["generated"] is True
    assert result["word"] == "pragmatic"
