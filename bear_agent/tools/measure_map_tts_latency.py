#!/usr/bin/env python3
"""
测量地图查询链路的分段延时。

默认 watch `pc_received_output/perception_preview.json` 的下一次变化：
1. 读 JSON / 组装 perception
2. Bear Agent 地图查询
3. TTS 请求与音频字节返回

也支持 `--once` 直接测当前快照。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
import wave
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from board_bridge.json_io import read_json_file
from board_bridge.perception_merge import build_perception
from map_guide import MapGuide


DEFAULT_PREVIEW = ROOT / "pc_received_output" / "perception_preview.json"
DEFAULT_ASR = ROOT / "pc_received_output" / "asr" / "latest_asr.json"
DEFAULT_VISION = ROOT / "pc_received_output" / "vision" / "latest_vision.json"


def ms(sec: float) -> float:
    return sec * 1000.0


def now_ms() -> float:
    return time.perf_counter() * 1000.0


def load_snapshot(preview_path: Path, asr_path: Path, vision_path: Path) -> dict[str, Any]:
    t0 = now_ms()
    preview_doc = read_json_file(preview_path)
    asr_doc = read_json_file(asr_path)
    vision_doc = read_json_file(vision_path)
    t1 = now_ms()

    perception = preview_doc.get("perception") if isinstance(preview_doc.get("perception"), dict) else None
    if not isinstance(perception, dict):
        perception = build_perception(vision_doc, asr_doc)

    speech_text = str(perception.get("speech_text") or "").strip()
    if not speech_text:
        bridge_trigger = preview_doc.get("bridge_trigger")
        if isinstance(bridge_trigger, dict):
            speech_text = str(bridge_trigger.get("speech_now") or "").strip()
    if not speech_text:
        speech_text = str(asr_doc.get("normalized") or asr_doc.get("final") or "").strip()

    return {
        "read_ms": t1 - t0,
        "preview_doc": preview_doc,
        "asr_doc": asr_doc,
        "vision_doc": vision_doc,
        "perception": perception,
        "speech_text": speech_text,
    }


def build_perception_from_text(text: str) -> dict[str, Any]:
    return {
        "emotion": "neutral",
        "emotion_confidence": 0.85,
        "gesture": "none",
        "gesture_confidence": 0.0,
        "hand_gesture": "none",
        "hand_gesture_confidence": 0.0,
        "person_detected": True,
        "person_count": 1,
        "speech_text": text.strip(),
    }


def file_age_ms(doc: dict[str, Any], path: Path) -> float | None:
    ts = file_epoch(doc, path)
    if ts is None:
        return None
    return ms(time.time() - ts)


def file_epoch(doc: dict[str, Any], path: Path) -> float | None:
    ts = doc.get("ts")
    try:
        if isinstance(ts, (int, float)) and ts > 0:
            return float(ts)
    except (TypeError, ValueError):
        pass
    try:
        return path.stat().st_mtime
    except OSError:
        return None


def post_json(url: str, body: dict[str, Any], timeout: float) -> dict[str, Any]:
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8")
    if not raw.strip():
        return {}
    out = json.loads(raw)
    return out if isinstance(out, dict) else {}


def post_tts(url: str, text: str, timeout: float, device: str | None = None) -> bytes:
    body: dict[str, Any] = {"text": text}
    if device:
        body["device"] = device
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def snapshot_speech_and_sig(doc: dict[str, Any]) -> tuple[str, tuple[Any, str]]:
    sig = (
        doc.get("ts"),
        json.dumps(doc.get("bridge_trigger", {}), ensure_ascii=False, sort_keys=True)
        if isinstance(doc.get("bridge_trigger"), dict)
        else "",
    )
    speech = ""
    perception = doc.get("perception")
    if isinstance(perception, dict):
        speech = str(perception.get("speech_text") or "").strip()
    if not speech:
        bt = doc.get("bridge_trigger")
        if isinstance(bt, dict):
            speech = str(bt.get("speech_now") or "").strip()
    return speech, sig


def wav_duration_ms(wav: bytes) -> float | None:
    import io

    try:
        with wave.open(io.BytesIO(wav), "rb") as w:
            rate = w.getframerate()
            if rate <= 0:
                return None
            return (w.getnframes() / rate) * 1000.0
    except Exception:
        return None


def wait_for_snapshot_change(
    preview_path: Path,
    poll_sec: float,
    timeout_sec: float | None,
    *,
    last_sig: tuple[Any, str] | None = None,
    last_speech: str = "",
) -> tuple[str, tuple[Any, str]]:
    deadline = time.time() + timeout_sec if timeout_sec and timeout_sec > 0 else None
    while True:
        doc = read_json_file(preview_path)
        speech, sig = snapshot_speech_and_sig(doc)

        if last_sig is None:
            last_sig = sig
        elif sig != last_sig and speech and speech != last_speech:
            return speech, sig

        if deadline is not None and time.time() >= deadline:
            raise TimeoutError(f"等待 perception_preview.json 更新超时：{preview_path}")
        time.sleep(poll_sec)


def measure_once(args: argparse.Namespace) -> None:
    t_all0 = now_ms()
    snap = None
    if args.text is not None:
        preview_doc: dict[str, Any] = {}
        asr_doc: dict[str, Any] = {}
        vision_doc: dict[str, Any] = {}
        perception = build_perception_from_text(args.text)
        speech_text = args.text.strip()
        read_ms = 0.0
    else:
        snap = load_snapshot(args.preview_path, args.asr_path, args.vision_path)
        preview_doc = snap["preview_doc"]
        asr_doc = snap["asr_doc"]
        vision_doc = snap["vision_doc"]
        perception = snap["perception"]
        speech_text = snap["speech_text"]
        read_ms = float(snap["read_ms"])
    t_all1 = now_ms()

    if not speech_text:
        raise SystemExit("没有可用于地图查询的 speech_text。请先让最新 ASR/preview 里出现一条有效地点询问。")

    preview_age = file_age_ms(preview_doc, args.preview_path) if snap is not None else None
    asr_age = file_age_ms(asr_doc, args.asr_path) if snap is not None else None
    vision_age = file_age_ms(vision_doc, args.vision_path) if snap is not None else None

    agent0 = now_ms()
    if args.route == "map-query":
        if args.map_mode == "http":
            agent_out = post_json(args.map_url, perception, timeout=args.map_timeout)
        else:
            agent_out = MapGuide().answer(speech_text)
    else:
        agent_out = post_json(args.process_url, perception, timeout=args.map_timeout)
    agent1 = now_ms()

    speech_out = str(agent_out.get("speech") or "").strip()
    if not speech_out:
        raise SystemExit(f"{args.route} 没有返回 speech，无法继续测 TTS。")

    tts0 = now_ms()
    wav = post_tts(args.tts_url, speech_out, timeout=args.tts_timeout, device=args.tts_device)
    tts1 = now_ms()
    done_wall = time.time()
    audio_ms = wav_duration_ms(wav)

    if args.save_wav:
        args.save_wav.parent.mkdir(parents=True, exist_ok=True)
        args.save_wav.write_bytes(wav)

    result: dict[str, Any] = {
        "ts": time.time(),
        "preview": str(args.preview_path),
        "speech": speech_text,
        "input_mode": "text" if args.text is not None else "preview",
        "route": args.route,
        "map_mode": args.map_mode,
        "interaction_type": str(agent_out.get("interaction_type") or ""),
        "map_speech": speech_out,
        "agent_speech": speech_out,
        "tts_bytes": len(wav),
        "read_json_ms": round(float(read_ms), 1),
        "build_total_ms": round(float(t_all1 - t_all0), 1),
        "map_query_ms": round(float(agent1 - agent0), 1),
        "agent_query_ms": round(float(agent1 - agent0), 1),
        "tts_request_ms": round(float(tts1 - tts0), 1),
        "total_ms": round(float(tts1 - t_all0), 1),
    }
    if audio_ms is not None:
        result["tts_audio_duration_ms"] = round(float(audio_ms), 1)
    if preview_age is not None:
        result["preview_age_ms"] = round(float(preview_age), 1)
    if asr_age is not None:
        result["asr_age_ms"] = round(float(asr_age), 1)
    if vision_age is not None:
        result["vision_age_ms"] = round(float(vision_age), 1)
    if snap is not None:
        asr_epoch = file_epoch(asr_doc, args.asr_path)
        preview_epoch = file_epoch(preview_doc, args.preview_path)
        if asr_epoch is not None:
            result["asr_json_to_tts_done_ms"] = round(ms(done_wall - asr_epoch), 1)
        if preview_epoch is not None:
            result["preview_json_to_tts_done_ms"] = round(ms(done_wall - preview_epoch), 1)
    if args.save_wav:
        result["wav_saved_to"] = str(args.save_wav)

    print("=== map_tts_latency ===")
    for key in (
        "preview",
        "speech",
        "input_mode",
        "route",
        "preview_age_ms",
        "asr_age_ms",
        "vision_age_ms",
        "asr_json_to_tts_done_ms",
        "preview_json_to_tts_done_ms",
        "read_json_ms",
        "build_total_ms",
        "map_mode",
        "map_query_ms",
        "agent_query_ms",
        "interaction_type",
        "map_speech",
        "agent_speech",
        "tts_request_ms",
        "tts_audio_duration_ms",
        "tts_bytes",
        "wav_saved_to",
        "total_ms",
    ):
        if key in result:
            print(f"{key}: {result[key]}")

    if args.log_file:
        args.log_file.parent.mkdir(parents=True, exist_ok=True)
        with open(args.log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(result, ensure_ascii=False, sort_keys=True) + "\n")
        print(f"log_file: {args.log_file}")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Measure map / random interaction + TTS latency from preview JSON or typed text.")
    p.add_argument("--preview-path", type=Path, default=DEFAULT_PREVIEW)
    p.add_argument("--asr-path", type=Path, default=DEFAULT_ASR)
    p.add_argument("--vision-path", type=Path, default=DEFAULT_VISION)
    p.add_argument("--route", choices=("map-query", "process"), default="map-query")
    p.add_argument("--map-mode", choices=("http", "local"), default="http")
    p.add_argument("--map-url", default="http://127.0.0.1:8765/api/map-query")
    p.add_argument("--process-url", default="http://127.0.0.1:8765/api/process")
    p.add_argument("--map-timeout", type=float, default=120.0)
    p.add_argument("--tts-url", default="http://127.0.0.1:9888/api/tts")
    p.add_argument("--tts-timeout", type=float, default=180.0)
    p.add_argument("--tts-device", default=(os.environ.get("XIONGDA_TTS_DEVICE") or "").strip() or None)
    p.add_argument("--save-wav", type=Path, default=None)
    p.add_argument("--text", type=str, default=None, help="Direct typed text input; bypass preview/asr/vision snapshot.")
    p.add_argument(
        "--log-file",
        type=Path,
        default=ROOT / "logs" / "map_tts_latency.jsonl",
        help="Append one JSON result per measurement. Use empty string to disable.",
    )
    p.add_argument("--once", action="store_true", help="Measure current snapshot immediately.")
    p.add_argument("--watch", action="store_true", help="Wait for the next preview JSON change, then measure.")
    p.add_argument("--continuous", action="store_true", help="Keep watching and logging until Ctrl+C.")
    p.add_argument("--poll-sec", type=float, default=0.2)
    p.add_argument("--watch-timeout-sec", type=float, default=0.0)
    return p


def main() -> int:
    args = build_parser().parse_args()
    if args.log_file is not None and str(args.log_file).strip() == "":
        args.log_file = None
    if args.continuous:
        args.watch = True
    if args.text is not None:
        args.once = True
        args.watch = False
        args.continuous = False
    if not args.once and not args.watch:
        args.watch = True

    if args.watch:
        print(f"watching: {args.preview_path}")
        last_speech = ""
        _, last_sig = snapshot_speech_and_sig(read_json_file(args.preview_path))
        while True:
            try:
                speech, last_sig = wait_for_snapshot_change(
                    args.preview_path,
                    args.poll_sec,
                    args.watch_timeout_sec or None,
                    last_sig=last_sig,
                    last_speech=last_speech,
                )
                last_speech = speech
            except KeyboardInterrupt:
                print("\n停止记录。")
                return 0
            except TimeoutError as e:
                print(str(e), file=sys.stderr)
                return 2

            try:
                measure_once(args)
            except urllib.error.URLError as e:
                print(f"HTTP 失败: {e}", file=sys.stderr)
                if not args.continuous:
                    return 1
            except Exception as e:
                print(f"测量失败: {e}", file=sys.stderr)
                if not args.continuous:
                    return 1

            if not args.continuous:
                return 0

    try:
        measure_once(args)
    except KeyboardInterrupt:
        print("\n停止记录。")
        return 0
    except urllib.error.URLError as e:
        print(f"HTTP 失败: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"测量失败: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
