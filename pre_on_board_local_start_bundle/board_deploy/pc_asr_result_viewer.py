from __future__ import annotations

import argparse
import base64
import json
import os
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from stream_protocol import recv_json

DEFAULT_CJK_FONT = Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc")
ROOT = Path(__file__).resolve().parents[1]

_FONT_CACHE: dict[int, ImageFont.FreeTypeFont | ImageFont.ImageFont] = {}
ASR_SRC = ROOT / "sound_to_text" / "voice_asr" / "src"
if str(ASR_SRC) not in sys.path:
    sys.path.insert(0, str(ASR_SRC))

from text_postprocess import normalize_asr_text  # noqa: E402

OFFLINE_MODEL_DIR = (
    ROOT
    / "sound_to_text"
    / "voice_asr"
    / ".cache"
    / "modelscope"
    / "models"
    / "iic"
    / "speech_seaco_paraformer_large_asr_nat-zh-cn-16k-common-vocab8404-pytorch"
)
# 本地目录不完整时用 Hub ID，由 FunASR/ModelScope 下载到默认缓存（避免指向无效路径触发 WinError 183）
OFFLINE_MODEL_HUB_ID = "iic/speech_seaco_paraformer_large_asr_nat-zh-cn-16k-common-vocab8404-pytorch"

BOARD_HOST_DEFAULT = "192.168.137.100"
BOARD_USER = "root"
BOARD_PASS = "Mind@123"


def resolve_pc_offline_model() -> tuple[str, bool]:
    """返回 (AutoModel 的 model 参数, disable_update)。目录就绪则离线目录 + 禁止更新。"""
    d = OFFLINE_MODEL_DIR
    if not d.is_dir():
        return OFFLINE_MODEL_HUB_ID, False
    markers = [
        d / "config.yaml",
        d / "configuration.json",
        d / "model.pt",
        d / "tokens.txt",
    ]
    if any(p.is_file() for p in markers) or bool(list(d.glob("*.bin"))) or bool(list(d.glob("*.onnx"))):
        return str(d.resolve()), True
    return OFFLINE_MODEL_HUB_ID, False


NOISE_SHORT_TOKENS = {
    "",
    "嗯",
    "啊",
    "呃",
    "哦",
    "唉",
    "欸",
    "哎",
    "诶",
    "一",
    "的",
    "了",
    "呢",
    "吧",
}


