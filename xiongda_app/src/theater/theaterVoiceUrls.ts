/** 预烘焙剧情语音：`public/theater_voice/tp_{id}.wav`，由 scripts/generate_theater_voices.py 生成 */

const BASE = "/theater_voice";

/** 单条台词对应的静态 WAV URL（文件名前缀 tp_ 避免与其它资源冲突） */
export function theaterVoiceUrl(voiceId: string): string {
  const id = voiceId.trim();
  return `${BASE}/tp_${id}.wav`;
}

/**
 * 后端 `story_engine` 与益智小剧场共用同一套 clip→台词 id；
 * 与 bear_agent/story_engine.py 中 CLIP_TO_VOICE 保持一致。
 */
export const STORY_CLIP_TO_VOICE_ID: Record<string, string> = {
  "0": "intro_prompt",
  "0A": "intro_resolve_a",
  "0B": "intro_resolve_b",
  "1": "act1_direction_prompt",
  "1A": "act1_direction_resolve_a",
  "1B": "act1_direction_resolve_b",
  "1C": "act1_direction_resolve_c",
  "2": "act2_route_prompt",
  "2A": "act2_route_resolve_a",
  "2B": "act2_route_resolve_b",
  "2C": "act2_route_resolve_c",
  "3": "act3_safety_prompt",
  "3A": "act3_safety_resolve_a",
  "3B": "act3_safety_resolve_b",
  "3C": "act3_safety_resolve_c",
  "4": "finale",
};

export function storyClipIdsToVoiceUrls(clipIds: string[]): string[] {
  const out: string[] = [];
  for (const c of clipIds) {
    const id = STORY_CLIP_TO_VOICE_ID[c.trim()];
    if (id) out.push(theaterVoiceUrl(id));
  }
  return out;
}
