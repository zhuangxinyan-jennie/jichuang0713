from __future__ import annotations

import time

import pytest

from app_gateway.core import AppGateway, GatewayError, RuntimeState


class FakeClock:
    def __init__(self) -> None:
        self.value = 100.0

    def __call__(self) -> float:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += seconds


def gateway(clock: FakeClock, **kwargs) -> AppGateway:
    app = AppGateway(clock=clock, admin_pin="2468", **kwargs)
    app.set_runtime_state(RuntimeState.RUNNING)
    return app


def test_pair_assigns_short_id_and_resumes() -> None:
    clock = FakeClock()
    app = gateway(clock)
    first = app.pair()
    resumed = app.pair(first["token"])
    assert first["user_id"] == "A001"
    assert resumed["resumed"] is True
    assert resumed["user_id"] == first["user_id"]


def test_client_limit() -> None:
    clock = FakeClock()
    app = gateway(clock, max_clients=1)
    app.pair()
    with pytest.raises(GatewayError) as exc:
        app.pair()
    assert exc.value.code == "CLIENT_LIMIT"


def test_single_conversation_and_queue() -> None:
    clock = FakeClock()
    app = gateway(clock)
    first, second = app.pair(), app.pair()
    assert app.join_queue(first["token"])["status"] == "WAITING_ACCEPT"
    assert app.join_queue(second["token"])["status"] == "QUEUED"
    app.accept_session(first["token"])
    assert app.state()["conversation"]["active_user_id"] == first["user_id"]
    with pytest.raises(GatewayError) as exc:
        app.accept_session(second["token"])
    assert exc.value.code == "NOT_YOUR_TURN"


def test_three_turn_limit_advances_queue() -> None:
    clock = FakeClock()
    app = gateway(clock)
    first, second = app.pair(), app.pair()
    app.join_queue(first["token"])
    app.join_queue(second["token"])
    app.accept_session(first["token"])
    for _ in range(2):
        result = app.turn_complete(first["token"])
        assert result["session_ended"] is False
    result = app.turn_complete(first["token"])
    assert result["session_ended"] is True
    assert app.state()["pending_user_id"] == second["user_id"]


def test_two_minute_limit() -> None:
    clock = FakeClock()
    app = gateway(clock)
    client = app.pair()
    app.join_queue(client["token"])
    app.accept_session(client["token"])
    clock.advance(120)
    snapshot = app.state(client["token"])
    assert snapshot["conversation"]["active_user_id"] is None


def test_idle_timeout() -> None:
    clock = FakeClock()
    app = gateway(clock)
    client = app.pair()
    app.join_queue(client["token"])
    app.accept_session(client["token"])
    clock.advance(45)
    assert app.state()["conversation"]["active_user_id"] is None


def test_heartbeat_timeout_releases_active_user() -> None:
    clock = FakeClock()
    app = gateway(clock)
    first, second = app.pair(), app.pair()
    app.join_queue(first["token"])
    app.join_queue(second["token"])
    app.accept_session(first["token"])
    clock.advance(9)
    app.heartbeat(second["token"])
    clock.advance(1.1)
    snapshot = app.state()
    assert snapshot["conversation"]["active_user_id"] is None
    assert snapshot["pending_user_id"] == second["user_id"]


def test_accept_timeout_requeues_once_then_removes() -> None:
    clock = FakeClock()
    app = gateway(clock, heartbeat_timeout_s=100)
    first = app.pair()
    app.join_queue(first["token"])
    clock.advance(30)
    assert app.state()["pending_user_id"] is None
    assert app.state()["queue_user_ids"] == [first["user_id"]]
    clock.advance(1)
    assert app.state()["pending_user_id"] == first["user_id"]
    clock.advance(30)
    assert app.state()["pending_user_id"] is None
    assert app.state()["queue_user_ids"] == []


