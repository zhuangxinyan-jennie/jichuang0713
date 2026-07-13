/**
 * 《熊大的智慧乐园任务》固定分支益智小剧场。
 * 动作名与 StreamingAssets/SmplhRetarget 下中文 *.json 一致。
 */

export type ChoiceKey = "A" | "B" | "C";

export type TheaterChoice = {
  key: ChoiceKey;
  label: string;
};

export type TheaterResolution = {
  /** 熊大反馈台词（可含换行） */
  speech: string;
  /** 与 `public/theater_voice/tp_{voiceId}.wav` 对应，预烘焙可降低 TTS 延时 */
  voiceId: string;
  /** 顺序播放的 SMPL 动作（中文名，不含 .json） */
  actions: string[];
  /** 是否正确（用于按钮配色；开场两选项都可视为参与） */
  correct?: boolean;
};

export type TheaterScene = {
  id: string;
  title: string;
  /** 剧情说明 + 熊大提问 */
  prompt: string;
  /** 当前幕提问台词对应的预烘焙 id */
  promptVoiceId: string;
  choices: TheaterChoice[];
  resolve: (key: ChoiceKey) => TheaterResolution;
};

export const THEATER_STORY_ID = "smart_park_theater";

/** 领取徽章前过渡句（与 bridge_badge 语音一致） */
export const BRIDGE_VOICE_ID = "bridge_badge";

export const THEATER_SCENES: TheaterScene[] = [
  {
    id: "intro",
    title: "开场 · 接到任务",
    prompt: "俺今天是智慧乐园守护员，有一个益智小任务要和你一起完成。",
    promptVoiceId: "intro_prompt",
    choices: [
      { key: "A", label: "好，一起完成任务" },
      { key: "B", label: "先听听规则" },
    ],
    resolve: (key) =>
      key === "A"
        ? {
            speech: "太好啦！那咱们这就出发，先把任务一项一项完成！",
            voiceId: "intro_resolve_a",
            actions: ["张臂欢迎", "鼓掌"],
            correct: true,
          }
        : {
            speech:
              "行，俺简单说下：每一幕会给你几个选项，你帮俺选；选对了俺会表扬，选错了俺会提示，最后再一起拿智慧徽章！",
            voiceId: "intro_resolve_b",
            actions: ["点头", "摊手疑问"],
            correct: true,
          },
  },
  {
    id: "act1_direction",
    title: "第一幕 · 帮小松鼠找路",
    prompt:
      "小松鼠要去「森林剧场」，站在岔路口。\n路牌写着：左边森林剧场 300 米，右边美食广场 100 米，前方过山车 500 米。\n你觉得它该往哪走？",
    promptVoiceId: "act1_direction_prompt",
    choices: [
      { key: "A", label: "往左走" },
      { key: "B", label: "往右走" },
      { key: "C", label: "往前走" },
    ],
    resolve: (key) => {
      if (key === "A") {
        return {
          speech: "对啦！路牌上写着森林剧场在左边，你观察得真仔细！",
          voiceId: "act1_direction_resolve_a",
          actions: ["鼓掌", "双手欢呼"],
          correct: true,
        };
      }
      if (key === "B") {
        return {
          speech: "右边是美食广场，不是森林剧场。咱们再看看路牌上的目的地呀。",
          voiceId: "act1_direction_resolve_b",
          actions: ["摇头", "左转指左"],
          correct: false,
        };
      }
      return {
        speech: "前方是过山车，方向不对。找路要先看清目的地再选路哦。",
        voiceId: "act1_direction_resolve_c",
        actions: ["挠头歪身", "左右张望"],
        correct: false,
      };
    },
  },
  {
    id: "act2_route",
    title: "第二幕 · 哪条路线最快",
    prompt:
      "要去「梦幻花园」：\n路线 A 很近但要排队约 20 分钟；路线 B 要走 8 分钟但不用排队；路线 C 走 15 分钟还要再等 10 分钟。\n想最快到达，该选哪条？",
    promptVoiceId: "act2_route_prompt",
    choices: [
      { key: "A", label: "路线 A" },
      { key: "B", label: "路线 B" },
      { key: "C", label: "路线 C" },
    ],
    resolve: (key) => {
      if (key === "B") {
        return {
          speech: "没错！路线 B 不用排队，总时间最短，脑子真灵光！",
          voiceId: "act2_route_resolve_b",
          actions: ["双手欢呼", "原地小跳"],
          correct: true,
        };
      }
      if (key === "A") {
        return {
          speech: "A 虽然看着近，但要等 20 分钟，加起来不一定最快哦。",
          voiceId: "act2_route_resolve_a",
          actions: ["摊手疑问", "摇头"],
          correct: false,
        };
      }
      return {
        speech: "C 又远又要等，时间花得最多，再想想「走路 + 排队」加起来谁最短？",
        voiceId: "act2_route_resolve_c",
        actions: ["挠头歪身", "摊手疑问"],
        correct: false,
      };
    },
  },
  {
    id: "act3_safety",
    title: "第三幕 · 安全与环保",
    prompt: "下面哪个行为在乐园里是正确、文明的？",
    promptVoiceId: "act3_safety_prompt",
    choices: [
      { key: "A", label: "在排队区翻越栏杆" },
      { key: "B", label: "把垃圾扔进分类垃圾桶" },
      { key: "C", label: "设备运行时伸手碰轨道" },
    ],
    resolve: (key) => {
      if (key === "B") {
        return {
          speech: "对啦！垃圾分类能让乐园更干净，大家都舒服！",
          voiceId: "act3_safety_resolve_b",
          actions: ["鼓掌", "点头"],
          correct: true,
        };
      }
      if (key === "A") {
        return {
          speech: "翻越栏杆很危险，排队要走规定通道，可不能偷懒抄近道。",
          voiceId: "act3_safety_resolve_a",
          actions: ["抱臂拒绝"],
          correct: false,
        };
      }
      return {
        speech: "设备运行时千万不能伸手触碰，要保持安全距离！",
        voiceId: "act3_safety_resolve_c",
        actions: ["推手后退", "摇头"],
        correct: false,
      };
    },
  },
];

export const FINALE_SPEECH =
  "太棒啦！三个任务都完成了。你又会看路牌、又会算时间，还懂得安全和环保——这枚智慧徽章送给你！下次再来帮俺守护乐园！";

/** 与 finale 预烘焙语音 id 一致 */
export const FINALE_VOICE_ID = "finale";

/** 结尾连续动作（庆祝 → 感谢 → 告别） */
export const FINALE_ACTIONS = ["振臂欢呼", "鼓掌", "鞠躬行礼", "挥手再见"] as const;
