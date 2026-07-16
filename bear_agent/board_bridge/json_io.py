from __future__ import annotations

import json
import os
import threading
import time
import uuid
from pathlib import Path
from typing import Any


def read_json_file(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        text = path.read_text(encoding="utf-8")
        data = json.loads(text)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def atomic_write_json(path: Path, obj: Any, *, indent: int | None = 2, fsync: bool = True) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(obj, ensure_ascii=False, indent=indent, separators=(",", ":") if indent is None else None)
    tmp = path.with_name(
        f"{path.name}.{os.getpid()}.{threading.get_ident()}.{uuid.uuid4().hex}.tmp"
    )
    for attempt in range(10):
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                f.write(data)
                f.flush()
                if fsync:
                    os.fsync(f.fileno())
            for replace_attempt in range(8):
                try:
                    tmp.replace(path)
                    return
                except PermissionError:
                    if replace_attempt == 7:
                        raise
                    time.sleep(0.05 * (replace_attempt + 1))
            return
        except PermissionError:
            if attempt == 9:
                raise
            time.sleep(0.05 * (attempt + 1))
    try:
        tmp.unlink(missing_ok=True)
    except OSError:
        pass


def atomic_write_json_fast(path: Path, obj: Any) -> None:
    """高频路径：紧凑 JSON、不做 fsync，降低手势光标延迟。"""
    atomic_write_json(path, obj, indent=None, fsync=False)
