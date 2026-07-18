# -*- coding: utf-8 -*-
"""Poll local board output JSON and post perception updates to Bear Agent."""
from __future__ import annotations

import json
import time
import urllib.error
from pathlib import Path
from typing import Any

from .agent_http import (
    agent_gate_status,
    agent_http_base,
    latency_log_append,
    latency_log_enabled,
    post_board_asr_live,
    post_json,
)
from .config import load_bridge_runtime_config
from .engagement import EngagementTracker, comfort_zone_status
from .fpga_fusion_bridge import (
    FusionSession,
    enrich_perception,
    ensure_speech_for_greeting,
    stable_event_doc,
)
from .json_io import atomic_write_json, read_json_file
from .perception_merge import build_perception, fingerprint_for_trigger
from .speech_pick import pick_speech_text
from .turn_fusion import InteractionTurnFusion, extract_hand_body_from_perception
from fpga_bridge.event_types import StableEventId

# 视觉 JSON 超过该秒数未更新 → 视为无人/无手，避免陈旧点赞反复送 Agent
_VISION_STALE_SEC = 2.5


def clear_latest_asr_utterance(path: Path) -> None:
    doc = read_json_file(path)
    if not doc:
        return
    doc["partial"] = ""
    doc["final"] = ""
    doc["normalized"] = ""
    summ = doc.get("summary")
    if isinstance(summ, dict):
        for k in ("normalized_text", "speech_text", "text", "utterance", "final_text"):
            if isinstance(summ.get(k), str):
                summ[k] = ""
    doc["ts"] = time.time()
    atomic_write_json(path, doc)


