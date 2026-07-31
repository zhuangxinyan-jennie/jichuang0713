/**
 * 补星游戏 + 手势虚拟光标（摄像头 / 鼠标演示）
 */
import {
  GestureCursorController,
  DEFAULT_GESTURE_CURSOR_CONFIG,
  applyServerMeta,
} from "./cursor_controller.js";
import { PawStarsGame, initBackgroundStars } from "./paw_stars.js";

const TEXT = {
  hint: "举起手掌移动光标，捏合拇指和食指抓住星星",
  waiting: "举起手掌",
  tracking: "移动手掌选星",
  hoverStar: "靠近星星，捏合抓取",
  pressingGrab: "捏合抓星",
  pressingDrag: "拖到熊掌空缺",
  cooldown: "放置成功",
  lost: "举起手掌",
  connecting: "正在连接摄像头…",
  mockMode: "演示模式：鼠标移动光标，按住左键模拟捏合抓星",
};

export function bootPawStarsGesture(options) {
  initBackgroundStars(options.bgStarsEl);

  const game = new PawStarsGame({
    board: options.gameBoard,
    starsField: options.starsField,
    slotsLayer: options.slotsLayer,
    progressEl: options.progressEl,
    statusEl: options.statusEl,
    overlay: options.successOverlay,
  });

  const config = {
    ...DEFAULT_GESTURE_CURSOR_CONFIG,
    enableClick: false,
    lockPositionOnPress: false,
  };

  const controller = new GestureCursorController();
  const cursor = options.cursorEl;
  const progressValue = options.progressValueEl;
  const gestureStatus = options.gestureStatusEl;
  const gestureHud = options.gestureHudEl;
  const gestureIcon = options.gestureIconEl;
  const idleHint = options.idleHintEl;
  const progressCircumference = 138;
  const trail = [];
  const trailLength = 7;

  let metaApplied = false;
  let fetchBusy = false;
  let apiReady = false;
  let wasPinching = false;
  let mockMode = false;
  let lastRippleAt = 0;

  const mock = {
    x: window.innerWidth / 2,
    y: window.innerHeight / 2,
    down: false,
    downAt: 0,
    cooldownUntil: 0,
  };

  const hudIcons = {
    idle: "○",
    tracking: "✋",
    hover: "✦",
    pressing: "◔",
    cooldown: "✓",
  };

  idleHint.textContent = TEXT.hint;
  gestureStatus.textContent = TEXT.connecting;

  for (let i = 0; i < trailLength; i += 1) {
    const dot = document.createElement("span");
    dot.className = "trail-dot";
    dot.style.opacity = "0";
    document.body.appendChild(dot);
    trail.push({ node: dot, x: 0, y: 0 });
  }

  options.resetBtn.addEventListener("click", () => {
    game.reset();
    wasPinching = false;
  });
  options.playAgainBtn.addEventListener("click", () => {
    game.reset();
    wasPinching = false;
  });

  window.addEventListener("pointermove", (event) => {
    mock.x = event.clientX;
    mock.y = event.clientY;
  });

  window.addEventListener("pointerdown", (event) => {
    if (!mockMode) return;
    mock.down = true;
    mock.downAt = performance.now();
    mock.x = event.clientX;
    mock.y = event.clientY;
  });

  window.addEventListener("pointerup", (event) => {
    if (!mockMode) return;
    mock.x = event.clientX;
    mock.y = event.clientY;
    mock.down = false;
    mock.cooldownUntil = performance.now() + 360;
  });

  function ripple(x, y) {
    const now = performance.now();
    if (now - lastRippleAt < 120) return;
    lastRippleAt = now;
    const node = document.createElement("span");
    node.className = "click-ripple";
    node.style.left = `${x}px`;
    node.style.top = `${y}px`;
    document.body.appendChild(node);
    node.addEventListener("animationend", () => node.remove(), { once: true });
  }

  function updateTrail(x, y, active) {
    if (!active) {
      trail.forEach((item) => {
        item.node.style.opacity = "0";
      });
      return;
    }
    trail.unshift({ node: trail.pop().node, x, y });
    trail.forEach((item, index) => {
      const opacity = Math.max(0, 0.34 - index * 0.045);
      const scale = Math.max(0.35, 1 - index * 0.08);
      item.node.style.left = `${item.x}px`;
      item.node.style.top = `${item.y}px`;
      item.node.style.opacity = String(opacity);
      item.node.style.transform = `translate(-50%, -50%) scale(${scale})`;
    });
  }

  function mockState(now) {
    const nearStar = game.findStarAt(mock.x, mock.y);
    let phase = "tracking";
    let progress = 0;
    if (now < mock.cooldownUntil) {
      phase = "cooldown";
    } else if (mock.down) {
      phase = "pressing";
      progress = Math.min(1, (now - mock.downAt) / 280);
    }
    return {
      active: true,
      phase,
      clientX: mock.x,
      clientY: mock.y,
      progress,
      hasTarget: Boolean(nearStar),
      nearTarget: Boolean(nearStar),
      lastUpdatedAt: now,
    };
  }

  function handleGestureDrag(display) {
    const pinching = display.active && display.phase === "pressing";

    if (pinching && !wasPinching) {
      game.gestureGrab(display.clientX, display.clientY);
    }
    if (pinching && game.gestureDragging) {
      game.gestureDrag(display.clientX, display.clientY);
    }
    if (!pinching && wasPinching && game.gestureDragging) {
      const snapped = game.gestureRelease(display.clientX, display.clientY);
      if (snapped) ripple(display.clientX, display.clientY);
    }

    wasPinching = pinching;

    if (!pinching && !game.gestureDragging && display.active) {
      const nearStar = game.findStarAt(display.clientX, display.clientY);
      game.setHoverStar(nearStar ? nearStar.el : null);
    } else if (game.gestureDragging) {
      game.setHoverStar(null);
    }
  }

  function renderCursor(display) {
    if (!display.active) {
      cursor.style.display = "none";
      progressValue.style.strokeDashoffset = String(progressCircumference);
      gestureHud.dataset.state = "idle";
      gestureIcon.textContent = hudIcons.idle;
      game.setHoverStar(null);
      updateTrail(0, 0, false);
      idleHint.classList.add("visible");
      return;
    }

    idleHint.classList.remove("visible");

    let visualX = display.clientX;
    let visualY = display.clientY;
    const nearStar = game.findStarAt(display.clientX, display.clientY);
    if (nearStar && display.phase !== "pressing") {
      const rect = nearStar.el.getBoundingClientRect();
      const cx = rect.left + rect.width / 2;
      const cy = rect.top + rect.height / 2;
      visualX += (cx - display.clientX) * 0.1;
      visualY += (cy - display.clientY) * 0.1;
    }

    cursor.style.display = "block";
    cursor.style.left = `${visualX}px`;
    cursor.style.top = `${visualY}px`;
    cursor.classList.toggle("hover", Boolean(nearStar) && !game.gestureDragging);
    cursor.classList.toggle("pressing", display.phase === "pressing");
    cursor.classList.toggle("cooldown", display.phase === "cooldown");
    progressValue.style.strokeDashoffset = String(
      progressCircumference * (1 - Math.max(0, Math.min(1, display.progress)))
    );

    let hudState = display.phase;
    if (display.phase === "tracking" && nearStar) hudState = "hover";
    gestureHud.dataset.state = hudState;
    gestureIcon.textContent = hudIcons[hudState] || hudIcons.tracking;
    updateTrail(visualX, visualY, display.phase !== "cooldown");
  }

  function gestureLabel(display) {
    if (!apiReady) return TEXT.connecting;
    if (mockMode) {
      if (game.gestureDragging) return TEXT.pressingDrag;
      if (display.phase === "pressing") return TEXT.pressingGrab;
      return game.findStarAt(display.clientX, display.clientY) ? TEXT.hoverStar : TEXT.mockMode;
    }
    if (!display.active) return TEXT.lost;
    if (game.gestureDragging || (display.phase === "pressing" && wasPinching)) {
      return TEXT.pressingDrag;
    }
    if (display.phase === "pressing") return TEXT.pressingGrab;
    if (game.findStarAt(display.clientX, display.clientY)) return TEXT.hoverStar;
    if (display.phase === "cooldown") return TEXT.cooldown;
    return TEXT.tracking;
  }

  async function pullLandmarks() {
    if (fetchBusy) return;
    fetchBusy = true;
    try {
      const res = await fetch("/api/landmarks", { cache: "no-store" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      apiReady = true;
      if (!metaApplied && data.meta) {
        applyServerMeta(config, data.meta);
        metaApplied = true;
      }
      const points =
        Array.isArray(data.hand_landmarks) && data.hand_landmarks.length >= 9
          ? data.hand_landmarks
          : null;
      controller.update(points, config);
    } catch (_error) {
      apiReady = true;
      mockMode = true;
      controller.update(null, config);
    } finally {
      fetchBusy = false;
    }
  }

  function frame() {
    const now = performance.now();
    const display = mockMode ? mockState(now) : controller.tickDisplay(config);
    handleGestureDrag(display);
    renderCursor(display);
    gestureStatus.textContent = gestureLabel(display);
    requestAnimationFrame(frame);
  }

  setInterval(pullLandmarks, 20);
  pullLandmarks();
  requestAnimationFrame(frame);

  setInterval(() => {
    if (mockMode) return;
    const state = controller.markStale(performance.now(), config.staleAfterMs);
    if (!state.active) renderCursor(state);
  }, 180);

  return game;
}
