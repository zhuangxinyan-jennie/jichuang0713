import type { AgentContext } from "../services/agentContext";
import {
  announceBearSpeech,
  playPrebakedWavSequence,
  speakBrowserFallback,
} from "../services/xiongdaTts";
import { theaterVoiceUrl, storyClipIdsToVoiceUrls } from "../theater/theaterVoiceUrls";
import { sendSmplStreamingRelativePath } from "../services/unitySendClip";
import { postMultimodalPlaybackDone, postMultimodalPlaybackStart } from "./bearAgentClient";
import { chineseActionToSmplPath } from "./chineseActionToSmplPath";
import { clipIdsToSmplPaths } from "./clipIdToSmplPath";
import { cancelQueuedSequences, DEFAULT_SMPL_STEP_MS, playSmplPathSequence } from "./playSequences";

export type BearAgentDispatchOptions = {
  smplStepMs?: number;
  /** @deprecated 已不再调用 PlayClipById；预留兼容 */
  clipStepMs?: number;
  /** 后端进入剧情分支（story_interaction）时回调，用于把界面切到「益智小剧场」页 */
  onEnterStoryTab?: () => void;
  /** 后端进入随机互动/语音聊天时回调，用于把界面切到「语音聊天」页 */
  onEnterVoiceTab?: () => void;
  /** 后端进入地图查询时回调，用于把界面切到「地图查询」页 */
  onEnterMapTab?: () => void;
  /**
   * board_bridge 串行闸门：本轮 Agent 返回触发的朗读/预烘焙 WAV **全部结束后**调用（例如 POST playback-done）。
   * 仅应在「板端自动同步」路径传入；手动发送不要传，避免误释放闸门。
   */
  onPlaybackChainFinished?: () => void;
};

export function notifyPlaybackStart(): void {
  void postMultimodalPlaybackStart();
}

export function notifyPlaybackDone(): void {
  void postMultimodalPlaybackDone();
}

function setSpeechFromPayload(ctx: AgentContext, o: Record<string, unknown>): boolean {
  const s = o.speech;
  if (typeof s === "string" && s.trim()) {
    const hint = typeof o.story_waiting_hint === "string" ? o.story_waiting_hint.trim() : "";
    ctx.setSubtitle(hint ? `${s.trim()}\n\n━━ 下一步 ━━\n${hint}` : s.trim());
    return true;
  }
  return false;
}

function voiceIdFromPayload(o: Record<string, unknown>): string {
  const explicit = typeof o.voice_id === "string" ? o.voice_id.trim() : "";
  if (explicit) return explicit;
  const speech = typeof o.speech === "string" ? o.speech.trim() : "";
  if (speech.startsWith("俺还没听懂要选哪种玩法呀")) return "mode_ack_voice";
  if (speech.startsWith("这个地方俺还没找着")) return "map_place_not_found";
  return "";
}

type SpeechCompletionGate = {
  speak: (text: string) => void;
  /** 剧情等：走系统朗读，避免板端异步触发后 SoVITS/HTMLAudio 被 autoplay 拦截 */
  speakBrowser: (text: string) => void;
  prebaked: (urls: string[], fallbackSpeak?: string, fallbackMode?: "tts" | "browser") => void;
  doneIfSilent: () => void;
};

/** 跟踪本轮 payload 触发的所有语音；全部结束后触发一次回调（无语音则立即触发）。 */
function createSpeechCompletionGate(onAllFinished?: () => void): SpeechCompletionGate {
  let pending = 0;
  let terminal = false;
  const tryFinish = () => {
    if (terminal) return;
    if (pending <= 0) {
      terminal = true;
      queueMicrotask(() => onAllFinished?.());
    }
  };
  return {
    speak(text: string) {
      const t = text.replace(/\n+/g, " ").trim();
      if (!t) return;
      pending++;
      announceBearSpeech(t, () => {
        pending--;
        tryFinish();
      });
    },
    speakBrowser(text: string) {
      const t = text.replace(/\n+/g, " ").trim();
      if (!t) return;
      pending++;
      speakBrowserFallback(t, () => {
        pending--;
        tryFinish();
      });
    },
    prebaked(urls: string[], fallbackSpeak?: string, fallbackMode: "tts" | "browser" = "tts") {
      pending++;
      playPrebakedWavSequence(urls, fallbackSpeak, () => {
        pending--;
        tryFinish();
      }, fallbackMode);
    },
    doneIfSilent() {
      tryFinish();
    },
  };
}

/**
 * 统一处理 Bear Agent 返回：动作一律走 **SMPL JSON**
 *（`PlaySmplStreamingRelativePath`）。后端的 `clip_ids` 会先映射到 `SmplhRetarget/*.json`
 *（见 `clipIdToSmplPath.ts`），再按间隔顺序播放。
 *
 * - `null`：状态机在「等待用户说话」等阶段无新 JSON。
 */
