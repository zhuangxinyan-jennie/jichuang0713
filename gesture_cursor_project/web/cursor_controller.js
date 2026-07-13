/**
 * 手势虚拟光标（改进版）
 * - 修复左右镜像：服务端已 flip 时 mirrorX 应为 false
 * - 掌心中心比食指尖更稳（参考 hand-tracking-with-controls 等项目）
 * - One Euro Filter 平滑（MediaPipe 社区常用，优于单纯 EMA）
 * - 捏合防抖 + 点击时锁定光标位置（减少漂移误点）
 */
import { OneEuroFilter } from "./one_euro_filter.js";

export const DEFAULT_GESTURE_CURSOR_CONFIG = {
  enabled: true,
  /** 服务端 cv2.flip 后应为 false；未 flip 时改为 true */
  mirrorX: false,
  /** 光标位置：palm=掌心更稳，index=食指尖更灵敏 */
  positionSource: "palm",
  /** oneEuro | ema */
  filterMode: "oneEuro",
  smoothing: 0.22,
  oneEuroMinCutoff: 1.0,
  oneEuroBeta: 0.06,
  /** 手在画面边缘留白，映射到全屏（提高可达范围） */
  mapMargin: 0.1,
  /** 死区：过大会造成“停一下再跳”；默认关闭，交给 One Euro 处理抖动 */
  deadZoneNorm: 0,
  /** 手短暂丢失时保留上一帧（减少闪烁/顿挫） */
  holdFramesOnLost: 4,
  /** 浏览器每帧向目标位置插值（与 HTTP 轮询解耦，消除阶梯感） */
  displayLerp: 0.55,
  pinchDownDistance: 0.05,
  pinchUpDistance: 0.068,
  pinchDebounceFrames: 3,
  lockPositionOnPress: true,
  clickHoldMs: 200,
  cooldownMs: 450,
  staleAfterMs: 900,
  /** false = 仅跟踪/捏合状态，不触发 click（用于拖拽类游戏） */
  enableClick: true,
};

const INDEX_TIP = 8;
const THUMB_TIP = 4;
const PALM_INDICES = [0, 5, 9, 13, 17];

function clamp01(v) {
  return Math.min(1, Math.max(0, v));
}

function distance(a, b) {
  return Math.hypot(a.x - b.x, a.y - b.y);
}

function pointLabel(target) {
  if (!target) return "";
  const text =
    target.getAttribute("aria-label") ||
    target.textContent ||
    target.dataset.gestureLabel ||
    target.tagName;
  return String(text).replace(/\s+/g, " ").trim().slice(0, 16);
}

function interactiveTargetAt(clientX, clientY) {
  const raw = document.elementFromPoint(clientX, clientY);
  if (!(raw instanceof HTMLElement)) return null;
  return raw.closest(GESTURE_CLICKABLE_SELECTOR);
}

function clickTarget(target) {
  target.focus({ preventScroll: true });
  target.dispatchEvent(new PointerEvent("pointerdown", { bubbles: true, pointerType: "touch" }));
  target.dispatchEvent(new PointerEvent("pointerup", { bubbles: true, pointerType: "touch" }));
  target.click();
}

function pickPosition(points, source) {
  if (source === "index" && points[INDEX_TIP]) {
    return points[INDEX_TIP];
  }
  let sx = 0;
  let sy = 0;
  let n = 0;
  for (const i of PALM_INDICES) {
    if (!points[i]) continue;
    sx += points[i].x;
    sy += points[i].y;
    n += 1;
  }
  if (!n) return points[INDEX_TIP] || null;
  return { x: sx / n, y: sy / n };
}

export const GESTURE_CLICKABLE_SELECTOR =
  "button,a,input,textarea,select,[role='button'],[data-gesture-clickable]";

export const GESTURE_NEAR_TARGET_RADIUS_PX = 72;

