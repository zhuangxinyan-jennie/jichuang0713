export interface RecommendationData {
  name: string;
  reason: string;
  queue_time: string;
  target_group: string;
  score: number;
}

export interface TerminalCommand {
  module: string;
  interaction_type?: string;
  speech?: string;
  motion_type?: string;
  actions?: string[];
  /** SMPL-H：相对 StreamingAssets，如 `SmplhRetarget/挥手致意.json` */
  smpl_streaming_path?: string;
  emotion?: string;
  ui_action?: string;
  highlight_poi?: string;
  recommendation?: RecommendationData;
}

/** 与 310B / Unity 共用的轻量 JSON（可嵌套在更外层 module 中） */
export interface AgentJsonPayload {
  interaction_type?: string;
  smpl_streaming_path?: string;
  speech?: string;
  emotion?: string;
  module?: string;
}

export type TopNavId = "world" | "story" | "recommend";
