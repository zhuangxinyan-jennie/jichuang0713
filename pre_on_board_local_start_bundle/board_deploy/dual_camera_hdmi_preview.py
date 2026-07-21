# -*- coding: utf-8 -*-
"""板端双摄 HDMI 预览：主摄正常，第二路极低画质，自动识别 /dev/video*。"""
from __future__ import annotations

import os
import re
import subprocess
import time

import cv2
import numpy as np


def _run(cmd: list[str]) -> str:
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=8)
        return (p.stdout or "") + (p.stderr or "")
    except Exception as exc:
        return str(exc)


def _list_devices_map() -> dict[str, list[int]]:
    """{'LRCP':[1,2], 'Web Camera':[0,3]}"""
    text = _run(["v4l2-ctl", "--list-devices"])
    mapping: dict[str, list[int]] = {}
    name = None
    for line in text.splitlines():
        if not line.startswith("\t") and line.strip():
            name = line.split("(")[0].strip().rstrip(":")
            mapping.setdefault(name, [])
        elif line.strip().startswith("/dev/video") and name:
            m = re.search(r"/dev/video(\d+)", line)
            if m:
                mapping[name].append(int(m.group(1)))
    return mapping


def _pick_indices() -> tuple[int, int]:
    env_a = os.environ.get("CAM_A")
    env_b = os.environ.get("CAM_B")
    if env_a and env_b:
        return int(env_a), int(env_b)
    mp = _list_devices_map()
    main_idx, second_idx = None, None
    for name, idxs in mp.items():
        low = name.lower()
        if "lrcp" in low or "f1080" in low:
            main_idx = idxs[0] if idxs else main_idx
        if "web camera" in low or "webcamera" in low.replace(" ", ""):
            second_idx = idxs[0] if idxs else second_idx
    # 回退：可打开的前两个
    if main_idx is None or second_idx is None:
        openable = []
        for i in range(0, 10):
            if not os.path.exists(f"/dev/video{i}"):
                continue
            cap = cv2.VideoCapture(i, cv2.CAP_V4L2)
            if cap.isOpened():
                ok, _ = cap.read()
                if ok:
                    openable.append(i)
            cap.release()
        if main_idx is None and openable:
            main_idx = openable[0]
        if second_idx is None:
            for i in openable:
                if i != main_idx:
                    second_idx = i
                    break
    if main_idx is None:
        main_idx = 1
    if second_idx is None:
        second_idx = 0
    return int(main_idx), int(second_idx)


def _force_fmt(dev: int, width: int, height: int) -> None:
    path = f"/dev/video{dev}"
    _run(
        [
            "v4l2-ctl",
            "-d",
            path,
            f"--set-fmt-video=width={width},height={height},pixelformat=MJPG",
        ]
    )


def _open_cam(index: int, width: int, height: int, fps: float | None = None) -> cv2.VideoCapture:
    _force_fmt(index, width, height)
    cap = cv2.VideoCapture(index, cv2.CAP_V4L2)
    if not cap.isOpened():
        cap.release()
        cap = cv2.VideoCapture(f"/dev/video{index}", cv2.CAP_V4L2)
    if not cap.isOpened():
        raise RuntimeError(f"cannot open /dev/video{index}")
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, float(width))
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, float(height))
    if fps:
        try:
            cap.set(cv2.CAP_PROP_FPS, float(fps))
        except Exception:
            pass
    try:
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    except Exception:
        pass
    ok = False
    for _ in range(8):
        ret, fr = cap.read()
        if ret and fr is not None:
            ok = True
            break
        time.sleep(0.05)
    if not ok:
        cap.release()
        raise RuntimeError(f"/dev/video{index} opened but no frame")
    return cap


def _label(frame: np.ndarray, text: str) -> np.ndarray:
    out = frame.copy()
    cv2.rectangle(out, (0, 0), (min(out.shape[1], 600), 34), (0, 0, 0), -1)
    cv2.putText(out, text, (8, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 255), 2, cv2.LINE_AA)
    return out


