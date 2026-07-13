import type { TerminalCommand } from "../types";

const randomGreetingSpeech = "嘿！俺在这儿呢，说啥都行哟。";

/** 与 `SmplhRetarget/*.json` + Unity `PlaySmplStreamingRelativePath` 一致 */
const SMPL = {
  idle: "SmplhRetarget/挥手致意.json",
  mapPoint: "SmplhRetarget/右转指右.json",
  recommend: "SmplhRetarget/摊手疑问.json",
  wave: "SmplhRetarget/挥手致意.json",
  nod: "SmplhRetarget/点头.json",
  storyIntro: "SmplhRetarget/张臂欢迎.json",
} as const;

/**
 * 根据游客文本返回模拟 Agent JSON（本地规则，不连 310B）。语音聊天简版。
 */
export function runMockAgent(userText: string): TerminalCommand {
  const t = userText.trim();
  if (!t) {
    return {
      module: "character_interaction",
      interaction_type: "voice_chat",
      speech: randomGreetingSpeech,
      smpl_streaming_path: SMPL.idle,
      emotion: "smile",
    };
  }

  if (t.includes("地图") || t.includes("哪里")) {
    return {
      module: "map_query",
      speech: "地图俺帮你记着，你先在界面上看标识走就好啦。",
      ui_action: "show_map",
      highlight_poi: "carousel",
      smpl_streaming_path: SMPL.mapPoint,
      emotion: "smile",
    };
  }
  if (t.includes("推荐") || t.includes("玩什么")) {
    return {
      module: "recommendation",
      speech: "想玩点啥？森林小火车和蜂蜜小屋都挺受欢迎！",
      smpl_streaming_path: SMPL.recommend,
      emotion: "smile",
    };
  }
  if (t.includes("挥手") || t.includes("你好") || t.includes("嗨")) {
    return {
      module: "character_interaction",
      interaction_type: "voice_chat",
      speech: "好嘞，看俺挥挥手，欢迎你！",
      smpl_streaming_path: SMPL.wave,
      emotion: "smile",
    };
  }

  return {
    module: "character_interaction",
    interaction_type: "voice_chat",
    speech: t.length > 0 ? `嗯，俺听你说的是「${t.slice(0, 40)}」` : randomGreetingSpeech,
    smpl_streaming_path: SMPL.nod,
    emotion: "calm",
  };
}
