/** 散落星星 → 补全熊掌 拖拽小游戏（纯浏览器，支持鼠标/触摸） */

const STAR_SVG = (uid) => `
<svg viewBox="0 0 100 100" aria-hidden="true">
  <defs>
    <radialGradient id="starGlow-${uid}" cx="50%" cy="45%" r="55%">
      <stop offset="0%" stop-color="#fff8c8"/>
      <stop offset="55%" stop-color="#ffd86a"/>
      <stop offset="100%" stop-color="#e8a820"/>
    </radialGradient>
  </defs>
  <polygon points="50,6 61,38 95,38 67,58 77,92 50,72 23,92 33,58 5,38 39,38"
    fill="url(#starGlow-${uid})" stroke="#fff3b0" stroke-width="2"/>
</svg>`;

/** 熊掌内 5 个空缺（相对 paw-panel 的 0~1 坐标） */
const SLOT_LAYOUT = [
  { id: "toe1", x: 0.24, y: 0.34 },
  { id: "toe2", x: 0.38, y: 0.2 },
  { id: "toe3", x: 0.62, y: 0.2 },
  { id: "toe4", x: 0.76, y: 0.34 },
  { id: "palm", x: 0.5, y: 0.62 },
];

/** 星星初始散落区域（相对 game-board） */
const SCATTER_ZONES = [
  { x: 0.12, y: 0.18 },
  { x: 0.08, y: 0.52 },
  { x: 0.18, y: 0.78 },
  { x: 0.28, y: 0.38 },
  { x: 0.14, y: 0.62 },
];

const SNAP_RADIUS = 72;
export const GRAB_RADIUS = 78;

export class PawStarsGame {
  constructor(options) {
    this.board = options.board;
    this.starsField = options.starsField;
    this.slotsLayer = options.slotsLayer;
    this.progressEl = options.progressEl;
    this.statusEl = options.statusEl;
    this.overlay = options.overlay;
    this.onComplete = options.onComplete || (() => {});

    this.slots = [];
    this.stars = [];
    this.dragging = null;
    this.gestureDragging = null;
    this.filledCount = 0;
    this.completed = false;
    this.hoverStarEl = null;

    this.onPointerMove = this.onPointerMove.bind(this);
    this.onPointerUp = this.onPointerUp.bind(this);

    this.reset();
  }

  reset() {
    this.completed = false;
    this.filledCount = 0;
    this.dragging = null;
    this.gestureDragging = null;
    this.setHoverStar(null);
    this.overlay.classList.remove("visible");
    this.starsField.innerHTML = "";
    this.slotsLayer.innerHTML = "";
    this.slots = [];
    this.stars = [];

    SLOT_LAYOUT.forEach((layout) => {
      const slot = document.createElement("div");
      slot.className = "slot";
      slot.dataset.slotId = layout.id;
      slot.style.left = `${layout.x * 100}%`;
      slot.style.top = `${layout.y * 100}%`;
      this.slotsLayer.appendChild(slot);
      this.slots.push({ el: slot, layout, filled: false, star: null });
    });

    SCATTER_ZONES.forEach((zone, index) => {
      const star = document.createElement("div");
      star.className = "star";
      star.dataset.starId = String(index);
      star.innerHTML = STAR_SVG(index);
      const jitterX = (Math.random() - 0.5) * 0.06;
      const jitterY = (Math.random() - 0.5) * 0.06;
      const home = { x: zone.x + jitterX, y: zone.y + jitterY };
      star.style.left = `${home.x * 100}%`;
      star.style.top = `${home.y * 100}%`;
      star.addEventListener("pointerdown", (event) => this.onPointerDown(event, star, home));
      this.starsField.appendChild(star);
      this.stars.push({ el: star, home, placed: false, slot: null });
    });

    this.updateHud();
    this.statusEl.textContent = "抓住星星，拖到熊掌空缺处";
  }

