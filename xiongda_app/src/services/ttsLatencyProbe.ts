type ProbeMark = {
  name: string;
  ms: number;
  data?: Record<string, unknown>;
};

export type TtsLatencyEvent = {
  id: string;
  kind: string;
  status: string;
  wall_ts: number;
  duration_ms: number;
  meta: Record<string, unknown>;
  marks: ProbeMark[];
  extra?: Record<string, unknown>;
};

const STORAGE_KEY = "xiongda.ttsLatency.events";
const ENABLE_KEY = "xiongda.ttsLatency.enabled";
const MAX_EVENTS = 200;

let activeContext: Record<string, unknown> | null = null;

type ProbeWindow = Window & {
  __xiongdaTtsLatency?: {
    enable: () => void;
    disable: () => void;
    dump: () => TtsLatencyEvent[];
    clear: () => void;
    download: () => void;
  };
};

function isEnabled(): boolean {
  if (typeof window === "undefined") return false;
  const env = (import.meta.env.VITE_TTS_LATENCY_PROBE as string | undefined)?.trim().toLowerCase();
  if (env === "1" || env === "true") return true;
  try {
    const qs = new URLSearchParams(window.location.search);
    if (qs.get("ttsLatency") === "1") return true;
    return window.localStorage.getItem(ENABLE_KEY) === "1";
  } catch {
    return false;
  }
}

function readEvents(): TtsLatencyEvent[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    const parsed: unknown = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? (parsed as TtsLatencyEvent[]) : [];
  } catch {
    return [];
  }
}

function writeEvents(events: TtsLatencyEvent[]): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(events.slice(-MAX_EVENTS)));
  } catch {
    /* ignore */
  }
}

function appendEvent(event: TtsLatencyEvent): void {
  if (typeof window === "undefined") return;
  const events = readEvents();
  events.push(event);
  writeEvents(events);
  // eslint-disable-next-line no-console
  console.info("[tts-latency]", event);
}

function installConsoleApi(): void {
  if (typeof window === "undefined") return;
  const w = window as ProbeWindow;
  if (w.__xiongdaTtsLatency) return;
  w.__xiongdaTtsLatency = {
    enable() {
      window.localStorage.setItem(ENABLE_KEY, "1");
      // eslint-disable-next-line no-console
      console.info("[tts-latency] enabled; refresh or trigger another speech.");
    },
    disable() {
      window.localStorage.removeItem(ENABLE_KEY);
      // eslint-disable-next-line no-console
      console.info("[tts-latency] disabled.");
    },
    dump() {
      const events = readEvents();
      // eslint-disable-next-line no-console
      console.table(
        events.map((e) => ({
          wall_ts: new Date(e.wall_ts).toLocaleTimeString(),
          kind: e.kind,
          status: e.status,
          total_ms: e.duration_ms,
          text: String(e.meta.text || "").slice(0, 40),
        }))
      );
      return events;
    },
    clear() {
      writeEvents([]);
      // eslint-disable-next-line no-console
      console.info("[tts-latency] cleared.");
    },
    download() {
      const blob = new Blob([readEvents().map((e) => JSON.stringify(e)).join("\n") + "\n"], {
        type: "application/jsonl;charset=utf-8",
      });
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = `xiongda_tts_latency_${Date.now()}.jsonl`;
      a.click();
      URL.revokeObjectURL(a.href);
    },
  };
}

export function createTtsLatencyProbe(
  kind: string,
  meta: Record<string, unknown>
): {
  id: string;
  mark: (name: string, data?: Record<string, unknown>) => void;
  finish: (status: string, extra?: Record<string, unknown>) => void;
} | null {
  installConsoleApi();
  if (!isEnabled() || typeof performance === "undefined") return null;

  const started = performance.now();
  const marks: ProbeMark[] = [];
  let done = false;
  const contextAtStart = activeContext ? { ...activeContext } : {};
  const id =
    typeof crypto !== "undefined" && "randomUUID" in crypto
      ? crypto.randomUUID()
      : `${Date.now()}-${Math.random().toString(16).slice(2)}`;

  return {
    id,
    mark(name: string, data?: Record<string, unknown>) {
      if (done) return;
      marks.push({
        name,
        ms: Math.round((performance.now() - started) * 10) / 10,
        ...(data ? { data } : {}),
      });
    },
    finish(status: string, extra?: Record<string, unknown>) {
      if (done) return;
      done = true;
      appendEvent({
        id,
        kind,
        status,
        wall_ts: Date.now(),
        duration_ms: Math.round((performance.now() - started) * 10) / 10,
        meta: { ...contextAtStart, ...meta },
        marks,
        ...(extra ? { extra } : {}),
      });
    },
  };
}

export const createLatencyProbe = createTtsLatencyProbe;

export function setTtsLatencyContext(meta: Record<string, unknown> | null): void {
  activeContext = meta && Object.keys(meta).length > 0 ? { ...meta } : null;
}

export function clearTtsLatencyContext(traceId?: string): void {
  if (!activeContext) return;
  if (traceId && activeContext.traceId !== traceId) return;
  activeContext = null;
}
