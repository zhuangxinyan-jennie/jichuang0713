/**
 * 将 Agent 输出的中文动作名映射到 Unity StreamingAssets 相对路径。
 * 与 `bear_agent/config.py` 的 ACTION_LIST、`smplhActions.ts` 中的文件名一致。
 */
const NAMES = [
  "挥手致意",
  "张臂欢迎",
  "摇头",
  "双手欢呼",
  "原地小跳",
  "挠头歪身",
  "伸懒腰",
  "左右张望",
  "摊手疑问",
  "左转指左",
  "右转指右",
  "推手后退",
  "受惊后退",
  "原地踏步",
  "快走向前",
  "下蹲坐下",
  "躺地起身",
  "抱胸轻摆",
  "躺地睡觉",
  "转身一圈",
  "捂耳倾听",
  "自信造型",
  "点头",
  "摇头拒绝",
  "振臂欢呼",
  "挥手再见",
  "鼓掌",
  "捂脸害羞",
  "擦眼低头",
  "叉腰昂首",
  "跺脚生气",
  "后退惊讶",
  "鞠躬行礼",
  "飞吻",
  "抱臂拒绝",
  "托腮沉思",
  "奋力纵跳",
  "擦额拭汗",
] as const;

const KNOWN = new Set<string>(NAMES);

const DEFAULT_FALLBACK = "SmplhRetarget/挥手致意.json";

export function chineseActionToSmplPath(actionName: string): string {
  const name = actionName?.trim();
  if (!name) return DEFAULT_FALLBACK;
  if (KNOWN.has(name)) {
    return `SmplhRetarget/${name}.json`;
  }
  console.warn("[bear_pipeline] 未在映射表中的动作名，仍按文件名拼接:", name);
  return `SmplhRetarget/${name}.json`;
}
