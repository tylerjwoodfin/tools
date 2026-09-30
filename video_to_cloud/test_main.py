"""Confirmations use Cherry and prefer an embedded title."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import main as video_to_cloud  # noqa: E402


def test_confirmation_names_the_title() -> None:
    assert (
        video_to_cloud.confirmation_message("The Grand Budapest Hotel")
        == "I moved The Grand Budapest Hotel into the cloud video library."
    )


def test_title_from_container_tags() -> None:
    data = {"format": {"tags": {"TITLE": "  Amélie  "}}, "streams": []}
    assert video_to_cloud.title_from_probe(data) == "Amélie"


def test_container_title_wins_over_stream_title() -> None:
    data = {
        "format": {"tags": {"title": "Movie"}},
        "streams": [{"codec_type": "video", "tags": {"title": "Track"}}],
    }
    assert video_to_cloud.title_from_probe(data) == "Movie"


def test_video_stream_title_when_container_has_none() -> None:
    data = {
        "format": {"tags": {}},
        "streams": [
            {"codec_type": "audio", "tags": {"title": "Stereo"}},
            {"codec_type": "video", "tags": {"title": "Episode One"}},
        ],
    }
    assert video_to_cloud.title_from_probe(data) == "Episode One"


def test_blank_title_is_missing() -> None:
    assert video_to_cloud.title_from_probe({"format": {"tags": {"title": "  "}}}) is None


def test_probe_skipped_for_non_video(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def unexpected(*_args: object, **_kwargs: object) -> str:
        raise AssertionError("non-video files should not be probed")

    monkeypatch.setattr(video_to_cloud.shutil, "which", unexpected)
    notes = tmp_path / "notes.txt"
    notes.write_text("x", encoding="utf-8")
    assert video_to_cloud.media_title(notes) is None


def test_send_confirmation_uses_title(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    sent: list[str] = []
    monkeypatch.setattr(video_to_cloud, "media_title", lambda _path: "Amélie")
    monkeypatch.setattr(
        video_to_cloud,
        "cabinet_telegram",
        lambda message, is_quiet=False: sent.append(message) or True,
    )
    monkeypatch.setattr(video_to_cloud.cabinet, "log", lambda *_args, **_kwargs: None)

    video_to_cloud.send_confirmation(tmp_path / "release-name.mkv")

    assert sent == ["I moved Amélie into the cloud video library."]


def test_send_confirmation_falls_back_to_filename(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sent: list[str] = []
    monkeypatch.setattr(video_to_cloud, "media_title", lambda _path: None)
    monkeypatch.setattr(
        video_to_cloud,
        "cabinet_telegram",
        lambda message, is_quiet=False: sent.append(message) or True,
    )
    monkeypatch.setattr(video_to_cloud.cabinet, "log", lambda *_args, **_kwargs: None)

    video_to_cloud.send_confirmation(tmp_path / "Family.Guy.S24E11.mkv")

    assert sent == ["I moved Family.Guy.S24E11.mkv into the cloud video library."]


def test_ffprobe_reads_embedded_title(tmp_path: Path) -> None:
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("ffmpeg/ffprobe not installed")
    dest = tmp_path / "clip.mp4"
    proc = subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=c=black:s=16x16:d=0.1",
            "-metadata",
            "title=The Grand Budapest Hotel",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(dest),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        pytest.skip(f"ffmpeg could not write a titled clip: {proc.stderr[-200:]}")
    assert video_to_cloud.media_title(dest) == "The Grand Budapest Hotel"


def test_probe_json_parses_ffprobe_output(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {"format": {"tags": {"title": "Porco Rosso"}}, "streams": []}

    class _Proc:
        returncode = 0
        stdout = json.dumps(payload)

    monkeypatch.setattr(video_to_cloud.shutil, "which", lambda _name: "/usr/bin/ffprobe")
    monkeypatch.setattr(video_to_cloud.subprocess, "run", lambda *_a, **_k: _Proc())
    clip = tmp_path / "clip.mkv"
    clip.write_bytes(b"")
    assert video_to_cloud.media_title(clip) == "Porco Rosso"
