import { useEffect, useState } from "react";
import { CloudSun } from "lucide-react";
import { fetchWeatherCurrent, type WeatherSnapshot } from "../bear_pipeline/bearAgentClient";

export function WeatherBadge() {
  const [weather, setWeather] = useState<WeatherSnapshot | null>(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const snap = await fetchWeatherCurrent();
        if (!cancelled) {
          setWeather(snap);
          setErr("");
        }
      } catch (e) {
        if (!cancelled) {
          setErr(e instanceof Error ? e.message : String(e));
        }
      }
    };
    void load();
    const id = window.setInterval(() => void load(), 10 * 60 * 1000);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, []);

  if (!weather && !err) return null;

  const label = weather
    ? `${weather.location_name || "乐园"} ${weather.text || "—"} ${weather.temp_c ?? "—"}℃`
    : "天气暂不可用";

  return (
    <div
      className="pointer-events-none absolute right-2 top-14 z-20 flex max-w-[min(92vw,320px)] items-center gap-1.5 rounded-full border border-sky-200/80 bg-white/90 px-3 py-1 text-xs font-semibold text-sky-950 shadow-sm backdrop-blur md:right-4 md:top-[3.25rem] md:text-sm"
      title={weather?.tip || err || label}
    >
      <CloudSun className="h-4 w-4 shrink-0 text-sky-600" aria-hidden />
      <span className="truncate">{label}</span>
      {weather?.source === "demo" ? (
        <span className="shrink-0 rounded bg-amber-100 px-1 text-[10px] text-amber-900">演示</span>
      ) : null}
    </div>
  );
}
