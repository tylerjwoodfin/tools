from diary_llm.sanitize import sanitize_user_text


def test_strips_openclaw_system_banner():
    raw = (
        "System: [2026-09-10 20:16:27 PDT] Node: ice (192.168.1.3) · app 2026.9.1 · mode local\n\n"
        "Probably feeling the need to accelerate back on track."
    )
    assert sanitize_user_text(raw) == "Probably feeling the need to accelerate back on track."


def test_keeps_normal_text():
    assert sanitize_user_text("Just a normal reply") == "Just a normal reply"