  updateHud() {
    this.progressEl.textContent = `${this.filledCount} / ${SLOT_LAYOUT.length}`;
  }

  boardPoint(clientX, clientY) {
    const rect = this.board.getBoundingClientRect();
    return {
      x: clientX - rect.left,
      y: clientY - rect.top,
      rect,
    };
  }

  slotCenter(slot) {
    const boardRect = this.board.getBoundingClientRect();
    const panel = this.slotsLayer.parentElement;
    const panelRect = panel.getBoundingClientRect();
    const x = panelRect.left - boardRect.left + slot.layout.x * panelRect.width;
    const y = panelRect.top - boardRect.top + slot.layout.y * panelRect.height;
    return { x, y };
  }

  findStarAt(clientX, clientY, radius = GRAB_RADIUS) {
    let best = null;
    let bestDist = Infinity;
    this.stars.forEach((star) => {
      if (star.placed) return;
      const rect = star.el.getBoundingClientRect();
      const cx = rect.left + rect.width / 2;
      const cy = rect.top + rect.height / 2;
      const dist = Math.hypot(clientX - cx, clientY - cy);
      if (dist <= radius && dist < bestDist) {
        best = star;
        bestDist = dist;
      }
    });
    return best;
  }

  setHoverStar(starEl) {
    if (this.hoverStarEl === starEl) return;
    if (this.hoverStarEl) this.hoverStarEl.classList.remove("gesture-near");
    this.hoverStarEl = starEl;
    if (this.hoverStarEl) this.hoverStarEl.classList.add("gesture-near");
  }

  highlightNearestSlot(clientX, clientY) {
    const point = this.boardPoint(clientX, clientY);
    let nearest = null;
    let nearestDist = Infinity;
    this.slots.forEach((slot) => {
      slot.el.classList.remove("highlight");
      if (slot.filled) return;
      const center = this.slotCenter(slot);
      const dist = Math.hypot(center.x - point.x, center.y - point.y);
      if (dist < nearestDist) {
        nearestDist = dist;
        nearest = slot;
      }
    });
    if (nearest && nearestDist <= SNAP_RADIUS) {
      nearest.el.classList.add("highlight");
    }
  }

  clearSlotHighlights() {
    this.slots.forEach((slot) => slot.el.classList.remove("highlight"));
  }

  trySnapAt(clientX, clientY) {
    const point = this.boardPoint(clientX, clientY);
    let targetSlot = null;
    let bestDist = Infinity;
    this.slots.forEach((slot) => {
      if (slot.filled) return;
      const center = this.slotCenter(slot);
      const dist = Math.hypot(center.x - point.x, center.y - point.y);
      if (dist <= SNAP_RADIUS && dist < bestDist) {
        bestDist = dist;
        targetSlot = slot;
      }
    });
    return targetSlot;
  }

  moveStarToClient(starEl, clientX, clientY) {
    const point = this.boardPoint(clientX, clientY);
    starEl.style.left = `${(point.x / point.rect.width) * 100}%`;
    starEl.style.top = `${(point.y / point.rect.height) * 100}%`;
  }

  gestureGrab(clientX, clientY) {
    if (this.completed || this.gestureDragging || this.dragging) return false;
    const star = this.findStarAt(clientX, clientY);
    if (!star) return false;
    this.gestureDragging = { star, starEl: star.el };
    star.el.classList.add("dragging");
    this.moveStarToClient(star.el, clientX, clientY);
    this.highlightNearestSlot(clientX, clientY);
    this.statusEl.textContent = "捏合抓星，移向熊掌空缺…";
    return true;
  }

  gestureDrag(clientX, clientY) {
    if (!this.gestureDragging) return;
    this.moveStarToClient(this.gestureDragging.starEl, clientX, clientY);
    this.highlightNearestSlot(clientX, clientY);
  }

