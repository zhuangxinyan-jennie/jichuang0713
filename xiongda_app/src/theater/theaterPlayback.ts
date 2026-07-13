import type { AgentContext } from "../services/agentContext";
import { cancelQueuedSequences, playSmplPathSequence } from "../bear_pipeline/playSequences";
import { announceBearSpeech, playPrebakedWavSequence, stopBearSpeech } from "../services/xiongdaTts";
import { theaterVoiceUrl } from "./theaterVoiceUrls";

const P = "SmplhRetarget/";

export function actionNamesToPaths(names: string[]): string[] {
  return names.map((n) => `${P}${n.trim()}.json`);
}

/** 播放小剧场反馈：字幕 + 顺序 SMPL */
export function playTheaterBeat(
  ctx: AgentContext,
  speech: string,
  actionNames: string[],
  stepMs = 2800
): void {
  cancelQueuedSequences();
  ctx.setSubtitle(speech);
  const paths = actionNamesToPaths(actionNames);
  if (paths.length > 0) {
    playSmplPathSequence(paths, ctx, stepMs);
  }
}

/** 熊大台词朗读：优先 GPT-SoVITS 服务，失败则浏览器 TTS */
export function speakTheaterLine(text: string): void {
  announceBearSpeech(text);
}

/**
 * 剧情预烘焙：`voiceIds` 对应 `public/theater_voice/tp_*.wav`。
 * 设置 `VITE_THEATER_VOICE_DISABLED=1` 时强制走在线/浏览器 TTS（仅字幕文本 `fallbackText`）。
 */
export function speakTheaterVoices(voiceIds: string[], fallbackText: string): void {
  const disabled = (import.meta.env.VITE_THEATER_VOICE_DISABLED as string | undefined)?.trim();
  if (disabled === "1" || disabled?.toLowerCase() === "true") {
    announceBearSpeech(fallbackText);
    return;
  }
  const urls = voiceIds
    .map((id) => id.trim())
    .filter(Boolean)
    .map((id) => theaterVoiceUrl(id));
  playPrebakedWavSequence(urls, fallbackText.replace(/\n+/g, " ").trim());
}

export function cancelTheaterSpeech(): void {
  stopBearSpeech();
}
