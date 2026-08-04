from __future__ import annotations

from app.notify.factory import build_dispatcher


def test_build_dispatcher_selon_env():
    assert len(build_dispatcher({})) == 0                                   # rien -> no-op
    assert len(build_dispatcher({"ARGUS_SMTP_HOST": "h", "ARGUS_SMTP_TO": "a@b"})) == 1
    assert len(build_dispatcher({"ARGUS_TEAMS_WEBHOOK": "https://w"})) == 1
    assert len(build_dispatcher({
        "ARGUS_SMTP_HOST": "h", "ARGUS_SMTP_TO": "a@b",
        "ARGUS_TEAMS_WEBHOOK": "https://w",
    })) == 2
