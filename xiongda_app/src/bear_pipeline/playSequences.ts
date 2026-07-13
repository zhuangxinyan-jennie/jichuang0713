import type { AgentContext } from "../services/agentContext";
import { sendClipById, sendSmplStreamingRelativePath } from "../services/unitySendClip";

/** 与 Unity ClipIdPlayer.PlayClipSequence 默认间隔接近 */
export const DEFAULT_CLIP_STEP_MS = 4000;
export const DEFAULT_SMPL_STEP_MS = 3500;

let runId = 0;

function nextRun(): number {
  runId += 1;
  return runId;
}

function isStale(gen: number): boolean {
  return gen !== runId;
}

/**
 * 按间隔依次发送 clip_id（WebGL 无法直接调 Unity 协程，由网页侧错峰触发）。
 */
export function playClipIdSequence(
  clipIds: string[],
  ctx: AgentContext,
  stepMs: number = DEFAULT_CLIP_STEP_MS
): void {
  const gen = nextRun();
  const ids = clipIds.map((s) => s.trim()).filter(Boolean);
  if (ids.length === 0) return;

  ids.forEach((id, i) => {
    window.setTimeout(() => {
      if (isStale(gen)) return;
      sendClipById(id);
      ctx.setCurrentSmplPath(`clip:${id}`);
    }, i * stepMs);
  });
}

/**
 * 按间隔依次播放 SMPL 相对路径。
 */
export function playSmplPathSequence(
  relativePaths: string[],
  ctx: AgentContext,
  stepMs: number = DEFAULT_SMPL_STEP_MS
): void {
  const gen = nextRun();
  const paths = relativePaths.map((s) => s.trim()).filter(Boolean);
  if (paths.length === 0) return;

  paths.forEach((p, i) => {
    window.setTimeout(() => {
      if (isStale(gen)) return;
      sendSmplStreamingRelativePath(p);
      ctx.setCurrentSmplPath(p);
    }, i * stepMs);
  });
}

/** 新一轮 Agent 输出开始时调用，取消尚未触发的队列回调 */
export function cancelQueuedSequences(): void {
  nextRun();
}
