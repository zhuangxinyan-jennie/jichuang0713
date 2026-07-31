import type { UnityWebGLHandle } from "./unitySendClip";
import { isUnityInstanceReady } from "./unitySendClip";
import { setMergedPlayMode } from "./unityMergedMode";
import { dispatchMapArrivalPlayback } from "../bear_pipeline/mapArrivalDispatch";
import { runNavigationArrivalHandoff } from "./mapNavigationHandoff";

const MAP_BRIDGE_OBJECT = "ParkMapUnityBridge";

let cachedMapInstance: UnityWebGLHandle | undefined;
let mapUnityFullyReady = false;
let pendingNavigation: (() => void) | null = null;
/** 问路导航进行中：防止 App 初始化 effect 把模式打回 chat */
let mapNavigationActive = false;

export function beginMapNavigationSession(): void {
  mapNavigationActive = true;
}

export function endMapNavigationSession(): void {
  mapNavigationActive = false;
}

export function isMapNavigationActive(): boolean {
  return mapNavigationActive;
}

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

/** Unity SendMessage 可用即可发导航（不必等 progress=1）。 */
function navigationUnityReady(): boolean {
  return isMapUnityInstanceReady() || isUnityInstanceReady();
}

function flushPendingNavigation(delayMs = 300): void {
  if (!pendingNavigation) return;
  const run = pendingNavigation;
  pendingNavigation = null;
  window.setTimeout(run, delayMs);
}

/** 地图 WebGL 场景加载完成（progress≈1）后调用。 */
export function markMapUnityFullyReady(): void {
  mapUnityFullyReady = true;
  flushPendingNavigation(300);
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

function sendMergedModeMessage(method: string, arg: string): void {
  const inst = mapInstance();
  if (!inst?.SendMessage) {
    console.log(`[合并模式 WebGL 未加载] ${method}`, arg);
    return;
  }
  try {
    inst.SendMessage("MergedPlayModeBridge", method, arg);
  } catch (e) {
    console.error(`[MergedPlayModeBridge.${method}] SendMessage 失败`, e);
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
  sendNavigationDestination(name);
  console.info("[地图导航] 目的地 =", name);
  sendMapMessage("NavigateToPlace", name);
}

/** 告知 Unity 本次导航目的地（到达后随坐标回传 Agent）。 */
export function sendNavigationDestination(placeName: string): void {
  const name = placeName?.trim();
  if (!name) return;
  sendMapMessage("SetNavigationDestination", name);
}

export function sendCancelMapNavigation(): void {
  sendMapMessage("CancelNavigation", "");
}

/** 地图 WebGL 加载完成后执行导航（最多等待 maxWaitMs）。 */
export function scheduleMapNavigation(run: () => void, maxWaitMs = 90_000): void {
  if (navigationUnityReady()) {
    window.setTimeout(run, 300);
    return;
  }

  pendingNavigation = run;
  const start = Date.now();
  const tick = () => {
    if (navigationUnityReady()) {
      flushPendingNavigation(300);
      return;
    }
    if (Date.now() - start > maxWaitMs) {
      pendingNavigation = null;
      console.warn("[地图导航] WebGL 等待超时，未能发送导航指令");
      endMapNavigationSession();
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

export type NavArrivalPayload = {
  x: number;
  y?: number;
  z: number;
  destination?: string;
};

let navArrivalHandlerInstalled = false;

/** Unity WebGL 导航到达回调（由 jslib 调用 window.xiongdaOnNavArrived）。 */
export function installNavArrivalHandler(): void {
  if (typeof window === "undefined" || navArrivalHandlerInstalled) return;
  navArrivalHandlerInstalled = true;

  (window as Window & { xiongdaOnNavArrived?: (payloadJson: string) => void }).xiongdaOnNavArrived = (
    payloadJson: string
  ) => {
    void handleNavArrivalPayload(payloadJson);
  };
}

async function handleNavArrivalPayload(payloadJson: string): Promise<void> {
  try {
    const raw = JSON.parse(payloadJson) as NavArrivalPayload;
    const x = Number(raw.x);
    const y = Number(raw.y);
    const z = Number(raw.z);
    if (!Number.isFinite(x) || !Number.isFinite(z)) return;

    const destination =
      typeof raw.destination === "string" && raw.destination.trim() ? raw.destination.trim() : undefined;

    console.info("[地图导航] 到达（等待路线 TTS 结束后再切互动熊）", { x, z, destination });

    const arrivalJson = JSON.stringify({
      x,
      y: Number.isFinite(y) ? y : 0.22,
      z,
      destination: destination ?? "",
    });

    const { postMapLocationUpdate } = await import("../bear_pipeline/bearAgentClient");

    await runNavigationArrivalHandoff({
      arrivalJson,
      confirmChatAtArrival: (json) => {
        sendMergedModeMessage("ConfirmNavigationArrival", json);
        setMergedPlayMode("chat");
      },
      postMapLocation: () =>
        postMapLocationUpdate({ x, z, destination }).then((result) => ({
          arrival: result.arrival as Record<string, unknown> | null | undefined,
        })),
      onHandoffComplete: () => {
        endMapNavigationSession();
      },
      dispatchArrivalPlayback: dispatchMapArrivalPlayback,
    });

    console.info("[地图导航] 到达交接完成");
  } catch (e) {
    console.warn("[地图导航] 到达位置上报失败", e);
    endMapNavigationSession();
  }
}

/**
 * 从 map_query Agent 响应触发 3D 导航。
 */
export function triggerMapNavigationFromPayload(payload: Record<string, unknown>): void {
  if (payload.found === false) return;

  const pathWorld = normalizePathWorld(payload.path_world);
  const destination =
    typeof payload.destination === "string" ? payload.destination.trim() : "";

  beginMapNavigationSession();
  // 立刻切导览熊 + 跟拍镜头；SendMessage 未就绪时会进入 pendingPlayMode 队列
  setMergedPlayMode("map");
  console.info("[地图导航] 触发导览", { destination, pathPoints: pathWorld.length });

  scheduleMapNavigation(() => {
    if (destination) {
      sendNavigationDestination(destination);
    }
    if (pathWorld.length >= 2) {
      sendNavigateAlongPath(pathWorld);
      return;
    }
    if (pathWorld.length === 1) {
      sendNavigateAlongPath(pathWorld);
      return;
    }
    if (destination) {
      sendNavigateToPlace(destination);
    }
  });
}
