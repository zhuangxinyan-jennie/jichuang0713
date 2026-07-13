import { useCallback, useMemo, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import type { AgentContext } from "../services/agentContext";
import {
  THEATER_SCENES,
  THEATER_STORY_ID,
  FINALE_ACTIONS,
  FINALE_SPEECH,
  FINALE_VOICE_ID,
  BRIDGE_VOICE_ID,
  type ChoiceKey,
  type TheaterResolution,
} from "../theater/smartParkTheaterData";
import {
  cancelTheaterSpeech,
  playTheaterBeat,
  speakTheaterVoices,
} from "../theater/theaterPlayback";
import { prepareBearAudioPlayback } from "../services/xiongdaTts";

type Props = {
  ctx: AgentContext;
  /** `sidebar`：贴在右侧深色栏内，不叠加在 Unity 上 */
  variant?: "overlay" | "sidebar";
  /** 与 App「板端自动同步」一致：正式玩法提示改为「对着麦克风说」 */
  boardAutoSync?: boolean;
};

export function SmartParkTheaterPanel({ ctx, variant = "overlay", boardAutoSync = false }: Props) {
  const isSidebar = variant === "sidebar";
  const [started, setStarted] = useState(false);
  const [sceneIndex, setSceneIndex] = useState(0);
  const [picked, setPicked] = useState<ChoiceKey | null>(null);
  const [feedback, setFeedback] = useState<TheaterResolution | null>(null);
  const [finalePlayed, setFinalePlayed] = useState(false);

  const scene = THEATER_SCENES[sceneIndex];
  const totalMain = THEATER_SCENES.length;
  const atLastScene = sceneIndex >= totalMain - 1;

  const resetAll = useCallback(() => {
    cancelTheaterSpeech();
    setStarted(false);
    setSceneIndex(0);
    setPicked(null);
    setFeedback(null);
    setFinalePlayed(false);
    ctx.setSubtitle(
      boardAutoSync
        ? "请对着麦克风说「剧情互动」进入后端固定剧本（不走大模型）。"
        : "请在页面底部输入「剧情互动」进入后端固定剧本（不走大模型）。"
    );
  }, [ctx, boardAutoSync]);

  const showScenePrompt = useCallback(
    (index: number) => {
      const s = THEATER_SCENES[index];
      if (!s) return;
      ctx.setSubtitle(s.prompt);
      speakTheaterVoices([s.promptVoiceId], s.prompt);
    },
    [ctx]
  );

  const handleStart = useCallback(() => {
    prepareBearAudioPlayback();
    cancelTheaterSpeech();
    setStarted(true);
    setSceneIndex(0);
    setPicked(null);
    setFeedback(null);
    setFinalePlayed(false);
    showScenePrompt(0);
    playTheaterBeat(ctx, THEATER_SCENES[0].prompt, ["张臂欢迎"], 2600);
  }, [ctx, showScenePrompt]);

  const logChoice = useCallback(
    (
      sceneId: string,
      choice: ChoiceKey,
      res: TheaterResolution,
      xiongdaAction: string
    ) => {
      if (!import.meta.env.DEV) return;
      // eslint-disable-next-line no-console
      console.debug(
        JSON.stringify(
          {
            story_id: THEATER_STORY_ID,
            scene_id: sceneId,
            choice,
            is_correct: res.correct ?? false,
            xiongda_action: xiongdaAction,
            voice_text: res.speech,
          },
          null,
          2
        )
      );
    },
    []
  );

  const handlePick = useCallback(
    (key: ChoiceKey) => {
      prepareBearAudioPlayback();
      if (!scene || picked) return;
      const res = scene.resolve(key);
      setPicked(key);
      setFeedback(res);
      playTheaterBeat(ctx, res.speech, res.actions, 2800);
      speakTheaterVoices([res.voiceId], res.speech);
      const primaryAction = res.actions[0] ?? "idle";
      logChoice(scene.id, key, res, primaryAction);
    },
    [ctx, scene, picked, logChoice]
  );

  const handleNext = useCallback(() => {
    prepareBearAudioPlayback();
    cancelTheaterSpeech();
    if (!atLastScene) {
      const next = sceneIndex + 1;
      setSceneIndex(next);
      setPicked(null);
      setFeedback(null);
      showScenePrompt(next);
      playTheaterBeat(ctx, THEATER_SCENES[next].prompt, ["点头"], 2200);
      return;
    }
    setFinalePlayed(false);
    setSceneIndex(totalMain);
    ctx.setSubtitle("三个任务都选对啦！点击下方按钮，领取智慧徽章。");
    speakTheaterVoices([BRIDGE_VOICE_ID], "三个任务都选对啦！来领取智慧徽章吧。");
  }, [atLastScene, ctx, sceneIndex, showScenePrompt, totalMain]);

  const handleFinale = useCallback(() => {
    prepareBearAudioPlayback();
    setFinalePlayed(true);
    playTheaterBeat(ctx, FINALE_SPEECH, [...FINALE_ACTIONS], 3200);
    speakTheaterVoices([FINALE_VOICE_ID], FINALE_SPEECH);
    if (import.meta.env.DEV) {
      // eslint-disable-next-line no-console
      console.debug(
        JSON.stringify({ story_id: THEATER_STORY_ID, scene_id: "finale", choice: "—" }, null, 2)
      );
    }
  }, [ctx]);

  const progressLabel = useMemo(() => {
    if (!started) return "";
    if (sceneIndex >= totalMain) return "结尾 · 智慧徽章";
    return `第 ${sceneIndex + 1} / ${totalMain} 幕 · ${scene?.title ?? ""}`;
  }, [started, sceneIndex, totalMain, scene?.title]);

  /** 侧栏：小号悬浮卡片，不占满整列；叠加模式仍压低高度 */
  const panelMaxClass = useMemo(() => {
    if (isSidebar) return "max-h-[min(65vh,440px)] w-full shrink-0";
    if (!started) return "max-h-[min(42vh,380px)]";
    if (sceneIndex >= totalMain) return "max-h-[min(36vh,320px)]";
    return "max-h-[min(32vh,290px)]";
  }, [isSidebar, started, sceneIndex, totalMain]);

  return (
    <motion.div
      initial={{ opacity: 0, y: isSidebar ? 0 : 12 }}
      animate={{ opacity: 1, y: 0 }}
      className={`flex w-full flex-col overflow-hidden border bg-gradient-to-b from-white/96 via-amber-50/92 to-cream/93 backdrop-blur-md ${
        isSidebar
          ? "rounded-xl border-amber-300/45 shadow-md shadow-slate-900/10 ring-1 ring-white/80"
          : "rounded-2xl border-amber-400/40 shadow-[0_-6px_28px_rgba(0,0,0,0.16)]"
      } ${panelMaxClass}`}
      role="region"
      aria-label="智慧乐园益智小剧场"
    >
      <div className="flex shrink-0 items-center justify-between gap-2 border-b border-amber-200/40 bg-forest/8 px-2 py-1 md:px-2.5">
        <div className="min-w-0">
          <p className="truncate text-[11px] font-black uppercase tracking-wide text-forest-deep md:text-xs">
            熊大的益智任务剧场
          </p>
          {started ? (
            <p className="truncate text-[9px] text-slate-600 md:text-[10px]">{progressLabel}</p>
          ) : (
            <p className="text-[9px] text-slate-600 md:text-[10px]">
              {isSidebar ? "小卡片选题 · 旁边留白即背景" : "选项在底部 · 上方可看熊大表演"}
            </p>
          )}
        </div>
        <button
          type="button"
          onClick={resetAll}
          className="shrink-0 rounded-lg border border-slate-300/80 bg-white/90 px-2 py-1 text-[10px] font-bold text-slate-600 hover:bg-amber-50 md:text-xs"
        >
          退出重置
        </button>
      </div>

      <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
        <div className={`min-h-0 flex-1 overflow-y-auto ${isSidebar ? "px-2 py-1.5" : "px-2 py-2 md:px-3 md:py-2.5"}`}>
        <AnimatePresence mode="wait">
          {!started ? (
            <motion.div
              key="splash"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className={`flex flex-col items-center text-center ${isSidebar ? "gap-2 py-2" : "gap-3 py-3"}`}
            >
              <div
                className={`space-y-2 text-left leading-relaxed text-slate-700 ${isSidebar ? "max-w-none text-[11px] md:text-xs" : "max-w-lg text-xs md:text-sm"}`}
              >
                <p>
                  熊大今天是智慧乐园守护员，请你帮他完成<strong className="text-forest-deep">三个益智任务</strong>
                  ：辨方向、算时间、讲文明。
                </p>
                <p className="rounded-lg border border-emerald-200/80 bg-emerald-50/90 px-2 py-1.5 text-[11px] font-semibold text-emerald-950 md:text-xs">
                  <strong className="font-black">正式玩法（不必点本卡片任何按钮）</strong>
                  {boardAutoSync ? (
                    <>
                      ：对着麦克风说「<strong>剧情互动</strong>」进入后端剧本；随后每一幕也用<strong>语音</strong>选答案（如「先听听规则」「往左」「路线 B」）。
                      剧本与选项已由后端写死，<strong>不经过大模型</strong>。
                    </>
                  ) : (
                    <>
                      ：拉到页面<strong>最下方输入框</strong>，发送「<strong>剧情互动</strong>」。
                      剧本与选项已由后端写死，<strong>不经过大模型</strong>；按字幕「下一步」用文字或「语音(模拟)」作答即可。
                    </>
                  )}
                </p>
                <p className="text-[10px] text-slate-500 md:text-[11px]">
                  下方按钮仅供离线调试：与 Bear Agent 无关，也不会替代底部剧情。
                </p>
              </div>
              <button
                type="button"
                onClick={handleStart}
                className={`rounded-lg border-2 border-dashed border-slate-300 bg-white/95 font-bold text-slate-600 shadow-sm transition hover:border-amber-400 hover:bg-amber-50/80 ${isSidebar ? "px-3 py-1.5 text-[10px]" : "px-4 py-2 text-xs md:text-sm"}`}
              >
                本地演示（可选）
              </button>
            </motion.div>
          ) : sceneIndex >= totalMain ? (
            <motion.div
              key="finale"
              initial={{ opacity: 0, x: 8 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0 }}
              className="flex flex-col gap-2 py-1"
            >
              <p className="text-xs leading-relaxed text-slate-800 md:text-sm">
                {finalePlayed
                  ? "徽章动画已播放。你可以重新开始，带新朋友再玩一遍。"
                  : "太棒了！你已经和熊大一起完成了全部选择。准备好接收「智慧徽章」 celebration 了吗？"}
              </p>
              <div className="flex flex-wrap gap-2">
                {!finalePlayed ? (
                  <button
                    type="button"
                    onClick={handleFinale}
                    className="rounded-xl bg-amber-500 px-5 py-2.5 text-sm font-black text-white shadow-md transition hover:scale-[1.02] hover:bg-amber-600"
                  >
                    领取智慧徽章
                  </button>
                ) : null}
                <button
                  type="button"
                  onClick={handleStart}
                  className="rounded-xl border-2 border-forest/40 bg-white px-5 py-2.5 text-sm font-bold text-forest-deep hover:bg-forest/5"
                >
                  再来一遍
                </button>
              </div>
            </motion.div>
          ) : (
            <motion.div
              key={scene.id}
              initial={{ opacity: 0, x: 10 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -10 }}
              className="flex flex-col gap-2"
            >
              <div
                className={`overflow-y-auto rounded-lg border border-slate-200/60 bg-white/75 px-2 py-1.5 leading-snug text-slate-800 whitespace-pre-line ${
                  isSidebar
                    ? "max-h-[140px] text-[11px] md:max-h-[160px] md:text-[11px]"
                    : "max-h-[4.75rem] text-[11px] md:max-h-[5.25rem] md:text-xs"
                }`}
              >
                {scene.prompt}
              </div>

              {!picked ? (
                <div className="flex flex-col gap-1.5">
                  <p className="text-[10px] font-bold text-slate-500 md:text-[11px]">
                    {isSidebar ? "点选一项继续剧情" : "点选一项（横向排列，不占画面中间）"}
                  </p>
                  <div
                    className={
                      isSidebar ? "flex flex-col gap-2" : "flex flex-row flex-wrap gap-2"
                    }
                  >
                    {scene.choices.map((c) => (
                      <button
                        key={c.key}
                        type="button"
                        onClick={() => handlePick(c.key)}
                        className={`group flex border-2 border-slate-200/85 bg-white/90 shadow-sm transition-all duration-200 hover:z-10 hover:border-amber-400 hover:shadow-md ${
                          isSidebar
                            ? "min-h-[40px] w-full flex-row items-center gap-2 rounded-lg px-2 py-2 text-left"
                            : "min-h-[44px] min-w-[calc(33.333%-0.5rem)] flex-1 basis-[120px] flex-col items-center justify-center gap-0.5 rounded-xl px-2 py-1.5 text-center sm:min-w-[100px] sm:flex-initial sm:basis-auto"
                        }`}
                      >
                        <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-forest/15 text-[10px] font-black text-forest-deep ring-1 ring-forest/15 transition group-hover:bg-amber-100 group-hover:ring-amber-300 md:h-6 md:w-6 md:text-[11px] md:ring-2">
                          {c.key}
                        </span>
                        <span
                          className={`font-bold leading-tight text-slate-800 ${
                            isSidebar
                              ? "min-w-0 flex-1 text-[11px] leading-snug md:text-xs"
                              : "line-clamp-2 text-[10px] md:text-[11px]"
                          }`}
                        >
                          {c.label}
                        </span>
                      </button>
                    ))}
                  </div>
                </div>
              ) : (
                <div className="flex flex-col gap-2">
                  <div className="flex flex-wrap items-center gap-1.5">
                    <span className="text-[10px] font-bold text-slate-500">已选</span>
                    {scene.choices.map((c) => {
                      const isSel = c.key === picked;
                      const ok = feedback?.correct === true;
                      const bad = feedback?.correct === false;
                      return (
                        <div
                          key={c.key}
                          className={`rounded-lg border px-2 py-1 text-[10px] font-bold md:text-[11px] ${
                            isSel
                              ? ok
                                ? "border-emerald-400 bg-emerald-100/95 text-emerald-950 ring-2 ring-emerald-300/70"
                                : bad
                                  ? "border-rose-400 bg-rose-100/95 text-rose-950 ring-2 ring-rose-300/60"
                                  : "border-amber-400 bg-amber-100/95 text-amber-950 ring-2 ring-amber-300/70"
                              : "border-slate-100 bg-slate-100/50 text-slate-400 line-through opacity-60"
                          }`}
                        >
                          {c.key} {c.label}
                        </div>
                      );
                    })}
                  </div>
                  {feedback ? (
                    <div
                      className={`max-h-[3.25rem] overflow-y-auto rounded-lg border px-2 py-1.5 text-[11px] leading-snug md:text-xs ${
                        feedback.correct
                          ? "border-emerald-200 bg-emerald-50/85 text-emerald-950"
                          : "border-amber-200 bg-amber-50/85 text-amber-950"
                      }`}
                    >
                      <span className="font-black">熊大：</span>
                      {feedback.speech}
                    </div>
                  ) : null}
                  <p className="text-center text-[10px] font-semibold text-slate-500">
                    {isSidebar ? "点下方绿色「下一幕」继续" : "点底部绿色「下一幕」继续"}
                  </p>
                </div>
              )}
            </motion.div>
          )}
        </AnimatePresence>
        </div>

        {started && sceneIndex < totalMain && picked ? (
          <div className="shrink-0 border-t border-amber-200/70 bg-white/80 px-2 py-1.5 md:px-2">
            <button
              type="button"
              onClick={handleNext}
              className={`w-full rounded-lg bg-forest text-center font-black text-white shadow-sm ring-1 ring-forest/30 transition hover:bg-emerald-700 active:scale-[0.99] ${isSidebar ? "py-2 text-xs" : "rounded-xl py-2.5 text-sm ring-2 ring-forest/25 hover:ring-emerald-500/35 md:py-3 md:text-base"}`}
            >
              {atLastScene ? "进入结尾 · 领取徽章前奏" : "下一幕"}
            </button>
          </div>
        ) : null}
      </div>
    </motion.div>
  );
}
