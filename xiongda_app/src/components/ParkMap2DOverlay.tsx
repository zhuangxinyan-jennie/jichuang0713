import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { motion, AnimatePresence } from "framer-motion";
import { MapPinned, Maximize2, X, Star } from "lucide-react";
import { subscribeMap2DHighlight, type Map2DHighlight } from "../services/map2dHighlightStore";

const MAP_SRC = "/map/park-map.png";
const PLACES_URL = "/map/places_2d.json";

export type Place2D = {
  name: string;
  leftPct: number;
  topPct: number;
  /** toilet / attraction / service … */
  category?: string;
};

type ParkMap2DOverlayProps = {
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
  onSelectPlace?: (name: string) => void;
};

function placeIsHighlighted(p: Place2D, hl: Map2DHighlight | null): boolean {
  if (!hl) return false;
  if (hl.names?.length) return hl.names.includes(p.name);
  if (hl.category) {
    if ((p.category || "").toLowerCase() === hl.category.toLowerCase()) return true;
    if (hl.category === "toilet" && /厕所|卫生间|洗手间/.test(p.name)) return true;
  }
  return false;
}

/**
 * 地图查询页：右下角 2D 缩略图；点击后浮层放大。
 * 说「厕所」时由 Agent 触发高亮（闪烁圈）。
 */
