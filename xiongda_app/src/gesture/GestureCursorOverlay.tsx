import type { GestureCursorState } from "./gestureCursorController";

type GestureCursorOverlayProps = {
  state: GestureCursorState;
  serviceOk: boolean;
  mockMode: boolean;
};

/** 地图页手势光标叠层（熊掌 + 状态条） */
export function GestureCursorOverlay({ state, serviceOk, mockMode }: GestureCursorOverlayProps) {
  const visible = state.active;
  const pressing = state.phase === "pressing";

  return (
    <>
      <div
        className="pointer-events-none fixed bottom-24 left-1/2 z-[90] -translate-x-1/2 rounded-full border border-emerald-400/40 bg-black/65 px-4 py-1.5 text-center text-[11px] font-semibold text-emerald-100 shadow-lg backdrop-blur md:text-xs"
        role="status"
      >
        {mockMode
          ? "演示模式：移动鼠标=光标，按住左键=捏合（请另开手势服务 8770）"
          : serviceOk
            ? state.active
              ? pressing
                ? `捏合中… ${state.targetLabel ? `→ ${state.targetLabel}` : ""}`
                : state.hasTarget
                  ? `对准「${state.targetLabel}」，捏合拇指与食指点击`
                  : "举起手掌移动光标，捏合点击"
              : "举起手掌出现光标"
            : "正在连接本机摄像头手势服务…"}
      </div>

      {visible ? (
        <div
          className="pointer-events-none fixed z-[95] -translate-x-1/2 -translate-y-1/2"
          style={{ left: state.clientX, top: state.clientY }}
          aria-hidden
        >
          <div
            className={`relative flex h-12 w-12 items-center justify-center rounded-full border-2 shadow-lg transition-transform ${
              pressing
                ? "scale-90 border-amber-300 bg-amber-400/90"
                : state.nearTarget
                  ? "border-emerald-300 bg-emerald-400/85"
                  : "border-white/80 bg-rose-400/90"
            }`}
          >
            <span className="text-lg leading-none">🐾</span>
            {pressing ? (
              <svg className="absolute inset-0 h-full w-full -rotate-90" viewBox="0 0 36 36">
                <circle
                  cx="18"
                  cy="18"
                  r="15"
                  fill="none"
                  stroke="rgba(255,255,255,0.85)"
                  strokeWidth="3"
                  strokeDasharray={`${Math.round(state.progress * 94)} 94`}
                />
              </svg>
            ) : null}
          </div>
        </div>
      ) : null}
    </>
  );
}
