from __future__ import annotations

import time

from app_gateway.agent_proxy import AgentProxy
from app_gateway.core import AppGateway, RuntimeState


def active_gateway() -> tuple[AppGateway, dict]:
    gateway = AppGateway(admin_pin="2468")
    gateway.set_runtime_state(RuntimeState.RUNNING)
    registered = gateway.register_agent("http://agent:8765", ["chat", "map"])
    assert registered["agent_token"]
    client = gateway.pair()
    gateway.join_queue(client["token"])
    gateway.accept_session(client["token"])
    return gateway, client


def test_agent_proxy_sends_voice_only_perception_and_completes_turn() -> None:
    gateway, client = active_gateway()
    calls = []
    phone_messages = []

    def fake_post(url, payload, **kwargs):
        calls.append((url, payload, kwargs))
        return {"interaction_type": "random_interaction", "speech": "你好"}

    proxy = AgentProxy(gateway, lambda token, payload: phone_messages.append((token, payload)), http_post=fake_post)
    proxy._process(client["token"], "你好熊大")

    assert calls[0][0] == "http://agent:8765/api/process"
    assert calls[0][1]["speech_text"] == "你好熊大"
    assert calls[0][1]["gesture"] == "none"
    assert "video" not in calls[0][1]
    assert phone_messages[0][0] == client["token"]
    assert phone_messages[0][1]["type"] == "agent_response"
    assert phone_messages[0][1]["turns"] == 1


def test_agent_busy_blocks_phone_audio() -> None:
    gateway, client = active_gateway()
    gateway.begin_agent_turn(client["token"])
    try:
        gateway.authorize_audio(client["token"])
    except Exception as exc:
        assert getattr(exc, "code", "") == "AGENT_BUSY"
    else:
        raise AssertionError("audio must be blocked while Agent is replying")


def test_session_callbacks_reset_agent() -> None:
    gateway = AppGateway(admin_pin="2468")
    gateway.set_runtime_state(RuntimeState.RUNNING)
    gateway.register_agent("http://agent:8765", ["chat"])
    calls = []

    def fake_post(url, payload, **kwargs):
        calls.append(url)
        return {"ok": True}

    proxy = AgentProxy(gateway, lambda _token, _payload: None, http_post=fake_post)
    gateway.set_session_callbacks(on_start=proxy.reset_session, on_end=proxy.reset_session)
    client = gateway.pair()
    gateway.join_queue(client["token"])
    gateway.accept_session(client["token"])
    deadline = time.time() + 1
    while len(calls) < 1 and time.time() < deadline:
        time.sleep(0.005)
    gateway.end_session(client["token"])
    while len(calls) < 2 and time.time() < deadline:
        time.sleep(0.005)
    assert calls == ["http://agent:8765/api/reset", "http://agent:8765/api/reset"]
