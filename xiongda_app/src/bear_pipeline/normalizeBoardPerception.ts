import type { PerceptionPayload } from "./bearAgentTypes";

function num(v: unknown, fallback: number): number {
  const n = typeof v === "number" ? v : Number(v);
  return Number.isFinite(n) ? n : fallback;
}

function bool(v: unknown, fallback: boolean): boolean {
  if (typeof v === "boolean") return v;
  if (v === "true" || v === 1 || v === "1") return true;
  if (v === "false" || v === 0 || v === "0") return false;
  return fallback;
}

function str(v: unknown): string {
  if (v === null || v === undefined) return "";
  return String(v).trim();
}

function faceBBox(v: unknown): number[] | null | undefined {
  if (v === null) return null;
  if (!Array.isArray(v) || v.length !== 4) return undefined;
  const out: number[] = [];
  for (const x of v) {
    const n = typeof x === "number" ? x : Number(x);
    if (!Number.isFinite(n)) return undefined;
    out.push(n);
  }
  return out;
}

/**
 * 将 GET /api/board-auto/last 中的 perception（或任意松散 JSON）整理成与 Bear Agent `PerceptionIn` 一致的形状。
 * 兼容 camelCase：`speechText`、数值字符串等。
 */
export function normalizePerceptionPayload(raw: unknown): PerceptionPayload | null {
  if (raw === null || raw === undefined) return null;
  if (typeof raw !== "object") return null;
  const o = raw as Record<string, unknown>;

  const speech =
    str(o.speech_text) ||
    str(o.speechText) ||
    str(o["speech"]) ||
    "";

  const out: PerceptionPayload = {
    emotion: str(o.emotion) || "neutral",
    emotion_confidence: num(o.emotion_confidence, 0.9),
    gesture: str(o.gesture) || "none",
    gesture_confidence: num(o.gesture_confidence, 0.8),
    hand_gesture: str(o.hand_gesture) || str(o.handGesture) || "none",
    hand_gesture_confidence: num(o.hand_gesture_confidence, num(o.handGestureConfidence, 0.8)),
    person_detected: bool(o.person_detected, bool(o.personDetected, true)),
    person_count: num(o.person_count, num(o.personCount, 1)),
    speech_text: speech,
  };

  const fb = faceBBox(o.face_bbox ?? o.faceBbox);
  if (fb !== undefined) {
    out.face_bbox = fb;
  }

  out.emotion_confidence = Math.min(1, Math.max(0, out.emotion_confidence ?? 0));
  out.gesture_confidence = Math.min(1, Math.max(0, out.gesture_confidence ?? 0));
  out.hand_gesture_confidence = Math.min(1, Math.max(0, out.hand_gesture_confidence ?? 0));

  return out;
}
