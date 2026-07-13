/** GameObject 名与 Unity 场景中一致 */
const UNITY_BRIDGE_OBJECT = "UnityBridge";
const SMPL_METHOD = "PlaySmplStreamingRelativePath";
const CLIP_METHOD = "PlayClipById";

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
