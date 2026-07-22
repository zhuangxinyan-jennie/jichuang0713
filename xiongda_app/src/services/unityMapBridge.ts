import type { UnityWebGLHandle } from "./unitySendClip";
import { isMergedUnityAvailableSync, setMergedPlayMode } from "./unityMergedMode";

const MAP_BRIDGE_OBJECT = "ParkMapUnityBridge";

let cachedMapInstance: UnityWebGLHandle | undefined;
let mapUnityFullyReady = false;
let pendingNavigation: (() => void) | null = null;

export type PathWorldPoint = {
  x: number;
  y?: number;
  z: number;
};

export function setMapUnityInstance(instance: UnityWebGLHandle | null | undefined): void {
  cachedMapInstance = instance ?? undefined;
  if (typeof window !== "undefined" && instance) {
    window.mapUnityInstance = instance;
  }
}

export function isMapUnityInstanceReady(): boolean {
  const w = window as Window & { mapUnityInstance?: UnityWebGLHandle };
  return !!(cachedMapInstance ?? w.mapUnityInstance)?.SendMessage;
}

/** 地图 WebGL 场景加载完成（progress≈1）后调用。 */
export function markMapUnityFullyReady(): void {
  mapUnityFullyReady = true;
  if (pendingNavigation) {
    const run = pendingNavigation;
    pendingNavigation = null;
    window.setTimeout(run, 300);
  }
}

export function isMapUnityFullyReady(): boolean {
  return mapUnityFullyReady && isMapUnityInstanceReady();
}

function mapInstance(): UnityWebGLHandle | undefined {
  const w = window as Window & {
    mapUnityInstance?: UnityWebGLHandle;
    unityInstance?: UnityWebGLHandle;
  };
  // 合并包：导航与表演共用同一 WebGL 实例
  return cachedMapInstance ?? w.mapUnityInstance ?? w.unityInstance;
}

function sendMapMessage(method: string, arg: string): void {
  const inst = mapInstance();
  if (!inst?.SendMessage) {
    console.log(`[地图 WebGL 未加载] ${method}`, arg);
    return;
  }
  try {
    inst.SendMessage(MAP_BRIDGE_OBJECT, method, arg);
  } catch (e) {
    console.error(`[${method}] SendMessage 失败`, e);
  }
}

/** 沿 Agent 下发的 path_world 逐点行走（推荐）。 */
export function sendNavigateAlongPath(points: PathWorldPoint[]): void {
  if (!points?.length) return;
  const payload = JSON.stringify(
    points.map((p) => ({
      x: p.x,
      y: typeof p.y === "number" ? p.y : 0.22,
      z: p.z,
    }))
  );
  console.info("[地图导航] path_world 点数 =", points.length, payload);
  sendMapMessage("NavigateAlongPathJson", payload);
}

/** 按中文地名查 StreamingAssets/poi_registry.json 后走过去。 */
export function sendNavigateToPlace(placeName: string): void {
  const name = placeName?.trim();
  if (!name) return;
  console.info("[地图导航] 目的地 =", name);
  sendMapMessage("NavigateToPlace", name);
}

export function sendCancelMapNavigation(): void {
  sendMapMessage("CancelNavigation", "");
}

/** 地图 WebGL 加载完成后执行导航（最多等待 maxWaitMs）。 */
export function scheduleMapNavigation(run: () => void, maxWaitMs = 90_000): void {
  if (isMapUnityFullyReady()) {
    window.setTimeout(run, 300);
    return;
  }

  pendingNavigation = run;
  const start = Date.now();
  const tick = () => {
    if (isMapUnityFullyReady()) {
      return;
    }
    if (Date.now() - start > maxWaitMs) {
      pendingNavigation = null;
      console.warn("[地图导航] WebGL 等待超时，未能发送导航指令");
      return;
    }
    window.setTimeout(tick, 400);
  };
  tick();
}

export function normalizePathWorld(raw: unknown): PathWorldPoint[] {
  if (!Array.isArray(raw)) return [];
  const out: PathWorldPoint[] = [];
  for (const item of raw) {
    if (!item || typeof item !== "object") continue;
    const o = item as Record<string, unknown>;
    const x = Number(o.x);
    const z = Number(o.z);
    if (!Number.isFinite(x) || !Number.isFinite(z)) continue;
    const y = Number(o.y);
    out.push({ x, y: Number.isFinite(y) ? y : 0.22, z });
  }
  return out;
}

/**
 * 从 map_query Agent 响应触发 3D 导航。
 */
export function triggerMapNavigationFromPayload(payload: Record<string, unknown>): void {
  if (payload.found === false) return;

  const pathWorld = normalizePathWorld(payload.path_world);
  const destination =
    typeof payload.destination === "string" ? payload.destination.trim() : "";

  scheduleMapNavigation(() => {
    if (isMergedUnityAvailableSync()) {
      setMergedPlayMode("map");
    }
    if (pathWorld.length >= 2) {
      // 沿 Agent 下发的密集 path_world 逐点行走（沿路，非直线）
      sendNavigateAlongPath(pathWorld);
      return;
    }
    if (pathWorld.length === 1) {
      sendNavigateAlongPath(pathWorld);
      return;
    }
    if (destination) {
      // 仅无 path_world 时回退：旧版 WebGL 直走到 POI
      sendNavigateToPlace(destination);
    }
  });
}
