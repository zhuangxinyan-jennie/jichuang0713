import { UnityEmbed } from "./UnityEmbed";
import { ParkMap2DOverlay } from "./ParkMap2DOverlay";
import { mergedUnityBasePath } from "../services/unityMergedMode";

type WorldUnityEmbedProps = {
  blockGamePointer?: boolean;
  onSelect2DPlace?: (name: string) => void;
  mergedReady: boolean;
};

/**
 * 「全图互动」：单 WebGL 内双熊（互动 + 导览），产物 public/webgl-merged/
 */
export function WorldUnityEmbed({
  blockGamePointer = false,
  onSelect2DPlace,
  mergedReady,
}: WorldUnityEmbedProps) {
  if (!mergedReady) {
    return (
      <div className="flex min-h-0 flex-1 flex-col items-center justify-center gap-3 bg-gradient-to-b from-sky-100/40 to-cream/80 p-6 text-center">
        <p className="text-lg font-extrabold text-forest-deep">全图互动 WebGL 尚未构建</p>
        <p className="max-w-md text-sm leading-relaxed text-slate-600">
          请在 Unity 打开 <code className="rounded bg-white/80 px-1">XiongdaParkMapMergedProject</code>
          ，运行菜单「合并工程：挂上 UnityBridge + 模式相机」，再「构建合并 WebGL 到 webgl-merged」。
        </p>
        <p className="text-xs text-slate-500">
          或执行：<code className="rounded bg-white/80 px-1">scripts/build_merged_webgl.ps1</code>
        </p>
      </div>
    );
  }

  return (
    <div className="relative flex min-h-0 flex-1 flex-col">
      <UnityEmbed
        blockGamePointer={blockGamePointer}
        basePath={mergedUnityBasePath()}
        badgeLabel="全图互动 · 聊天 + 导览"
      />
      {onSelect2DPlace ? (
        <div className="pointer-events-none absolute inset-0 z-30 [&_button]:pointer-events-auto">
          <ParkMap2DOverlay onSelectPlace={onSelect2DPlace} />
        </div>
      ) : null}
    </div>
  );
}
