/**
 * 地图问路：协调「导览熊跑路 + 路线 TTS」与「切互动熊 + 到站讲解」的时序。
 *
 * 规则：到达后仍保持导览模式，直到路线 TTS 全部播完 + postSpeechHoldMs，再切 chat 并播 map_arrival。
 */
import { postMultimodalPlaybackDone } from "../bear_pipeline/bearAgentClient";

const POST_ROUTE_SPEECH_HOLD_MS = 1000;

let routeSpeechDone: Promise<void> = Promise.resolve();
let resolveRouteSpeech: (() => void) | null = null;

/** 导航会话期间推迟释放播音闸门（路线 TTS 结束到到站讲解结束，避免熊大跑路时 PC 音响被板端麦录入）。 */
let mapNavPlaybackGateHeld = false;

export function beginMapNavigationGateHold(): void {
  mapNavPlaybackGateHeld = true;
}

export function shouldDeferMapNavigationPlaybackGateRelease(): boolean {
  return mapNavPlaybackGateHeld;
}

/** 到站讲解播完后调用，释放导航期间持有的闸门。 */
export function finishMapNavigationPlaybackGate(): void {
  if (!mapNavPlaybackGateHeld) return;
  mapNavPlaybackGateHeld = false;
  void postMultimodalPlaybackDone();
}

export function cancelMapNavigationGateHold(): void {
  mapNavPlaybackGateHeld = false;
}

export function beginMapQueryRouteSpeech(): void {
  routeSpeechDone = new Promise<void>((resolve) => {
    resolveRouteSpeech = resolve;
  });
}

export function completeMapQueryRouteSpeech(): void {
  resolveRouteSpeech?.();
  resolveRouteSpeech = null;
}

/** map_query 无语音时调用 */
export function skipMapQueryRouteSpeechWait(): void {
  completeMapQueryRouteSpeech();
}

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

/**
 * Unity 上报到达后：等路线 TTS 结束 → 再等 1s → 切互动熊 → 上报位置 → 到站讲解。
 */
export async function runNavigationArrivalHandoff(args: {
  arrivalJson: string;
  postMapLocation: () => Promise<{ arrival?: Record<string, unknown> | null }>;
  confirmChatAtArrival: (arrivalJson: string) => void;
  onHandoffComplete: () => void;
  dispatchArrivalPlayback: (payload: Record<string, unknown>) => void;
}): Promise<void> {
  try {
    await routeSpeechDone;
    await delay(POST_ROUTE_SPEECH_HOLD_MS);
    args.confirmChatAtArrival(args.arrivalJson);
    const result = await args.postMapLocation();
    args.onHandoffComplete();
    if (result.arrival && typeof result.arrival === "object") {
      args.dispatchArrivalPlayback(result.arrival);
    } else if (mapNavPlaybackGateHeld) {
      finishMapNavigationPlaybackGate();
    }
  } catch (e) {
    console.warn("[地图导航] 到达交接失败", e);
    args.onHandoffComplete();
    if (mapNavPlaybackGateHeld) {
      finishMapNavigationPlaybackGate();
    }
  } finally {
    routeSpeechDone = Promise.resolve();
    resolveRouteSpeech = null;
  }
}
