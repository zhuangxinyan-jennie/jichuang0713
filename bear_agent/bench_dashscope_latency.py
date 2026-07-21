from __future__ import annotations

import json
import os
import statistics
import time

from config import ACTION_LIST, EMOTION_LIST, MEMORY_CONFIG
from memory import SimpleMemory
from output_parser import OutputParser
from perception import PerceptionFusion
from planner import Planner


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return values[0]
    ordered = sorted(values)
    pos = (len(ordered) - 1) * p
    lo = int(pos)
    hi = min(lo + 1, len(ordered) - 1)
    frac = pos - lo
    return ordered[lo] * (1.0 - frac) + ordered[hi] * frac


def main() -> None:
    perception_result = {
        "person_detected": True,
        "person_count": 1,
        "emotion": "happy",
        "emotion_confidence": 0.92,
        "gesture": "none",
        "gesture_confidence": 0.0,
        "hand_gesture": "like",
        "hand_gesture_confidence": 0.86,
        "speech_text": "熊大你好，带我去看看海盗船",
    }

    memory = SimpleMemory(
        max_history=MEMORY_CONFIG["max_history"],
        reset_timeout=MEMORY_CONFIG["reset_timeout"],
    )
    memory.add("游客挥手，表情开心，说：熊大你好", "嘿，你好哇，俺是熊大")

    perception = PerceptionFusion()
    parser = OutputParser()
    planner = Planner("rules.json")

    perception_data = perception.fuse(perception_result)
    memory_prompt = memory.to_prompt()
    user_prompt = f"""{memory_prompt}

【当前情况】
{perception_data['description']}

请根据当前情况，以熊大的身份做出回应。"""

    print("=== prompt_meta ===")
    print(json.dumps({
        "provider": planner.llm_settings.provider,
        "base_url": planner.llm_settings.base_url,
        "model": planner.llm_settings.model,
        "system_prompt_chars": len(planner.system_prompt),
        "user_prompt_chars": len(user_prompt),
        "description": perception_data["description"],
    }, ensure_ascii=False))

    latencies_ms: list[float] = []
    parse_ok = 0
    outputs = []

    runs = int(os.environ.get("BEAR_LLM_BENCH_RUNS", "5"))
    for i in range(runs):
        t0 = time.perf_counter()
        try:
            llm_output = planner.llm_backend.generate(planner.system_prompt, user_prompt)
        except Exception as exc:
            dt_ms = (time.perf_counter() - t0) * 1000.0
            item = {
                "run": i + 1,
                "latency_ms": round(dt_ms, 1),
                "valid": False,
                "error": type(exc).__name__,
                "message": str(exc),
            }
            outputs.append(item)
            print("=== run ===")
            print(json.dumps(item, ensure_ascii=False), flush=True)
            continue
        dt_ms = (time.perf_counter() - t0) * 1000.0

        parsed = parser.repair(parser.parse(llm_output), ACTION_LIST, EMOTION_LIST)
        valid = parser.validate(parsed, ACTION_LIST, EMOTION_LIST)
        parse_ok += int(valid)
        latencies_ms.append(dt_ms)
        outputs.append({
            "run": i + 1,
            "latency_ms": round(dt_ms, 1),
            "valid": valid,
            "speech": parsed.get("speech"),
            "motion_type": parsed.get("motion_type"),
            "actions": parsed.get("actions"),
            "emotion": parsed.get("emotion"),
        })
        print("=== run ===")
        print(json.dumps(outputs[-1], ensure_ascii=False), flush=True)

    print("=== summary ===")
    if latencies_ms:
        summary = {
            "runs_requested": runs,
            "runs_succeeded": len(latencies_ms),
            "parse_valid": parse_ok,
            "mean_ms": round(statistics.mean(latencies_ms), 1),
            "p50_ms": round(percentile(latencies_ms, 0.50), 1),
            "p95_ms": round(percentile(latencies_ms, 0.95), 1),
            "min_ms": round(min(latencies_ms), 1),
            "max_ms": round(max(latencies_ms), 1),
        }
    else:
        summary = {
            "runs_requested": runs,
            "runs_succeeded": 0,
            "parse_valid": 0,
            "error": "all requests failed",
        }
    print(json.dumps(summary, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
