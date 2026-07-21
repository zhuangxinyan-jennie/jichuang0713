"""Stateful control plane for the phone app.

This module intentionally has no web framework dependency.  It owns pairing,
the single conversation lease, queue timeouts, admin auth, and board runtime
operations.  HTTP/WebSocket adapters can call it from a board-side service.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import subprocess
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Mapping


class GatewayError(Exception):
    """Expected client error with an HTTP-like status code."""

    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status = int(status)
        self.code = code
        self.message = message


class RuntimeState(str, Enum):
    UNKNOWN = "UNKNOWN"
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    STOPPING = "STOPPING"
    MAINTENANCE = "MAINTENANCE"
    FAILED = "FAILED"


@dataclass
class Client:
    token: str
    user_id: str
    paired_at: float
    last_seen: float
    queue_attempts: int = 0
    accept_expired: int = 0
    not_before: float = 0.0


@dataclass
class Conversation:
    token: str
    started_at: float
    last_activity_at: float
    turns: int = 0
    agent_busy: bool = False


@dataclass
class PendingAccept:
    token: str
    deadline: float


@dataclass
class RuntimeOperation:
    operation_id: str
    action: str
    state: str = "PENDING"
    error: str = ""
    started_at: float = field(default_factory=time.time)
    finished_at: float | None = None


class AppGateway:
    """Thread-safe state machine for one board and one active conversation."""

    def __init__(
        self,
        *,
        clock: Callable[[], float] = time.monotonic,
        max_clients: int = 10,
        max_video_clients: int = 4,
        heartbeat_timeout_s: float = 10.0,
        accept_timeout_s: float = 30.0,
        session_timeout_s: float = 120.0,
        idle_timeout_s: float = 45.0,
        max_turns: int = 3,
        admin_pin: str | None = None,
        runtime_start: Callable[[], None] | None = None,
        runtime_stop: Callable[[], None] | None = None,
    ) -> None:
        self.clock = clock
        self.max_clients = int(max_clients)
        self.max_video_clients = int(max_video_clients)
        self.heartbeat_timeout_s = float(heartbeat_timeout_s)
        self.accept_timeout_s = float(accept_timeout_s)
        self.session_timeout_s = float(session_timeout_s)
        self.idle_timeout_s = float(idle_timeout_s)
        self.max_turns = int(max_turns)
        self._lock = threading.RLock()
        self._clients: dict[str, Client] = {}
        self._ids: set[str] = set()
        self._id_counter = 0
        self._queue: list[str] = []
        self._pending: PendingAccept | None = None
        self._conversation: Conversation | None = None
        self._revision = 0
        self._runtime_state = RuntimeState.UNKNOWN
        self._runtime_error = ""
        self._operations: dict[str, RuntimeOperation] = {}
        self._runtime_start = runtime_start
        self._runtime_stop = runtime_stop
        self._agent: dict[str, object] = {
            "online": False,
            "base_url": "",
            "capabilities": [],
            "last_seen": None,
        }
        self._admin_salt = secrets.token_bytes(16)
        self._admin_hash = self._hash_pin(admin_pin) if admin_pin else None
        self._admin_tokens: dict[str, float] = {}
        self._admin_failures: list[float] = []
        self._safety_state = "NORMAL"
        self._safety_paused_at: float | None = None
        self._safety_resume_deadline: float | None = None
        self._vision_state: dict[str, object] = {}
        self._on_session_start: Callable[[str], None] | None = None
        self._on_session_end: Callable[[str], None] | None = None

    # ---------- public client/session API ----------

    def pair(self, resume_token: str | None = None) -> dict:
        with self._lock:
            now = self.clock()
            self._tick_locked(now)
            if resume_token and resume_token in self._clients:
                client = self._clients[resume_token]
                client.last_seen = now
                self._touch_locked()
                return self._client_result_locked(client, resumed=True)
            if len(self._clients) >= self.max_clients:
                raise GatewayError(429, "CLIENT_LIMIT", "连接数量已满")
            token = secrets.token_urlsafe(24)
            user_id = self._new_user_id_locked()
            client = Client(token=token, user_id=user_id, paired_at=now, last_seen=now)
            self._clients[token] = client
            self._touch_locked()
            return self._client_result_locked(client, resumed=False)

    def heartbeat(self, token: str) -> dict:
        with self._lock:
            now = self.clock()
            self._tick_locked(now)
            client = self._client_locked(token)
            client.last_seen = now
            self._touch_locked()
            return self._client_result_locked(client, resumed=True)

    def join_queue(self, token: str) -> dict:
        with self._lock:
            now = self.clock()
            client = self._client_locked(token)
            self._tick_locked(now)
            if self._runtime_state != RuntimeState.RUNNING:
                raise GatewayError(409, "RUNTIME_NOT_READY", "互动服务未运行")
            if self._conversation and self._conversation.token == token:
                return self._client_result_locked(client)
            if self._pending and self._pending.token == token:
                return self._client_result_locked(client)
            if token in self._queue:
                return self._client_result_locked(client)
            self._queue.append(token)
            self._advance_queue_locked(now)
            self._touch_locked()
            return self._client_result_locked(client)

    def leave_queue(self, token: str) -> dict:
        with self._lock:
            client = self._client_locked(token)
            now = self.clock()
            self._tick_locked(now)
            if self._conversation and self._conversation.token == token:
                self._end_conversation_locked(now, reason="user_leave")
            elif self._pending and self._pending.token == token:
                self._pending = None
                self._advance_queue_locked(now)
            else:
                self._remove_from_queue_locked(token)
            self._touch_locked()
            return self._client_result_locked(client)

    def accept_session(self, token: str) -> dict:
        with self._lock:
            now = self.clock()
            self._client_locked(token)
            self._tick_locked(now)
            self._raise_if_safety_locked()
            if not self._pending or self._pending.token != token:
                raise GatewayError(409, "NOT_YOUR_TURN", "当前未轮到该用户")
            self._pending = None
            self._conversation = Conversation(token, now, now)
            self._notify_session_callback(self._on_session_start, token)
            self._touch_locked()
            return self._client_result_locked(self._clients[token])

    def session_activity(self, token: str) -> dict:
        with self._lock:
            now = self.clock()
            self._client_locked(token)
            self._tick_locked(now)
            self._raise_if_safety_locked()
            conversation = self._require_conversation_locked(token)
            conversation.last_activity_at = now
            self._touch_locked()
            return self._client_result_locked(self._clients[token])

    def turn_complete(self, token: str) -> dict:
        with self._lock:
            now = self.clock()
            self._client_locked(token)
            self._tick_locked(now)
            self._raise_if_safety_locked()
            conversation = self._require_conversation_locked(token)
            conversation.turns += 1
            conversation.last_activity_at = now
            ended = conversation.turns >= self.max_turns or now - conversation.started_at >= self.session_timeout_s
            if ended:
                self._end_conversation_locked(now, reason="turn_limit")
            self._touch_locked()
            result = self._client_result_locked(self._clients[token])
            result["turns"] = conversation.turns
            result["session_ended"] = ended
            return result

    def begin_agent_turn(self, token: str) -> dict:
        with self._lock:
            now = self.clock()
            self._tick_locked(now)
            self._raise_if_safety_locked()
            conversation = self._require_conversation_locked(token)
            if conversation.agent_busy:
                raise GatewayError(409, "AGENT_BUSY", "上一轮回复尚未完成")
            if not self._agent.get("online") or not self._agent.get("base_url"):
                raise GatewayError(503, "AGENT_OFFLINE", "智能服务离线")
            conversation.agent_busy = True
            conversation.last_activity_at = now
            self._touch_locked()
            return {
                "base_url": str(self._agent["base_url"]),
                "turns": conversation.turns,
                "remaining_turns": self.max_turns - conversation.turns,
            }

    def finish_agent_turn(self, token: str, *, success: bool) -> dict:
        with self._lock:
            now = self.clock()
            conversation = self._require_conversation_locked(token)
            conversation.agent_busy = False
            conversation.last_activity_at = now
            ended = False
            if success:
                conversation.turns += 1
                ended = (
                    conversation.turns >= self.max_turns
                    or now - conversation.started_at >= self.session_timeout_s
                )
                if ended:
                    self._end_conversation_locked(now, reason="turn_limit")
            self._touch_locked()
            return {"turns": conversation.turns, "session_ended": ended}

    def set_session_callbacks(
        self,
        *,
        on_start: Callable[[str], None] | None = None,
        on_end: Callable[[str], None] | None = None,
    ) -> None:
        with self._lock:
            self._on_session_start = on_start
            self._on_session_end = on_end

    def resume_session(self, token: str) -> dict:
        with self._lock:
            now = self.clock()
            client = self._client_locked(token)
            self._tick_locked(now)
            self._require_conversation_locked(token)
            if self._safety_state != "RECOVERY":
                raise GatewayError(409, "NOT_RECOVERING", "当前无需恢复对话")
            self._safety_state = "NORMAL"
            self._safety_resume_deadline = None
            self._touch_locked()
            return self._client_result_locked(client)

    def end_session(self, token: str, *, reason: str = "user_end") -> dict:
        with self._lock:
            client = self._client_locked(token)
            now = self.clock()
            self._tick_locked(now)
            if not self._conversation or self._conversation.token != token:
                raise GatewayError(409, "NO_ACTIVE_SESSION", "当前没有该用户的对话")
            self._end_conversation_locked(now, reason=reason)
            self._touch_locked()
            return self._client_result_locked(client)

    def state(self, token: str | None = None) -> dict:
        with self._lock:
            now = self.clock()
            self._tick_locked(now)
            own = self._clients.get(token) if token else None
            return self._snapshot_locked(own)

    def validate_client(self, token: str) -> dict:
        with self._lock:
            now = self.clock()
            self._tick_locked(now)
            client = self._client_locked(token)
            client.last_seen = now
            return {"user_id": client.user_id, "status": self._client_result_locked(client)["status"]}

    def authorize_audio(self, token: str) -> dict:
        """Validate one phone audio chunk without incrementing public revision."""
        with self._lock:
            now = self.clock()
            self._tick_locked(now)
            client = self._client_locked(token)
            self._raise_if_safety_locked()
            conversation = self._require_conversation_locked(token)
            if conversation.agent_busy:
                raise GatewayError(409, "AGENT_BUSY", "请等待当前回复完成")
            client.last_seen = now
            conversation.last_activity_at = now
            return {"user_id": client.user_id, "turns": conversation.turns}

    def active_conversation_identity(self) -> dict | None:
        with self._lock:
            now = self.clock()
            self._tick_locked(now)
            if not self._conversation:
                return None
            client = self._clients.get(self._conversation.token)
            if client is None:
                return None
            return {"token": client.token, "user_id": client.user_id}

    def update_safety(self, state: str) -> dict:
        """Apply board crowd safety state and pause/resume the active lease."""
        with self._lock:
            now = self.clock()
            level = str(state or "NORMAL").strip().upper()
            if level in {"CRITICAL", "SAFETY_ALERT"}:
                if self._safety_state not in {"CRITICAL", "SAFETY_ALERT"}:
                    self._safety_paused_at = now
                self._safety_state = "SAFETY_ALERT"
                self._safety_resume_deadline = None
            elif level == "NORMAL":
                if self._safety_state in {"CRITICAL", "SAFETY_ALERT"} and self._conversation:
                    paused_at = self._safety_paused_at if self._safety_paused_at is not None else now
                    paused_for = max(0.0, now - paused_at)
                    self._conversation.started_at += paused_for
                    self._conversation.last_activity_at += paused_for
                    self._safety_state = "RECOVERY"
                    self._safety_resume_deadline = now + 30.0
                else:
                    self._safety_state = "NORMAL"
                    self._safety_resume_deadline = None
                self._safety_paused_at = None
            elif self._safety_state not in {"CRITICAL", "SAFETY_ALERT", "RECOVERY"}:
                self._safety_state = level if level in {"WARNING", "MONITOR_FAULT"} else "NORMAL"
            self._touch_locked()
            return self._snapshot_locked(None)

    def update_vision_state(self, state: Mapping[str, object]) -> None:
        with self._lock:
            self._vision_state = dict(state)
            self._touch_locked()

    # ---------- admin/runtime API ----------

    def admin_login(self, pin: str) -> dict:
        with self._lock:
            now = time.time()
            self._admin_failures = [value for value in self._admin_failures if now - value < 60.0]
            if len(self._admin_failures) >= 5:
                raise GatewayError(429, "ADMIN_LOGIN_LIMITED", "PIN 尝试过多，请稍后再试")
            if self._admin_hash is None:
                raise GatewayError(503, "ADMIN_PIN_UNCONFIGURED", "未配置管理员 PIN")
            supplied = self._hash_pin(pin)
            if not hmac.compare_digest(supplied, self._admin_hash):
                self._admin_failures.append(now)
                raise GatewayError(401, "INVALID_PIN", "管理员 PIN 错误")
            token = secrets.token_urlsafe(32)
            self._admin_failures.clear()
            self._admin_tokens[token] = now + 1800.0
            return {"admin_token": token, "expires_in_s": 1800}

    def start_runtime(self, admin_token: str) -> dict:
        self._require_admin(admin_token)
        return self._runtime_operation("start")

    def stop_runtime(self, admin_token: str) -> dict:
        self._require_admin(admin_token)
        with self._lock:
            now = self.clock()
            self._clear_sessions_locked(now)
        return self._runtime_operation("stop")

    def operation(self, admin_token: str, operation_id: str) -> dict:
        self._require_admin(admin_token)
        with self._lock:
            operation = self._operations.get(operation_id)
            if operation is None:
                raise GatewayError(404, "OPERATION_NOT_FOUND", "操作不存在")
            return self._operation_dict(operation)

    def set_runtime_state(self, state: RuntimeState | str, error: str = "") -> None:
        with self._lock:
            self._runtime_state = RuntimeState(state)
            self._runtime_error = error
            self._touch_locked()

    # ---------- PC Agent API ----------

    def register_agent(self, base_url: str, capabilities: list[str] | None = None) -> dict:
        with self._lock:
            token = secrets.token_urlsafe(24)
            now = time.time()
            self._agent = {
                "online": True,
                "base_url": str(base_url).rstrip("/"),
                "capabilities": list(capabilities or []),
                "last_seen": now,
                "token": token,
            }
            self._touch_locked()
            return {"agent_token": token, "heartbeat_interval_s": 2, "lease_timeout_s": 5}

    def agent_heartbeat(self, agent_token: str) -> dict:
        with self._lock:
            if not hmac.compare_digest(str(self._agent.get("token", "")), str(agent_token)):
                raise GatewayError(401, "INVALID_AGENT_TOKEN", "Agent token 无效")
            self._agent["online"] = True
            self._agent["last_seen"] = time.time()
            self._touch_locked()
            return {"ok": True, "agent": dict(self._agent)}

    # ---------- internals ----------

    def _tick_locked(self, now: float) -> None:
        expired = [token for token, c in self._clients.items() if now - c.last_seen > self.heartbeat_timeout_s]
        for token in expired:
            self._remove_client_locked(token, now, reason="heartbeat_timeout")
        if self._pending and now >= self._pending.deadline:
            token = self._pending.token
            self._pending = None
            client = self._clients.get(token)
            if client is not None:
                client.accept_expired += 1
                if client.accept_expired < 2:
                    client.not_before = now + 1.0
                    self._queue.append(token)
                else:
                    self._remove_client_locked(token, now, reason="accept_timeout")
            self._advance_queue_locked(now)
        if self._conversation and self._safety_state == "RECOVERY":
            if self._safety_resume_deadline is not None and now >= self._safety_resume_deadline:
                self._end_conversation_locked(now, reason="safety_resume_timeout")
                self._safety_state = "NORMAL"
                self._safety_resume_deadline = None
        elif self._conversation and self._safety_state not in {"CRITICAL", "SAFETY_ALERT"}:
            conversation = self._conversation
            if now - conversation.started_at >= self.session_timeout_s:
                self._end_conversation_locked(now, reason="session_timeout")
            elif now - conversation.last_activity_at >= self.idle_timeout_s:
                self._end_conversation_locked(now, reason="idle_timeout")
        if self._agent.get("online") and self._agent.get("last_seen"):
            if time.time() - float(self._agent["last_seen"]) > 5.0:
                self._agent["online"] = False
        self._advance_queue_locked(now)

    def _advance_queue_locked(self, now: float) -> None:
        if self._runtime_state != RuntimeState.RUNNING or self._conversation or self._pending:
            return
        for index, token in enumerate(self._queue):
            client = self._clients.get(token)
            if client is None:
                continue
            if client.not_before > now:
                continue
            self._queue.pop(index)
            self._pending = PendingAccept(token, now + self.accept_timeout_s)
            return

    def _end_conversation_locked(self, now: float, *, reason: str) -> None:
        del reason
        token = self._conversation.token if self._conversation else None
        self._conversation = None
        if token:
            self._notify_session_callback(self._on_session_end, token)
        self._advance_queue_locked(now)

    def _clear_sessions_locked(self, now: float) -> None:
        del now
        active_token = self._conversation.token if self._conversation else None
        self._queue.clear()
        self._pending = None
        self._conversation = None
        self._safety_state = "MAINTENANCE"
        self._safety_paused_at = None
        self._safety_resume_deadline = None
        for client in self._clients.values():
            client.queue_attempts = 0
        if active_token:
            self._notify_session_callback(self._on_session_end, active_token)

    def _remove_client_locked(self, token: str, now: float, *, reason: str) -> None:
        del reason
        self._remove_from_queue_locked(token)
        if self._pending and self._pending.token == token:
            self._pending = None
        if self._conversation and self._conversation.token == token:
            self._conversation = None
        client = self._clients.pop(token, None)
        if client:
            self._ids.discard(client.user_id)
        self._advance_queue_locked(now)

    def _remove_from_queue_locked(self, token: str) -> None:
        self._queue = [item for item in self._queue if item != token]

    def _client_locked(self, token: str) -> Client:
        client = self._clients.get(str(token))
        if client is None:
            raise GatewayError(401, "INVALID_CLIENT_TOKEN", "用户连接已失效")
        return client

    def _require_conversation_locked(self, token: str) -> Conversation:
        if not self._conversation or self._conversation.token != token:
            raise GatewayError(409, "NOT_ACTIVE_USER", "当前用户没有对话控制权")
        return self._conversation

    def _new_user_id_locked(self) -> str:
        for _ in range(10000):
            self._id_counter = (self._id_counter % 999) + 1
            value = f"A{self._id_counter:03d}"
            if value not in self._ids:
                self._ids.add(value)
                return value
        raise GatewayError(503, "ID_EXHAUSTED", "临时用户 ID 已耗尽")

    def _client_result_locked(self, client: Client, *, resumed: bool = False) -> dict:
        status = "CONNECTED"
        if self._conversation and self._conversation.token == client.token:
            status = "ACTIVE"
        elif self._pending and self._pending.token == client.token:
            status = "WAITING_ACCEPT"
        elif client.token in self._queue:
            status = "QUEUED"
        return {
            "user_id": client.user_id,
            "token": client.token,
            "status": status,
            "resumed": resumed,
            "queue_position": self._queue_position_locked(client.token),
            "active_user_id": self._user_id_for_token_locked(self._conversation.token) if self._conversation else None,
            "revision": self._revision,
        }

    def _queue_position_locked(self, token: str) -> int | None:
        if self._pending and self._pending.token == token:
            return 0
        try:
            return self._queue.index(token) + 1
        except ValueError:
            return None

    def _user_id_for_token_locked(self, token: str | None) -> str | None:
        return self._clients[token].user_id if token and token in self._clients else None

    def _snapshot_locked(self, own: Client | None) -> dict:
        clients = [self._clients[token] for token in self._queue if token in self._clients]
        return {
            "revision": self._revision,
            "runtime": {
                "state": self._runtime_state.value,
                "error": self._runtime_error,
            },
            "agent": {
                "online": bool(self._agent.get("online")),
                "base_url": self._agent.get("base_url", ""),
                "capabilities": list(self._agent.get("capabilities", [])),
            },
            "safety": {
                "state": self._safety_state,
                "locked": self._safety_state in {"CRITICAL", "SAFETY_ALERT", "RECOVERY"},
                "resume_deadline_s": max(0, int(self._safety_resume_deadline - self.clock()))
                if self._safety_resume_deadline is not None
                else 0,
            },
            "vision": dict(self._vision_state),
            "conversation": {
                "active_user_id": self._user_id_for_token_locked(self._conversation.token) if self._conversation else None,
                "turns": self._conversation.turns if self._conversation else 0,
                "remaining_turns": max(0, self.max_turns - self._conversation.turns) if self._conversation else 0,
                "remaining_s": max(0, int(self.session_timeout_s - (self.clock() - self._conversation.started_at))) if self._conversation else 0,
                "agent_busy": self._conversation.agent_busy if self._conversation else False,
            },
            "pending_user_id": self._user_id_for_token_locked(self._pending.token) if self._pending else None,
            "queue_user_ids": [client.user_id for client in clients],
            "connected_clients": len(self._clients),
            "video_clients": 0,
            "own": self._client_result_locked(own) if own else None,
        }

    def _runtime_operation(self, action: str) -> dict:
        with self._lock:
            if action == "start" and self._runtime_state in {RuntimeState.STARTING, RuntimeState.RUNNING}:
                raise GatewayError(409, "RUNTIME_ALREADY_RUNNING", "互动服务已在运行或启动中")
            if action == "stop" and self._runtime_state in {RuntimeState.STOPPING, RuntimeState.MAINTENANCE}:
                raise GatewayError(409, "RUNTIME_ALREADY_STOPPED", "互动服务已停止或停止中")
            operation = RuntimeOperation(uuid.uuid4().hex, action)
            self._operations[operation.operation_id] = operation
            self._runtime_state = RuntimeState.STARTING if action == "start" else RuntimeState.STOPPING
            self._runtime_error = ""
            self._touch_locked()
            threading.Thread(target=self._run_runtime_operation, args=(operation,), daemon=True).start()
            return self._operation_dict(operation)

    def _run_runtime_operation(self, operation: RuntimeOperation) -> None:
        try:
            callback = self._runtime_start if operation.action == "start" else self._runtime_stop
            if callback:
                callback()
            else:
                command = os.environ.get(
                    "APP_GATEWAY_START_CMD" if operation.action == "start" else "APP_GATEWAY_STOP_CMD", ""
                ).strip()
                if command:
                    completed = subprocess.run(command, shell=True, timeout=90, check=False)
                    if completed.returncode != 0:
                        raise RuntimeError(f"command exit {completed.returncode}")
            with self._lock:
                operation.state = "SUCCEEDED"
                operation.finished_at = time.time()
                self._runtime_state = RuntimeState.RUNNING if operation.action == "start" else RuntimeState.MAINTENANCE
                self._runtime_error = ""
                if operation.action == "start":
                    self._safety_state = "NORMAL"
                self._touch_locked()
        except Exception as exc:  # pragma: no cover - exercised through callback test
            with self._lock:
                operation.state = "FAILED"
                operation.error = str(exc)
                operation.finished_at = time.time()
                self._runtime_state = RuntimeState.FAILED
                self._runtime_error = str(exc)
                self._touch_locked()

    def _operation_dict(self, operation: RuntimeOperation) -> dict:
        return {
            "operation_id": operation.operation_id,
            "action": operation.action,
            "state": operation.state,
            "error": operation.error,
            "started_at": operation.started_at,
            "finished_at": operation.finished_at,
        }

    def _require_admin(self, token: str) -> None:
        with self._lock:
            expiry = self._admin_tokens.get(str(token))
            if expiry is None or time.time() >= expiry:
                self._admin_tokens.pop(str(token), None)
                raise GatewayError(401, "INVALID_ADMIN_TOKEN", "管理员令牌无效或已过期")

    def _raise_if_safety_locked(self) -> None:
        if self._safety_state in {"CRITICAL", "SAFETY_ALERT", "RECOVERY"}:
            raise GatewayError(423, "SAFETY_LOCKED", "安全状态下互动已暂停")

    def _hash_pin(self, pin: str) -> bytes:
        return hashlib.pbkdf2_hmac("sha256", str(pin).encode(), self._admin_salt, 120_000)

    def _touch_locked(self) -> None:
        self._revision += 1

    @staticmethod
    def _notify_session_callback(callback: Callable[[str], None] | None, token: str) -> None:
        if callback is None:
            return
        threading.Thread(target=callback, args=(token,), daemon=True).start()
