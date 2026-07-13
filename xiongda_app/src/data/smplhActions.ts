/**
 * 与 Unity `StreamingAssets/SmplhRetarget/clip_manifest.json` 中 `jsonFile` 一致。
 * 按钮文案 = 文件名（含 .json），点击发送 `SmplhRetarget/<文件名>`。
 */
export interface SmplhActionItem {
  streamingRelativePath: string;
  /** 与磁盘上的 JSON 文件名一致，便于对照 */
  label: string;
}

const P = "SmplhRetarget/";

/** 新入库动作置顶，避免列表过长时要滚到底才看得见 */
const NEW_CLIP_FIRST = ["托腮沉思.json", "奋力纵跳.json", "擦额拭汗.json"] as const;

const JSON_FILES_REST = [
  "挥手致意.json",
  "张臂欢迎.json",
  "摇头.json",
  "双手欢呼.json",
  "原地小跳.json",
  "挠头歪身.json",
  "伸懒腰.json",
  "左右张望.json",
  "摊手疑问.json",
  "左转指左.json",
  "右转指右.json",
  "推手后退.json",
  "受惊后退.json",
  "原地踏步.json",
  "快走向前.json",
  "下蹲坐下.json",
  "躺地起身.json",
  "抱胸轻摆.json",
  "躺地睡觉.json",
  "转身一圈.json",
  "捂耳倾听.json",
  "自信造型.json",
  "点头.json",
  "摇头拒绝.json",
  "振臂欢呼.json",
  "挥手再见.json",
  "鼓掌.json",
  "捂脸害羞.json",
  "擦眼低头.json",
  "叉腰昂首.json",
  "跺脚生气.json",
  "后退惊讶.json",
  "鞠躬行礼.json",
  "飞吻.json",
  "抱臂拒绝.json",
] as const;

const JSON_FILES = [...NEW_CLIP_FIRST, ...JSON_FILES_REST] as readonly string[];

export const defaultSmplhActions: SmplhActionItem[] = JSON_FILES.map((file) => ({
  streamingRelativePath: `${P}${file}`,
  label: file,
}));
