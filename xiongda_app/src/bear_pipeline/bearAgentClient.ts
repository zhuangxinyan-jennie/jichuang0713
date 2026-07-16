import type {
  BearAgentBoardAutoLast,
  BearAgentProcessTestResponse,
  PerceptionPayload,
} from "./bearAgentTypes";

function strField(o: Record<string, unknown>, key: string): string {
  const v = o[key];
  return typeof v === "string" ? v.trim() : "";
}

function numOrNull(v: unknown): number | null {
  if (v === null || v === undefined) return null;
  const n = typeof v === "number" ? v : Number(v);
  return Number.isFinite(n) ? n : null;
}
import { normalizePerceptionPayload } from "./normalizeBoardPerception";
import { rewriteLoopbackServiceUrl } from "../services/lanServiceUrl";

type HttpProbe = {
  mark: (name: string, data?: Record<string, unknown>) => void;
};

type RequestProbeOptions = {
  probe?: HttpProbe | null;
};

/**
 * Agent HTTP 基址。
 * - 显式设置 `VITE_BEAR_AGENT_URL` 时优先（局域网调试填 http://电脑IP:8765）。
 * - 开发模式下 `VITE_BEAR_AGENT_USE_PROXY=1` 且未设置 URL 时走同源 `/api/*`，由 Vite 转发到本机 8765，避免 CORS 遗漏。
 */
/** 界面展示的连接说明（与 fetch 使用的 base 一致） */
export function bearAgentBaseLabel(): string {
  const b = baseUrl();
  return b || "(开发模式：请求同源 /api/*，由 Vite 转发到 Bear Agent)";
}

function baseUrl(): string {
  const explicit = (import.meta.env.VITE_BEAR_AGENT_URL as string | undefined)?.trim();
  if (explicit) {
    return rewriteLoopbackServiceUrl(explicit, "http://127.0.0.1:8765");
  }
  const useProxy = (import.meta.env.VITE_BEAR_AGENT_USE_PROXY as string | undefined)?.trim().toLowerCase();
  if (import.meta.env.DEV && (useProxy === "1" || useProxy === "true")) {
    return "";
  }
  return rewriteLoopbackServiceUrl(undefined, "http://127.0.0.1:8765");
}

export async function postProcessTest(
  perception: PerceptionPayload
): Promise<BearAgentProcessTestResponse> {
  const res = await fetch(`${baseUrl().replace(/\/$/, "")}/api/process-test`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(perception),
  });
  const text = await res.text();
  if (!res.ok) {
    throw new Error(text || `HTTP ${res.status}`);
  }
  return JSON.parse(text) as BearAgentProcessTestResponse;
}

/** 完整状态机；无输出时为 `null` */
export async function postProcessFull(perception: PerceptionPayload): Promise<BearAgentProcessTestResponse | null> {
  return postProcessFullWithOptions(perception);
}

export async function postProcessFullWithOptions(
  perception: PerceptionPayload,
  options?: RequestProbeOptions
): Promise<BearAgentProcessTestResponse | null> {
  options?.probe?.mark("agent_fetch_start", { endpoint: "/api/process" });
  const res = await fetch(`${baseUrl().replace(/\/$/, "")}/api/process`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(perception),
  });
  options?.probe?.mark("agent_response_headers", { endpoint: "/api/process", ok: res.ok, status: res.status });
  const text = await res.text();
  options?.probe?.mark("agent_response_body", { endpoint: "/api/process", bytes: text.length });
  if (!res.ok) {
    throw new Error(text || `HTTP ${res.status}`);
  }
  const parsed: unknown = JSON.parse(text);
  if (parsed === null) {
    return null;
  }
  return parsed as BearAgentProcessTestResponse;
}

function parseAgentOutput(raw: unknown): BearAgentProcessTestResponse | null {
  if (raw === null || raw === undefined) return null;
  if (typeof raw !== "object") return null;
  return raw as BearAgentProcessTestResponse;
}

