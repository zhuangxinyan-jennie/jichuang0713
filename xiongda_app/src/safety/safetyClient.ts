import { rewriteLoopbackServiceUrl } from "../services/lanServiceUrl";
import type { SafetyState } from "./types";

const DEFAULT_AGENT_BASE = "http://127.0.0.1:8765";

function baseUrl(): string {
  const raw = (import.meta.env.VITE_BEAR_AGENT_URL as string | undefined)?.trim();
  if (raw) return rewriteLoopbackServiceUrl(raw, DEFAULT_AGENT_BASE).replace(/\/$/, "");
  const useProxy = String(import.meta.env.VITE_BEAR_AGENT_USE_PROXY || "").trim().toLowerCase();
  if (import.meta.env.DEV && (useProxy === "1" || useProxy === "true")) return "";
  return rewriteLoopbackServiceUrl(undefined, DEFAULT_AGENT_BASE).replace(/\/$/, "");
}

async function parseSafetyResponse(response: Response): Promise<SafetyState> {
  if (!response.ok) {
    const text = await response.text().catch(() => "");
    throw new Error(`Safety HTTP ${response.status}${text ? `: ${text.slice(0, 160)}` : ""}`);
  }
  return (await response.json()) as SafetyState;
}

export async function fetchSafetyState(signal?: AbortSignal): Promise<SafetyState> {
  const response = await fetch(`${baseUrl()}/api/safety/state`, {
    cache: "no-store",
    signal,
  });
  return parseSafetyResponse(response);
}

export async function triggerSafetyDemo(): Promise<SafetyState> {
  const response = await fetch(`${baseUrl()}/api/safety/demo/trigger`, { method: "POST" });
  return parseSafetyResponse(response);
}

export async function releaseSafetyDemo(): Promise<SafetyState> {
  const response = await fetch(`${baseUrl()}/api/safety/demo/release`, { method: "POST" });
  return parseSafetyResponse(response);
}

export async function finishSafetyRecovery(): Promise<SafetyState> {
  const response = await fetch(`${baseUrl()}/api/safety/recovery-done`, { method: "POST" });
  return parseSafetyResponse(response);
}
