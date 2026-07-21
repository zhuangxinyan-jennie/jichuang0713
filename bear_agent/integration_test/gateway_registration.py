"""Best-effort PC Agent registration with board App Gateway."""
from __future__ import annotations

import json
import os
import ssl
import threading
import urllib.error
import urllib.request
from typing import Any, Callable


def _post_json(url: str, payload: dict[str, Any], *, context: ssl.SSLContext | None, timeout: float = 3.0) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout, context=context) as response:
        raw = response.read()
    result = json.loads(raw.decode("utf-8")) if raw else {}
    return result if isinstance(result, dict) else {}


class GatewayRegistrar:
    def __init__(
        self,
        gateway_url: str,
        agent_url: str,
        *,
        verify_tls: bool = True,
        ca_file: str = "",
        post_json: Callable[..., dict[str, Any]] = _post_json,
    ) -> None:
        self.gateway_url = gateway_url.rstrip("/")
        self.agent_url = agent_url.rstrip("/")
        self.post_json = post_json
        self.context: ssl.SSLContext | None = None
        if self.gateway_url.startswith("https://"):
            if not verify_tls:
                self.context = ssl._create_unverified_context()
            elif ca_file:
                self.context = ssl.create_default_context(cafile=ca_file)
        self._token = ""
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    @classmethod
    def from_env(cls) -> "GatewayRegistrar | None":
        gateway_url = os.environ.get("APP_GATEWAY_URL", "").strip()
        agent_url = os.environ.get("BEAR_AGENT_PUBLIC_URL", "").strip()
        if not gateway_url or not agent_url:
            return None
        verify = os.environ.get("APP_GATEWAY_VERIFY_TLS", "1").strip().lower() not in {"0", "false", "no"}
        return cls(
            gateway_url,
            agent_url,
            verify_tls=verify,
            ca_file=os.environ.get("APP_GATEWAY_CA_FILE", "").strip(),
        )

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="app-gateway-registration", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=3.0)

    def register_once(self) -> None:
        response = self.post_json(
            self.gateway_url + "/api/v1/agent/register",
            {"base_url": self.agent_url, "capabilities": ["chat", "map"]},
            context=self.context,
        )
        token = str(response.get("agent_token", ""))
        if not token:
            raise RuntimeError("Gateway register response missing agent_token")
        self._token = token

    def heartbeat_once(self) -> None:
        if not self._token:
            self.register_once()
            return
        self.post_json(
            self.gateway_url + "/api/v1/agent/heartbeat",
            {"agent_token": self._token},
            context=self.context,
        )

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                self.heartbeat_once()
            except (OSError, ValueError, RuntimeError, urllib.error.URLError):
                self._token = ""
            self._stop.wait(2.0)

