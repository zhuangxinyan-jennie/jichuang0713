/** POST /api/process-test 请求体（与 bear_agent agent.process 文档一致，字段均可选） */
export type PerceptionPayload = {
  emotion?: string;
  emotion_confidence?: number;
  gesture?: string;
  gesture_confidence?: number;
  hand_gesture?: string;
  hand_gesture_confidence?: number;
  person_detected?: boolean;
  person_count?: number;
  face_bbox?: number[] | null;
  speech_text?: string;
};

/** 随机互动典型返回（字段可能随 parser 扩展） */
export type BearAgentProcessTestResponse = {
  speech?: string;
  motion_type?: string;
  actions?: string[];
  motion_description?: string | null;
  emotion?: string;
  interaction_type?: string;
  /** 后端玩法状态机给前端的目标页面提示 */
  target_mode?: "random" | "voice" | "story" | "map";
  clip_ids?: string[];
  /** 剧情预烘焙语音 id，与 public/theater_voice/tp_{id}.wav 对应 */
  story_voice_ids?: (string | null | undefined)[];
  story_waiting_hint?: string;
  story_finished?: boolean;
};

/** board_bridge 高频同步的 ASR 原文（与 latest_asr.json 一致） */
export type BoardAsrLiveFields = {
  /** 流式草稿（散句） */
  asr_partial: string;
  /** 整句 raw */
  asr_final: string;
  /** 整句归一化 */
  asr_normalized: string;
  /** 服务端更新时间戳（秒），可选 */
  asr_live_ts: number | null;
};

/** GET /api/board-auto/last — 板端 board_bridge 触发的最近一次响应（供前端轮询） */
export type BearAgentBoardAutoLast = BoardAsrLiveFields & {
  seq: number;
  ts: number | null;
  output: BearAgentProcessTestResponse | null;
  /** 与 POST /api/process 请求体一致；由 board_bridge 上报时写入 */
  perception: PerceptionPayload | null;
};