def _fit(frame: np.ndarray, tw: int, th: int) -> np.ndarray:
    canvas = np.zeros((th, tw, 3), dtype=np.uint8)
    if frame is None or frame.size == 0:
        return canvas
    h, w = frame.shape[:2]
    if h <= 0 or w <= 0:
        return canvas
    scale = min(tw / float(w), th / float(h))
    nw, nh = max(1, int(w * scale)), max(1, int(h * scale))
    resized = cv2.resize(frame, (nw, nh), interpolation=cv2.INTER_AREA)
    x0, y0 = (tw - nw) // 2, (th - nh) // 2
    canvas[y0 : y0 + nh, x0 : x0 + nw] = resized
    return canvas


def _ph(h: int, w: int, text: str) -> np.ndarray:
    img = np.zeros((max(h, 120), max(w, 160), 3), dtype=np.uint8)
    cv2.putText(img, text, (12, img.shape[0] // 2), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
    return img


def main() -> int:
    cam_a, cam_b = _pick_indices()
    wa = int(os.environ.get("DUAL_CAM_A_WIDTH", "320"))
    ha = int(os.environ.get("DUAL_CAM_A_HEIGHT", "240"))
    wb = int(os.environ.get("DUAL_CAM_B_WIDTH", "160"))
    hb = int(os.environ.get("DUAL_CAM_B_HEIGHT", "120"))
    fps_b = float(os.environ.get("DUAL_CAM_B_FPS", "5"))
    every = max(1, int(os.environ.get("DUAL_CAM_B_EVERY", "4")))
    display = os.environ.get("DISPLAY", ":0")
    os.environ["DISPLAY"] = display

    print(f"[dual-cam] map={_list_devices_map()}", flush=True)
    print(
        f"[dual-cam] L=video{cam_a}@{wa}x{ha} R=video{cam_b}@{wb}x{hb}@{fps_b}fps every={every}",
        flush=True,
    )

    # 先只开主摄，再开低画质第二路，降低 USB 争抢
    cap_a = _open_cam(cam_a, wa, ha, fps=12)
    time.sleep(0.4)
    cap_b = None
    try:
        cap_b = _open_cam(cam_b, wb, hb, fps=fps_b)
    except Exception as exc:
        print(f"[dual-cam] second cam open failed ({exc}), retry lower 96x72", flush=True)
        time.sleep(0.5)
        try:
            wb, hb, fps_b = 96, 72, 3.0
            cap_b = _open_cam(cam_b, wb, hb, fps=fps_b)
        except Exception as exc2:
            print(f"[dual-cam] second cam still failed: {exc2}", flush=True)
            cap_b = None

    win = "dual_cameras_hdmi"
    cv2.namedWindow(win, cv2.WINDOW_NORMAL)
    try:
        cv2.setWindowProperty(win, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
    except Exception:
        pass

    sw, sh = 1920, 1080
    last_b = _ph(hb, wb, f"video{cam_b} offline" if cap_b is None else "waiting")
    fail_b = 0
    last_log = 0.0
    frame_i = 0
    ok_b = False

    try:
        while True:
            frame_i += 1
            ok_a, fa = cap_a.read()
            if not ok_a or fa is None:
                fa = _ph(ha, wa, f"video{cam_a} NO FRAME")

            if cap_b is not None and frame_i % every == 0:
                ok_b, fb = cap_b.read()
                if ok_b and fb is not None:
                    last_b = fb
                    fail_b = 0
                else:
                    fail_b += 1
                    fb = last_b
            else:
                fb = last_b

            left = _label(fa, f"L main video{cam_a} {wa}x{ha}")
            right = _label(fb, f"R low video{cam_b} {wb}x{hb}")
            half = sw // 2
            canvas = np.hstack([_fit(left, half, sh), _fit(right, sw - half, sh)])
            cv2.line(canvas, (half, 0), (half, sh), (70, 70, 70), 2)
            cv2.imshow(win, canvas)
            if (cv2.waitKey(1) & 0xFF) in (ord("q"), 27):
                break
            now = time.time()
            if now - last_log >= 2.0:
                print(f"[dual-cam] okA={ok_a} okB={ok_b} failB={fail_b}", flush=True)
                last_log = now
    finally:
        try:
            cap_a.release()
        except Exception:
            pass
        if cap_b is not None:
            try:
                cap_b.release()
            except Exception:
                pass
        cv2.destroyAllWindows()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(0)
