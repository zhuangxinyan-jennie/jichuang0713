import { AlertTriangle, RadioTower, ShieldAlert, ShieldCheck } from "lucide-react";
import type { SafetyState } from "./types";

type Props = {
  safety: SafetyState;
  connectionError: string;
  demoEnabled: boolean;
  demoBusy: boolean;
  onDemoToggle: () => void;
};

export function SafetyOverlay({
  safety,
  connectionError,
  demoEnabled,
  demoBusy,
  onDemoToggle,
}: Props) {
  const alerting = safety.state === "SAFETY_ALERT";
  const recovering = safety.state === "RECOVERY";

  return (
    <>
      {safety.state === "WARNING" ? (
        <div className="pointer-events-none fixed inset-x-0 top-0 z-[80] flex min-h-12 items-center justify-center gap-2 bg-amber-400 px-4 py-2 text-center text-sm font-semibold text-neutral-950 shadow-md">
          <AlertTriangle className="h-5 w-5 shrink-0" aria-hidden />
          <span>当前区域人流较密，请注意保持间距</span>
        </div>
      ) : null}

      {!safety.locked && (safety.monitor_fault || connectionError) ? (
        <div
          className={`pointer-events-none fixed right-3 z-[81] flex max-w-[calc(100vw-1.5rem)] items-center gap-2 rounded-md border border-amber-500 bg-neutral-950 px-3 py-2 text-xs font-medium text-white shadow-lg ${
            safety.state === "WARNING" ? "top-16" : "top-3"
          }`}
        >
          <RadioTower className="h-4 w-4 shrink-0 text-amber-400" aria-hidden />
          <span>人流监控连接异常</span>
        </div>
      ) : null}

      {alerting || recovering ? (
        <div
          className={`fixed inset-0 z-[100] flex min-h-[100dvh] flex-col items-center justify-center px-5 py-8 text-center ${
            alerting ? "bg-red-700 text-white" : "bg-emerald-700 text-white"
          }`}
          role="alert"
          aria-live="assertive"
        >
          {alerting ? (
            <ShieldAlert className="h-20 w-20 md:h-28 md:w-28" strokeWidth={1.8} aria-hidden />
          ) : (
            <ShieldCheck className="h-20 w-20 md:h-28 md:w-28" strokeWidth={1.8} aria-hidden />
          )}
          <h1 className="mt-5 text-3xl font-bold leading-tight md:text-5xl">
            {alerting ? "安全预警" : "安全状态已恢复"}
          </h1>
          <p className="mt-4 max-w-2xl text-lg leading-relaxed md:text-2xl">
            {alerting ? "当前区域人流密集，请减速并保持安全距离" : "正在恢复互动服务"}
          </p>
          {safety.monitor_fault ? (
            <div className="mt-7 flex items-center gap-2 rounded-md border border-white/60 px-3 py-2 text-sm font-semibold">
              <RadioTower className="h-4 w-4" aria-hidden />
              <span>检测信号中断，安全预警继续保持</span>
            </div>
          ) : null}
        </div>
      ) : null}

      {demoEnabled ? (
        <button
          type="button"
          onClick={onDemoToggle}
          disabled={demoBusy}
          className="fixed bottom-3 left-3 z-[110] inline-flex min-h-10 items-center gap-2 rounded-md border border-neutral-700 bg-neutral-950 px-3 py-2 text-xs font-semibold text-white shadow-lg transition hover:bg-neutral-800 disabled:cursor-wait disabled:opacity-60"
        >
          <ShieldAlert className="h-4 w-4" aria-hidden />
          <span>{safety.demo_active ? "解除演示预警" : "演示人流预警"}</span>
        </button>
      ) : null}
    </>
  );
}
