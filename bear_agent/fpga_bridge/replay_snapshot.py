# -*- coding: utf-8 -*-
"""离线回放：用 vision/asr JSON 或内置场景测试多模态融合。"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ is None:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fpga_bridge.edge_event_encoder import encode_board_snapshot
from fpga_bridge.fusion_sim import FusionEngine
from fpga_bridge.event_types import CandidateEvent, CandidateEventId, Modality, StableEventId


def run_snapshot(vision_doc: dict, asr_doc: dict, *, audio_peak: int = 0) -> None:
    events = encode_board_snapshot(vision_doc, asr_doc, audio_peak=audio_peak)
    engine = FusionEngine()
    stable = engine.ingest_many(events)
    print("=== 候选事件 ===")
    for e in events:
        print(f"  {e.event_id.name:16} conf={e.confidence:3} ts={e.timestamp_ms}")
    print("=== 稳定事件 ===")
    if not stable:
        print("  (无)")
    for s in stable:
        print(f"  {s.stable_id.name:18} score={s.fusion_score} ts={s.timestamp_ms}")
    print("=== 统计 ===")
    st = engine.stats
    print(
        f"  in={st.events_in} stable_out={st.stable_out} "
        f"greeting={st.greeting_count} noise={st.noise_suppressed} clap={st.clap_count}"
    )


def demo_greeting() -> None:
    print("\n[场景] 文档例题：挥手 + 熊大你好\n")
    engine = FusionEngine()
    wave = CandidateEvent(1, Modality.VISION, CandidateEventId.GESTURE_WAVE, 72, 61, 44, 128034)
    hello = CandidateEvent(2, Modality.AUDIO, CandidateEventId.VOICE_HELLO, 86, 0, 0, 128071)
    stable = engine.ingest(wave) + engine.ingest(hello)
    for s in stable:
        print(f"  -> {s.stable_id.name} score={s.fusion_score}")


def demo_noise() -> None:
    print("\n[场景] 噪声：大声但无人\n")
    engine = FusionEngine()
    peak = CandidateEvent(1, Modality.AUDIO, CandidateEventId.AUDIO_PEAK, 91, 91, 0, 2000)
    stable = engine.ingest(peak)
    for s in stable:
        print(f"  -> {s.stable_id.name}")


def main() -> int:
    ap = argparse.ArgumentParser(description="离线测试 fpga_bridge 多模态融合")
    ap.add_argument("--vision", type=Path, help="latest_vision.json 路径")
    ap.add_argument("--asr", type=Path, help="latest_asr.json 路径")
    ap.add_argument("--audio-peak", type=int, default=0, help="模拟音量峰值 0~100")
    ap.add_argument("--demo", choices=("greeting", "noise", "all"), help="运行内置例题")
    args = ap.parse_args()

    if args.demo:
        if args.demo in ("greeting", "all"):
            demo_greeting()
        if args.demo in ("noise", "all"):
            demo_noise()
        if args.demo != "all" or (not args.vision and not args.asr):
            return 0

    if args.vision and args.asr:
        vision_doc = json.loads(args.vision.read_text(encoding="utf-8"))
        asr_doc = json.loads(args.asr.read_text(encoding="utf-8"))
        print(f"\n[回放] {args.vision.name} + {args.asr.name}\n")
        run_snapshot(vision_doc, asr_doc, audio_peak=args.audio_peak)
        return 0

    ap.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
