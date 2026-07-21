from __future__ import annotations

from gateway_registration import GatewayRegistrar


def test_register_then_heartbeat_uses_agent_url_and_capabilities() -> None:
    calls = []

    def fake_post(url, payload, **_kwargs):
        calls.append((url, payload))
        if url.endswith("/register"):
            return {"agent_token": "token-1"}
        return {"ok": True}

    registrar = GatewayRegistrar("http://board:8788", "http://pc:8765", post_json=fake_post)
    registrar.heartbeat_once()
    registrar.heartbeat_once()

    assert calls[0] == (
        "http://board:8788/api/v1/agent/register",
        {"base_url": "http://pc:8765", "capabilities": ["chat", "map"]},
    )
    assert calls[1] == (
        "http://board:8788/api/v1/agent/heartbeat",
        {"agent_token": "token-1"},
    )