  gestureRelease(clientX, clientY) {
    if (!this.gestureDragging) return false;
    const { star, starEl } = this.gestureDragging;
    starEl.classList.remove("dragging");
    this.clearSlotHighlights();

    const targetSlot = this.trySnapAt(clientX, clientY);
    let snapped = false;
    if (targetSlot) {
      this.snapStar(star, targetSlot);
      snapped = true;
    } else {
      starEl.style.left = `${star.home.x * 100}%`;
      starEl.style.top = `${star.home.y * 100}%`;
      this.statusEl.textContent = "没对准空缺，再试一次";
    }

    this.gestureDragging = null;
    return snapped;
  }

  onPointerDown(event, starEl, home) {
    if (this.completed) return;
    const star = this.stars.find((item) => item.el === starEl);
    if (!star || star.placed) return;

    event.preventDefault();
    starEl.setPointerCapture(event.pointerId);
    starEl.classList.add("dragging");
    this.dragging = { star, starEl, pointerId: event.pointerId };
    this.statusEl.textContent = "拖动中… 对准熊掌上的虚线圆圈";
    window.addEventListener("pointermove", this.onPointerMove);
    window.addEventListener("pointerup", this.onPointerUp);
    window.addEventListener("pointercancel", this.onPointerUp);
  }

  onPointerMove(event) {
    if (!this.dragging || event.pointerId !== this.dragging.pointerId) return;
    const point = this.boardPoint(event.clientX, event.clientY);
    this.dragging.starEl.style.left = `${(point.x / point.rect.width) * 100}%`;
    this.dragging.starEl.style.top = `${(point.y / point.rect.height) * 100}%`;

    this.highlightNearestSlot(event.clientX, event.clientY);
  }

  onPointerUp(event) {
    if (!this.dragging || event.pointerId !== this.dragging.pointerId) return;

    const { star, starEl } = this.dragging;
    starEl.classList.remove("dragging");
    starEl.releasePointerCapture(event.pointerId);
    window.removeEventListener("pointermove", this.onPointerMove);
    window.removeEventListener("pointerup", this.onPointerUp);
    window.removeEventListener("pointercancel", this.onPointerUp);

    const targetSlot = this.trySnapAt(event.clientX, event.clientY);
    this.clearSlotHighlights();

    if (targetSlot) {
      this.snapStar(star, targetSlot);
    } else {
      starEl.style.left = `${star.home.x * 100}%`;
      starEl.style.top = `${star.home.y * 100}%`;
      this.statusEl.textContent = "没对准空缺，再试一次";
    }

    this.dragging = null;
  }

  snapStar(star, slot) {
    star.placed = true;
    star.slot = slot;
    slot.filled = true;
    slot.star = star;
    slot.el.classList.add("filled");

    const center = this.slotCenter(slot);
    const rect = this.board.getBoundingClientRect();
    star.el.style.left = `${(center.x / rect.width) * 100}%`;
    star.el.style.top = `${(center.y / rect.height) * 100}%`;
    star.el.classList.add("placed");

    this.filledCount += 1;
    this.updateHud();
    this.statusEl.textContent = `已补全 ${this.filledCount} 处`;

    if (this.filledCount >= SLOT_LAYOUT.length) {
      this.complete();
    }
  }

  complete() {
    if (this.completed) return;
    this.completed = true;
    this.statusEl.textContent = "熊掌补全成功！";
    this.overlay.classList.add("visible");
    this.onComplete();
  }
}

export function initBackgroundStars(container, count = 48) {
  container.innerHTML = "";
  for (let i = 0; i < count; i += 1) {
    const dot = document.createElement("span");
    dot.style.left = `${Math.random() * 100}%`;
    dot.style.top = `${Math.random() * 100}%`;
    dot.style.animationDelay = `${Math.random() * 3.6}s`;
    dot.style.opacity = String(0.2 + Math.random() * 0.6);
    container.appendChild(dot);
  }
}
