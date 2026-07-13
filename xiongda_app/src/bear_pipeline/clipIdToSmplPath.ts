/**
 * 后端 `clip_ids`（Animator 逻辑 id）→ 你当前工程里实际使用的 SMPL-H JSON。
 * 可按剧情观感改映射；未知 id 会回落到默认动作并打控制台警告。
 */
const P = "SmplhRetarget/";

const MAP: Record<string, string> = {
  /** 玩法介绍 */
  mode_select_intro: `${P}张臂欢迎.json`,

  /**
   * 《智慧乐园任务》固定剧情（story_engine 数字 clip）
   * 与益智小剧场文案同步，一镜一案便于联调。
   */
  "0": `${P}张臂欢迎.json`,
  "0A": `${P}鼓掌.json`,
  "0B": `${P}摊手疑问.json`,
  "1": `${P}摊手疑问.json`,
  "1A": `${P}鼓掌.json`,
  "1B": `${P}摇头.json`,
  "1C": `${P}挠头歪身.json`,
  "2": `${P}摊手疑问.json`,
  "2A": `${P}摊手疑问.json`,
  "2B": `${P}双手欢呼.json`,
  "2C": `${P}挠头歪身.json`,
  "3": `${P}点头.json`,
  "3A": `${P}抱臂拒绝.json`,
  "3B": `${P}鼓掌.json`,
  "3C": `${P}推手后退.json`,
  "4": `${P}振臂欢呼.json`,

  /** 剧情：叫醒分支 */
  story_intro_wake_choice: `${P}捂耳倾听.json`,
  story_wake_yes_honey_trick: `${P}自信造型.json`,
  story_wake_yes_cheer_choice: `${P}摊手疑问.json`,
  story_wake_yes_cheer_yes: `${P}振臂欢呼.json`,
  story_wake_yes_cheer_no: `${P}跺脚生气.json`,

  /** 剧情：不叫醒分支 */
  story_wake_no_dream_wakeup: `${P}伸懒腰.json`,
  story_wake_no_fight_choice: `${P}摊手疑问.json`,
  story_wake_no_fight_yes: `${P}双手欢呼.json`,
  story_wake_no_fight_no: `${P}张臂欢迎.json`,

  /** 收尾 */
  story_finale_return: `${P}挥手再见.json`,

  /** 与 Unity ClipIdPlayer 里其它 id 对齐（若后端将来用到） */
  stand_idle_friendly: `${P}挥手致意.json`,
  wave_right_hand: `${P}挥手致意.json`,
  laugh: `${P}鼓掌.json`,
  nod: `${P}点头.json`,
  point_right: `${P}右转指右.json`,
  point_left: `${P}左转指左.json`,
  talk_gesture_small: `${P}摊手疑问.json`,
};

const DEFAULT_SMPL = `${P}挥手致意.json`;

export function clipIdToSmplPath(clipId: string): string {
  const id = clipId?.trim();
  if (!id) return DEFAULT_SMPL;
  const path = MAP[id];
  if (path) return path;
  console.warn("[clipIdToSmplPath] 未映射的 clip_id，使用默认 SMPL:", id);
  return DEFAULT_SMPL;
}

export function clipIdsToSmplPaths(clipIds: string[]): string[] {
  return clipIds.map((c) => clipIdToSmplPath(c));
}
