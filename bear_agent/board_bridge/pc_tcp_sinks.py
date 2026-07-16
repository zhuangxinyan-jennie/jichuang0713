# -*- coding: utf-8 -*-
"""
无界面 TCP 接收：与 pc_result_viewer / pc_asr_result_viewer 相同端口与协议，
将最新状态写入 output_dir（供 agent 桥接轮询）。
"""
from __future__ import annotations

import json
import os
import socket
import threading
import time
from pathlib import Path
from typing import Callable

from .asr_multimodal import smooth_segment_summaries
from .json_io import atomic_write_json, atomic_write_json_fast
from .perception_merge import merge_vision_sink_summary
from .perception_from_board import vision_meta_to_summary
from .stream_protocol import recv_json, recv_packet


def _atomic_write_bytes(path: Path, data: bytes, *, fsync: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    try:
        with open(tmp, "wb") as f:
            f.write(data)
            f.flush()
            if fsync:
                os.fsync(f.fileno())
        tmp.replace(path)
    except OSError:
        try:
            if tmp.is_file():
                tmp.unlink()
        except OSError:
            pass


def _strip_summary_speech_fields(summary: dict) -> None:
    for k in ("normalized_text", "speech_text", "text", "utterance", "final_text"):
        if isinstance(summary.get(k), str):
            summary[k] = ""


def _flush_utterance_clear_if_needed(
    st: dict,
    flush_asr_file: Callable[[], None],
    clear_event: threading.Event | None,
    wakeup_event: threading.Event | None,
) -> None:
    if clear_event is None or not clear_event.is_set():
        return
    clear_event.clear()
    st["partial"] = ""
    st["final"] = ""
    st["normalized"] = ""
    summ = st.get("summary")
    if isinstance(summ, dict):
        _strip_summary_speech_fields(summ)
    flush_asr_file()
    if wakeup_event is not None:
        wakeup_event.set()


def _vision_connection_loop(
    conn: socket.socket,
    vision_latest: Path,
    stop_event: threading.Event,
    wakeup_event: threading.Event | None = None,
) -> None:
    landmarks_latest = vision_latest.parent / "latest_hand_landmarks.json"
    preview_jpg = vision_latest.parent / "latest_preview.jpg"
    last_preview_at = 0.0
    last_vision_json_at = 0.0
    preview_interval = 0.20  # 预览约 5fps，避免拖慢关键点落盘
    vision_json_interval = 0.15
    try:
        hello = recv_json(conn)
        atomic_write_json(
            vision_latest.parent / "vision_hello.json",
            {"role": "vision", "hello": hello, "ts": time.time()},
        )
        while not stop_event.is_set():
            meta = recv_json(conn)
            if not meta:
                break
            try:
                jpeg = recv_packet(conn)
            except ConnectionError:
                break
            now = time.time()
            if jpeg and (now - last_preview_at) >= preview_interval:
                _atomic_write_bytes(preview_jpg, jpeg, fsync=False)
                last_preview_at = now
            derived = vision_meta_to_summary(meta)
            board_summary = meta.get("summary") if isinstance(meta.get("summary"), dict) else {}
            # 保留板端 summary（人脸 / 表情 / faces.bbox 等）；手势骨架字段由 meta 叠加补齐。
            # 合并时避免板端空 label 覆盖 gesture_overlays 推导出的标签（见 merge_vision_sink_summary）。
            summary = merge_vision_sink_summary(derived, board_summary)
            if (now - last_vision_json_at) >= vision_json_interval:
                atomic_write_json_fast(
                    vision_latest,
                    {
                        "summary": summary,
                        "raw_meta_keys": sorted(meta.keys()) if isinstance(meta, dict) else [],
                        "ts": now,
                    },
                )
                last_vision_json_at = now
                if wakeup_event is not None:
                    wakeup_event.set()
            # 光标关键点默认只由 UDP 快通道写。慢通道（JPEG）仅在快通道超过 1.2s 无心跳时兜底。
            alive_marker = vision_latest.parent / ".cursor_fast_alive"
            cursor_fast_live = False
            try:
                if alive_marker.is_file() and (time.time() - alive_marker.stat().st_mtime) < 1.2:
                    cursor_fast_live = True
            except OSError:
                cursor_fast_live = False
            if cursor_fast_live:
                pass
            else:
                landmarks = meta.get("hand_landmarks") if isinstance(meta, dict) else None
                lm_meta = meta.get("hand_landmarks_meta") if isinstance(meta, dict) else None
                if not isinstance(lm_meta, dict):
                    lm_meta = {"mirror_frame": True, "source": "board_npu"}
                pts = landmarks if isinstance(landmarks, list) else []
                try:
                    from .landmarks_store import STORE

                    STORE.set(pts, lm_meta, channel="vision_tcp_fallback")
                except Exception:
                    pass
                atomic_write_json_fast(
                    landmarks_latest,
                    {
                        "hand_landmarks": pts,
                        "meta": lm_meta,
                        "ts": now,
                        "channel": "vision_tcp_fallback",
                        "frame": {
                            "width": meta.get("width") if isinstance(meta, dict) else None,
                            "height": meta.get("height") if isinstance(meta, dict) else None,
                        },
                    },
                )
    finally:
        try:
            conn.close()
        except OSError:
            pass


def run_vision_sink(
    output_dir: Path,
    host: str = "0.0.0.0",
    port: int = 18082,
    stop_event: threading.Event | None = None,
    log: Callable[[str], None] | None = None,
    bridge_wakeup_event: threading.Event | None = None,
) -> None:
    stop_event = stop_event or threading.Event()
    log = log or (lambda m: print(m, flush=True))

    out = output_dir / "vision"
    out.mkdir(parents=True, exist_ok=True)
    latest = out / "latest_vision.json"

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((host, port))
    server.listen(4)
    log(f"[board_bridge] vision sink listening {host}:{port} → {latest}")

    while not stop_event.is_set():
        try:
            server.settimeout(0.5)
            try:
                conn, addr = server.accept()
            except socket.timeout:
                continue
            finally:
                server.settimeout(None)
            log(f"[board_bridge] vision connected from {addr}")
            _vision_connection_loop(conn, latest, stop_event, bridge_wakeup_event)
            log("[board_bridge] vision connection closed, waiting for next")
        except OSError as e:
            if stop_event.is_set():
                break
            log(f"[board_bridge] vision sink error: {e}")
            time.sleep(0.2)

    try:
        server.close()
    except OSError:
        pass


def run_asr_sink(
    output_dir: Path,
    host: str = "0.0.0.0",
    port: int = 18083,
    stop_event: threading.Event | None = None,
    log: Callable[[str], None] | None = None,
    utterance_clear_event: threading.Event | None = None,
    bridge_wakeup_event: threading.Event | None = None,
) -> None:
    stop_event = stop_event or threading.Event()
    log = log or (lambda m: print(m, flush=True))

    out = output_dir / "asr"
    out.mkdir(parents=True, exist_ok=True)
    latest = out / "latest_asr.json"

    st: dict = {
        "partial": "",
        "final": "",
        "normalized": "",
        "summary": {},
        "_segment_hist": [],  # segment_packet board_summary_window，供 smooth_segment_summaries
    }

    def flush_asr_file() -> None:
        atomic_write_json(
            latest,
            {
                "partial": st["partial"],
                "final": st["final"],
                "normalized": st["normalized"],
                "summary": st["summary"],
                "ts": time.time(),
            },
        )
        if bridge_wakeup_event is not None:
            bridge_wakeup_event.set()

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((host, port))
    server.listen(4)
    log(f"[board_bridge] ASR sink listening {host}:{port} → {latest}")

    while not stop_event.is_set():
        try:
            server.settimeout(0.5)
            try:
                conn, addr = server.accept()
            except socket.timeout:
                continue
            finally:
                server.settimeout(None)
            log(f"[board_bridge] ASR connected from {addr}")
            try:
                hello = recv_json(conn)
                atomic_write_json(out / "asr_hello.json", {"role": "asr", "hello": hello, "ts": time.time()})
                conn.settimeout(0.35)
                while not stop_event.is_set():
                    try:
                        msg = recv_json(conn)
                    except socket.timeout:
                        _flush_utterance_clear_if_needed(st, flush_asr_file, utterance_clear_event, bridge_wakeup_event)
                        continue
                    except json.JSONDecodeError:
                        break
                    if not msg:
                        break
                    _flush_utterance_clear_if_needed(st, flush_asr_file, utterance_clear_event, bridge_wakeup_event)
                    msg_type = str(msg.get("type", "")).strip()
                    if msg_type == "asr_partial":
                        st["partial"] = str(msg.get("text", ""))
                        flush_asr_file()
                    elif msg_type == "state_packet":
                        # 板端约 1Hz：partial + 当前 summary
                        pt = msg.get("partial_text")
                        if pt is not None:
                            st["partial"] = str(pt)
                        maybe = msg.get("summary", {})
                        if isinstance(maybe, dict):
                            st["summary"] = maybe
                        flush_asr_file()
                    elif msg_type == "segment_packet":
                        # 断句：整句 + 同期视觉 summary（可选二次平滑）
                        st["partial"] = ""
                        board_partial = str(msg.get("board_partial_text", "") or "")
                        st["final"] = board_partial
                        norm = str(msg.get("normalized_text") or "").strip()
                        st["normalized"] = norm or board_partial.strip()
                        maybe_summary = msg.get("board_summary_window", {})
                        if isinstance(maybe_summary, dict) and maybe_summary:
                            hist: list = st["_segment_hist"]
                            hist.append(dict(maybe_summary))
                            if len(hist) > 16:
                                hist[:] = hist[-16:]
                            st["summary"] = smooth_segment_summaries(hist)
                        flush_asr_file()
                    elif msg_type == "asr_final":
                        st["final"] = str(msg.get("raw_text", ""))
                        st["normalized"] = str(msg.get("normalized_text", ""))
                        summ = msg.get("summary", st["summary"])
                        st["summary"] = summ if isinstance(summ, dict) else st["summary"]
                        st["partial"] = ""
                        flush_asr_file()
                    elif msg_type == "asr_summary":
                        maybe = msg.get("summary", {})
                        if isinstance(maybe, dict):
                            st["summary"] = maybe
                        flush_asr_file()
                    else:
                        flush_asr_file()
            except Exception as exc:
                log(f"[board_bridge] ASR connection dropped: {exc}")
            finally:
                try:
                    conn.close()
                except OSError:
                    pass
        except OSError as e:
            if stop_event.is_set():
                break
            log(f"[board_bridge] ASR sink error: {e}")
            time.sleep(0.2)

    try:
        server.close()
    except OSError:
        pass
