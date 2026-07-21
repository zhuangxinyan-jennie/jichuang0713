"""Proxy one active phone conversation to the registered PC Bear Agent."""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from typing import Any, Callable

from .core import AppGateway, GatewayError


def post_json(url: str, payload: dict, *, headers: dict[str, str] | None = None, timeout: float = 45.0) -> Any:
    raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=raw,
        headers={"Content-Type": "application/json", **(headers or {})},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Agent HTTP {exc.code}: {detail}") from exc
    return json.loads(body.decode("utf-8")) if body else None


class AgentProxy:
    def __init__(
        self,
        gateway: AppGateway,
        send_to_phone: Callable[[str, dict], None],
        *,
        http_post: Callable[..., Any] = post_json,
    ) -> None:
        self.gateway = gateway
        self.send_to_phone = send_to_phone
        self.http_post = http_post

    def submit_final(self, token: str, text: str) -> None:
        clean_text = str(text or "").strip()
        if not clean_text:
            return
        threading.Thread(target=self._process, args=(token, clean_text), daemon=True).start()

    def reset_session(self, _token: str) -> None:
        target = self.gateway.state().get("agent", {})
        if not target.get("online") or not target.get("base_url"):
            return
        try:
            self.http_post(str(target["base_url"]).rstrip("/") + "/api/reset", {}, timeout=5.0)
        except Exception:
            pass

    def _process(self, token: str, text: str) -> None:
        begun = False
        try:
            turn = self.gateway.begin_agent_turn(token)
            begun = True
            base_url = str(turn["base_url"]).rstrip("/")
            payload = {
                "emotion": "neutral",
                "emotion_confidence": 0.0,
                "gesture": "none",
                "gesture_confidence": 0.0,
                "hand_gesture": "none",
                "hand_gesture_confidence": 0.0,
                "person_detected": True,
                "person_count": 1,
                "speech_text": text,
            }
            result = self.http_post(
                base_url + "/api/process",
                payload,
                headers={"X-Agent-Caller": "board-bridge"},
                timeout=45.0,
            )
            outcome = self.gateway.finish_agent_turn(token, success=True)
            self.send_to_phone(token, {"type": "agent_response", "payload": result, **outcome})
        except GatewayError as exc:
            if begun:
                self._finish_failed(token)
            self.send_to_phone(token, {"type": "error", "code": exc.code, "message": exc.message})
        except Exception as exc:
            if begun:
                self._finish_failed(token)
            self.send_to_phone(token, {"type": "error", "code": "AGENT_REQUEST_FAILED", "message": str(exc)})

    def _finish_failed(self, token: str) -> None:
        try:
            self.gateway.finish_agent_turn(token, success=False)
        except GatewayError:
            pass