def smooth_segment_summaries(history: list[dict], hold_seconds: float = 1.2) -> dict:
    now = time.time()
    recent = [
        item
        for item in history
        if isinstance(item, dict) and now - float(item.get("timestamp", 0.0) or 0.0) <= hold_seconds
    ]
    if not recent:
        return {}
    latest = max(recent, key=lambda item: float(item.get("timestamp", 0.0) or 0.0))
    face_count = max(int(item.get("face_count", 0) or 0) for item in recent)
    hand_count = max(int(item.get("hand_count", 0) or 0) for item in recent)
    person_count = max(int(item.get("person_count", 0) or 0) for item in recent)
    emotion_scores: dict[str, float] = {}
    gesture_scores: dict[str, float] = {}
    action_scores: dict[str, float] = {}
    faces_by_id: dict[int, dict] = {}
    hands_by_id: dict[int, dict] = {}

    for item in recent:
        top_emotion = item.get("top_emotion", {})
        if isinstance(top_emotion, dict):
            label = str(top_emotion.get("label", "") or "").strip()
            conf = float(top_emotion.get("confidence", 0.0) or 0.0)
            if label:
                emotion_scores[label] = emotion_scores.get(label, 0.0) + max(conf, 0.01)
        top_gesture = item.get("top_gesture", {})
        if isinstance(top_gesture, dict):
            label = str(top_gesture.get("label", "") or "").strip()
            conf = float(top_gesture.get("confidence", 0.0) or 0.0)
            if label:
                gesture_scores[label] = gesture_scores.get(label, 0.0) + max(conf, 0.01)
        action = item.get("action", {})
        if isinstance(action, dict):
            label = str(action.get("label", "") or "").strip()
            conf = float(action.get("confidence", 0.0) or 0.0)
            if label:
                action_scores[label] = action_scores.get(label, 0.0) + max(conf, 0.01)
        for face in item.get("faces", []) if isinstance(item.get("faces", []), list) else []:
            if not isinstance(face, dict):
                continue
            track_id = int(face.get("id", -1))
            if track_id < 0:
                continue
            current = faces_by_id.get(track_id)
            if current is None or float(face.get("confidence", 0.0) or 0.0) >= float(
                current.get("confidence", 0.0) or 0.0
            ):
                faces_by_id[track_id] = {
                    "id": track_id,
                    "emotion": str(face.get("emotion", "") or ""),
                    "confidence": float(face.get("confidence", 0.0) or 0.0),
                }
        for hand in item.get("hands", []) if isinstance(item.get("hands", []), list) else []:
            if not isinstance(hand, dict):
                continue
            track_id = int(hand.get("id", -1))
            if track_id < 0:
                continue
            current = hands_by_id.get(track_id)
            if current is None or float(hand.get("confidence", 0.0) or 0.0) >= float(
                current.get("confidence", 0.0) or 0.0
            ):
                hands_by_id[track_id] = {
                    "id": track_id,
                    "gesture": str(hand.get("gesture", "") or ""),
                    "confidence": float(hand.get("confidence", 0.0) or 0.0),
                }

    def top_label(score_map: dict[str, float]) -> dict:
        if not score_map:
            return {"label": "", "confidence": 0.0}
        label, conf = max(score_map.items(), key=lambda kv: kv[1])
        return {"label": label, "confidence": float(conf)}

    return {
        "face_count": face_count,
        "hand_count": hand_count,
        "person_count": person_count,
        "top_emotion": top_label(emotion_scores),
        "top_gesture": top_label(gesture_scores),
        "faces": list(faces_by_id.values()),
        "hands": list(hands_by_id.values()),
        "action": top_label(action_scores),
        "timestamp": float(latest.get("timestamp", time.time()) or time.time()),
    }


def summarize_debug_message(msg: dict) -> dict:
    summary = dict(msg)
    audio_b64 = summary.get("audio_pcm16_b64")
    if isinstance(audio_b64, str):
        summary["audio_pcm16_b64"] = f"<base64:{len(audio_b64)} chars>"
    board_summary = summary.get("board_summary_window")
    if isinstance(board_summary, dict):
        compact = dict(board_summary)
        for key in ("faces", "hands"):
            value = compact.get(key)
            if isinstance(value, list) and len(value) > 4:
                compact[key] = value[:4] + ["..."]
        summary["board_summary_window"] = compact
    return summary


def _cjk_font_candidate_paths() -> list[Path]:
    paths: list[Path] = [DEFAULT_CJK_FONT]
    if sys.platform == "win32":
        fonts = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
        paths.extend(
            fonts / name
            for name in (
                "msyh.ttc",
                "msyhbd.ttc",
                "simhei.ttf",
                "simsun.ttc",
                "simsunb.ttf",
                "msjh.ttc",
                "malgun.ttf",
            )
        )
    return paths


