import type { TopNavId } from "../types";

/** 与 bear_agent game_state.parse_mode_choice 语义对齐 */

export type GuestNavIntent = Extract<TopNavId, "world" | "story">;

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

/** 原「语音聊天 / 随机互动」口令 → 全图互动页 */
export const VOICE_TAB_SPEECH_KEYS = [
  "语音聊天",
  "语音互动",
  "返回语音",
  "语音模式",
  "语音主页",
  "随机互动",
  "聊聊天",
  "唠嗑",
  "全图互动",
] as const;

/** 原「地图查询」口令 → 全图互动页（Unity 内切导览熊） */
export const MAP_TAB_SPEECH_KEYS = [
  "地图查询",
  "查地图",
  "打开地图",
  "园区地图",
  "地图导览",
  "问路",
] as const;

function normalizeNavText(text: string): string {
  return text.trim().replace(/\s+/g, "");
}

export function parseGuestNavIntent(text: string): GuestNavIntent | null {
  const t = normalizeNavText(text);
  if (!t) return null;
  if (STORY_TAB_SPEECH_KEYS.some((k) => t.includes(k))) return "story";
  if (VOICE_TAB_SPEECH_KEYS.some((k) => t.includes(k))) return "world";
  if (MAP_TAB_SPEECH_KEYS.some((k) => t.includes(k))) return "world";
  return null;
}

export function guestInputMatchesStoryNav(text: string): boolean {
  return parseGuestNavIntent(text) === "story";
}

/** @deprecated 使用 guestInputMatchesWorldNav */
export function guestInputMatchesVoiceNav(text: string): boolean {
  return parseGuestNavIntent(text) === "world";
}

export function guestInputMatchesWorldNav(text: string): boolean {
  return parseGuestNavIntent(text) === "world";
}

/** @deprecated 地图口令也进全图互动 */
export function guestInputMatchesMapNav(text: string): boolean {
  const t = normalizeNavText(text);
  if (!t) return false;
  return MAP_TAB_SPEECH_KEYS.some((k) => t.includes(k));
}

/** 底部输入像问路（走 map-query API） */
export function guestInputLooksLikeMapQuestion(text: string): boolean {
  const t = normalizeNavText(text);
  if (!t) return false;
  if (guestInputMatchesMapNav(text)) return true;
  return /(怎么走|怎么去|在哪|在哪儿|去哪|到哪|导航|路线|路径|往哪|带我去|领我去)/.test(t);
}
