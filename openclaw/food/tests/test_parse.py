from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import food_cli


def test_parse_simple_tacos():
    assert food_cli.parse_simple("tacos 100") == [{"food": "tacos", "calories": 100}]


def test_parse_simple_should_be():
    assert food_cli.parse_simple("matcha should be 200") == [
        {"food": "matcha", "calories": 200}
    ]


def test_parse_simple_slash_food():
    assert food_cli.parse_simple("/food chicken salad 540") == [
        {"food": "chicken salad", "calories": 540}
    ]


def test_not_food():
    assert food_cli.NOT_FOOD.match("later")
    assert not food_cli.looks_like_food("anyway about that PR")
