"""Write HGBO tiling config to binary file consumed by Ascend C host TilingFunc."""

from __future__ import annotations

import struct
from pathlib import Path
from typing import Any, Dict

SPLIT_AXIS_MAP = {"H": 0, "W": 1, "flat": 2, "by_person": 3}

IH, IW, IC = 720, 1280, 3
OH, OW, OC = 640, 640, 3
TILING_BIN = Path("/tmp/hgbo_vpf_tiling.bin")


def write_tiling_bin(config: Dict[str, Any], path: Path | None = None) -> Path:
    out = path or TILING_BIN
    split = SPLIT_AXIS_MAP.get(config.get("split_axis", "H"), 0)
    payload = struct.pack(
        "IIIIIIIIIII",
        IH,
        IW,
        IC,
        OH,
        OW,
        OC,
        split,
        int(config.get("tile_h", 8)),
        int(config.get("tile_w", 128)),
        int(config.get("tile_len", 4096)),
        int(config.get("buffer_num", 1)),
    )
    out.write_bytes(payload)
    return out
