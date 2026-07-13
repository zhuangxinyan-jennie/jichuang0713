import { useEffect } from "react";

const ISLAND = "[data-terminal-input-island]";

function isActiveFocusInsideIsland(): boolean {
  const a = document.activeElement;
  return !!(a && a instanceof Element && a.closest(ISLAND));
}

/**
 * Unity WebGL 常在 window 捕获阶段监听键盘，导致右侧/底部输入框在交互过一次画布后无法再输入。
 * 当焦点在带 `data-terminal-input-island` 的区域内时，阻止键盘事件继续向外传播。
 */
export function useTerminalKeyboardIsolation(active: boolean): void {
  useEffect(() => {
    if (!active) return;

    const eat = (e: Event) => {
      if (!isActiveFocusInsideIsland()) return;
      e.stopImmediatePropagation();
    };

    const opts: AddEventListenerOptions = { capture: true };
    window.addEventListener("keydown", eat, opts);
    window.addEventListener("keyup", eat, opts);
    window.addEventListener("keypress", eat, opts);

    return () => {
      window.removeEventListener("keydown", eat, opts);
      window.removeEventListener("keyup", eat, opts);
      window.removeEventListener("keypress", eat, opts);
    };
  }, [active]);
}
