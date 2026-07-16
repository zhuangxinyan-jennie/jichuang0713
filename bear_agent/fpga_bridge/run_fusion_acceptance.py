# -*- coding: utf-8 -*-
"""多模态融合一键验收：场景测试 + 结果报告。"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path

if __package__ is None:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from board_bridge.fpga_fusion_bridge import FusionSession, enrich_perception
from fpga_bridge.edge_event_encoder import encode_board_snapshot
from fpga_bridge.event_types import StableEventId
from fpga_bridge.fusion_sim import FusionEngine


@dataclass
class CaseResult:
    name: str
    passed: bool
    detail: str


def run_case(name: str, fn) -> CaseResult:
    try:
        ok, detail = fn()
        return CaseResult(name, ok, detail)
    except Exception as exc:
        return CaseResult(name, False, f"异常: {exc}")


def case_greeting() -> tuple[bool, str]:
    engine = FusionEngine()
    events = encode_board_snapshot(
        {"summary": {"person_count": 1, "action": {"label": "hand_waving", "confidence": 0.72}, "timestamp": 1280.034}},
        {"partial": "熊大你好", "summary": {}},
        audio_peak=0,
    )
    stable = engine.ingest_many(events)
    ids = [s.stable_id for s in stable]
    if StableEventId.USER_GREETING not in ids:
        return False, f"未产生 USER_GREETING，实际: {[s.name for s in ids]}"
    score = next(s.fusion_score for s in stable if s.stable_id == StableEventId.USER_GREETING)
    return score >= 850, f"USER_GREETING score={score}"


def case_noise() -> tuple[bool, str]:
    engine = FusionEngine()
    events = encode_board_snapshot(
        {"summary": {"person_count": 0, "timestamp": 1280.0}},
        {"summary": {}},
        audio_peak=91,
    )
    stable = engine.ingest_many(events)
    ids = [s.stable_id for s in stable]
    if StableEventId.NOISE_SUPPRESSED not in ids:
        return False, f"未产生 NOISE_SUPPRESSED，实际: {[s.name for s in ids]}"
    if StableEventId.USER_GREETING in ids:
        return False, "误触发 USER_GREETING"
    return True, "NOISE_SUPPRESSED，未误触发问候"


def case_wave_only_no_greeting() -> tuple[bool, str]:
    engine = FusionEngine()
    events = encode_board_snapshot(
        {"summary": {"person_count": 1, "action": {"label": "hand_waving", "confidence": 0.72}, "timestamp": 1280.0}},
        {"summary": {}},
    )
    stable = engine.ingest_many(events)
    if any(s.stable_id == StableEventId.USER_GREETING for s in stable):
        return False, "仅挥手不应触发 USER_GREETING"
    return True, "仅挥手未触发问候（符合预期）"


def case_attention() -> tuple[bool, str]:
    engine = FusionEngine()
    events = encode_board_snapshot(
        {"summary": {"person_count": 1, "timestamp": 1280.0}},
        {"summary": {}},
        audio_peak=80,
    )
    stable = engine.ingest_many(events)
    if StableEventId.ATTENTION not in [s.stable_id for s in stable]:
        return False, "有人+大声应产生 ATTENTION"
    return True, "ATTENTION 已触发"


def case_bridge_dedup() -> tuple[bool, str]:
    session = FusionSession()
    vdoc = {"ts": 100.0, "summary": {"person_count": 1, "timestamp": 100.0}}
    adoc = {"ts": 200.0, "summary": {}}
    a = session.process(vdoc, adoc)
    b = session.process(vdoc, adoc)
    if b:
        return False, "相同 ts 不应重复融合"
    post = session.find_postworthy(a)
    if post:
        session.mark_posted(post)
        if session.find_postworthy(a):
            return False, "POST 后不应重复触发"
    return True, f"去重正常，首轮 stable 数={len(a)}"


def case_enrich_perception() -> tuple[bool, str]:
    from fpga_bridge.event_types import StableEvent

    s = StableEvent(StableEventId.USER_GREETING, 128071, fusion_score=947, source_seq=2)
    p = enrich_perception({"speech_text": "熊大你好", "person_detected": True}, s)
    if p.get("stable_event") != "user_greeting":
        return False, str(p)
    return True, "perception 已写入 stable_event=user_greeting"


def main() -> int:
    cases = [
        ("场景1: 挥手+你好 → 问候", case_greeting),
        ("场景2: 无人+大声 → 噪声抑制", case_noise),
        ("场景3: 仅挥手 → 不问候", case_wave_only_no_greeting),
        ("场景4: 有人+大声 → 关注", case_attention),
        ("场景5: board_bridge 去重", case_bridge_dedup),
        ("场景6: perception 字段写入", case_enrich_perception),
    ]
    results = [run_case(name, fn) for name, fn in cases]
    passed = sum(1 for r in results if r.passed)
    total = len(results)

    lines = ["=" * 50, "多模态融合验收报告", "=" * 50, ""]
    for r in results:
        mark = "PASS" if r.passed else "FAIL"
        lines.append(f"[{mark}] {r.name}")
        lines.append(f"       {r.detail}")
        lines.append("")
    lines.append(f"合计: {passed}/{total} 通过")
    lines.append("")

    report = "\n".join(lines)
    print(report)

    out = Path(__file__).resolve().parents[2] / "pre_on_board_local_start_bundle" / "logs" / "fusion_test_report.txt"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(report, encoding="utf-8")
    print(f"报告已写入: {out}")

    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
