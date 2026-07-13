from __future__ import annotations

import argparse
import os
import socket
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from stream_protocol import recv_json, recv_packet

DEFAULT_CJK_FONT = Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc")
GESTURE_CN_MAP = {
    "call": "打电话",
    "dislike": "踩",
    "fist": "拳头",
    "four": "四",
    "grab": "抓握",
    "grip": "握持",
    "heart": "比心",
    "heart2": "比心2",
    "holy": "圣角",
    "like": "点赞",
    "little": "小拇指",
    "middle": "中指",
    "mute": "静音",
    "OK": "OK",
    "one": "一",
    "palm": "手掌",
    "peace": "剪刀手",
    "peace_inv": "倒剪刀手",
    "point": "指向",
    "rock": "摇滚",
    "stop": "停止",
    "stop_inv": "倒停止",
    "photo": "拍照",
    "three": "三",
    "three2": "三2",
    "three3": "三3",
    "gun": "手枪",
    "thumb_idx": "拇指食指",
    "thumb_idx2": "拇指食指2",
    "timeout": "暂停",
    "two": "二",
    "two_inv": "倒二",
    "xsign": "叉",
}
ACTION_CN_MAP = {
    "clap": "鼓掌",
    "wave": "欢迎挥手",
    "kiss": "飞吻",
    "idle": "待机",
}


def _windows_cjk_font_candidates() -> list[Path]:
    windir = Path(os.environ.get("WINDIR", r"C:\Windows"))
    fonts = windir / "Fonts"
    return [
        fonts / "msyh.ttc",
        fonts / "msyhbd.ttc",
        fonts / "simhei.ttf",
        fonts / "simsun.ttc",
    ]


def choose_font(font_size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for candidate in [DEFAULT_CJK_FONT, *_windows_cjk_font_candidates()]:
        try:
            if candidate.exists():
                return ImageFont.truetype(str(candidate), font_size)
        except Exception:
            continue
    return ImageFont.load_default()


def overlay_gesture_cn(frame: np.ndarray, overlays: list[dict]) -> np.ndarray:
    if not overlays:
        return frame
    pil_image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(pil_image)
    font = choose_font(22)
    for item in overlays:
        en_label = str(item.get("gesture", "")).strip()
        cn_label = GESTURE_CN_MAP.get(en_label, "")
        if not cn_label:
            continue
        bbox = item.get("bbox", [])
        if len(bbox) != 4:
            continue
        x1, y1, x2, y2 = [int(v) for v in bbox]
        confidence = float(item.get("confidence", 0.0))
        text = f"{cn_label} {confidence * 100:.0f}%"
        tb = draw.textbbox((0, 0), text, font=font)
        tw = tb[2] - tb[0]
        th = tb[3] - tb[1]
        box_left = max(0, min(frame.shape[1] - (tw + 8), x1))
        box_top = max(0, min(frame.shape[0] - (th + 8), y2 + 2))
        box_right = box_left + tw + 8
        box_bottom = box_top + th + 8
        draw.rectangle((box_left, box_top, box_right, box_bottom), fill=(255, 180, 0))
        draw.text((box_left + 4, box_top + 2), text, font=font, fill=(255, 255, 255))
    return cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)


def overlay_action_cn(frame: np.ndarray, overlay: dict) -> np.ndarray:
    if not overlay:
        return frame
    action = str(overlay.get("action", "")).strip()
    if not action:
        return frame
    cn_label = ACTION_CN_MAP.get(action, action)
    confidence = float(overlay.get("confidence", 0.0))
    text = f"动作 {cn_label} {confidence * 100:.0f}%"
    pil_image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(pil_image)
    font = choose_font(28)
    tb = draw.textbbox((0, 0), text, font=font)
    tw = tb[2] - tb[0]
    th = tb[3] - tb[1]
    left = 16
    top = 52
    right = left + tw + 12
    bottom = top + th + 12
    draw.rectangle((left, top, right, bottom), fill=(0, 0, 0))
    draw.text((left + 6, top + 2), text, font=font, fill=(255, 255, 255))
    return cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)


def stream_session(conn: socket.socket, addr: tuple[str, int]) -> bool:
    """Return True to quit viewer, False to wait for next board connection."""
    print(f"[RESULT-VIEWER] connected from {addr}", flush=True)
    try:
        hello = recv_json(conn)
        print(f"[RESULT-VIEWER] hello={hello}", flush=True)
        frame_idx = 0
        while True:
            meta = recv_json(conn)
            if not meta:
                print("[RESULT-VIEWER] empty meta, board disconnected", flush=True)
                break
            payload = recv_packet(conn)
            img = cv2.imdecode(np.frombuffer(payload, dtype=np.uint8), cv2.IMREAD_COLOR)
            if img is None:
                continue
            overlays = meta.get("gesture_overlays", []) if isinstance(meta, dict) else []
            action_overlay = meta.get("action_overlay", {}) if isinstance(meta, dict) else {}
            img = overlay_gesture_cn(img, overlays)
            img = overlay_action_cn(img, action_overlay)
            cv2.imshow("board_result_viewer", img)
            frame_idx += 1
            if frame_idx == 1 or frame_idx % 30 == 0:
                det = meta.get("summary", {}).get("det_count") if isinstance(meta, dict) else None
                print(
                    f"[RESULT-VIEWER] frame={frame_idx} ts={meta.get('timestamp', 0):.3f} det={det}",
                    flush=True,
                )
            if cv2.waitKey(1) & 0xFF == ord("q"):
                return True
    except (ConnectionError, OSError) as exc:
        print(f"[RESULT-VIEWER] connection lost: {exc}", flush=True)
    finally:
        try:
            conn.close()
        except OSError:
            pass
    return False


def main() -> None:
    parser = argparse.ArgumentParser(description="PC viewer for board-rendered result stream.")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=18082)
    args = parser.parse_args()

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((args.host, args.port))
    server.listen(5)
    print(f"[RESULT-VIEWER] listening on {args.host}:{args.port} (press q to quit)", flush=True)
    try:
        while True:
            conn, addr = server.accept()
            if stream_session(conn, addr):
                break
            print("[RESULT-VIEWER] waiting for board to reconnect...", flush=True)
    finally:
        server.close()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
