/** Unity 导航到达后播放到站讲解（由 App 注册 ctx 与 handleBearAgentPayload） */
let mapArrivalHandler: ((payload: Record<string, unknown>) => void) | null = null;

export function registerMapArrivalPlayback(
  handler: (payload: Record<string, unknown>) => void
): void {
  mapArrivalHandler = handler;
}

export function dispatchMapArrivalPlayback(payload: Record<string, unknown>): void {
  if (!mapArrivalHandler) {
    console.warn("[地图导航] 到站讲解未注册 handler，跳过播放");
    return;
  }
  // 等 Unity 切回互动熊（SMPL+BlendShape）后再播 TTS/口型/动作
  window.setTimeout(() => {
    mapArrivalHandler?.(payload);
  }, 650);
}
