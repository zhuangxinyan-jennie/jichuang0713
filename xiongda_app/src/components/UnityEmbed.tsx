import { motion } from "framer-motion";
import { Film } from "lucide-react";
import { isUnityInstanceReady, setGlobalUnityInstance } from "../services/unitySendClip";
import { lastUnityLoadError, tryLoadUnityWebGL } from "../unity/loadUnityWebGL";
import { registerMergedUnityInstance } from "../services/unityMergedMode";
import { useEffect, useState } from "react";

type UnityEmbedProps = {
  /** 正在编辑终端输入时屏蔽画布指针，避免 Unity 再次抢走焦点导致无法连续输入 */
  blockGamePointer?: boolean;
  /** public 下目录，默认 /webgl；合并包用 /webgl-merged */
  basePath?: string;
  /** 角标文案 */
  badgeLabel?: string;
};

/**
 * WebGL：支持 Unity 2018 `UnityLoader.instantiate` 与 2019+ `createUnityInstance`。
 */
export function UnityEmbed({
  blockGamePointer = false,
  basePath = "/webgl",
  badgeLabel = "熊大互动",
}: UnityEmbedProps) {
  const [ready, setReady] = useState(false);
  const [bootHint, setBootHint] = useState<string | null>(null);
  const merged = basePath.replace(/\/+$/, "") === "/webgl-merged";

  useEffect(() => {
    const canvas = document.getElementById("unity-canvas") as HTMLCanvasElement | null;
    let cancelled = false;

    void tryLoadUnityWebGL("unity-game-mount", canvas, {
      basePath,
      hideCanvasId: "unity-canvas",
      logTag: merged ? "[MergedUnity]" : "[Unity]",
      onInstanceReady: (inst) => {
        setGlobalUnityInstance(inst);
        if (merged) registerMergedUnityInstance(inst);
      },
    }).then((ok) => {
      if (cancelled) return;
      if (!ok && lastUnityLoadError) {
        setBootHint(lastUnityLoadError);
      }
    });

    const id = window.setInterval(() => {
      if (isUnityInstanceReady()) {
        setReady(true);
        setBootHint(null);
        window.clearInterval(id);
      }
    }, 400);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, [basePath, merged]);

  return (
    <div
      id="unity-container"
      className="relative flex min-h-0 w-full flex-1 flex-col overflow-hidden rounded-2xl border-2 border-cyan-500/30 bg-gradient-to-b from-slate-900/90 to-slate-950/95 shadow-[0_0_40px_rgba(34,197,94,0.12)]"
      onMouseDown={() => {
        if (!blockGamePointer) return;
        (document.activeElement as HTMLElement | null)?.blur?.();
      }}
    >
      <div className="pointer-events-none absolute left-3 top-3 z-20 rounded-lg bg-black/45 px-2.5 py-1 text-[10px] font-bold text-cyan-100/90 backdrop-blur md:text-xs">
        <span className="flex items-center gap-1.5">
          <Film className="h-3.5 w-3.5" aria-hidden />
          {ready ? badgeLabel : `${badgeLabel}加载中…`}
        </span>
      </div>

      <div
        className={`relative min-h-0 flex-1 ${blockGamePointer ? "pointer-events-none select-none" : ""}`}
      >
        <div
          id="unity-game-mount"
          className="absolute inset-0 min-h-[200px] touch-none bg-black/40"
          aria-hidden
        />
        <canvas
          id="unity-canvas"
          className="absolute inset-0 min-h-[200px] h-full w-full touch-none bg-black/40"
          tabIndex={-1}
          aria-label="Unity WebGL 熊大画面"
        />

        {!ready && (
          <motion.div
            initial={{ opacity: 0.9 }}
            animate={{ opacity: 1 }}
            className="pointer-events-none absolute inset-0 z-10 flex flex-col items-center justify-center gap-2 bg-slate-950/75 px-4 text-center"
          >
            <p className="text-lg font-extrabold tracking-wide text-cyan-100">
              {merged ? "统一 WebGL（熊大 + 地图）" : "Unity 熊大实时互动窗口"}
            </p>
            <p className="max-w-md text-sm leading-relaxed text-cyan-100/80">
              {bootHint ? (
                <>正在加载 3D 场景…若长时间黑屏，请按 F12 看控制台报错。</>
              ) : merged ? (
                <>正在启动统一 WebGL（熊大 + 地图），首次加载约需 30 秒…</>
              ) : (
                <>
                  若已拷贝 WebGL 仍为本页：请确认存在{" "}
                  <code className="rounded bg-black/50 px-1">public/webgl/build-info.json</code>
                  ，且需重启 <code className="rounded bg-black/50 px-1">npm run dev</code>。
                </>
              )}
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
