/** 2D 地图高亮（厕所等设施）：Agent map_query 结果 → ParkMap2DOverlay */
export type Map2DHighlight = {
  /** 如 toilet */
  category?: string;
  /** 精确地点名列表（可选；有则只亮这些） */
  names?: string[];
  /** 是否自动打开放大浮层 */
  openModal?: boolean;
};

type Listener = (h: Map2DHighlight | null) => void;

let current: Map2DHighlight | null = null;
const listeners = new Set<Listener>();

export function getMap2DHighlight(): Map2DHighlight | null {
  return current;
}

export function setMap2DHighlight(h: Map2DHighlight | null): void {
  current = h;
  listeners.forEach((fn) => {
    try {
      fn(current);
    } catch {
      /* ignore */
    }
  });
}

export function clearMap2DHighlight(): void {
  setMap2DHighlight(null);
}

export function subscribeMap2DHighlight(fn: Listener): () => void {
  listeners.add(fn);
  fn(current);
  return () => {
    listeners.delete(fn);
  };
}