def poll_loop(
    output_dir: Path,
    agent_url: str,
    *,
    poll_interval_sec: float = 0.2,
    min_post_interval_sec: float = 0.8,
    response_dump: Path | None = None,
    stop_flag: Any | None = None,
    utterance_clear_event: Any | None = None,
    wakeup_event: Any | None = None,
    log_print=print,
) -> None:
    cfg = load_bridge_runtime_config()
    vision_path = output_dir / "vision" / "latest_vision.json"
    asr_path = output_dir / "asr" / "latest_asr.json"
    fpga_path = output_dir / "fpga" / "latest_stable.json"
    url = agent_url.strip()
    use_fingerprint_trigger = cfg.use_fingerprint_trigger
    fusion = FusionSession()
    turn_fusion = InteractionTurnFusion(
        post_speech_grace_sec=1.0,
        post_gesture_grace_sec=1.0,
    )
    engagement = EngagementTracker()

    last_fp: str | None = None
    last_post_mono = 0.0
    last_posted_speech: str = ""
    last_asr_clear_token: int | None = None

    while True:
        if stop_flag is not None and getattr(stop_flag, "is_set", lambda: False)():
            break

        if wakeup_event is not None:
            wakeup_event.wait(timeout=poll_interval_sec)
            wakeup_event.clear()

        vdoc = read_json_file(vision_path)
        adoc = read_json_file(asr_path)

        perception = build_perception(vdoc, adoc)
        # 视觉文件停更（人或板端离开后仍残留最后一帧 like）→ 当作无人
        try:
            v_ts = float(vdoc.get("ts") or 0.0)
        except (TypeError, ValueError):
            v_ts = 0.0
        if v_ts > 0 and (time.time() - v_ts) > _VISION_STALE_SEC:
            perception = dict(perception)
            perception["person_detected"] = False
            perception["person_count"] = 0
            perception["hand_gesture"] = "none"
            perception["hand_gesture_confidence"] = 0.0
            perception["gesture"] = "none"
            perception["gesture_confidence"] = 0.0

        fp = fingerprint_for_trigger(perception)
        speech_now = pick_speech_text(adoc, use_partial_fallback=cfg.speech_use_partial_fallback).strip()
        partial = (adoc.get("partial") or "").strip()
        final_txt = (adoc.get("final") or "").strip()
        norm_txt = (adoc.get("normalized") or "").strip()
        now = time.monotonic()
        base = agent_http_base(url)
        gate_status = agent_gate_status(base, log_print=log_print) if cfg.respect_agent_gate else {"enabled": False, "busy": False}
        gate_busy = bool(gate_status.get("enabled")) and bool(gate_status.get("busy"))
        raw_token = gate_status.get("asr_clear_token", 0)
        try:
            asr_clear_token = int(raw_token)
        except (TypeError, ValueError):
            asr_clear_token = 0

        if last_asr_clear_token is None:
            last_asr_clear_token = asr_clear_token
        elif asr_clear_token != last_asr_clear_token:
            last_asr_clear_token = asr_clear_token
            if utterance_clear_event is not None:
                utterance_clear_event.set()
            clear_latest_asr_utterance(asr_path)
            last_posted_speech = ""
            last_fp = None
            fusion.reset_trigger_memory()
            turn_fusion.reset()
            engagement.reset()
            post_board_asr_live(url, partial="", final="", normalized="")
            continue

        if gate_busy:
            if utterance_clear_event is not None:
                utterance_clear_event.set()
            clear_latest_asr_utterance(asr_path)
            last_posted_speech = ""
            last_fp = None
            fusion.reset_trigger_memory()
            turn_fusion.reset()
            # 不 reset engagement：熊大说话时人仍可能在互动中
            post_board_asr_live(url, partial="", final="", normalized="")
            continue

        post_board_asr_live(url, partial=partial, final=final_txt, normalized=norm_txt)

        hand_l, hand_c, body_l, body_c = extract_hand_body_from_perception(perception)
        turn_fusion.observe(
            hand_label=hand_l,
            hand_conf=hand_c,
            body_label=body_l,
            body_conf=body_c,
            asr_partial=partial,
            asr_finalish=norm_txt or final_txt or speech_now,
            now_mono=now,
            person_detected=bool(perception.get("person_detected")),
        )

        try:
            distance_m = float(perception["distance_m_est"]) if perception.get("distance_m_est") is not None else None
        except (TypeError, ValueError):
            distance_m = None

        # 先 peek 手势是否已满 2s（不消费），供意向判定
        gesture_peek = turn_fusion.ready_gesture_only_perception(perception, now_mono=now)
        engagement.update(
            now_mono=now,
            person_detected=bool(perception.get("person_detected")),
            distance_m=distance_m,
            speech_text=speech_now or partial,
            gesture_hold_ready=gesture_peek is not None,
        )
        # 站位提示默认关；远近优先于左右
        coach_kind = None
        if cfg.distance_coach_enabled:
            coach_kind = engagement.decide_coach(now_mono=now, distance_m=distance_m)
        if coach_kind is None and cfg.position_coach_enabled:
            coach_kind = engagement.decide_position_coach(
                now_mono=now,
                distance_m=distance_m,
                position_hint=str(perception.get("position_coach_hint") or ""),
            )

        stable_batch = fusion.process(vdoc, adoc)
        postworthy = fusion.find_postworthy(
            stable_batch,
            distance_band=str(perception.get("distance_band") or ""),
        )
        try:
            fpga_path.parent.mkdir(parents=True, exist_ok=True)
            atomic_write_json(fpga_path, stable_event_doc(postworthy or fusion.last_postworthy, fusion.stats))
        except OSError:
            pass

        trigger_mode = (
            "hybrid"
            if cfg.use_hybrid_trigger
            else ("stable_event" if cfg.use_stable_event_trigger else ("fingerprint" if use_fingerprint_trigger else "speech_novelty"))
        )
        try:
            atomic_write_json(
                output_dir / "perception_preview.json",
                {
                    "perception": perception,
                    "asr_partial": partial,
                    "asr_final": (adoc.get("final") or "").strip(),
                    "asr_normalized": (adoc.get("normalized") or "").strip(),
                    "vision_ts": vdoc.get("ts"),
                    "asr_ts": adoc.get("ts"),
                    "ts": time.time(),
                    "bridge_trigger": {
                        "mode": trigger_mode,
                        "speech_now": speech_now,
                        "last_posted_speech_to_agent": last_posted_speech,
                        "fingerprint": fp,
                        "stable_event": (postworthy.stable_id.name if postworthy else ""),
                        "fpga_stats": stable_event_doc(None, fusion.stats)["stats"],
                        "turn_fusion": {
                            "mode": turn_fusion.mode,
                            "best_hand": turn_fusion.best_hand.label,
                            "best_hand_confidence": turn_fusion.best_hand.confidence,
                            "best_body": turn_fusion.best_body.label,
                            "pending_speech": turn_fusion.pending_speech,
                            "grace_until_mono": turn_fusion.grace_until_mono,
                        },
                        "engagement": {
                            **engagement.snapshot(now),
                            "distance_m_est": distance_m,
                            "comfort_zone": comfort_zone_status(distance_m),
                            "lateral_zone": perception.get("lateral_zone"),
                            "position_coach_hint": perception.get("position_coach_hint"),
                            "coach_pending": coach_kind,
                        },
                    },
                },
            )
        except OSError:
            pass

        interval_ok = (now - last_post_mono) >= min_post_interval_sec
        post_eligible = False
        perception_to_post = perception
        posted_via_turn_fusion = False
        posted_via_gesture_only = False
        posted_via_distance_coach = False

        # 站位提示优先：远近或左右
        if coach_kind and interval_ok and bool(perception.get("person_detected")):
            perception_to_post = dict(perception)
            perception_to_post["speech_text"] = ""
            if coach_kind in ("lean_left", "lean_right"):
                perception_to_post["position_coach"] = coach_kind
            else:
                perception_to_post["distance_coach"] = coach_kind
            perception_to_post["interaction_engaged"] = True
            post_eligible = True
            posted_via_distance_coach = True
        elif cfg.use_stable_event_trigger:
            post_eligible = postworthy is not None and interval_ok
            if postworthy is not None:
                perception_to_post = enrich_perception(perception, postworthy)
                if postworthy.stable_id == StableEventId.USER_GREETING:
                    perception_to_post = ensure_speech_for_greeting(perception_to_post, speech_now or partial)
        elif cfg.use_hybrid_trigger:
            if bool(speech_now) and speech_now != last_posted_speech:
                turn_fusion.note_speech_candidate(speech_now, now)
            enriched = turn_fusion.ready_enriched_perception(perception, now_mono=now)
            gesture_only = None
            if enriched is None:
                gesture_only = turn_fusion.ready_gesture_only_perception(perception, now_mono=now)
            speech_ready = enriched is not None and interval_ok
            gesture_ready = gesture_only is not None and interval_ok
            stable_hit = postworthy is not None and interval_ok
            post_eligible = speech_ready or gesture_ready or stable_hit
            if speech_ready and enriched is not None:
                perception_to_post = enriched
                posted_via_turn_fusion = True
            elif gesture_ready and gesture_only is not None:
                perception_to_post = gesture_only
                posted_via_turn_fusion = True
                posted_via_gesture_only = True
            elif stable_hit and postworthy is not None:
                perception_to_post = enrich_perception(perception, postworthy)
                if postworthy.stable_id == StableEventId.USER_GREETING:
                    perception_to_post = ensure_speech_for_greeting(perception_to_post, speech_now or partial)
        elif use_fingerprint_trigger:
            post_eligible = fp != last_fp and interval_ok
        else:
            # speech_novelty：整句收束窗，或纯手势保持 2s
            if bool(speech_now) and speech_now != last_posted_speech:
                turn_fusion.note_speech_candidate(speech_now, now)
            enriched = turn_fusion.ready_enriched_perception(perception, now_mono=now)
            gesture_only = None
            if enriched is None:
                gesture_only = turn_fusion.ready_gesture_only_perception(perception, now_mono=now)
            post_eligible = (enriched is not None or gesture_only is not None) and interval_ok
            if enriched is not None:
                perception_to_post = enriched
                posted_via_turn_fusion = True
            elif gesture_only is not None:
                perception_to_post = gesture_only
                posted_via_turn_fusion = True
                posted_via_gesture_only = True

        # 旁观过滤：无意向时不把路过说话/误检送进 Agent（距离提示与唤醒除外）
        if post_eligible and not posted_via_distance_coach:
            speech_for_gate = (perception_to_post.get("speech_text") or speech_now or "").strip()
            if not engagement.allow_interaction_post(
                now_mono=now,
                speech_for_post=speech_for_gate,
                is_gesture_only=posted_via_gesture_only,
            ):
                post_eligible = False
                posted_via_turn_fusion = False
                posted_via_gesture_only = False

        if post_eligible:
            try:
                perception_to_post = dict(perception_to_post)
                perception_to_post.pop("_turn_fusion", None)
                perception_to_post["interaction_engaged"] = bool(
                    engagement.wants_interact(now) or posted_via_distance_coach or posted_via_gesture_only
                )
                t_http = time.perf_counter()
                agent_out = post_json(url, perception_to_post)
                if latency_log_enabled():
                    _ln = f"[latency] board_bridge POST {url} {(time.perf_counter() - t_http) * 1000.0:.1f}ms"
                    log_print(_ln, flush=True)
                    latency_log_append(_ln)
                log_print(f"[board_bridge] POST {url}\n  perception={json.dumps(perception_to_post, ensure_ascii=False)}")
                log_print(f"[board_bridge] agent_out keys={list(agent_out.keys())}")
                if partial and not (perception_to_post.get("speech_text") or "").strip():
                    log_print(f"[board_bridge] ASR 实时草稿 partial（尚未 final）: {partial[:120]}", flush=True)
                if response_dump and agent_out:
                    atomic_write_json(response_dump, agent_out)
                last_post_mono = now
                last_posted_speech = (perception_to_post.get("speech_text") or speech_now or "").strip()
                if use_fingerprint_trigger:
                    last_fp = fp
                if posted_via_distance_coach and coach_kind:
                    engagement.mark_coach_posted(now, coach_kind)
                elif not posted_via_distance_coach:
                    engagement.note_activity(now)
                if postworthy is not None and not posted_via_turn_fusion and not posted_via_distance_coach:
                    fusion.mark_posted(postworthy)
                if posted_via_turn_fusion:
                    if posted_via_gesture_only:
                        turn_fusion.mark_gesture_only_posted(now)
                    else:
                        turn_fusion.reset()
                if cfg.clear_asr_after_post and not posted_via_distance_coach:
                    if utterance_clear_event is not None:
                        utterance_clear_event.set()
                    clear_latest_asr_utterance(asr_path)
                    post_board_asr_live(url, partial="", final="", normalized="")
            except urllib.error.URLError as e:
                log_print(f"[board_bridge] POST failed: {e}")
                # 纯手势失败也进入冷却+须释放，避免每 0.8s 用同一陈旧 like 狂打
                if posted_via_gesture_only:
                    turn_fusion.mark_gesture_only_posted(now)
                    last_post_mono = now
                if posted_via_distance_coach and coach_kind:
                    engagement.mark_coach_posted(now, coach_kind)
                    last_post_mono = now

