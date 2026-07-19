#!/usr/bin/env python3
"""HGBO-OpTune 命令行入口."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from hgbo_optune.boto.op_dse import main

if __name__ == "__main__":
    main()
