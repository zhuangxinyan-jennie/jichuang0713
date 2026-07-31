/** GameObject 名与 Unity 场景中一致 */
const UNITY_BRIDGE_OBJECT = "UnityBridge";
const SMPL_METHOD = "PlaySmplStreamingRelativePath";
const CLIP_METHOD = "PlayClipById";
const LIP_SYNC_START_METHOD = "StartSpeechLipSync";
const LIP_SYNC_STOP_METHOD = "StopSpeechLipSync";
const LIP_SYNC_LEVEL_METHOD = "SetSpeechLipSyncLevel";

export type UnityWebGLHandle = {
  SendMessage: (objectName: string, methodName: string, value?: string) => void;
};

let cachedInstance: UnityWebGLHandle | undefined;

export function setGlobalUnityInstance(instance: UnityWebGLHandle | null | undefined): void {
  cachedInstance = instance ?? undefined;
  if (typeof window !== "undefined" && instance) {
    (window as Window & { unityInstance?: UnityWebGLHandle }).unityInstance = instance;
  }
}

export function isUnityInstanceReady(): boolean {
  const w = window as Window & { unityInstance?: UnityWebGLHandle };
  return !!(cachedInstance ?? w.unityInstance)?.SendMessage;
}

function sendUnityBridgeMessage(methodName: string, value?: string): void {
  const w = window as Window & { unityInstance?: UnityWebGLHandle };
  const inst = cachedInstance ?? w.unityInstance;
  if (!inst?.SendMessage) return;

  try {
    if (value === undefined) {
      inst.SendMessage(UNITY_BRIDGE_OBJECT, methodName);
    } else {
      inst.SendMessage(UNITY_BRIDGE_OBJECT, methodName, value);
    }
  } catch (e) {
    console.error(`[unitySendClip] SendMessage ${methodName} 失败`, e);
  }
}

/** TTS 开始：熊大口型（与 Stop 成对；振幅由 SetSpeechLipSyncLevel 推送）。 */
export function startUnitySpeechLipSync(): void {
  sendUnityBridgeMessage(LIP_SYNC_START_METHOD);
}

/** TTS 结束或打断：停止口型驱动。 */
export function stopUnitySpeechLipSync(): void {
  sendUnityBridgeMessage(LIP_SYNC_STOP_METHOD);
}

/** 发送 0–1 音量振幅（Web Audio RMS 归一化）。 */
export function sendUnitySpeechLipSyncLevel(level: number): void {
  const clamped = Math.min(1, Math.max(0, level));
  sendUnityBridgeMessage(LIP_SYNC_LEVEL_METHOD, clamped.toFixed(4));
}

/**
 * 播放 StreamingAssets 下 SMPL-H JSON（相对路径，如 `SmplhRetarget/挥手致意.json`）。
 */
export function sendSmplStreamingRelativePath(relativePath: string): void {
  const p = relativePath?.trim();
  if (!p) return;

  const w = window as Window & { unityInstance?: UnityWebGLHandle };
  const inst = cachedInstance ?? w.unityInstance;
  if (inst?.SendMessage) {
    try {
      inst.SendMessage(UNITY_BRIDGE_OBJECT, SMPL_METHOD, p);
    } catch (e) {
      console.error("[sendSmplStreamingRelativePath] SendMessage 失败", e);
    }
  } else {
    console.log("[WebGL 未加载] 将播放 SMPL JSON =", p);
  }
}

/**
 * 播放 Animator clip（clip_id 需在 Unity ClipIdPlayer 映射表中，如 mode_select_intro）。
 */
export function sendClipById(clipId: string): void {
  const id = clipId?.trim();
  if (!id) return;

  const w = window as Window & { unityInstance?: UnityWebGLHandle };
  const inst = cachedInstance ?? w.unityInstance;
  if (inst?.SendMessage) {
    try {
      inst.SendMessage(UNITY_BRIDGE_OBJECT, CLIP_METHOD, id);
    } catch (e) {
      console.error("[sendClipById] SendMessage 失败", e);
    }
  } else {
    console.log("[WebGL 未加载] 将播放 clip_id =", id);
  }
}
