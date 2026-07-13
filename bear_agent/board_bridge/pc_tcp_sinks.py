# -*- coding: utf-8 -*-
"""
无界面 TCP 接收：与 pc_result_viewer / pc_asr_result_viewer 相同端口与协议，
将最新状态写入 output_dir（供 agent 桥接轮询）。
"""
from __future__ import annotations

import json
import socket
import threading
import time
from pathlib import Path
from typing import Callable

from .asr_multimodal import smooth_segment_summaries
from .json_io import atomic_write_json
from .perception_merge import merge_vision_sink_summary
from .perception_from_board import vision_meta_to_summary
from .stream_protocol import recv_json, recv_packet


def _strip_summary_speech_fields(summary: dict) -> None:
    for k in ("normalized_text", "speech_text", "text", "utterance", "final_text"):
        if isinstance(summary.get(k), str):
            summary[k] = ""


def _flush_utterance_clear_if_needed(
    st: dict,
    flush_asr_file: Callable[[], None],
    clear_event: threading.Event | None,
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


def _vision_connection_loop(conn: socket.socket, vision_latest: Path, stop_event: threading.Event) -> None:
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
                recv_packet(conn)
            except ConnectionError:
                break
            derived = vision_meta_to_summary(meta)
            board_summary = meta.get("summary") if isinstance(meta.get("summary"), dict) else {}
            # 保留板端 summary（人脸 / 表情 / faces.bbox 等）；手势骨架字段由 meta 叠加补齐。
            # 合并时避免板端空 label 覆盖 gesture_overlays 推导出的标签（见 merge_vision_sink_summary）。
            summary = merge_vision_sink_summary(derived, board_summary)
            atomic_write_json(
                vision_latest,
                {
                    "summary": summary,
                    "raw_meta_keys": sorted(meta.keys()) if isinstance(meta, dict) else [],
                    "ts": time.time(),
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
            _vision_connection_loop(conn, latest, stop_event)
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
                        _flush_utterance_clear_if_needed(st, flush_asr_file, utterance_clear_event)
                        continue
                    except json.JSONDecodeError:
                        break
                    if not msg:
                        break
                    _flush_utterance_clear_if_needed(st, flush_asr_file, utterance_clear_event)
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
