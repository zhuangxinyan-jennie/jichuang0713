import type { UnityWebGLHandle } from "../services/unitySendClip";

const UNITY_BRIDGE_OBJECT = "UnityBridge";

export function sendUnityEmergencyStop(): void {
  const win = window as Window & { unityInstance?: UnityWebGLHandle };
  const instance = win.unityInstance;
  if (!instance?.SendMessage) return;
  try {
    instance.SendMessage(UNITY_BRIDGE_OBJECT, "EmergencyStop", "");
  } catch (error) {
    console.error("[safety] Unity EmergencyStop failed", error);
  }
}

