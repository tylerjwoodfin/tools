import base64
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import media_cli  # noqa: E402

SEED = Path.home() / "git/docker/media/scripts/seed_qbit.py"
if SEED.exists():
    sys.path.insert(0, str(SEED.parent))
    import seed_qbit  # noqa: E402
else:
    seed_qbit = None


def _series(monitored=True, episodes=10, files=10, season=36, series_id=7):
    return {
        "id": series_id,
        "title": "The Simpsons",
        "tvdbId": 71663,
        "seasons": [
            {
                "seasonNumber": season,
                "monitored": monitored,
                "statistics": {"episodeCount": episodes, "episodeFileCount": files},
            }
        ],
    }


def test_plan_series_add_when_missing():
    assert media_cli.plan_series_action(None, in_queue=False) == ("added", "add")


def test_plan_series_completed():
    assert media_cli.plan_series_action(_series(), in_queue=False) == ("completed", "none")


def test_plan_series_queue_is_downloading():
    assert media_cli.plan_series_action(_series(files=2), in_queue=True) == (
        "downloading",
        "none",
    )


def test_plan_series_missing_episodes_searches():
    assert media_cli.plan_series_action(_series(files=2), in_queue=False) == (
        "downloading",
        "search",
    )


def test_plan_series_unmonitored_current_season():
    assert media_cli.plan_series_action(_series(monitored=False, files=0), in_queue=False) == (
        "added",
        "search",
    )


def test_plan_movie_file_is_completed():
    assert media_cli.plan_movie_action({"hasFile": True, "monitored": True}, in_queue=False) == (
        "completed",
        "none",
    )


def test_pick_best_prefers_exact_title():
    items = [{"title": "The Simpson"}, {"title": "The Simpsons"}]
    assert media_cli.pick_best(items, "the simpsons")["title"] == "The Simpsons"


def test_parse_music_query():
    assert media_cli.parse_music_query("Daft Punk - Discovery") == ("Daft Punk", "Discovery")
    assert media_cli.parse_music_query("Discovery") == (None, "Discovery")


def test_ssh_target_from_cloud_function():
    text = """
cloud () {
    ssh -o ConnectTimeout=4 tyler@192.168.1.101 -p 62561 -t zsh -cil "'$@'"
}
"""
    assert media_cli.ssh_target_from_which(text) == ("tyler@192.168.1.101", "62561")


def test_rewrite_jackett_url():
    sys.path.insert(0, str(Path.home() / "git/docker/media/scripts"))
    import configure

    url = "http://192.168.1.101:9117/api/v2.0/indexers/eztv/results/torznab/"
    assert configure.rewrite_jackett_url(url) == (
        "http://jackett:9117/api/v2.0/indexers/eztv/results/torznab/"
    )


def test_qbit_shares_gluetun_namespace():
    compose = Path.home() / "git/docker/media/docker-compose.yml"
    text = compose.read_text(encoding="utf-8")
    assert "network_mode: service:gluetun" in text
    assert text.count("network_mode: service:gluetun") == 2
    assert "WIREGUARD_PRIVATE_KEY:" in text
    assert "wOEI9rqq" not in text


@pytest.mark.skipif(seed_qbit is None, reason="seed_qbit.py is not checked out")
def test_qbittorrent_pbkdf2_matches_upstream_adminadmin_vector():
    salt = base64.b64decode("ARQ77eY1NUZaQsuDHbIMCA==")
    hashed = seed_qbit.pbkdf2_qbittorrent("adminadmin", salt)
    assert hashed == (
        "ARQ77eY1NUZaQsuDHbIMCA==:"
        "0WMRkYTUWVT9wVvdDtHAjU9b3b7uB8NR1Gur2hmQCvCDpm39Q+PsJRJPaCU51dEiz+dTzh8qbPsL8WkFljQYFQ=="
    )
