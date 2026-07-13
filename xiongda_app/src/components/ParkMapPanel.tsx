import { useState } from "react";
import { MapPinned } from "lucide-react";

const MAP_SRC = "/map/park-map.png";

/**
 * 乐园平面图（与 bear_agent/map_guide 地名一致的可视参考）。
 * 图片置于 `public/map/park-map.png`（可由 bear_agent/地图.png 拷贝）。
 */
export function ParkMapPanel() {
  const [imgErr, setImgErr] = useState(false);

  return (
    <div className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-2xl border-2 border-emerald-500/25 bg-slate-900/5 shadow-inner">
      <div className="flex shrink-0 items-center gap-2 border-b border-emerald-500/15 bg-white/60 px-3 py-2 backdrop-blur-sm">
        <MapPinned className="h-4 w-4 text-emerald-700" aria-hidden />
        <span className="text-xs font-black text-emerald-900 md:text-sm">乐园地图</span>
        <span className="text-[10px] font-semibold text-slate-500 md:text-xs">
          问路结果见底部「熊大回复」；本页不显示 3D 熊大
        </span>
      </div>
      <div className="relative min-h-0 flex-1 bg-gradient-to-b from-sky-100/40 to-slate-100/30">
        {imgErr ? (
          <div className="flex h-full min-h-[200px] flex-col items-center justify-center gap-2 p-6 text-center text-sm text-slate-600">
            <p>未找到地图文件。</p>
            <p className="font-mono text-xs">
              请将乐园平面图放到 <code className="rounded bg-white px-1">public/map/park-map.png</code>
            </p>
          </div>
        ) : (
          <img
            src={MAP_SRC}
            alt="乐园导览地图"
            className="h-full w-full object-contain object-center"
            loading="lazy"
            decoding="async"
            onError={() => setImgErr(true)}
          />
        )}
      </div>
    </div>
  );
}