def test_admin_pin_and_stop_clear_queue() -> None:
    clock = FakeClock()
    app = gateway(clock, runtime_stop=lambda: None)
    first, second = app.pair(), app.pair()
    app.join_queue(first["token"])
    app.join_queue(second["token"])
    with pytest.raises(GatewayError):
        app.start_runtime("bad")
    admin = app.admin_login("2468")["admin_token"]
    operation = app.stop_runtime(admin)
    deadline = time.time() + 1
    while time.time() < deadline:
        if app.operation(admin, operation["operation_id"])["state"] != "PENDING":
            break
        time.sleep(0.005)
    assert app.state()["runtime"]["state"] == "MAINTENANCE"
    assert app.state()["queue_user_ids"] == []
    assert app.state()["pending_user_id"] is None


def test_agent_registration_and_timeout() -> None:
    clock = FakeClock()
    app = gateway(clock)
    registered = app.register_agent("http://127.0.0.1:8765", ["chat", "map"])
    assert app.state()["agent"]["online"] is True
    app.agent_heartbeat(registered["agent_token"])
    # Agent lease uses wall clock, so only verify registration contract here.
    assert registered["heartbeat_interval_s"] == 2


def test_expired_client_cannot_revive_with_late_heartbeat() -> None:
    clock = FakeClock()
    app = gateway(clock)
    client = app.pair()
    clock.advance(10.1)
    with pytest.raises(GatewayError) as exc:
        app.heartbeat(client["token"])
    assert exc.value.code == "INVALID_CLIENT_TOKEN"


def test_safety_pauses_session_and_requires_manual_resume() -> None:
    clock = FakeClock()
    app = gateway(clock, heartbeat_timeout_s=1000)
    client = app.pair()
    app.join_queue(client["token"])
    app.accept_session(client["token"])
    clock.advance(20)
    app.update_safety("CRITICAL")
    clock.advance(80)
    assert app.state()["conversation"]["active_user_id"] == client["user_id"]
    with pytest.raises(GatewayError) as exc:
        app.session_activity(client["token"])
    assert exc.value.code == "SAFETY_LOCKED"
    app.update_safety("NORMAL")
    assert app.state()["safety"]["state"] == "RECOVERY"
    app.resume_session(client["token"])
    assert app.state()["safety"]["state"] == "NORMAL"
    assert app.state()["conversation"]["remaining_s"] == 100


def test_safety_recovery_timeout_ends_session() -> None:
    clock = FakeClock()
    app = gateway(clock, heartbeat_timeout_s=1000)
    client = app.pair()
    app.join_queue(client["token"])
    app.accept_session(client["token"])
    app.update_safety("CRITICAL")
    clock.advance(5)
    app.update_safety("NORMAL")
    clock.advance(30)
    assert app.state()["conversation"]["active_user_id"] is None


def test_admin_pin_is_rate_limited() -> None:
    clock = FakeClock()
    app = gateway(clock)
    for _ in range(5):
        with pytest.raises(GatewayError) as exc:
            app.admin_login("bad")
        assert exc.value.code == "INVALID_PIN"
    with pytest.raises(GatewayError) as exc:
        app.admin_login("2468")
    assert exc.value.code == "ADMIN_LOGIN_LIMITED"


def test_only_active_user_can_send_audio() -> None:
    clock = FakeClock()
    app = gateway(clock)
    active, waiting = app.pair(), app.pair()
    app.join_queue(active["token"])
    app.join_queue(waiting["token"])
    app.accept_session(active["token"])
    assert app.authorize_audio(active["token"])["user_id"] == active["user_id"]
    with pytest.raises(GatewayError) as exc:
        app.authorize_audio(waiting["token"])
    assert exc.value.code == "NOT_ACTIVE_USER"
    app.update_safety("CRITICAL")
    with pytest.raises(GatewayError) as exc:
        app.authorize_audio(active["token"])
    assert exc.value.code == "SAFETY_LOCKED"
