from __future__ import annotations

from pathlib import Path

from safety_supervisor import SafetyConfig, SafetyState, SafetySupervisor


class FakeTime:
    def __init__(self) -> None:
        self.mono = 0.0
        self.wall = 1_700_000_000.0

    def set(self, value: float) -> float:
        delta = value - self.mono
        self.mono = value
        self.wall += delta
        return value


def supervisor(tmp_path: Path | None = None) -> tuple[SafetySupervisor, FakeTime]:
    fake = FakeTime()
    state_path = tmp_path / "safety.json" if tmp_path else None
    sup = SafetySupervisor(
        config=SafetyConfig(),
        state_path=state_path,
        clock=lambda: fake.mono,
        wall_clock=lambda: fake.wall,
    )
    return sup, fake


def sample(seq: int, level: str) -> dict[str, object]:
    return {"event_seq": seq, "crowd_state": level}


def enter_alert(sup: SafetySupervisor, fake: FakeTime) -> None:
    for seq, at in enumerate((0.0, 0.6, 1.2, 1.8, 2.4, 3.0), start=1):
        snap = sup.update(sample(seq, "CRITICAL"), now=fake.set(at))
    assert snap.state == SafetyState.SAFETY_ALERT


def test_critical_requires_duration_and_new_sample_count() -> None:
    sup, fake = supervisor()
    for seq, at in enumerate((0.0, 0.5, 1.0, 1.5, 2.0, 2.5), start=1):
        snap = sup.update(sample(seq, "CRITICAL"), now=fake.set(at))
    assert snap.state != SafetyState.SAFETY_ALERT
    snap = sup.update(sample(7, "CRITICAL"), now=fake.set(3.0))
    assert snap.state == SafetyState.SAFETY_ALERT
    assert snap.locked is True
    assert snap.event == "safety_alert"


def test_duplicate_sequence_does_not_count() -> None:
    sup, fake = supervisor()
    sup.update(sample(1, "CRITICAL"), now=fake.set(0.0))
    snap = sup.update(sample(1, "CRITICAL"), now=fake.set(4.0))
    assert snap.critical_samples == 1
    assert snap.state != SafetyState.SAFETY_ALERT


def test_debounced_board_state_is_not_delayed_twice() -> None:
    sup, fake = supervisor()
    snap = sup.update(
        {**sample(1, "CRITICAL"), "debounced": True},
        now=fake.set(0.0),
    )
    assert snap.state == SafetyState.SAFETY_ALERT
    snap = sup.update(
        {**sample(2, "NORMAL"), "debounced": True},
        now=fake.set(10.0),
    )
    assert snap.state == SafetyState.RECOVERY


def test_recovery_requires_ten_seconds_and_twenty_new_samples() -> None:
    sup, fake = supervisor()
    enter_alert(sup, fake)
    for offset in range(20):
        at = 3.1 + offset * 0.5
        snap = sup.update(sample(100 + offset, "NORMAL"), now=fake.set(at))
    assert snap.state == SafetyState.SAFETY_ALERT
    snap = sup.update(sample(120, "NORMAL"), now=fake.set(13.1))
    assert snap.state == SafetyState.RECOVERY
    snap = sup.recovery_done(now=fake.set(14.0))
    assert snap.state == SafetyState.NORMAL
    assert snap.locked is False


def test_monitor_fault_does_not_lock_normal_business() -> None:
    sup, fake = supervisor()
    snap = sup.tick(now=fake.set(2.1))
    assert snap.state == SafetyState.MONITOR_FAULT
    assert snap.monitor_fault is True
    assert snap.locked is False


def test_monitor_fault_keeps_existing_alert_locked() -> None:
    sup, fake = supervisor()
    enter_alert(sup, fake)
    snap = sup.tick(now=fake.set(6.0))
    assert snap.state == SafetyState.SAFETY_ALERT
    assert snap.monitor_fault is True
    assert snap.locked is True


def test_monitor_fault_during_recovery_returns_to_alert() -> None:
    sup, fake = supervisor()
    sup.update({**sample(1, "CRITICAL"), "debounced": True}, now=fake.set(0.0))
    snap = sup.update({**sample(2, "NORMAL"), "debounced": True}, now=fake.set(10.0))
    assert snap.state == SafetyState.RECOVERY
    snap = sup.tick(now=fake.set(12.1))
    assert snap.state == SafetyState.SAFETY_ALERT
    assert snap.monitor_fault is True


def test_warning_notification_has_global_cooldown() -> None:
    sup, fake = supervisor()
    snap = sup.update(sample(1, "WARNING"), now=fake.set(0.0))
    assert snap.event == "warning_notify"
    sup.update(sample(2, "NORMAL"), now=fake.set(1.0))
    snap = sup.update(sample(3, "WARNING"), now=fake.set(10.0))
    assert snap.state == SafetyState.WARNING
    assert snap.event == "warning"
    sup.update(sample(4, "NORMAL"), now=fake.set(20.0))
    snap = sup.update(sample(5, "WARNING"), now=fake.set(61.0))
    assert snap.event == "warning_notify"


def test_demo_release_cannot_override_live_critical() -> None:
    sup, fake = supervisor()
    sup.update(sample(1, "CRITICAL"), now=fake.set(0.0))
    snap = sup.trigger_demo(now=fake.set(0.1))
    assert snap.state == SafetyState.SAFETY_ALERT
    snap = sup.release_demo(now=fake.set(0.2))
    assert snap.state == SafetyState.SAFETY_ALERT
    assert snap.crowd_state == "CRITICAL"


def test_demo_release_can_complete_without_board_stream() -> None:
    sup, fake = supervisor()
    sup.trigger_demo(now=fake.set(0.0))
    sup.release_demo(now=fake.set(0.1))
    for index in range(1, 21):
        snap = sup.tick(now=fake.set(0.1 + index * 0.5))
    assert snap.state == SafetyState.RECOVERY


def test_alert_latch_survives_restart(tmp_path: Path) -> None:
    sup, fake = supervisor(tmp_path)
    enter_alert(sup, fake)
    restarted = SafetySupervisor(
        state_path=tmp_path / "safety.json",
        clock=lambda: fake.mono,
        wall_clock=lambda: fake.wall,
    )
    snap = restarted.snapshot(now=fake.mono)
    assert snap.state == SafetyState.SAFETY_ALERT
    assert snap.locked is True
    assert snap.monitor_fault is True


def test_resume_cache_expires_from_first_alert_time() -> None:
    sup, fake = supervisor()
    enter_alert(sup, fake)
    snap = sup.snapshot(now=fake.set(302.9))
    assert snap.resume_cache_expired is False
    snap = sup.snapshot(now=fake.set(303.1))
    assert snap.resume_cache_expired is True