export function createIdleState() {
  return {
    active: false,
    phase: "idle",
    clientX: 0,
    clientY: 0,
    progress: 0,
    targetLabel: "",
    hasTarget: false,
    nearTarget: false,
    lastUpdatedAt: 0,
  };
}

function targetProximity(clientX, clientY, target) {
  if (!target) return { hasTarget: false, nearTarget: false };
  const rect = target.getBoundingClientRect();
  const cx = rect.left + rect.width / 2;
  const cy = rect.top + rect.height / 2;
  const dist = Math.hypot(clientX - cx, clientY - cy);
  return {
    hasTarget: true,
    nearTarget: dist <= GESTURE_NEAR_TARGET_RADIUS_PX,
  };
}

export function applyServerMeta(config, meta) {
  if (!meta) return config;
  if (typeof meta.mirror_frame === "boolean") {
    config.mirrorX = !meta.mirror_frame;
  }
  return config;
}

export class GestureCursorController {
  constructor() {
    this.state = createIdleState();
    this.pinchStartedAt = 0;
    this.pinchFrameCount = 0;
    this.cooldownUntil = 0;
    this.filterX = new OneEuroFilter({ freq: 60, mincutoff: 1.0, beta: 0.06 });
    this.filterY = new OneEuroFilter({ freq: 60, mincutoff: 1.0, beta: 0.06 });
    this.lastNormX = null;
    this.lastNormY = null;
    this.lastInputNormX = null;
    this.lastInputNormY = null;
    this.missedFrames = 0;
    this.displayClientX = 0;
    this.displayClientY = 0;
    this.lockedClientX = 0;
    this.lockedClientY = 0;
  }

  resetFilters() {
    this.filterX.reset();
    this.filterY.reset();
    this.lastNormX = null;
    this.lastNormY = null;
    this.lastInputNormX = null;
    this.lastInputNormY = null;
    this.missedFrames = 0;
  }

  /** 每帧调用：把显示坐标插值到逻辑坐标，消除 HTTP 轮询带来的阶梯感 */
  tickDisplay(config, now = performance.now()) {
    if (!this.state.active) {
      this.displayClientX = 0;
      this.displayClientY = 0;
      return this.state;
    }
    const alpha = clamp01(config.displayLerp ?? 0.55);
    if (!this.displayClientX && !this.displayClientY) {
      this.displayClientX = this.state.clientX;
      this.displayClientY = this.state.clientY;
    }
    this.displayClientX += (this.state.clientX - this.displayClientX) * alpha;
    this.displayClientY += (this.state.clientY - this.displayClientY) * alpha;
    return {
      ...this.state,
      clientX: this.displayClientX,
      clientY: this.displayClientY,
      lastUpdatedAt: now,
    };
  }

  smoothNorm(normX, normY, config, now) {
    if (config.filterMode === "ema") {
      const alpha = clamp01(config.smoothing);
      const x =
        this.lastNormX === null ? normX : this.lastNormX + (normX - this.lastNormX) * alpha;
      const y =
        this.lastNormY === null ? normY : this.lastNormY + (normY - this.lastNormY) * alpha;
      this.lastNormX = x;
      this.lastNormY = y;
      return { x, y };
    }

    this.filterX.mincutoff = config.oneEuroMinCutoff;
    this.filterX.beta = config.oneEuroBeta;
    this.filterY.mincutoff = config.oneEuroMinCutoff;
    this.filterY.beta = config.oneEuroBeta;
    const x = this.filterX.filter(normX, now);
    const y = this.filterY.filter(normY, now);
    this.lastNormX = x;
    this.lastNormY = y;
    return { x, y };
  }

