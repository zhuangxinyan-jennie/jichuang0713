"""PC-side crowd safety state machine.

The board decides crowd level. This module owns the PC safety latch, recovery
timers, demo override, and a small durable safety state record. Business
resume data deliberately does not live here.
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
import time
from dataclasses import asdict, dataclass
from enum import Enum
from functools import wraps
from pathlib import Path
from typing import Any, Mapping


class SafetyState(str, Enum):
    NORMAL = "NORMAL"
    WARNING = "WARNING"
    SAFETY_ALERT = "SAFETY_ALERT"
    RECOVERY = "RECOVERY"
    MONITOR_FAULT = "MONITOR_FAULT"


@dataclass(frozen=True)
class SafetyConfig:
    critical_hold_s: float = 3.0
    critical_min_samples: int = 6
    recovery_hold_s: float = 10.0
    recovery_min_samples: int = 20
    monitor_fault_after_s: float = 2.0
    warning_notify_cooldown_s: float = 60.0
    alert_repeat_s: float = 15.0
    resume_cache_ttl_s: float = 300.0


@dataclass(frozen=True)
class SafetySnapshot:
    state: SafetyState
    crowd_state: str
    monitor_fault: bool
    locked: bool
    alert_id: int
    alert_started_at: float | None
    resume_cache_expired: bool
    demo_active: bool
    source: str
    last_sample_at: float | None
    last_sample_seq: int | None
    critical_samples: int
    recovery_samples: int
    transition_seq: int
    event: str | None = None
    event_seq: int | None = None

    def to_dict(self) -> dict[str, Any]:
        out = asdict(self)
        out["state"] = self.state.value
        return out


def _synchronized(method):
    @wraps(method)
    def wrapped(self, *args, **kwargs):
        with self._lock:
            return method(self, *args, **kwargs)

    return wrapped


class SafetySupervisor:
    """Fail-closed safety state machine for one board/camera stream."""

    def __init__(
        self,
        *,
        config: SafetyConfig | None = None,
        state_path: str | Path | None = None,
        clock=time.monotonic,
        wall_clock=time.time,
    ) -> None:
        self.config = config or SafetyConfig()
        self.state_path = Path(state_path) if state_path else None
        self._clock = clock
        self._wall_clock = wall_clock
        self._lock = threading.RLock()
        self._started_at = self._clock()
        self.state = SafetyState.NORMAL
        self.crowd_state = "NORMAL"
        self._live_crowd_state = "NORMAL"
        self.monitor_fault = False
        self.demo_active = False
        self.source = "live"
        self.alert_id = 0
        self.alert_started_at: float | None = None
        self.last_sample_at: float | None = None
        self.last_sample_seq: int | None = None
        self._critical_since: float | None = None
        self._critical_samples = 0
        self._recovery_since: float | None = None
        self._recovery_samples = 0
        self._last_warning_notify: float | None = None
        self._next_alert_notify: float | None = None
        self._transition_seq = 0
        self._require_revalidation = False
        self._demo_release_pending = False
        self._demo_recovery_active = False
        self._event: str | None = None
        self._event_seq: int | None = None
        self._restore()

    @property
    def locked(self) -> bool:
        return self.state in {SafetyState.SAFETY_ALERT, SafetyState.RECOVERY}

    @_synchronized
    def update(self, payload: Mapping[str, Any] | None, *, now: float | None = None) -> SafetySnapshot:
        """Consume one board crowd snapshot. Duplicate sequence is ignored."""
        now = self._clock() if now is None else float(now)
        data = payload if isinstance(payload, Mapping) else {}
        seq = _sample_seq(data)
        is_new = seq is not None and seq != self.last_sample_seq
        if seq is None:
            # Missing sequence is not trusted as a fresh safety sample.
            is_new = False

        if is_new:
            self.last_sample_seq = seq
            self.last_sample_at = now
            self.monitor_fault = False
            level = _normalise_level(data.get("crowd_state", data.get("level", "NORMAL")))
            self._live_crowd_state = level
            self.crowd_state = "CRITICAL" if self.demo_active else level
            if self.demo_active:
                self.source = "demo+live"
                if self.state != SafetyState.SAFETY_ALERT:
                    self._enter_alert(now, reason="demo_trigger")
            else:
                self.source = "live"
                if level != "NORMAL":
                    self._demo_release_pending = False
                    self._demo_recovery_active = False
                if bool(data.get("debounced")) and not self._require_revalidation:
                    self._consume_debounced_level(level, now)
                else:
                    self._consume_level(level, now)
        elif self._monitor_timed_out(now) and not self._demo_recovery_active:
            self.monitor_fault = True
            if self.state == SafetyState.RECOVERY and not self._demo_recovery_active:
                self._require_revalidation = True
                self._set_state(SafetyState.SAFETY_ALERT, "monitor_fault_during_recovery")
            elif self.state in {SafetyState.NORMAL, SafetyState.WARNING, SafetyState.MONITOR_FAULT}:
                self._set_state(SafetyState.MONITOR_FAULT, "monitor_fault")

        return self.snapshot(now=now)

    @_synchronized
    def trigger_demo(self, *, now: float | None = None) -> SafetySnapshot:
        now = self._clock() if now is None else float(now)
        self.demo_active = True
        self._require_revalidation = True
        self._demo_release_pending = False
        self._demo_recovery_active = False
        self.crowd_state = "CRITICAL"
        self.source = "demo"
        self.monitor_fault = False
        self._enter_alert(now, reason="demo_trigger")
        self._persist()
        return self.snapshot(now=now)

    @_synchronized
    def release_demo(self, *, now: float | None = None) -> SafetySnapshot:
        now = self._clock() if now is None else float(now)
        self.demo_active = False
        self._demo_recovery_active = False
        self.crowd_state = self._live_crowd_state
        if self.state == SafetyState.SAFETY_ALERT and self._live_crowd_state == "NORMAL":
            self._critical_since = None
            self._critical_samples = 0
            self._recovery_since = now
            self._recovery_samples = 0
            self._demo_release_pending = True
        self.source = "live"
        self._persist()
        return self.snapshot(now=now)

    @_synchronized
    def recovery_done(self, *, now: float | None = None) -> SafetySnapshot:
        now = self._clock() if now is None else float(now)
        if self.state == SafetyState.RECOVERY:
            self._set_state(SafetyState.NORMAL, "recovery_done")
            self.alert_started_at = None
            self._critical_since = None
            self._recovery_since = None
            self._recovery_samples = 0
            self._require_revalidation = False
            self._demo_release_pending = False
            self._demo_recovery_active = False
            self.monitor_fault = False
            self._persist()
        return self.snapshot(now=now)

    @_synchronized
    def tick(self, *, now: float | None = None) -> SafetySnapshot:
        """Advance timeout-only transitions without requiring a new sample."""
        now = self._clock() if now is None else float(now)
        if self._demo_release_pending and self.state == SafetyState.SAFETY_ALERT:
            self._recovery_samples += 1
            since = self._recovery_since if self._recovery_since is not None else now
            if (
                now - since >= self.config.recovery_hold_s
                and self._recovery_samples >= self.config.recovery_min_samples
            ):
                self._demo_release_pending = False
                self._demo_recovery_active = True
                self._set_state(SafetyState.RECOVERY, "demo_recovery_threshold")
        if self._monitor_timed_out(now) and not self._demo_recovery_active:
            self.monitor_fault = True
            if self.state == SafetyState.RECOVERY and not self._demo_recovery_active:
                self._require_revalidation = True
                self._set_state(SafetyState.SAFETY_ALERT, "monitor_fault_during_recovery")
            elif self.state in {SafetyState.NORMAL, SafetyState.WARNING}:
                self._set_state(SafetyState.MONITOR_FAULT, "monitor_fault")
        return self.snapshot(now=now)

    @_synchronized
    def snapshot(self, *, now: float | None = None) -> SafetySnapshot:
        now = self._clock() if now is None else float(now)
        expired = bool(
            self.alert_started_at is not None
            and self._wall_clock() - self.alert_started_at > self.config.resume_cache_ttl_s
        )
        return SafetySnapshot(
            state=self.state,
            crowd_state=self.crowd_state,
            monitor_fault=self.monitor_fault,
            locked=self.locked,
            alert_id=self.alert_id,
            alert_started_at=self.alert_started_at,
            resume_cache_expired=expired,
            demo_active=self.demo_active,
            source=self.source,
            last_sample_at=self.last_sample_at,
            last_sample_seq=self.last_sample_seq,
            critical_samples=self._critical_samples,
            recovery_samples=self._recovery_samples,
            transition_seq=self._transition_seq,
            event=self._event,
            event_seq=self._event_seq,
        )

    def _consume_level(self, level: str, now: float) -> None:
        if level == "CRITICAL":
            self._recovery_since = None
            self._recovery_samples = 0
            if self.state in {SafetyState.SAFETY_ALERT, SafetyState.RECOVERY}:
                if self.state == SafetyState.RECOVERY:
                    self._enter_alert(now, reason="critical_during_recovery")
                return
            if self._critical_since is None:
                self._critical_since = now
                self._critical_samples = 0
            self._critical_samples += 1
            if (
                now - self._critical_since >= self.config.critical_hold_s
                and self._critical_samples >= self.config.critical_min_samples
            ):
                self._enter_alert(now, reason="critical_threshold")
            return

        self._critical_since = None
        self._critical_samples = 0
        if self.state == SafetyState.SAFETY_ALERT:
            if level == "NORMAL":
                if self._recovery_since is None:
                    self._recovery_since = now
                    self._recovery_samples = 0
                self._recovery_samples += 1
                if (
                    now - self._recovery_since >= self.config.recovery_hold_s
                    and self._recovery_samples >= self.config.recovery_min_samples
                ):
                    self._set_state(SafetyState.RECOVERY, "recovery_threshold")
            else:
                self._recovery_since = None
                self._recovery_samples = 0
            return

        if level == "WARNING":
            self._recovery_since = None
            self._recovery_samples = 0
            if self.state != SafetyState.WARNING:
                self._set_state(SafetyState.WARNING, "warning")
                if self._warning_due(now):
                    self._last_warning_notify = now
                    self._emit("warning_notify")
            return

        self._recovery_since = None
        self._recovery_samples = 0
        if self.state in {SafetyState.WARNING, SafetyState.MONITOR_FAULT}:
            self._set_state(SafetyState.NORMAL, "normal")

    def _consume_debounced_level(self, level: str, now: float) -> None:
        self._critical_since = None
        self._critical_samples = 0
        self._recovery_since = None
        self._recovery_samples = 0
        if level == "CRITICAL":
            if self.state != SafetyState.SAFETY_ALERT:
                self._enter_alert(now, reason="board_critical")
            return
        if self.state == SafetyState.SAFETY_ALERT:
            if level == "NORMAL":
                self._set_state(SafetyState.RECOVERY, "board_recovered")
            return
        if level == "WARNING":
            if self.state != SafetyState.WARNING:
                self._set_state(SafetyState.WARNING, "warning")
                if self._warning_due(now):
                    self._last_warning_notify = now
                    self._emit("warning_notify")
            return
        if self.state in {SafetyState.WARNING, SafetyState.MONITOR_FAULT}:
            self._set_state(SafetyState.NORMAL, "normal")

    def _warning_due(self, now: float) -> bool:
        return (
            self._last_warning_notify is None
            or now - self._last_warning_notify >= self.config.warning_notify_cooldown_s
        )

    def _enter_alert(self, now: float, *, reason: str) -> None:
        was_locked = self.locked
        self.alert_id += 1 if not was_locked else 0
        if self.alert_started_at is None:
            self.alert_started_at = self._wall_clock()
        self._next_alert_notify = now + self.config.alert_repeat_s
        self.monitor_fault = False
        self._set_state(SafetyState.SAFETY_ALERT, reason)
        self._emit("safety_alert")
        self._persist()

    def _set_state(self, state: SafetyState, event: str) -> None:
        if self.state == state and event != "safety_alert":
            return
        self.state = state
        self._transition_seq += 1
        self._emit(event)
        self._persist()

    def _emit(self, event: str) -> None:
        self._event = event
        self._event_seq = self._transition_seq

    def _monitor_timed_out(self, now: float) -> bool:
        reference = self.last_sample_at if self.last_sample_at is not None else self._started_at
        return now - reference > self.config.monitor_fault_after_s

    def _persist(self) -> None:
        if self.state_path is None:
            return
        doc = {
            "state": self.state.value,
            "crowd_state": self.crowd_state,
            "monitor_fault": self.monitor_fault,
            "demo_active": self.demo_active,
            "source": self.source,
            "alert_id": self.alert_id,
            "alert_started_at": self.alert_started_at,
            "last_sample_at": self.last_sample_at,
            "last_sample_seq": self.last_sample_seq,
            "transition_seq": self._transition_seq,
            "saved_at": self._wall_clock(),
        }
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(
            prefix=f".{self.state_path.name}.",
            suffix=".tmp",
            dir=str(self.state_path.parent),
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(doc, handle, ensure_ascii=False, indent=2)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_name, self.state_path)
        finally:
            try:
                os.unlink(tmp_name)
            except FileNotFoundError:
                pass

    def _restore(self) -> None:
        if self.state_path is None or not self.state_path.is_file():
            return
        try:
            raw = json.loads(self.state_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return
        if not isinstance(raw, Mapping):
            return
        saved_state = str(raw.get("state", "NORMAL")).upper()
        self.alert_id = max(0, _int_or(raw.get("alert_id"), 0))
        self.alert_started_at = _float_or_none(raw.get("alert_started_at"))
        self.last_sample_at = None
        self.last_sample_seq = None
        self.crowd_state = _normalise_level(raw.get("crowd_state", "NORMAL"))
        self._live_crowd_state = self.crowd_state
        self.demo_active = bool(raw.get("demo_active", False))
        self.source = str(raw.get("source", "live") or "live")
        self._transition_seq = max(0, _int_or(raw.get("transition_seq"), 0))
        if saved_state in {SafetyState.SAFETY_ALERT.value, SafetyState.RECOVERY.value}:
            self.state = SafetyState.SAFETY_ALERT
            self.monitor_fault = True
            self._require_revalidation = True
        else:
            self.state = SafetyState.MONITOR_FAULT
            self.monitor_fault = True


def _normalise_level(value: Any) -> str:
    level = str(value or "NORMAL").strip().upper()
    return level if level in {"NORMAL", "WARNING", "CRITICAL"} else "NORMAL"


def _sample_seq(data: Mapping[str, Any]) -> int | None:
    for key in ("event_seq", "sample_seq", "heartbeat", "seq"):
        value = data.get(key)
        try:
            return int(value)
        except (TypeError, ValueError):
            continue
    return None


def _int_or(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _float_or_none(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
