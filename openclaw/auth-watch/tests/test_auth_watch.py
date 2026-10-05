from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import auth_watch


HEALTHY = {
    "auth": {
        "missingProvidersInUse": [],
        "modelRouteIssues": [],
        "oauth": {
            "profiles": [
                {
                    "profileId": "openai:openai@tylerwoodfin.com",
                    "provider": "openai",
                    "status": "ok",
                    "label": "openai:openai@tylerwoodfin.com (openai@tylerwoodfin.com)",
                }
            ]
        },
    }
}

EXPIRED = {
    "auth": {
        "missingProvidersInUse": ["openai"],
        "modelRouteIssues": [
            {
                "kind": "missing-auth",
                "provider": "openai",
                "model": "gpt-5.6-luna",
                "message": "No usable subscription authentication is available for openai/gpt-5.6-luna.",
            }
        ],
        "oauth": {
            "profiles": [
                {
                    "profileId": "openai:setup-old",
                    "provider": "openai",
                    "status": "expired",
                    "label": "openai:setup-old (openai@tylerwoodfin.com)",
                }
            ]
        },
    }
}


def test_healthy_auth_is_quiet():
    assert auth_watch.openai_auth_problem(HEALTHY) is None


def test_expired_auth_is_a_problem():
    problem = auth_watch.openai_auth_problem(EXPIRED)
    assert problem is not None
    assert "expired" in problem
    assert "subscription authentication" in problem


def test_repair_message_has_the_login_steps():
    assert "models auth login --provider openai --force" in auth_watch.REPAIR_MESSAGE
    assert "--set-default" in auth_watch.REPAIR_MESSAGE
    assert "openai/gpt-5.6-sol" in auth_watch.REPAIR_MESSAGE
    assert "Leave off --set-default" in auth_watch.REPAIR_MESSAGE


def test_tick_sends_once_then_clears(tmp_path):
    state = tmp_path / "openai-alert"
    sent: list[str] = []

    first = auth_watch.cmd_tick(
        status=EXPIRED,
        state_path=state,
        send_fn=lambda message: sent.append(message) or True,
    )
    second = auth_watch.cmd_tick(
        status=EXPIRED,
        state_path=state,
        send_fn=lambda message: sent.append(message) or True,
    )
    cleared = auth_watch.cmd_tick(
        status=HEALTHY,
        state_path=state,
        send_fn=lambda message: sent.append(message) or True,
    )
    again = auth_watch.cmd_tick(
        status=EXPIRED,
        state_path=state,
        send_fn=lambda message: sent.append(message) or True,
    )

    assert first["action"] == "sent"
    assert second["action"] == "quiet"
    assert cleared["action"] == "cleared"
    assert again["action"] == "sent"
    assert sent == [auth_watch.REPAIR_MESSAGE, auth_watch.REPAIR_MESSAGE]
    assert "models auth login --provider openai --force" in sent[0]


def test_failed_send_does_not_stick(tmp_path):
    state = tmp_path / "openai-alert"
    result = auth_watch.cmd_tick(
        status=EXPIRED,
        state_path=state,
        send_fn=lambda _message: False,
    )
    assert result["ok"] is False
    assert not state.exists()