  update(points, config, now = performance.now()) {
    if (!config.enabled || !points?.[INDEX_TIP] || !points?.[THUMB_TIP]) {
      const hold = config.holdFramesOnLost ?? 0;
      if (this.state.active && this.missedFrames < hold) {
        this.missedFrames += 1;
        return { state: this.state, click: null };
      }
      this.state = createIdleState();
      this.pinchStartedAt = 0;
      this.pinchFrameCount = 0;
      this.resetFilters();
      return { state: this.state, click: null };
    }
    this.missedFrames = 0;

    const pos = pickPosition(points, config.positionSource);
    if (!pos) {
      this.state = createIdleState();
      this.resetFilters();
      return { state: this.state, click: null };
    }

    let normX = clamp01(config.mirrorX ? 1 - pos.x : pos.x);
    let normY = clamp01(pos.y);
    const margin = clamp01(config.mapMargin);
    const span = Math.max(0.2, 1 - margin * 2);
    normX = clamp01((normX - margin) / span);
    normY = clamp01((normY - margin) / span);

    const dz = config.deadZoneNorm ?? 0;
    if (
      dz > 0 &&
      this.lastInputNormX !== null &&
      this.lastInputNormY !== null &&
      Math.abs(normX - this.lastInputNormX) < dz &&
      Math.abs(normY - this.lastInputNormY) < dz
    ) {
      normX = this.lastInputNormX;
      normY = this.lastInputNormY;
    }
    this.lastInputNormX = normX;
    this.lastInputNormY = normY;

    const smoothed = this.smoothNorm(normX, normY, config, now);
    let clientX = smoothed.x * window.innerWidth;
    let clientY = smoothed.y * window.innerHeight;

    const thumbTip = points[THUMB_TIP];
    const indexTip = points[INDEX_TIP];
    const pinchDistance = distance(indexTip, thumbTip);
    const pinchCandidate =
      this.state.phase === "pressing"
        ? pinchDistance < config.pinchUpDistance
        : pinchDistance < config.pinchDownDistance;

    if (pinchCandidate) {
      this.pinchFrameCount += 1;
    } else {
      this.pinchFrameCount = 0;
    }
    const isPinching = this.pinchFrameCount >= config.pinchDebounceFrames;

    if (isPinching && !this.pinchStartedAt) {
      this.lockedClientX = clientX;
      this.lockedClientY = clientY;
    }

    const pointerX =
      config.lockPositionOnPress && isPinching ? this.lockedClientX : clientX;
    const pointerY =
      config.lockPositionOnPress && isPinching ? this.lockedClientY : clientY;
    const target = interactiveTargetAt(pointerX, pointerY);

    let phase = "tracking";
    let progress = 0;
    let click = null;

    if (now < this.cooldownUntil) {
      phase = "cooldown";
    } else if (isPinching) {
      if (!this.pinchStartedAt) this.pinchStartedAt = now;
      const heldMs = now - this.pinchStartedAt;
      progress = clamp01(heldMs / config.clickHoldMs);
      phase = "pressing";
      if (heldMs >= config.clickHoldMs && config.enableClick !== false) {
        if (target) clickTarget(target);
        click = { clientX: pointerX, clientY: pointerY, target };
        this.cooldownUntil = now + config.cooldownMs;
        this.pinchStartedAt = 0;
        this.pinchFrameCount = 0;
        phase = "cooldown";
        progress = 0;
      }
    } else {
      this.pinchStartedAt = 0;
    }

    const proximity = targetProximity(pointerX, pointerY, target);
    this.state = {
      active: true,
      phase,
      clientX: pointerX,
      clientY: pointerY,
      progress,
      targetLabel: pointLabel(target),
      hasTarget: proximity.hasTarget,
      nearTarget: proximity.nearTarget,
      lastUpdatedAt: now,
    };
    return { state: this.state, click };
  }

  markStale(now = performance.now(), staleAfterMs = DEFAULT_GESTURE_CURSOR_CONFIG.staleAfterMs) {
    if (this.state.active && now - this.state.lastUpdatedAt > staleAfterMs) {
      this.state = createIdleState();
      this.pinchStartedAt = 0;
      this.pinchFrameCount = 0;
      this.resetFilters();
    }
    return this.state;
  }
}
