"""
Bear Agent 联调 HTTP 服务：接收模拟感知 JSON，直接走随机互动链路（等同 process_test_pipeline），返回完整 Agent 输出。
请在 bear_agent 仓库根目录运行：  python integration_test/server.py
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from typing import Any

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from agent import BearAgent

from multimodal_gate import MultimodalTurnGate, gate_enabled, is_board_bridge_request
from board_state import (
    BOARD_BRIDGE_HEADER,
    board_auto_last_payload,
    record_board_drive_if_bridge,
    reset_board_state,
    update_board_asr_live,
)
from schemas import BoardAsrLiveIn, PerceptionIn
from settings import load_server_settings
from safety_supervisor import SafetySupervisor


class BearAgentForHttp(BearAgent):
    """
    HTTP 服务专用：随机互动分支沿用 LLM 原文，不再做 TTS 字数截断。
    （服务端 sounddevice 直接播 + 标点切片已能稳定流式播放，无需限长）
    """


_LATENCY_HTTP_PATHS = frozenset({"/api/process", "/api/process-test", "/api/map-query"})


def _latency_log_enabled() -> bool:
    """终端打印关键 POST 耗时（服务端视角，含推理与闸门阻塞）；设 BEAR_LATENCY_LOG=1 开启。"""
    return load_server_settings().latency_log_enabled


def _latency_log_append(line: str) -> None:
    path = load_server_settings().latency_log_file
    if not path:
        return
    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def perception_dump_for_agent(body: PerceptionIn) -> dict:
    """
    转为送入 BearAgent.process / 随机互动 的 perception 字典。
    默认屏蔽躯干动作 gesture（wave/clapping 等模型误识别多）：强制为 none。
    若需恢复上游 gesture，设置环境变量 BEAR_AGENT_PASS_BODY_GESTURE=1。
    """
    d = body.model_dump(exclude_none=True)
    if not load_server_settings().pass_body_gesture:
        d["gesture"] = "none"
        d["gesture_confidence"] = 0.0
    return d


def _record_board_drive_if_bridge(request: Request, result, perception: dict | None = None):
    """板端 board_bridge 发来的 POST 记录序号与感知，供前端 GET 轮询驱动 WebGL 并展示实时字段。"""
    record_board_drive_if_bridge(
        request_headers=request.headers,
        app_state=request.app.state,
        result=result,
        perception=perception,
        keep_speech=load_server_settings().keep_bridge_speech_in_poll,
    )


def _safety(request: Request) -> SafetySupervisor:
    supervisor = getattr(request.app.state, "safety_supervisor", None)
    if supervisor is None:
        raise HTTPException(status_code=503, detail="safety supervisor unavailable")
    return supervisor


def _raise_if_safety_locked(request: Request) -> None:
    snap = _safety(request).tick()
    if snap.locked:
        raise HTTPException(
            status_code=423,
            detail={
                "code": "SAFETY_LOCKED",
                "state": snap.state.value,
                "alert_id": snap.alert_id,
            },
        )


def _safety_demo_enabled() -> bool:
    raw = os.environ.get("SAFETY_DEMO_ENABLED", "0").strip().lower()
    return raw in {"1", "true", "yes", "on"}


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.bear_agent = BearAgentForHttp()
    reset_board_state(app.state)
    app.state.multimodal_gate = MultimodalTurnGate()
    state_path = os.environ.get("SAFETY_STATE_PATH", "").strip()
    if not state_path:
        state_path = str(Path(ROOT) / "outputs" / "safety_state.json")
    app.state.safety_supervisor = SafetySupervisor(state_path=state_path)
    yield


_SETTINGS = load_server_settings()
app = FastAPI(title="Bear Agent Integration Test", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(_SETTINGS.cors_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def latency_log_middleware(request: Request, call_next):
    if request.url.path not in _LATENCY_HTTP_PATHS or not _latency_log_enabled():
        return await call_next(request)
    t0 = time.perf_counter()
    response = await call_next(request)
    dt_ms = (time.perf_counter() - t0) * 1000.0
    caller = (request.headers.get("X-Agent-Caller") or "").strip().lower() or "—"
    msg = f"[latency] {request.method} {request.url.path} {dt_ms:.1f}ms caller={caller}"
    print(msg, flush=True)
    _latency_log_append(msg)
    return response


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/multimodal/gate-status")
def multimodal_gate_status(request: Request):
    """
    board_bridge 轮询：Agent 是否在「上一轮 board_bridge 推理 + 前端播放」占用中。
    busy=true 时不应发起新的 /api/process（否则请求体会卡在阻塞前的旧快照上）。
    """
    gate = getattr(request.app.state, "multimodal_gate", None)
    safety = _safety(request).tick()
    if gate is None or not gate_enabled():
        return {
            "enabled": False,
            "busy": False,
            "asr_clear_token": 0,
            "safety_locked": safety.locked,
            "safety_state": safety.state.value,
        }
    status = gate.status()
    return {
        "enabled": True,
        **status,
        "safety_locked": safety.locked,
        "safety_state": safety.state.value,
    }


@app.get("/api/safety/state")
def safety_state(request: Request):
    """Frontend safety poll; 400 ms polling is intentionally unconditional."""
    return _safety(request).tick().to_dict()


@app.post("/api/safety/update")
def safety_update(body: dict[str, Any], request: Request):
    """board_bridge forwards every new board crowd sample."""
    caller = (request.headers.get("X-Agent-Caller") or "").strip().lower()
    if caller != BOARD_BRIDGE_HEADER:
        raise HTTPException(status_code=403, detail="X-Agent-Caller must be board-bridge")
    supervisor = _safety(request)
    snapshot = supervisor.update(body)
    if snapshot.locked:
        gate = getattr(request.app.state, "multimodal_gate", None)
        if gate is not None:
            gate.force_idle()
    return snapshot.to_dict()


@app.post("/api/safety/demo/trigger")
def safety_demo_trigger(request: Request):
    if not _safety_demo_enabled():
        raise HTTPException(status_code=404, detail="safety demo disabled")
    snapshot = _safety(request).trigger_demo()
    gate = getattr(request.app.state, "multimodal_gate", None)
    if gate is not None:
        gate.force_idle()
    return snapshot.to_dict()


@app.post("/api/safety/demo/release")
def safety_demo_release(request: Request):
    if not _safety_demo_enabled():
        raise HTTPException(status_code=404, detail="safety demo disabled")
    return _safety(request).release_demo().to_dict()


@app.post("/api/safety/recovery-done")
def safety_recovery_done(request: Request):
    return _safety(request).recovery_done().to_dict()


@app.post("/api/multimodal/playback-done")
def multimodal_playback_done(request: Request):
    """
    前端在熊大本轮语音/预烘焙 WAV **全部播放结束后**调用，释放 board_bridge 下一轮 POST。
    若未启用闸门或未处于等待播放，幂等忽略。
    """
    gate = getattr(request.app.state, "multimodal_gate", None)
    if gate is not None and gate_enabled():
        gate.release_playback_done()
    return {"ok": True}


@app.post("/api/multimodal/playback-start")
def multimodal_playback_start(request: Request):
    """
    前端开始播放熊大语音时调用：临时关闭 board_bridge 对麦克风 ASR 的采纳，
    避免扬声器里的熊大声音被识别成游客输入。
    """
    gate = getattr(request.app.state, "multimodal_gate", None)
    if gate is not None and gate_enabled():
        gate.mark_playback_started()
    return {"ok": True}


@app.post("/api/board-asr-live")
def board_asr_live(body: BoardAsrLiveIn, request: Request):
    """board_bridge 每轮 poll 调用：刷新前端可见的 ASR 散句/整句，不计入 seq。"""
    caller = (request.headers.get("X-Agent-Caller") or "").strip().lower()
    if caller != BOARD_BRIDGE_HEADER:
        raise HTTPException(status_code=403, detail="X-Agent-Caller must be board-bridge")
    update_board_asr_live(
        request.app.state,
        partial=body.partial,
        final=body.final,
        normalized=body.normalized,
    )
    return {"ok": True}


@app.get("/api/board-auto/last")
def board_auto_last(request: Request):
    """
    最近一次由 board_bridge（请求头 X-Agent-Caller: board-bridge）触发的 Agent 响应。
    前端轮询：seq 递增且 output 非 null 时调用 handleBearAgentPayload(output)。
    """
    return board_auto_last_payload(request.app.state)


@app.post("/api/process-test")
def process_test(body: PerceptionIn, request: Request):
    """绕过玩法状态机，直接推理并返回随机互动 JSON（含 speech、actions、emotion）。"""
    _raise_if_safety_locked(request)
    agent: BearAgent = request.app.state.bear_agent
    perception_dump = perception_dump_for_agent(body)
    result = agent._process_random_interaction(perception_dump)
    _record_board_drive_if_bridge(request, result, perception_dump)
    return result


@app.post("/api/map-query")
def map_query(body: PerceptionIn, request: Request):
    """
    纯地图问路：直接调用 map_guide.MapGuide（Dijkstra + 方位话术），
    不经过玩法状态机，适合前端「地图查询」页只展示平面图 + 字幕/语音。
    """
    _raise_if_safety_locked(request)
    from map_guide import MapGuide

    text = (body.speech_text or "").strip()
    perception_dump = perception_dump_for_agent(body)

    if not text:
        out = {
            "interaction_type": "map_query",
            "speech": "你想去哪儿？可以说「海螺湾」「飞越极限」「方特城堡」之类的地点名。",
            "motion_type": "sequential",
            "actions": [],
            "emotion": "neutral",
            "motion_description": None,
        }
        _record_board_drive_if_bridge(request, out, perception_dump)
        return out
    result = MapGuide().answer(text)
    _record_board_drive_if_bridge(request, result, perception_dump)
    return result


@app.post("/api/process")
def process_full(body: PerceptionIn, request: Request):
    """
    完整玩法状态机：新游客 → mode_select → 等你说「随机互动」/「剧情互动」→ 对应分支。
    等待用户说话时可能返回 JSON null（前端 handleBearAgentPayload 已处理）。

    board_bridge 请求（X-Agent-Caller: board-bridge）在启用闸门时串行：
    上一轮若需要前端配音，会阻塞直至 POST /api/multimodal/playback-done。
    """
    _raise_if_safety_locked(request)
    agent: BearAgent = request.app.state.bear_agent
    perception_dump = perception_dump_for_agent(body)
    gate = getattr(request.app.state, "multimodal_gate", None)
    held = False
    if gate_enabled() and gate is not None and is_board_bridge_request(request.headers):
        gate.board_bridge_acquire()
        held = True
    try:
        _raise_if_safety_locked(request)
        result = agent.process(perception_dump)
        _record_board_drive_if_bridge(request, result, perception_dump)
    except Exception:
        if held and gate is not None:
            gate.force_idle()
        raise
    if held and gate is not None:
        if _safety(request).tick().locked:
            gate.force_idle()
        else:
            gate.release_after_inference(result)
    return result


@app.post("/api/reset")
def reset_memory(request: Request):
    """清空记忆并重置玩法状态机（联调时重新开始一轮）。"""
    agent: BearAgent = request.app.state.bear_agent
    agent.reset()
    gate = getattr(request.app.state, "multimodal_gate", None)
    if gate is not None:
        gate.force_idle()
    reset_board_state(request.app.state)
    return {"ok": True}


def main():
    settings = load_server_settings()
    import uvicorn

    uvicorn.run(app, host=settings.host, port=settings.port, reload=False)


if __name__ == "__main__":
    main()
