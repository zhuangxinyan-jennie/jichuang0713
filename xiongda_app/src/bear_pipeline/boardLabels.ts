/**
 * 与 pre_on_board `board_deploy/pc_result_viewer.py` 中 GESTURE_CN_MAP / ACTION_CN_MAP 对齐，
 * 仅用于前端展示，不参与推理。
 */
export const HAND_GESTURE_CN: Record<string, string> = {
  call: "打电话",
  dislike: "踩",
  fist: "拳头",
  four: "四",
  grab: "抓握",
  grip: "握持",
  heart: "比心",
  heart2: "比心2",
  holy: "圣角",
  like: "点赞",
  little: "小拇指",
  middle: "中指",
  mute: "静音",
  OK: "OK",
  ok: "OK",
  one: "一",
  palm: "手掌",
  peace: "剪刀手",
  peace_inv: "倒剪刀手",
  point: "指向",
  rock: "摇滚",
  stop: "停止",
  stop_inv: "倒停止",
  photo: "拍照",
  three: "三",
  three2: "三2",
  three3: "三3",
  gun: "手枪",
  thumb_idx: "拇指食指",
  thumb_idx2: "拇指食指2",
  thumb_index: "拇指食指",
  thumb_index2: "拇指食指2",
  timeout: "暂停",
  two: "二",
  two_inv: "倒二",
  xsign: "叉",
  none: "无",
};

const BODY_AGENT_TO_CN: Record<string, string> = {
  none: "无",
  wave_hand: "欢迎挥手",
  clapping: "鼓掌",
};

const EMOTION_CN: Record<string, string> = {
  neutral: "平静",
  happy: "开心",
  sad: "难过",
  surprised: "惊讶",
  angry: "生气",
  scared: "害怕",
  disgust: "厌恶",
};

export function labelHandGesture(en: string | undefined): string {
  const k = (en ?? "").trim();
  if (!k) return "—";
  return HAND_GESTURE_CN[k] ?? HAND_GESTURE_CN[k.toLowerCase()] ?? k;
}

export function labelBodyGesture(agentKey: string | undefined): string {
  const k = (agentKey ?? "").trim();
  if (!k) return "—";
  return BODY_AGENT_TO_CN[k] ?? k;
}

export function labelEmotion(en: string | undefined): string {
  const k = (en ?? "").trim();
  if (!k) return "—";
  return EMOTION_CN[k] ?? EMOTION_CN[k.toLowerCase()] ?? k;
}