def choose_font(font_size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    cached = _FONT_CACHE.get(font_size)
    if cached is not None:
        return cached
    for path in _cjk_font_candidate_paths():
        if not path.is_file():
            continue
        try:
            if path.suffix.lower() == ".ttc":
                font = ImageFont.truetype(str(path), font_size, index=0)
            else:
                font = ImageFont.truetype(str(path), font_size)
            _FONT_CACHE[font_size] = font
            return font
        except OSError:
            continue
    fallback = ImageFont.load_default()
    _FONT_CACHE[font_size] = fallback
    return fallback


def render_asr_panel(partial: str, final: str, normalized: str, summary: dict | None = None) -> np.ndarray:
    canvas = np.zeros((470, 1280, 3), dtype=np.uint8)
    pil_image = Image.fromarray(cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(pil_image)
    title_font = choose_font(28)
    body_font = choose_font(28)

    draw.rectangle((0, 0, 1279, 469), fill=(8, 8, 8))
    draw.text((24, 16), "板端 ASR 实时字幕", font=title_font, fill=(255, 255, 255))
    draw.text((24, 72), f"实时: {partial or '(空)'}", font=body_font, fill=(255, 220, 120))
    draw.text((24, 138), f"整句: {final or '(空)'}", font=body_font, fill=(180, 255, 180))
    draw.text((24, 204), f"归一化: {normalized or '(空)'}", font=body_font, fill=(180, 220, 255))
    summary = summary or {}
    faces = summary.get("faces", []) if isinstance(summary, dict) else []
    hands = summary.get("hands", []) if isinstance(summary, dict) else []
    action = summary.get("action", {}) if isinstance(summary, dict) else {}
    top_emotion = summary.get("top_emotion", {}) if isinstance(summary, dict) else {}
    top_gesture = summary.get("top_gesture", {}) if isinstance(summary, dict) else {}
    face_desc = ", ".join(
        f"#{item.get('id')}:{item.get('emotion') or '-'}"
        for item in faces[:4]
        if isinstance(item, dict)
    ) or "(空)"
    hand_desc = ", ".join(
        f"#{item.get('id')}:{item.get('gesture') or '-'}"
        for item in hands[:4]
        if isinstance(item, dict)
    ) or "(空)"
    action_desc = "(空)"
    if isinstance(action, dict):
        label = str(action.get("label", "") or "")
        conf = float(action.get("confidence", 0.0) or 0.0)
        if label:
            action_desc = f"{label} {conf * 100:.0f}%"
    top_emotion_desc = "(空)"
    if isinstance(top_emotion, dict):
        label = str(top_emotion.get("label", "") or "")
        conf = float(top_emotion.get("confidence", 0.0) or 0.0)
        if label:
            top_emotion_desc = f"{label} {conf:.2f}"
    top_gesture_desc = "(空)"
    if isinstance(top_gesture, dict):
        label = str(top_gesture.get("label", "") or "")
        conf = float(top_gesture.get("confidence", 0.0) or 0.0)
        if label:
            top_gesture_desc = f"{label} {conf:.2f}"
    face_count = int(summary.get("face_count", 0) or 0) if isinstance(summary, dict) else 0
    hand_count = int(summary.get("hand_count", 0) or 0) if isinstance(summary, dict) else 0
    person_count = int(summary.get("person_count", 0) or 0) if isinstance(summary, dict) else 0
    draw.text((24, 270), f"脸数量: {face_count} | 手数量: {hand_count} | 人数量: {person_count}", font=body_font, fill=(255, 255, 180))
    draw.text((24, 318), f"表情: {top_emotion_desc} | 明细: {face_desc}", font=body_font, fill=(255, 200, 200))
    draw.text((24, 366), f"手势/动作: {top_gesture_desc} | {action_desc}", font=body_font, fill=(200, 255, 200))
    npu = summary.get("_board_npu", {}) if isinstance(summary, dict) else {}
    npu_text = "(空)"
    if isinstance(npu, dict) and npu:
        parts = []
        if "name" in npu:
            parts.append(f"NPU:{npu.get('name')}")
        if "aicore" in npu:
            parts.append(f"AICore:{npu.get('aicore')}%")
        if "memory_used" in npu and "memory_total" in npu:
            parts.append(f"Mem:{npu.get('memory_used')}/{npu.get('memory_total')}MB")
        if "temp" in npu:
            parts.append(f"Temp:{npu.get('temp')}C")
        if "power" in npu:
            parts.append(f"Power:{npu.get('power')}W")
        npu_text = " | ".join(parts) if parts else "(空)"
    draw.text((24, 414), f"板端NPU: {npu_text}", font=body_font, fill=(180, 255, 255))
    return cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)


def run_pc_offline_enhance(
    model_holder: dict[str, object],
    audio_pcm16_b64: str,
    sample_rate: int,
) -> tuple[str, str]:
    if not audio_pcm16_b64:
        return "", ""
    raw = base64.b64decode(audio_pcm16_b64.encode("ascii"))
    audio = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32767.0
    if audio.size == 0:
        return "", ""
    try:
        from funasr import AutoModel  # type: ignore
        from qwen_client import parse_with_qwen  # type: ignore
    except ImportError as exc:
        if not model_holder.get("_offline_import_warned"):
            print(f"[ASR-VIEWER] offline enhance skipped (optional deps missing): {exc}", flush=True)
            model_holder["_offline_import_warned"] = True
        return "", ""
    model = model_holder.get("model")
    if model is None:
        spec, disable_update = resolve_pc_offline_model()
        try:
            model = AutoModel(model=spec, device="cpu", disable_update=disable_update)
            model_holder["model"] = model
            print(f"[ASR-VIEWER] AutoModel loaded: {spec!r} disable_update={disable_update}", flush=True)
        except Exception as exc:
            print(f"[ASR-VIEWER] AutoModel load failed, skip offline enhance: {exc}", flush=True)
            return "", ""
    try:
        result = model.generate(input=audio.reshape(-1), batch_size_s=0)
    except Exception as exc:
        print(f"[ASR-VIEWER] offline generate failed: {exc}", flush=True)
        return "", ""
    if isinstance(result, list):
        text = "".join(str(item.get("text", "")).strip() for item in result if isinstance(item, dict))
    elif isinstance(result, dict):
        text = str(result.get("text", "")).strip()
    else:
        text = str(result).strip()
    normalized = normalize_asr_text(text)
    _ = parse_with_qwen(normalized)
    return text, normalized


def should_run_offline_enhance(raw_text: str, normalized_text: str) -> bool:
    candidate = (normalized_text or raw_text or "").strip()
    compact = candidate.replace(" ", "")
    if compact in NOISE_SHORT_TOKENS:
        return False
    if len(compact) <= 1:
        return False
    unique_chars = set(compact)
    if len(compact) <= 3 and len(unique_chars) == 1:
        return False
    alpha_num_count = sum(ch.isalnum() or ("\u4e00" <= ch <= "\u9fff") for ch in compact)
    if alpha_num_count < 2:
        return False
    return True


def fetch_board_npu_summary(host: str) -> dict:
    cmd = [
        "sshpass",
        "-p",
        BOARD_PASS,
        "ssh",
        "-o",
        "StrictHostKeyChecking=no",
        f"{BOARD_USER}@{host}",
        "npu-smi info",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=5.0)
    if result.returncode != 0:
        return {}
    lines = [line.rstrip() for line in result.stdout.splitlines()]
    name = ""
    power = ""
    temp = ""
    aicore = ""
    mem_used = ""
    mem_total = ""
    for idx, line in enumerate(lines):
        if "|" not in line:
            continue
        cols = [c.strip() for c in line.split("|")[1:-1]]
        if len(cols) >= 3 and cols[0].startswith("0") and "310B" in cols[0]:
            left_parts = cols[0].split()
            if len(left_parts) >= 2:
                name = left_parts[1]
            right_parts = cols[2].split()
            if len(right_parts) >= 2:
                power = right_parts[0]
                temp = right_parts[1]
            if idx + 1 < len(lines) and "|" in lines[idx + 1]:
                cols2 = [c.strip() for c in lines[idx + 1].split("|")[1:-1]]
                if len(cols2) >= 3:
                    right2 = cols2[2].split()
                    if len(right2) >= 3:
                        aicore = right2[0]
                        mem_used = right2[1]
                        mem_total = right2[3] if len(right2) >= 4 else ""
            break
    if not any([name, power, temp, aicore, mem_used, mem_total]):
        return {}
    return {
        "name": name,
        "power": power,
        "temp": temp,
        "aicore": aicore,
        "memory_used": mem_used,
        "memory_total": mem_total,
    }


def npu_monitor_loop(host: str, summary_ref: dict[str, dict], stop_event: threading.Event) -> None:
    while not stop_event.is_set():
        try:
            summary_ref["npu"] = fetch_board_npu_summary(host)
        except Exception:
            summary_ref["npu"] = {}
        stop_event.wait(1.0)


def main() -> None:
    parser = argparse.ArgumentParser(description="PC viewer for board-returned ASR results.")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=18083)
    parser.add_argument(
        "--board-host",
        default=BOARD_HOST_DEFAULT,
        help="板卡 IP（用于 sshpass 拉取 npu-smi；应与 run_all --host 一致）。",
    )
    parser.add_argument(
        "--debug-json",
        action="store_true",
        help="每条 18083 JSON 打印一行 [18083-JSON]（base64 音频字段会缩写）。",
    )
    parser.add_argument(
        "--no-offline-asr",
        action="store_true",
        help="禁用本机 FunASR 整句离线推理（segment_packet / asr_final 携带音频时默认会推理）。",
    )
    parser.add_argument(
        "--offline-asr-noise-filter",
        action="store_true",
        help="仅当板端文本通过噪声启发式时才跑离线 ASR（默认关闭，尽量每条整句都推理）。",
    )
    args = parser.parse_args()

    offline_asr = not args.no_offline_asr
    if offline_asr:
        spec, dis = resolve_pc_offline_model()
        print(
            f"[ASR-VIEWER] PC 整句离线推理: model={spec!r} disable_update={dis} "
            f"(本地目录完整则用目录，否则从 Hub 拉取)",
            flush=True,
        )

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((args.host, args.port))
    server.listen(1)
    print(f"[ASR-VIEWER] listening on {args.host}:{args.port}", flush=True)
    latest_partial = ""
    latest_final = ""
    latest_normalized = ""
    latest_summary: dict = {}
    segment_summary_history: list[dict] = []
    offline_model_holder: dict[str, object] = {}
    monitor_ref: dict[str, dict] = {"npu": {}}
    stop_event = threading.Event()
    monitor_thread = threading.Thread(
        target=npu_monitor_loop,
        args=(args.board_host, monitor_ref, stop_event),
        daemon=True,
    )
    monitor_thread.start()

    def merge_render_summary() -> dict:
        out = dict(latest_summary)
        out["_board_npu"] = dict(monitor_ref.get("npu", {}))
        return out

    try:
        while True:
            panel = render_asr_panel(latest_partial, latest_final, latest_normalized, merge_render_summary())
            cv2.imshow("board_asr_result_viewer", panel)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
            server.settimeout(0.05)
            try:
                conn, addr = server.accept()
            except socket.timeout:
                continue
            finally:
                server.settimeout(None)
            print(f"[ASR-VIEWER] connected from {addr}", flush=True)
            try:
                hello = recv_json(conn)
                print(f"[ASR-VIEWER] hello={hello}", flush=True)
                while True:
                    msg = recv_json(conn)
                    if not msg:
                        break
                    if args.debug_json:
                        print(
                            f"[18083-JSON] {json.dumps(summarize_debug_message(msg), ensure_ascii=False)}",
                            flush=True,
                        )
                    msg_type = str(msg.get("type", "")).strip()
                    if msg_type == "asr_partial":
                        latest_partial = str(msg.get("text", ""))
                        print(f"[ASR-Partial] {latest_partial}", flush=True)
                    elif msg_type == "segment_packet":
                        latest_partial = ""
                        board_partial = str(msg.get("board_partial_text", "") or "")
                        latest_final = board_partial
                        latest_normalized = normalize_asr_text(board_partial)
                        maybe_summary = msg.get("board_summary_window", {})
                        if isinstance(maybe_summary, dict) and maybe_summary:
                            segment_summary_history.append(dict(maybe_summary))
                            if len(segment_summary_history) > 16:
                                segment_summary_history = segment_summary_history[-16:]
                            latest_summary = smooth_segment_summaries(segment_summary_history)
                        audio_b64 = str(msg.get("audio_pcm16_b64", "")).strip()
                        run_offline = offline_asr and bool(audio_b64) and (
                            not args.offline_asr_noise_filter
                            or should_run_offline_enhance(latest_final, latest_normalized)
                        )
                        if run_offline:
                            try:
                                enhanced_final, enhanced_norm = run_pc_offline_enhance(
                                    offline_model_holder,
                                    audio_b64,
                                    int(msg.get("sample_rate", 16000)),
                                )
                                if enhanced_final:
                                    latest_final = enhanced_final
                                    latest_normalized = enhanced_norm
                            except Exception as exc:
                                print(f"[ASR-VIEWER] offline enhance error (keeping stream text): {exc}", flush=True)
                        print(f"[ASR-Final] {latest_final}", flush=True)
                        print(f"[Normalized] {latest_normalized}", flush=True)
                    elif msg_type == "state_packet":
                        maybe_summary = msg.get("summary", {})
                        if isinstance(maybe_summary, dict):
                            latest_summary = maybe_summary
                        latest_partial = str(msg.get("partial_text", latest_partial) or latest_partial)
                    elif msg_type == "asr_final":
                        latest_final = str(msg.get("raw_text", ""))
                        latest_normalized = str(msg.get("normalized_text", ""))
                        latest_summary = (
                            msg.get("summary", latest_summary)
                            if isinstance(msg.get("summary", latest_summary), dict)
                            else latest_summary
                        )
                        segment_id = int(msg.get("segment_id", 0))
                        audio_b64 = str(msg.get("audio_pcm16_b64", "")).strip()
                        run_offline = offline_asr and bool(audio_b64) and (
                            not args.offline_asr_noise_filter
                            or should_run_offline_enhance(latest_final, latest_normalized)
                        )
                        if run_offline:
                            try:
                                enhanced_final, enhanced_norm = run_pc_offline_enhance(
                                    offline_model_holder,
                                    audio_b64,
                                    int(msg.get("sample_rate", 16000)),
                                )
                                if enhanced_final:
                                    latest_final = enhanced_final
                                    latest_normalized = enhanced_norm
                            except Exception as exc:
                                print(f"[ASR-VIEWER] offline enhance error (keeping stream text): {exc}", flush=True)
                        latest_partial = ""
                        _ = segment_id
                        print(f"[ASR-Final] {latest_final}", flush=True)
                        print(f"[Normalized] {latest_normalized}", flush=True)
                        action = msg.get("action", {})
                        print(f"[Action JSON] {action}", flush=True)
                    elif msg_type == "asr_summary":
                        maybe_summary = msg.get("summary", {})
                        if isinstance(maybe_summary, dict):
                            latest_summary = maybe_summary
                    else:
                        print(f"[ASR-VIEWER] msg={msg}", flush=True)
                    panel = render_asr_panel(
                        latest_partial,
                        latest_final,
                        latest_normalized,
                        merge_render_summary(),
                    )
                    cv2.imshow("board_asr_result_viewer", panel)
                    if cv2.waitKey(1) & 0xFF == ord("q"):
                        return
            except Exception as exc:
                print(f"[ASR-VIEWER] connection dropped: {exc}", flush=True)
            finally:
                try:
                    conn.close()
                except Exception:
                    pass
    finally:
        stop_event.set()
        server.close()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
