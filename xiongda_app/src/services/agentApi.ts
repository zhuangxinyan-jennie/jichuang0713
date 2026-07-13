import type { AgentContext } from "./agentContext";
import type { AgentJsonPayload, TerminalCommand } from "../types";
import { handleBearAgentPayload } from "../bear_pipeline/handleBearAgentPayload";
import { sendSmplStreamingRelativePath } from "./unitySendClip";
import { runMockAgent } from "./mockAgent";
import { announceBearSpeech } from "./xiongdaTts";

function applySmplFromPayload(
  o: AgentJsonPayload & Record<string, unknown>,
  ctx: AgentContext
): boolean {
  const raw =
    (typeof o.smpl_streaming_path === "string" && o.smpl_streaming_path) ||
    (typeof o.smpl_rel_path === "string" && o.smpl_rel_path) ||
    (typeof (o as { smpl_path?: string }).smpl_path === "string" && (o as { smpl_path: string }).smpl_path);
  if (!raw || typeof raw !== "string") return false;
  const path = raw.trim();
  sendSmplStreamingRelativePath(path);
  ctx.setCurrentSmplPath(path);
  return true;
}

/**
 * 接 310B / 云端 Agent 的 JSON 字符串；解析后驱动 Unity SMPL JSON 与页面字幕。
 */
export function handleAgentJson(json: string, ctx: AgentContext): void {
  try {
    const o = JSON.parse(json) as AgentJsonPayload & Record<string, unknown>;
    const looksLikeBearAgent =
      typeof o.interaction_type === "string" ||
      (Array.isArray(o.clip_ids) && o.clip_ids.length > 0) ||
      o.motion_type === "generated" ||
      (Array.isArray(o.actions) && o.actions.length > 0);

    if (looksLikeBearAgent) {
      handleBearAgentPayload(o, ctx);
      return;
    }

    if (!applySmplFromPayload(o, ctx)) {
      console.warn("[handleAgentJson] 无 smpl_streaming_path（或兼容字段 smpl_rel_path / smpl_path）", o);
    }
    if (o.speech && typeof o.speech === "string") {
      ctx.setSubtitle(o.speech);
      announceBearSpeech(o.speech);
    } else {
      const cmd = o as import("../types").TerminalCommand;
      if (cmd.speech) {
        ctx.setSubtitle(String(cmd.speech));
        announceBearSpeech(String(cmd.speech));
      }
    }
  } catch (e) {
    console.error("[handleAgentJson] JSON 解析失败", e);
  }
}

/**
 * 文字 / 本地 Mock Agent → 播放 SMPL 动作与更新字幕（后续可换为真实 ASR+310B）。
 */
export function handleSpeechInput(text: string, ctx: AgentContext): void {
  const t = text.trim();
  if (!t) return;
  const cmd = runMockAgent(t);
  if (cmd.smpl_streaming_path) {
    sendSmplStreamingRelativePath(cmd.smpl_streaming_path);
    ctx.setCurrentSmplPath(cmd.smpl_streaming_path);
  }
  const reply = cmd.speech ?? "";
  ctx.setSubtitle(reply);
  if (reply.trim()) announceBearSpeech(reply);
}

/**
 * 地图查询：占位，可接导航或 Unity UI。
 */
export function handleMapQuery(_query: string, ctx: AgentContext): void {
  console.log("[handleMapQuery] 进入地图模式", _query);
  ctx.setCurrentSmplPath("—（地图模式）");
  ctx.setSubtitle(
    "在下方输入目的地，例如「怎么去海螺湾」「飞越极限怎么走」。需 bear_agent 开启并提供 POST /api/map-query。熊大语音另启：cosyvoice_live_release → python tts_server.py（默认 9890）。"
  );
}

/**
 * 项目推荐：占位动作与台词。
 */
export function handleRecommendation(ctx: AgentContext): void {
  console.log("[handleRecommendation] 预留 项目推荐");
  const path = "SmplhRetarget/摊手疑问.json";
  sendSmplStreamingRelativePath(path);
  ctx.setCurrentSmplPath(path);
  const s = "推荐位后续从后端拉取，当前为占位讲解动作。";
  ctx.setSubtitle(s);
  announceBearSpeech(s);
}

/**
 * 把完整 `TerminalCommand` 交给桥（如已有结构体）。
 */
export function dispatchTerminalCommand(cmd: TerminalCommand, ctx: AgentContext): void {
  if (cmd.smpl_streaming_path) {
    sendSmplStreamingRelativePath(cmd.smpl_streaming_path);
    ctx.setCurrentSmplPath(cmd.smpl_streaming_path);
  }
  console.log("[Command To Unity/Bridge]", cmd);
  if (cmd.speech) {
    ctx.setSubtitle(cmd.speech);
    announceBearSpeech(cmd.speech);
  }
}