export function ParkMap2DOverlay({ open: openProp, onOpenChange, onSelectPlace }: ParkMap2DOverlayProps) {
  const [internalOpen, setInternalOpen] = useState(false);
  const open = openProp ?? internalOpen;
  const setOpen = (v: boolean) => {
    onOpenChange?.(v);
    if (openProp === undefined) setInternalOpen(v);
  };

  const [places, setPlaces] = useState<Place2D[]>([]);
  const [imgErr, setImgErr] = useState(false);
  const [selected, setSelected] = useState<string | null>(null);
  const [highlight, setHighlight] = useState<Map2DHighlight | null>(null);

  useEffect(() => {
    let cancelled = false;
    void fetch(PLACES_URL, { cache: "no-store" })
      .then((r) => r.json())
      .then((data: { places?: Place2D[] }) => {
        if (cancelled) return;
        const list = Array.isArray(data.places) ? data.places : [];
        setPlaces(list.filter((p) => p?.name && Number.isFinite(p.leftPct) && Number.isFinite(p.topPct)));
      })
      .catch(() => {
        if (!cancelled) setPlaces([]);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    return subscribeMap2DHighlight((h) => {
      setHighlight(h);
      if (h && h.openModal !== false) {
        setOpen(true);
      }
    });
    // setOpen 稳定闭包足够
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const onStarClick = (name: string) => {
    setSelected(name);
    onSelectPlace?.(name);
  };

  const highlightedCount = places.filter((p) => placeIsHighlighted(p, highlight)).length;
  const highlightHint =
    highlight?.category === "toilet"
      ? `已高亮卫生间 ${highlightedCount} 处（闪烁圈）`
      : highlight?.names?.length
        ? `已高亮：${highlight.names.join("、")}`
        : null;

  const renderMarkers = (compact: boolean) =>
    places.map((p) => {
      const active = selected === p.name;
      const lit = placeIsHighlighted(p, highlight);
      const isToilet = (p.category || "").toLowerCase() === "toilet" || /厕所/.test(p.name);
      if (compact && !lit && !isToilet) {
        // 缩略图只显示高亮/厕所，避免星星过密
        return null;
      }
      return (
        <button
          key={p.name}
          type="button"
          data-gesture-clickable
          data-gesture-label={p.name}
          aria-label={p.name}
          title={p.name}
          onClick={() => onStarClick(p.name)}
          className={`absolute z-10 -translate-x-1/2 -translate-y-1/2 rounded-full p-0.5 focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-200 ${
            active || lit ? "scale-125" : "hover:scale-110"
          }`}
          style={{ left: `${p.leftPct}%`, top: `${p.topPct}%` }}
        >
          {lit ? (
            <span className="pointer-events-none absolute left-1/2 top-1/2 z-0 h-12 w-12 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-cyan-300/90 bg-cyan-400/25 animate-ping" />
          ) : null}
          <span
            className={`relative z-10 flex items-center justify-center rounded-full border-2 shadow-md ${
              compact ? "h-5 w-5" : "h-7 w-7 md:h-8 md:w-8"
            } ${
              lit
                ? "border-cyan-200 bg-cyan-400 text-slate-950 ring-2 ring-cyan-300/80"
                : active
                  ? "border-amber-200 bg-amber-400 text-amber-950"
                  : isToilet
                    ? "border-yellow-200 bg-yellow-400 text-slate-900"
                    : "border-white/90 bg-rose-500/95 text-white"
            }`}
          >
            {isToilet ? (
              <span className={`font-black ${compact ? "text-[8px]" : "text-[10px] md:text-xs"}`}>WC</span>
            ) : (
              <Star className={`${compact ? "h-2.5 w-2.5" : "h-3.5 w-3.5 md:h-4 md:w-4"} fill-current`} aria-hidden />
            )}
          </span>
          {!compact && (active || lit) ? (
            <span className="absolute left-1/2 top-full z-20 mt-1 -translate-x-1/2 whitespace-nowrap rounded bg-black/80 px-2 py-0.5 text-[10px] font-bold text-amber-100 md:text-xs">
              {p.name}
            </span>
          ) : null}
        </button>
      );
    });

  const modal =
    typeof document !== "undefined"
      ? createPortal(
          <AnimatePresence>
            {open ? (
              <motion.div
                className="fixed inset-0 z-[80] flex items-center justify-center bg-black/70 p-3 backdrop-blur-sm md:p-6"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                role="dialog"
                aria-modal="true"
                aria-label="2D 乐园地图"
              >
                <button
                  type="button"
                  aria-label="关闭背景"
                  data-gesture-clickable
                  className="absolute inset-0 cursor-default"
                  onClick={() => setOpen(false)}
                />
                <motion.div
                  initial={{ scale: 0.72, opacity: 0.6, y: 40 }}
                  animate={{ scale: 1, opacity: 1, y: 0 }}
                  exit={{ scale: 0.85, opacity: 0, y: 24 }}
                  transition={{ type: "spring", stiffness: 280, damping: 26 }}
                  className="relative z-[81] flex max-h-[min(92vh,900px)] w-full max-w-[min(96vw,1100px)] flex-col overflow-hidden rounded-2xl border-2 border-amber-300/70 bg-slate-950 shadow-2xl"
                  onClick={(e) => e.stopPropagation()}
                >
                  <div className="flex shrink-0 items-center justify-between gap-2 border-b border-amber-400/30 bg-gradient-to-r from-amber-600/90 to-emerald-700/80 px-3 py-2 text-amber-50">
                    <div className="min-w-0">
                      <p className="text-sm font-black md:text-base">2D 乐园地图</p>
                      <p className="truncate text-[11px] text-amber-50/90 md:text-xs">
                        {highlightHint
                          ? highlightHint
                          : selected
                            ? `已选：${selected}`
                            : "星星=景点 · 黄标 WC=厕所 · 说「厕所」可一键高亮"}
                      </p>
                    </div>
                    <button
                      type="button"
                      data-gesture-clickable
                      aria-label="关闭2D地图"
                      onClick={() => setOpen(false)}
                      className="inline-flex items-center gap-1 rounded-lg bg-black/35 px-3 py-1.5 text-xs font-bold hover:bg-black/50 focus:outline-none focus-visible:ring-2 focus-visible:ring-white"
                    >
                      <X className="h-4 w-4" aria-hidden />
                      关闭
                    </button>
                  </div>

                  <div className="relative min-h-0 flex-1 overflow-auto bg-slate-900">
                    <div className="relative mx-auto w-full max-w-[1100px]">
                      {imgErr ? (
                        <div className="flex min-h-[280px] items-center justify-center p-8 text-sm text-slate-300">
                          未找到 public/map/park-map.png
                        </div>
                      ) : (
                        <img
                          src={MAP_SRC}
                          alt="乐园 2D 导览图"
                          className="block h-auto w-full select-none"
                          draggable={false}
                          onError={() => setImgErr(true)}
                        />
                      )}
                      {renderMarkers(false)}
                    </div>
                  </div>
                </motion.div>
              </motion.div>
            ) : null}
          </AnimatePresence>,
          document.body
        )
      : null;

  return (
    <>
      {!open ? (
        <button
          type="button"
          data-gesture-clickable
          aria-label="2D地图"
          title="打开 2D 平面图"
          onClick={() => setOpen(true)}
          className="group absolute bottom-3 right-3 z-30 flex w-[min(42vw,220px)] flex-col overflow-hidden rounded-xl border-2 border-amber-300/80 bg-black/55 shadow-[0_8px_28px_rgba(0,0,0,0.45)] backdrop-blur transition hover:scale-[1.02] hover:border-amber-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-300"
        >
          <div className="flex items-center justify-between gap-1 bg-amber-500/90 px-2 py-1 text-[11px] font-black text-amber-950">
            <span className="flex items-center gap-1">
              <MapPinned className="h-3.5 w-3.5" aria-hidden />
              2D地图
            </span>
            <Maximize2 className="h-3.5 w-3.5 opacity-80" aria-hidden />
          </div>
          <div className="relative">
            {imgErr ? (
              <div className="flex h-28 items-center justify-center bg-slate-800 px-2 text-center text-[10px] text-slate-200">
                缺少 park-map.png
              </div>
            ) : (
              <img
                src={MAP_SRC}
                alt=""
                className="h-28 w-full object-cover object-center"
                draggable={false}
                onError={() => setImgErr(true)}
              />
            )}
            <div className="pointer-events-none absolute inset-0">{renderMarkers(true)}</div>
          </div>
          <span className="bg-black/70 px-2 py-1 text-[10px] font-semibold text-amber-100 group-hover:text-white">
            {highlightHint ? highlightHint : "点击放大 · 说「厕所」可高亮"}
          </span>
        </button>
      ) : null}
      {modal}
    </>
  );
}
