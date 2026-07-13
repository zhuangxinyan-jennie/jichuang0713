import type { TopNavId } from "../types";

/** 与 bear_agent game_state.parse_mode_choice 语义对齐，用于底部栏快速切换顶栏 + 同步状态机 */

export type GuestNavIntent = Extract<TopNavId, "voice" | "story" | "map">;

export const STORY_TAB_SPEECH_KEYS = [
  "剧情互动",
  "益智小剧场",
  "小剧场",
  "智慧乐园任务",
  "做任务",
  "开始剧情",
  "玩剧情",
  "剧情任务",
] as const;

/** 说出口令后发给后端的仍是原句；若仅用于「切回语音页」则另行替换为「随机互动」 */
export const VOICE_TAB_SPEECH_KEYS = [
  "语音聊天",
  "语音互动",
  "返回语音",
  "语音模式",
  "语音主页",
  "随机互动",
  "聊聊天",
  "唠嗑",
] as const;

export const MAP_TAB_SPEECH_KEYS = [
  "地图查询",
  "查地图",
  "打开地图",
  "园区地图",
] as const;

function normalizeNavText(text: string): string {
  return text.trim().replace(/\s+/g, "");
}

export function parseGuestNavIntent(text: string): GuestNavIntent | null {
  const t = normalizeNavText(text);
  if (!t) return null;
  if (STORY_TAB_SPEECH_KEYS.some((k) => t.includes(k))) return "story";
  if (VOICE_TAB_SPEECH_KEYS.some((k) => t.includes(k))) return "voice";
  if (MAP_TAB_SPEECH_KEYS.some((k) => t.includes(k))) return "map";
  return null;
}

export function guestInputMatchesStoryNav(text: string): boolean {
  return parseGuestNavIntent(text) === "story";
}

export function guestInputMatchesVoiceNav(text: string): boolean {
  return parseGuestNavIntent(text) === "voice";
}

export function guestInputMatchesMapNav(text: string): boolean {
  return parseGuestNavIntent(text) === "map";
}
