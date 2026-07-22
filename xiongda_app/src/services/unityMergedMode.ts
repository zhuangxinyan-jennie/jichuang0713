import { markMapUnityFullyReady, setMapUnityInstance } from "./unityMapBridge";
import { isUnityInstanceReady, type UnityWebGLHandle } from "./unitySendClip";

const MERGED_MODE_BRIDGE = "MergedPlayModeBridge";
const MERGED_BASE = "/webgl-merged";

let mergedAvailable: boolean | null = null;
let mergedProbePromise: Promise<boolean> | null = null;
let pendingPlayMode: "chat" | "map" | null = null;

/**
 * 探测 public/webgl-merged/build-info.json。
 * 未构建合并包时返回 false → 前端继续用双包（可回退）。
 */
export function probeMergedUnityAvailable(): Promise<boolean> {
  if (mergedAvailable !== null) return Promise.resolve(mergedAvailable);
  if (mergedProbePromise) return mergedProbePromise;

  const forced = (import.meta.env.VITE_UNITY_MERGED as string | undefined)?.trim();
  if (forced === "0" || forced === "false" || forced === "off") {
    mergedAvailable = false;
    return Promise.resolve(false);
  }
  if (forced === "1" || forced === "true" || forced === "on") {
    // 仍探测文件，避免空包硬开
  }

  mergedProbePromise = fetch(`${MERGED_BASE}/build-info.json`, { cache: "no-store" })
    .then(async (res) => {
      if (!res.ok) {
        mergedAvailable = false;
        return false;
      }
      try {
        const j = (await res.json()) as { merged?: boolean };
        mergedAvailable = j.merged === true || true;
      } catch {
        mergedAvailable = true;
      }
      return mergedAvailable;
    })
    .catch(() => {
      mergedAvailable = false;
      return false;
    });

  return mergedProbePromise;
}

export function isMergedUnityAvailableSync(): boolean {
  return mergedAvailable === true;
}

export function mergedUnityBasePath(): string {
  return MERGED_BASE;
}

/** 合并包加载成功后：同一实例同时充当熊大 + 地图桥。 */
export function registerMergedUnityInstance(instance: UnityWebGLHandle): void {
  setMapUnityInstance(instance);
  markMapUnityFullyReady();
  if (typeof window !== "undefined") {
    (window as Window & { unityInstance?: UnityWebGLHandle }).unityInstance = instance;
  }
  if (pendingPlayMode) {
    const mode = pendingPlayMode;
    pendingPlayMode = null;
    window.setTimeout(() => setMergedPlayMode(mode), 400);
  }
}

export function setMergedPlayMode(mode: "chat" | "map"): void {
  const w = window as Window & { unityInstance?: UnityWebGLHandle; mapUnityInstance?: UnityWebGLHandle };
  const inst = w.unityInstance ?? w.mapUnityInstance;
  if (!inst?.SendMessage) {
    pendingPlayMode = mode;
    console.log("[merged] WebGL 未就绪，稍后 SetPlayMode", mode);
    return;
  }
  try {
    inst.SendMessage(MERGED_MODE_BRIDGE, "SetPlayMode", mode);
    inst.SendMessage(MERGED_MODE_BRIDGE, "SetInteractionMode", mode);
  } catch (e) {
    console.error("[merged] SetPlayMode failed", e);
  }
}

export function syncMergedPlayModeFromTopNav(topNav: string): void {
  // 全图互动默认近景聊天熊；具体问路时 triggerMapNavigationFromPayload 会切 map
  if (topNav === "world" || topNav === "voice") {
    setMergedPlayMode("chat");
    return;
  }
  if (topNav === "map") {
    setMergedPlayMode("map");
    return;
  }
  setMergedPlayMode("chat");
}

export function canUseMergedUnityNow(): boolean {
  return isMergedUnityAvailableSync() && isUnityInstanceReady();
}
