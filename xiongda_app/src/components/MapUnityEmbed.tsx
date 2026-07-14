import { motion } from "framer-motion";
import { MapPinned } from "lucide-react";
import { isMapUnityFullyReady, setMapUnityInstance } from "../services/unityMapBridge";
import { lastMapUnityLoadError, tryLoadUnityWebGL } from "../unity/loadUnityWebGL";
import { useEffect, useState } from "react";

type MapUnityEmbedProps = {
  blockGamePointer?: boolean;
};

/**
 * 地图查询页：加载 ParkMap3DBlockout 的 WebGL（/webgl-map/）。
 * 与语音页的熊大 WebGL（/webgl/）相互独立。
 */
export function MapUnityEmbed({ blockGamePointer = false }: MapUnityEmbedProps) {
  const [ready, setReady] = useState(false);
  const [bootHint, setBootHint] = useState<string | null>(null);

  useEffect(() => {
    const canvas = document.getElementById("map-unity-canvas") as HTMLCanvasElement | null;
    let cancelled = false;

    void tryLoadUnityWebGL("map-unity-game-mount", canvas, {
      basePath: "/webgl-map",
      logTag: "[MapUnity]",
      onInstanceReady: setMapUnityInstance,
    }).then((ok) => {
      if (cancelled) return;
      if (!ok && lastMapUnityLoadError) {
        setBootHint(lastMapUnityLoadError);
      }
    });

    const id = window.setInterval(() => {
      const w = window as Window & { mapUnityInstance?: { SendMessage?: unknown } };
      if (w.mapUnityInstance?.SendMessage && isMapUnityFullyReady()) {
        setReady(true);
        setBootHint(null);
        window.clearInterval(id);
      }
    }, 400);

    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, []);

  return (
    <div
      id="map-unity-container"
      className="relative flex min-h-0 w-full flex-1 flex-col overflow-hidden rounded-2xl border-2 border-emerald-500/30 bg-gradient-to-b from-sky-100/20 to-slate-950/95 shadow-[0_0_40px_rgba(16,185,129,0.12)]"
      onMouseDown={() => {
        if (!blockGamePointer) return;
        (document.activeElement as HTMLElement | null)?.blur?.();
      }}
    >
      <div className="absolute left-3 right-3 top-3 z-20 flex items-center justify-between gap-2 rounded-lg bg-black/50 px-3 py-1.5 text-xs font-bold text-emerald-200/95 backdrop-blur">
        <span className="flex items-center gap-1.5">
          <MapPinned className="h-3.5 w-3.5" aria-hidden />
          3D 乐园地图 · WebGL
        </span>
        <span
          className={ready ? "rounded bg-emerald-500/20 px-2 text-emerald-200" : "text-amber-200/90"}
        >
          {ready ? "地图已加载" : "待构建 WebGL（见 public/webgl-map/说明.txt）"}
        </span>
      </div>

      <div
        className={`relative min-h-0 flex-1 ${blockGamePointer ? "pointer-events-none select-none" : ""}`}
      >
        <div
          id="map-unity-game-mount"
          className="absolute inset-0 min-h-[200px] touch-none bg-black/40"
          aria-hidden
        />
        <canvas
          id="map-unity-canvas"
          className="absolute inset-0 min-h-[200px] h-full w-full touch-none bg-black/40"
          tabIndex={-1}
          aria-label="3D 乐园地图 WebGL"
        />

        {!ready && (
          <motion.div
            initial={{ opacity: 0.9 }}
            animate={{ opacity: 1 }}
            className="pointer-events-none absolute inset-0 z-10 flex flex-col items-center justify-center gap-3 bg-slate-950/80 px-4 text-center"
          >
            <p className="text-lg font-extrabold tracking-wide text-emerald-100">3D 乐园地图窗口</p>
            <p className="max-w-lg text-sm leading-relaxed text-emerald-100/80">
              请用 Unity 打开 <code className="rounded bg-black/50 px-1">XiongdaParkMapProject</code>，
              菜单 <strong>Tools → 狗熊岭智慧终端 → 构建地图 WebGL 到 xiongda_app</strong>，
              或手动 Build 后运行 <code className="rounded bg-black/50 px-1">copy-webgl-map-from-unity.ps1</code>。
              然后重启 <code className="rounded bg-black/50 px-1">npm run dev</code>。
            </p>
            {bootHint ? (
              <p className="max-w-lg rounded-lg bg-red-950/80 px-3 py-2 text-left text-xs leading-snug text-red-100">
                {bootHint}
              </p>
            ) : null}
          </motion.div>
        )}
      </div>
    </div>
  );
}