/** 轮询板端自动推理结果（需 board_bridge POST 时带 X-Agent-Caller: board-bridge） */
export async function fetchBoardAutoLast(): Promise<BearAgentBoardAutoLast> {
  const res = await fetch(`${baseUrl().replace(/\/$/, "")}/api/board-auto/last`);
  const text = await res.text();
  if (!res.ok) {
    if (res.status === 404) {
      throw new Error(
        "HTTP 404：未找到 /api/board-auto/last。请更新 bear_agent 并重启 integration_test/server.py。"
      );
    }
    throw new Error(text || `HTTP ${res.status}`);
  }
  let parsed: unknown;
  try {
    parsed = JSON.parse(text) as unknown;
  } catch {
    throw new Error("board-auto 返回不是合法 JSON");
  }
  if (!parsed || typeof parsed !== "object") {
    throw new Error("Invalid board-auto response");
  }
  const o = parsed as Record<string, unknown>;
  const seq = typeof o.seq === "number" ? o.seq : Number(o.seq);
  const ts = o.ts === null || o.ts === undefined ? null : Number(o.ts);
  const output = o.output === undefined ? null : parseAgentOutput(o.output);
  const perception = normalizePerceptionPayload(o.perception);
  return {
    seq: Number.isFinite(seq) ? seq : 0,
    ts: ts !== null && Number.isFinite(ts) ? ts : null,
    output,
    perception,
    asr_partial: strField(o, "asr_partial"),
    asr_final: strField(o, "asr_final"),
    asr_normalized: strField(o, "asr_normalized"),
    asr_live_ts: numOrNull(o.asr_live_ts),
  };
}

/** 通知 Agent：本轮熊大语音（SoVITS / 浏览器 / 预烘焙 WAV 队列）已全部播完，允许 board_bridge 下一次 POST。 */
export async function postMultimodalPlaybackDone(): Promise<void> {
  try {
    const res = await fetch(`${baseUrl().replace(/\/$/, "")}/api/multimodal/playback-done`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
    });
    if (!res.ok) {
      const t = await res.text().catch(() => "");
      console.warn("[bearAgent] playback-done HTTP", res.status, t);
    }
  } catch (e) {
    console.warn("[bearAgent] playback-done failed", e);
  }
}

export async function postMultimodalPlaybackStart(): Promise<void> {
  try {
    const res = await fetch(`${baseUrl().replace(/\/$/, "")}/api/multimodal/playback-start`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
    });
    if (!res.ok) {
      const t = await res.text().catch(() => "");
      console.warn("[bearAgent] playback-start HTTP", res.status, t);
    }
  } catch (e) {
    console.warn("[bearAgent] playback-start failed", e);
  }
}

export async function postReset(): Promise<void> {
  const res = await fetch(`${baseUrl().replace(/\/$/, "")}/api/reset`, { method: "POST" });
  if (!res.ok) {
    const t = await res.text();
    throw new Error(t || `HTTP ${res.status}`);
  }
}

/** 纯地图问路（bear_agent `POST /api/map-query` → MapGuide），不经玩法状态机 */
export async function postMapQuery(perception: PerceptionPayload): Promise<BearAgentProcessTestResponse> {
  return postMapQueryWithOptions(perception);
}

export async function postMapQueryWithOptions(
  perception: PerceptionPayload,
  options?: RequestProbeOptions
): Promise<BearAgentProcessTestResponse> {
  options?.probe?.mark("agent_fetch_start", { endpoint: "/api/map-query" });
  const res = await fetch(`${baseUrl().replace(/\/$/, "")}/api/map-query`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(perception),
  });
  options?.probe?.mark("agent_response_headers", { endpoint: "/api/map-query", ok: res.ok, status: res.status });
  const text = await res.text();
  options?.probe?.mark("agent_response_body", { endpoint: "/api/map-query", bytes: text.length });
  if (!res.ok) {
    throw new Error(text || `HTTP ${res.status}`);
  }
  return JSON.parse(text) as BearAgentProcessTestResponse;
}
