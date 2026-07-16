from __future__ import annotations

from app.domain.debounce import DebounceTracker


def make() -> DebounceTracker:
    return DebounceTracker(confirm_seconds=3.0, clear_seconds=3.0, cooldown_seconds=30.0)


def test_no_event_before_confirm_window():
    d = make()
    assert d.update(1, compliant=False, timestamp=0.0) is False
    assert d.update(1, compliant=False, timestamp=1.0) is False
    assert d.update(1, compliant=False, timestamp=2.9) is False


def test_event_fires_once_after_continuous_anomaly():
    d = make()
    d.update(1, compliant=False, timestamp=0.0)
    d.update(1, compliant=False, timestamp=2.0)
    assert d.update(1, compliant=False, timestamp=3.0) is True   # confirmé
    assert d.update(1, compliant=False, timestamp=4.0) is False  # déjà en infraction


def test_compliance_resets_anomaly_window():
    d = make()
    d.update(1, compliant=False, timestamp=0.0)
    d.update(1, compliant=True, timestamp=1.0)      # reset
    d.update(1, compliant=False, timestamp=2.0)     # redémarre le compteur
    assert d.update(1, compliant=False, timestamp=4.9) is False  # 2.9s < 3s
    assert d.update(1, compliant=False, timestamp=5.0) is True   # 3.0s -> confirmé


def test_clear_then_new_violation_fires_again_after_cooldown():
    d = DebounceTracker(confirm_seconds=1.0, clear_seconds=1.0, cooldown_seconds=2.0)
    assert d.update(1, compliant=False, timestamp=0.0) is False
    assert d.update(1, compliant=False, timestamp=1.0) is True    # 1re infraction @ t=1
    d.update(1, compliant=True, timestamp=2.0)                    # conforme -> clear_since=2
    d.update(1, compliant=True, timestamp=3.0)                    # 1s conforme -> in_violation effacé
    d.update(1, compliant=False, timestamp=4.0)                   # anomalie repart
    # cooldown = 2s depuis le dernier event (t=1) -> t=5 OK ; confirm=1s depuis t=4 -> t=5 OK
    assert d.update(1, compliant=False, timestamp=5.0) is True


def test_cooldown_blocks_immediate_refire():
    d = DebounceTracker(confirm_seconds=1.0, clear_seconds=1.0, cooldown_seconds=100.0)
    d.update(1, compliant=False, timestamp=0.0)
    assert d.update(1, compliant=False, timestamp=1.0) is True    # event @ t=1
    d.update(1, compliant=True, timestamp=2.0)
    d.update(1, compliant=True, timestamp=3.0)                    # clear
    d.update(1, compliant=False, timestamp=4.0)
    # confirm satisfait à t=5 mais cooldown=100s depuis t=1 -> bloqué
    assert d.update(1, compliant=False, timestamp=5.0) is False


def test_tracks_are_independent():
    d = make()
    d.update(1, compliant=False, timestamp=0.0)
    d.update(2, compliant=False, timestamp=2.0)
    assert d.update(1, compliant=False, timestamp=3.0) is True    # track 1 : 3s
    assert d.update(2, compliant=False, timestamp=3.0) is False   # track 2 : 1s
