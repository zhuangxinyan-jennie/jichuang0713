import { useEffect, useRef, useState } from "react";
import {
  applyServerMeta,
  createIdleState,
  DEFAULT_GESTURE_CURSOR_CONFIG,
  GestureCursorController,
  type GestureCursorConfig,
  type GestureCursorState,
  type GestureLandmark,
} from "./gestureCursorController";

const LANDMARKS_URL = "/gesture-api/api/landmarks";
const POLL_MS = 20;

type LandmarksPayload = {
  hand_landmarks?: GestureLandmark[];
  meta?: { mirror_frame?: boolean };
};

/**
 * 轮询本机 MediaPipe landmarks 服务，驱动 GestureCursorController。
 * 服务不可用时自动降级：鼠标移动 = 光标，左键按住 = 捏合。
 */
export function useGestureCursor(enabled: boolean) {
  const [state, setState] = useState<GestureCursorState>(createIdleState);
  const [serviceOk, setServiceOk] = useState(false);
  const [mockMode, setMockMode] = useState(false);
  const controllerRef = useRef(new GestureCursorController());
  const configRef = useRef<GestureCursorConfig>({ ...DEFAULT_GESTURE_CURSOR_CONFIG });
  const mockPinchingRef = useRef(false);
  const mockPosRef = useRef({ x: 0.5, y: 0.5 });
  const failCountRef = useRef(0);

  useEffect(() => {
    if (!enabled) {
      setState(createIdleState());
      controllerRef.current.state = createIdleState();
      return;
    }

    configRef.current = { ...DEFAULT_GESTURE_CURSOR_CONFIG };
    let cancelled = false;
    let pollId = 0;
    let rafId = 0;

    const pull = async () => {
      if (cancelled) return;
      try {
        const res = await fetch(LANDMARKS_URL, { cache: "no-store" });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = (await res.json()) as LandmarksPayload;
        failCountRef.current = 0;
        setServiceOk(true);
        setMockMode(false);
        applyServerMeta(configRef.current, data.meta);
        const pts = Array.isArray(data.hand_landmarks) ? data.hand_landmarks : [];
        controllerRef.current.update(pts.length >= 9 ? pts : null, configRef.current);
      } catch {
        failCountRef.current += 1;
        if (failCountRef.current >= 8) {
          setServiceOk(false);
          setMockMode(true);
          // 鼠标演示：用假 landmarks（掌心 + 拇指/食指）驱动同一控制器
          const { x, y } = mockPosRef.current;
          const pinch = mockPinchingRef.current;
          const tipGap = pinch ? 0.02 : 0.12;
          const fake: GestureLandmark[] = Array.from({ length: 21 }, () => ({ x, y, z: 0 }));
          for (const i of [0, 5, 9, 13, 17]) fake[i] = { x, y, z: 0 };
          fake[4] = { x: x - tipGap / 2, y, z: 0 };
          fake[8] = { x: x + tipGap / 2, y, z: 0 };
          controllerRef.current.update(fake, configRef.current);
        }
      }
    };

    const onMove = (e: MouseEvent) => {
      mockPosRef.current = {
        x: e.clientX / Math.max(1, window.innerWidth),
        y: e.clientY / Math.max(1, window.innerHeight),
      };
    };
    const onDown = (e: MouseEvent) => {
      if (e.button === 0) mockPinchingRef.current = true;
    };
    const onUp = () => {
      mockPinchingRef.current = false;
    };
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mousedown", onDown);
    window.addEventListener("mouseup", onUp);

    pollId = window.setInterval(() => void pull(), POLL_MS);

    const tick = () => {
      if (cancelled) return;
      const next = controllerRef.current.tickDisplay(configRef.current);
      setState(next);
      rafId = window.requestAnimationFrame(tick);
    };
    rafId = window.requestAnimationFrame(tick);

    return () => {
      cancelled = true;
      window.clearInterval(pollId);
      window.cancelAnimationFrame(rafId);
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mousedown", onDown);
      window.removeEventListener("mouseup", onUp);
    };
  }, [enabled]);

  return { state, serviceOk, mockMode };
}
