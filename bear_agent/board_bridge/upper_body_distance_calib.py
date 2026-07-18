# -*- coding: utf-8 -*-
"""仅上半身单目测距：展台临时站位标定（地面不用贴东西）。

思路：
  距离 ∝ 1 / 人脸框像素宽。用卷尺让人站在 0.4/1.0/1.5m 等处采几次脸宽，
  拟合查表；运行时只看主摄人脸框即可。

标定文件默认：
  bear_agent/board_bridge/data/upper_body_distance_calib.json
环境变量 BEAR_DISTANCE_CALIB 可覆盖路径。
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


def default_calib_path() -> Path:
    env = (os.environ.get("BEAR_DISTANCE_CALIB") or "").strip()
    if env:
        return Path(env)
    return Path(__file__).resolve().parent / "data" / "upper_body_distance_calib.json"


@dataclass
class UpperBodyDistanceCalib:
    """face_width_px → distance_m 的分段线性（在 1/w 空间更稳）。"""

    # 样本：真实距离(m) → 观测到的人脸宽(px) 列表（可多人多次）
    samples: list[dict[str, Any]] = field(default_factory=list)
    frame_width: float | None = None
    note: str = "upper-body face-width calib; no floor markers"

    def add_sample(self, distance_m: float, face_width_px: float, *, face_cy: float | None = None) -> None:
        d = float(distance_m)
        w = float(face_width_px)
        if d < 0.15 or d > 6.0 or w < 8.0:
            raise ValueError(f"invalid sample distance_m={d} face_width_px={w}")
        item: dict[str, Any] = {"distance_m": round(d, 3), "face_width_px": round(w, 2)}
        if face_cy is not None:
            item["face_cy"] = round(float(face_cy), 2)
        self.samples.append(item)

    def _points_inv_w(self) -> list[tuple[float, float]]:
        """返回按 1/w 排序的 (1/w, distance_m)，同距离取脸宽中位数。"""
        by_d: dict[float, list[float]] = {}
        for s in self.samples:
            try:
                d = float(s["distance_m"])
                w = float(s["face_width_px"])
            except (KeyError, TypeError, ValueError):
                continue
            if w <= 1e-6:
                continue
            by_d.setdefault(round(d, 3), []).append(w)
        pts: list[tuple[float, float]] = []
        for d, ws in sorted(by_d.items()):
            ws_sorted = sorted(ws)
            mid = ws_sorted[len(ws_sorted) // 2]
            pts.append((1.0 / mid, float(d)))
        pts.sort(key=lambda p: p[0])
        return pts

    def estimate_m(self, face_width_px: float | None) -> float | None:
        if face_width_px is None or face_width_px <= 8.0:
            return None
        pts = self._points_inv_w()
        if len(pts) < 2:
            return None
        x = 1.0 / float(face_width_px)
        if x <= pts[0][0]:
            # 外推：用前两段斜率
            (x0, y0), (x1, y1) = pts[0], pts[1]
            if abs(x1 - x0) < 1e-12:
                return round(y0, 2)
            y = y0 + (y1 - y0) * (x - x0) / (x1 - x0)
            return round(max(0.15, min(8.0, y)), 2)
        if x >= pts[-1][0]:
            (x0, y0), (x1, y1) = pts[-2], pts[-1]
            if abs(x1 - x0) < 1e-12:
                return round(y1, 2)
            y = y0 + (y1 - y0) * (x - x0) / (x1 - x0)
            return round(max(0.15, min(8.0, y)), 2)
        for i in range(len(pts) - 1):
            x0, y0 = pts[i]
            x1, y1 = pts[i + 1]
            if x0 <= x <= x1:
                if abs(x1 - x0) < 1e-12:
                    return round(y0, 2)
                y = y0 + (y1 - y0) * (x - x0) / (x1 - x0)
                return round(y, 2)
        return None

    def ready(self) -> bool:
        return len(self._points_inv_w()) >= 2

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": 1,
            "note": self.note,
            "frame_width": self.frame_width,
            "samples": list(self.samples),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "UpperBodyDistanceCalib":
        data = data if isinstance(data, dict) else {}
        c = cls()
        c.note = str(data.get("note") or c.note)
        try:
            fw = data.get("frame_width")
            c.frame_width = float(fw) if fw is not None else None
        except (TypeError, ValueError):
            c.frame_width = None
        raw = data.get("samples")
        if isinstance(raw, list):
            for s in raw:
                if isinstance(s, dict):
                    c.samples.append(dict(s))
        return c

    def save(self, path: Path | None = None) -> Path:
        path = path or default_calib_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        return path


_CACHE: UpperBodyDistanceCalib | None = None
_CACHE_MTIME: float | None = None


def load_calib(path: Path | None = None, *, force: bool = False) -> UpperBodyDistanceCalib | None:
    global _CACHE, _CACHE_MTIME
    path = path or default_calib_path()
    if not path.is_file():
        return None
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return None
    if not force and _CACHE is not None and _CACHE_MTIME == mtime:
        return _CACHE
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    calib = UpperBodyDistanceCalib.from_dict(data if isinstance(data, dict) else {})
    if not calib.ready():
        return None
    _CACHE = calib
    _CACHE_MTIME = mtime
    return calib