export function handleBearAgentPayload(
  data: unknown,
  ctx: AgentContext,
  options?: BearAgentDispatchOptions
): void {
  const sg = options?.onPlaybackChainFinished ? createSpeechCompletionGate(options.onPlaybackChainFinished) : null;
  const end = () => {
    sg?.doneIfSilent();
  };

  const speakLine = (text: string) => {
    if (sg) sg.speak(text);
    else {
      announceBearSpeech(text, notifyPlaybackDone);
    }
  };

  const announcePayloadSpeechWrapped = (o: Record<string, unknown>) => {
    const s = typeof o.speech === "string" ? o.speech.trim() : "";
    if (!s) return;
    speakLine(s);
  };

  cancelQueuedSequences();
  const maybeEnterStoryTab = () => options?.onEnterStoryTab?.();
  const maybeEnterVoiceTab = () => options?.onEnterVoiceTab?.();
  const maybeEnterMapTab = () => options?.onEnterMapTab?.();

  if (data === null || data === undefined) {
    ctx.setSubtitle(
      "（本轮无新输出：状态机在等你的 speech_text，例如「剧情互动」「往左走」「路线B」或「随机互动」）"
    );
    end();
    return;
  }

  if (typeof data !== "object") {
    console.warn("[handleBearAgentPayload] 非对象响应", data);
    end();
    return;
  }

  const o = data as Record<string, unknown>;
  const interactionType = typeof o.interaction_type === "string" ? o.interaction_type : "";
  const targetMode = typeof o.target_mode === "string" ? o.target_mode : "";
  const smplStep = options?.smplStepMs ?? DEFAULT_SMPL_STEP_MS;

  const clipIds = Array.isArray(o.clip_ids)
    ? o.clip_ids.filter((x): x is string => typeof x === "string" && x.trim().length > 0)
    : [];

  if (interactionType === "mode_ack") {
    if (targetMode === "random") maybeEnterVoiceTab();
    if (targetMode === "map") maybeEnterMapTab();
    const hadSpeech = setSpeechFromPayload(ctx, o);
    const voiceId = voiceIdFromPayload(o);
    const speech = typeof o.speech === "string" ? o.speech.trim() : "";
    if (voiceId && speech) {
      if (sg) sg.prebaked([theaterVoiceUrl(voiceId)], speech, "tts");
      else playPrebakedWavSequence([theaterVoiceUrl(voiceId)], speech, notifyPlaybackDone, "tts");
    } else if (hadSpeech) {
      announcePayloadSpeechWrapped(o);
    }
    if (targetMode === "story") maybeEnterStoryTab();
    ctx.setCurrentSmplPath("—（玩法确认，无新动画）");
    end();
    return;
  }

  if (interactionType === "mode_select") {
    if (targetMode === "random") maybeEnterVoiceTab();
    if (targetMode === "map") maybeEnterMapTab();
    const hadSpeech = setSpeechFromPayload(ctx, o);
    const voiceId = voiceIdFromPayload(o);
    const speech = typeof o.speech === "string" ? o.speech.trim() : "";
    if (voiceId && speech) {
      if (sg) sg.prebaked([theaterVoiceUrl(voiceId)], speech, "tts");
      else playPrebakedWavSequence([theaterVoiceUrl(voiceId)], speech, notifyPlaybackDone, "tts");
    } else if (hadSpeech) {
      announcePayloadSpeechWrapped(o);
    }
    if (clipIds.length > 0) {
      playSmplPathSequence(clipIdsToSmplPaths(clipIds), ctx, smplStep);
    }
    if (targetMode === "story") maybeEnterStoryTab();
    end();
    return;
  }

  if (interactionType === "mode_select" || interactionType === "story_interaction") {
    if (interactionType === "story_interaction") maybeEnterStoryTab();
    if (targetMode === "random") maybeEnterVoiceTab();
    if (targetMode === "map") maybeEnterMapTab();
    const hadSpeech = setSpeechFromPayload(ctx, o);

    const voDisabled = (import.meta.env.VITE_THEATER_VOICE_DISABLED as string | undefined)?.trim();
    const prebakedOff = voDisabled === "1" || voDisabled?.toLowerCase() === "true";

    /** 仅当纯麦克风轮询且浏览器拦截 HTMLAudio/SoVITS 时使用系统朗读；默认走预烘焙 WAV → 失败则 SoVITS（熊大声线） */
    const storyAudioFallbackBrowser =
      import.meta.env.VITE_STORY_AUDIO_FALLBACK_BROWSER === "1" ||
      String(import.meta.env.VITE_STORY_AUDIO_FALLBACK_BROWSER || "").toLowerCase() === "true";

    let storyUrls: string[] = [];
    if (interactionType === "story_interaction" && clipIds.length > 0) {
      const storyVoiceIds = o.story_voice_ids;
      const rawVoiceIds = Array.isArray(storyVoiceIds)
        ? storyVoiceIds.filter((x): x is string => typeof x === "string" && x.trim().length > 0)
        : [];
      storyUrls =
        rawVoiceIds.length > 0
          ? rawVoiceIds.map((id) => theaterVoiceUrl(id.trim()))
          : Array.isArray(storyVoiceIds)
            ? storyClipIdsToVoiceUrls(clipIds)
            : [];
    }

    const playLocalStory =
      interactionType === "story_interaction" && storyUrls.length > 0 && !prebakedOff;

    const storyFallbackSpeak = typeof o.speech === "string" ? o.speech.trim() : "";

    const storyFallbackMode: "tts" | "browser" = storyAudioFallbackBrowser ? "browser" : "tts";

    if (hadSpeech && !playLocalStory) {
      if (interactionType === "story_interaction" && storyAudioFallbackBrowser) {
        const raw = typeof o.speech === "string" ? o.speech.trim() : "";
        if (raw) {
          if (sg) sg.speakBrowser(raw);
          else {
            speakBrowserFallback(raw.replace(/\n+/g, " "), notifyPlaybackDone);
          }
        }
      } else {
        announcePayloadSpeechWrapped(o);
      }
    }
    if (playLocalStory) {
      if (sg) sg.prebaked(storyUrls, storyFallbackSpeak || undefined, storyFallbackMode);
      else {
        playPrebakedWavSequence(storyUrls, storyFallbackSpeak || undefined, notifyPlaybackDone, storyFallbackMode);
      }
    }

    if (!hadSpeech && clipIds.length > 0) {
      ctx.setSubtitle(
        `剧情/选模式（SMPL）：${clipIds.join(" → ")} — 可在 clipIdToSmplPath.ts 调整动作映射`
      );
    }
    if (clipIds.length > 0) {
      playSmplPathSequence(clipIdsToSmplPaths(clipIds), ctx, smplStep);
    }
    if (targetMode === "story") maybeEnterStoryTab();
    end();
    return;
  }

  if (interactionType === "map_query") {
    maybeEnterMapTab();
    const hadSpeech = setSpeechFromPayload(ctx, o);
    const voiceId = voiceIdFromPayload(o);
    const speech = typeof o.speech === "string" ? o.speech.trim() : "";
    if (voiceId && speech) {
      if (sg) sg.prebaked([theaterVoiceUrl(voiceId)], speech, "tts");
      else playPrebakedWavSequence([theaterVoiceUrl(voiceId)], speech, notifyPlaybackDone, "tts");
    } else if (hadSpeech) {
      announcePayloadSpeechWrapped(o);
    }
    ctx.setCurrentSmplPath("—（地图模式不驱动 3D）");
    end();
    return;
  }

  if (interactionType === "random_interaction") {
    maybeEnterVoiceTab();
    const speechRaw = typeof o.speech === "string" ? o.speech.trim() : "";
    setSpeechFromPayload(ctx, o);

    const motionType = typeof o.motion_type === "string" ? o.motion_type : "";

    if (motionType === "generated") {
      const speech = speechRaw;
      const desc =
        typeof o.motion_description === "string" && o.motion_description.trim()
          ? o.motion_description.trim()
          : "";
      if (desc) {
        ctx.setSubtitle(speech ? `${speech}\n（生成动作说明）${desc}` : `（生成动作说明）${desc}`);
      }
      if (speechRaw) speakLine(speechRaw);
      const fallback = "SmplhRetarget/摊手疑问.json";
      sendSmplStreamingRelativePath(fallback);
      ctx.setCurrentSmplPath(fallback);
      end();
      return;
    }

    if (speechRaw) speakLine(speechRaw);

    const actions = Array.isArray(o.actions)
      ? o.actions.filter((x): x is string => typeof x === "string" && x.trim().length > 0)
      : [];
    if (actions.length > 0) {
      const paths = actions.map((a) => chineseActionToSmplPath(a));
      playSmplPathSequence(paths, ctx, smplStep);
    }
    end();
    return;
  }

  /* 兜底：未写 interaction_type 时的兼容 */
  if (clipIds.length > 0) {
    const hadSp = setSpeechFromPayload(ctx, o);
    if (hadSp) announcePayloadSpeechWrapped(o);
    if (!hadSp) {
      ctx.setSubtitle(`片段（SMPL）：${clipIds.join(" → ")}`);
    }
    playSmplPathSequence(clipIdsToSmplPaths(clipIds), ctx, smplStep);
    end();
    return;
  }

  const actions = Array.isArray(o.actions)
    ? o.actions.filter((x): x is string => typeof x === "string" && x.trim().length > 0)
    : [];
  if (actions.length > 0) {
    const hadSp = setSpeechFromPayload(ctx, o);
    if (hadSp) announcePayloadSpeechWrapped(o);
    playSmplPathSequence(
      actions.map((a) => chineseActionToSmplPath(a)),
      ctx,
      smplStep
    );
    end();
    return;
  }

  if (setSpeechFromPayload(ctx, o)) announcePayloadSpeechWrapped(o);
  end();
}
