import { useCallback, useEffect, useMemo, useRef, useState, type FocusEvent } from "react";
import { motion } from "framer-motion";
import { TopMenu } from "./components/TopMenu";
import { UnityEmbed } from "./components/UnityEmbed";
import { ActionPanel } from "./components/ActionPanel";
import { BottomCommandBar } from "./components/BottomCommandBar";
import { ParkMapPanel } from "./components/ParkMapPanel";
import type { TopNavId } from "./types";
import type { SmplhActionItem } from "./data/smplhActions";
import { makeAgentContext } from "./services/agentContext";
import { handleAgentJson, handleMapQuery, handleRecommendation } from "./services/agentApi";
import { prepareBearAudioPlayback } from "./services/xiongdaTts";
import { sendSmplStreamingRelativePath } from "./services/unitySendClip";
import { useUnityReady } from "./hooks/useUnityReady";
import { agentPipelineDebugUi } from "./bear_pipeline/agentPipelineUi";
import { BearPipelineTestCard } from "./bear_pipeline/BearPipelineTestCard";
import { useTerminalKeyboardIsolation } from "./hooks/useTerminalKeyboardIsolation";
import { SmartParkTheaterPanel } from "./components/SmartParkTheaterPanel";
import {
  fetchBoardAutoLast,
  postMapQueryWithOptions,
  postMultimodalPlaybackDone,
  postProcessFullWithOptions,
  postReset,
} from "./bear_pipeline/bearAgentClient";
import { handleBearAgentPayload } from "./bear_pipeline/handleBearAgentPayload";
import type { BoardAsrLiveFields, PerceptionPayload } from "./bear_pipeline/bearAgentTypes";
import { parseGuestNavIntent } from "./bear_pipeline/navIntentTriggers";
import {
  clearTtsLatencyContext,
  createLatencyProbe,
  setTtsLatencyContext,
} from "./services/ttsLatencyProbe";

function boardAutoPollDefault(): boolean {
  const v = import.meta.env.VITE_BOARD_AUTO_POLL as string | undefined;
  if (v === undefined) return true;
  const s = String(v).trim().toLowerCase();
  return !(s === "0" || s === "false" || s === "off");
}

type ManualInputSource = "typed" | "voice_mock" | "board_auto";
type ManualInputRoute = "map_query" | "process";
type LatencyProbe = ReturnType<typeof createLatencyProbe>;

export default function App() {
  const [topNav, setTopNav] = useState<TopNavId>("voice");
  const [guestInput, setGuestInput] = useState("");
  const [subtitle, setSubtitle] = useState("");
  const [currentSmplPath, setCurrentSmplPath] = useState("—");
  /** 与底部游客句子一并发给 /api/process 的感知字段 */
  const [bearEmotion, setBearEmotion] = useState("happy");
  const [bearGesture, setBearGesture] = useState("wave_hand");
  const [bearHandGesture, setBearHandGesture] = useState("like");
  const [bearPersonDetected, setBearPersonDetected] = useState(true);
  const [agentLoading, setAgentLoading] = useState(false);
  const [agentErr, setAgentErr] = useState("");
  const [lastAgentJson, setLastAgentJson] = useState("");
  const [boardAutoFollow, setBoardAutoFollow] = useState(boardAutoPollDefault);
  const [boardPollErr, setBoardPollErr] = useState("");
  const [boardBridgePerception, setBoardBridgePerception] = useState<PerceptionPayload | null>(null);
  const [boardLiveAsr, setBoardLiveAsr] = useState<BoardAsrLiveFields | null>(null);
  const lastBoardDriveSeqRef = useRef(0);
  const didAutoStartRef = useRef(false);
  /** 焦点在右侧/底部表单内：隔离键盘并暂时禁止点击 Unity，避免「只能输入一次」 */
  const [terminalIslandFocused, setTerminalIslandFocused] = useState(false);

  useTerminalKeyboardIsolation(terminalIslandFocused);

  const onTerminalIslandFocusCapture = useCallback(() => setTerminalIslandFocused(true), []);

  const onTerminalIslandBlurCapture = useCallback((e: FocusEvent<HTMLElement>) => {
    const rt = e.relatedTarget as Node | null;
    if (rt instanceof Element && rt.closest("[data-terminal-input-island]")) return;
    setTerminalIslandFocused(false);
  }, []);

  const ctx = useMemo(
    () => makeAgentContext(setCurrentSmplPath, setSubtitle),
    [setCurrentSmplPath, setSubtitle]
  );

  const unityReady = useUnityReady();
  const unityStatusText = unityReady
    ? "WebGL 已连接（PlaySmplStreamingRelativePath）"
    : "未加载（占位 / 调试用，仍会更新当前 SMPL 路径）";

  const onSelectSmpl = useCallback(
    (item: SmplhActionItem) => {
      sendSmplStreamingRelativePath(item.streamingRelativePath);
      setCurrentSmplPath(item.streamingRelativePath);
      setSubtitle(item.label);
    },
    [setCurrentSmplPath, setSubtitle]
  );

  const enterStoryTabFromAgent = useCallback(() => {
    setTopNav("story");
  }, []);

  const enterVoiceTabFromAgent = useCallback(() => {
    setTopNav("voice");
    setSubtitle("已切换到「语音聊天」。你可以直接和熊大聊天，也可以说「剧情互动」或「地图查询」切换玩法。");
  }, []);

  const enterMapTabFromAgent = useCallback(() => {
    setTopNav("map");
    handleMapQuery("", ctx);
  }, [ctx]);

  const bearPayloadNavOptions = useMemo(
    () => ({
      onEnterStoryTab: enterStoryTabFromAgent,
      onEnterVoiceTab: enterVoiceTabFromAgent,
      onEnterMapTab: enterMapTabFromAgent,
    }),
    [enterMapTabFromAgent, enterStoryTabFromAgent, enterVoiceTabFromAgent]
  );

  const onTopNav = useCallback(
    (id: TopNavId) => {
      setTopNav(id);
      if (id === "voice") return;
      if (id === "story") {
        setSubtitle(
          boardAutoFollow
            ? "益智小剧场：若熊大还没念开场，请对着麦克风说「剧情互动」。进入后请用语音回答选项（如 A/B、先听听规则、往左）。"
            : "益智小剧场：右侧小卡片选题，其余区域为页面背景。"
        );
        return;
      }
      if (id === "map") {
        handleMapQuery("", ctx);
        return;
      }
      if (id === "recommend") {
        handleRecommendation(ctx);
      }
    },
    [ctx, boardAutoFollow]
  );

  const mapPerception = useCallback(
    (speechText: string): PerceptionPayload => ({
      speech_text: speechText,
      emotion: bearEmotion,
      gesture: bearGesture,
      hand_gesture: bearHandGesture,
      person_detected: bearPersonDetected,
      emotion_confidence: 0.9,
      gesture_confidence: 0.85,
      hand_gesture_confidence: 0.8,
      person_count: 1,
    }),
    [bearEmotion, bearGesture, bearHandGesture, bearPersonDetected]
  );

  /**
   * 底部输入 / 模拟语音 → Agent：在开启板端同步且已有 perception 时，
   * 用「最新板端多模态快照」做底，`speech_text` 一律用你键入的文字（覆盖 ASR 整句）。
   * 这样语音识别有问题时仍可只用打字驱动状态机，同时保留表情/手势/人脸框等视觉字段。
   */
  const buildPerceptionForManualSend = useCallback(
    (speechText: string): PerceptionPayload => {
      const text = speechText.trim();
      let p: PerceptionPayload;
      if (boardAutoFollow && boardBridgePerception) {
        p = {
          ...boardBridgePerception,
          speech_text: text,
        };
      } else {
        p = mapPerception(text);
      }
      /** 语音聊天页不参与躯干动作推理：固定为 none（仍可用手势 / 表情等其它字段） */
      if (topNav === "voice") {
        return { ...p, gesture: "none" };
      }
      return p;
    },
    [boardAutoFollow, boardBridgePerception, mapPerception, topNav]
  );

  const createManualInputProbe = useCallback(
    (source: ManualInputSource, route: ManualInputRoute, text: string): LatencyProbe => {
      const probe = createLatencyProbe("manual_input_to_agent_json", {
        source,
        route,
        mode: topNav,
        text: text.slice(0, 160),
        textLength: text.length,
      });
      probe?.mark("manual_submit");
      if (probe) {
        setTtsLatencyContext({
          traceId: probe.id,
          source,
          route,
          mode: topNav,
          inputText: text.slice(0, 160),
        });
      }
      return probe;
    },
    [topNav]
  );

  /** 将 board_bridge 上报的 perception 同步到右侧控件（表情 · 手势 · 躯干动作） */
  const applyLiveBoardPerception = useCallback(
    (p: PerceptionPayload) => {
      if (typeof p.emotion === "string" && p.emotion.trim()) setBearEmotion(p.emotion.trim());
      if (topNav !== "voice" && typeof p.gesture === "string" && p.gesture.trim()) {
        setBearGesture(p.gesture.trim());
      }
      if (typeof p.hand_gesture === "string" && p.hand_gesture.trim()) {
        setBearHandGesture(p.hand_gesture.trim());
      }
      if (typeof p.person_detected === "boolean") setBearPersonDetected(p.person_detected);
    },
    [topNav]
  );

  const sendMapQuestion = useCallback(
    async (text: string, probe?: LatencyProbe, source: ManualInputSource = "typed") => {
      const t = text.trim();
      if (!t) return;
      setAgentErr("");
      setAgentLoading(true);
      try {
        const out = await postMapQueryWithOptions(buildPerceptionForManualSend(t), { probe });
        probe?.mark("agent_json_ready", {
          interaction_type: out.interaction_type || "",
          speechLength: (out.speech || "").length,
        });
        setLastAgentJson(JSON.stringify(out, null, 2));
        handleBearAgentPayload(out, ctx, bearPayloadNavOptions);
        probe?.finish("ok", {
          source,
          interaction_type: out.interaction_type || "",
          speechLength: (out.speech || "").length,
        });
        clearTtsLatencyContext(probe?.id);
      } catch (e) {
        const msg = e instanceof Error ? e.message : String(e);
        probe?.finish("error", { source, reason: msg });
        clearTtsLatencyContext(probe?.id);
        setAgentErr(msg);
        setLastAgentJson("");
        ctx.setSubtitle(
          `地图向导请求失败：${msg}。请在本机启动 bear_agent：python integration_test/server.py（默认 8765），并确认已包含路由 POST /api/map-query。`
        );
      } finally {
        setAgentLoading(false);
      }
    },
    [ctx, buildPerceptionForManualSend, bearPayloadNavOptions]
  );

  /** 统一走 Bear Agent 玩法状态机 POST /api/process */
  const dispatchBearFsm = useCallback(
    async (speechForAgent: string, probe?: LatencyProbe, source: ManualInputSource = "typed") => {
      setAgentErr("");
      setAgentLoading(true);
      try {
        const out = await postProcessFullWithOptions(buildPerceptionForManualSend(speechForAgent), { probe });
        probe?.mark("agent_json_ready", {
          interaction_type: out?.interaction_type || "",
          target_mode: out?.target_mode || "",
          speechLength: (out?.speech || "").length,
        });
        setLastAgentJson(out === null ? "null" : JSON.stringify(out, null, 2));
        handleBearAgentPayload(out, ctx, bearPayloadNavOptions);
        probe?.finish("ok", {
          source,
          interaction_type: out?.interaction_type || "",
          target_mode: out?.target_mode || "",
          speechLength: (out?.speech || "").length,
        });
        clearTtsLatencyContext(probe?.id);
      } catch (e) {
        const msg = e instanceof Error ? e.message : String(e);
        probe?.finish("error", { source, reason: msg });
        clearTtsLatencyContext(probe?.id);
        setAgentErr(msg);
        setLastAgentJson("");
        ctx.setSubtitle(
          `Bear Agent 请求失败：${msg}。请确认已运行 python integration_test/server.py（默认 8765）。`
        );
      } finally {
        setAgentLoading(false);
      }
    },
    [ctx, buildPerceptionForManualSend, bearPayloadNavOptions]
  );

  const onResetAgent = useCallback(async () => {
    prepareBearAudioPlayback();
    setAgentErr("");
    setAgentLoading(true);
    try {
      await postReset();
      lastBoardDriveSeqRef.current = 0;
      setSubtitle("");
      setGuestInput("");
      setBoardBridgePerception(null);
      setBoardLiveAsr(null);
      setLastAgentJson("（已 reset）");
      const out = await postProcessFullWithOptions(mapPerception(""));
      setLastAgentJson(out === null ? "null" : JSON.stringify(out, null, 2));
      handleBearAgentPayload(out, ctx, bearPayloadNavOptions);
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      setAgentErr(msg);
    } finally {
      setAgentLoading(false);
    }
  }, [ctx, bearPayloadNavOptions, mapPerception]);

  const onSend = useCallback(() => {
    const text = guestInput.trim();
    if (!text) return;
    prepareBearAudioPlayback();
    const navIntent = parseGuestNavIntent(text);
    const route: ManualInputRoute = !navIntent && topNav === "map" ? "map_query" : "process";
    const probe = createManualInputProbe("typed", route, text);
    if (navIntent) {
      void dispatchBearFsm(text, probe, "typed");
      return;
    }
    if (topNav === "map") {
      void sendMapQuestion(text, probe, "typed");
      return;
    }
    void dispatchBearFsm(text, probe, "typed");
  }, [guestInput, topNav, sendMapQuestion, dispatchBearFsm, createManualInputProbe]);

  const onVoiceMock = useCallback(() => {
    prepareBearAudioPlayback();
    if (topNav === "map") {
      const simulated = "怎么去海螺湾";
      setGuestInput(simulated);
      const probe = createManualInputProbe("voice_mock", "map_query", simulated);
      void sendMapQuestion(simulated, probe, "voice_mock");
      return;
    }
    const simulated = "（模拟 ASR）你好熊大，给俺挥个手！";
    setGuestInput(simulated);
    const probe = createManualInputProbe("voice_mock", "process", simulated);
    void dispatchBearFsm(simulated, probe, "voice_mock");
  }, [topNav, sendMapQuestion, dispatchBearFsm, createManualInputProbe]);

  useEffect(() => {
    const flag = (import.meta.env.VITE_AGENT_AUTO_START as string | undefined)?.trim().toLowerCase();
    if (flag === "0" || flag === "false" || flag === "off") return;
    if (didAutoStartRef.current) return;
    const autoStartWindow = window as unknown as { __xiongdaAgentAutoStartDone?: boolean };
    if (autoStartWindow.__xiongdaAgentAutoStartDone) return;
    autoStartWindow.__xiongdaAgentAutoStartDone = true;
    didAutoStartRef.current = true;

    let cancelled = false;
    void (async () => {
      try {
        await postReset();
        if (cancelled) return;
        lastBoardDriveSeqRef.current = 0;
        setGuestInput("");
        setSubtitle("");
        setBoardBridgePerception(null);
        setBoardLiveAsr(null);
        setLastAgentJson("（已自动 reset）");

        const out = await postProcessFullWithOptions(mapPerception(""));
        if (cancelled) return;
        setLastAgentJson(out === null ? "null" : JSON.stringify(out, null, 2));
        handleBearAgentPayload(out, ctx, bearPayloadNavOptions);
      } catch (e) {
        if (!cancelled) {
          const msg = e instanceof Error ? e.message : String(e);
          setAgentErr(msg);
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [ctx, bearPayloadNavOptions, mapPerception]);

  useEffect(() => {
    if (!boardAutoFollow) {
      setBoardPollErr("");
      setBoardBridgePerception(null);
      setBoardLiveAsr(null);
      return;
    }
    let cancelled = false;
    const tick = async () => {
      try {
        const r = await fetchBoardAutoLast();
        if (cancelled) return;
        setBoardPollErr("");
        setBoardLiveAsr({
          asr_partial: r.asr_partial,
          asr_final: r.asr_final,
          asr_normalized: r.asr_normalized,
          asr_live_ts: r.asr_live_ts,
        });
        if (r.perception) {
          setBoardBridgePerception(r.perception);
          applyLiveBoardPerception(r.perception);
        }
        if (r.seq < lastBoardDriveSeqRef.current) {
          lastBoardDriveSeqRef.current = 0;
        }
        if (r.seq > lastBoardDriveSeqRef.current) {
          lastBoardDriveSeqRef.current = r.seq;
          if (r.output !== null && r.output !== undefined) {
            handleBearAgentPayload(r.output, ctx, {
              ...bearPayloadNavOptions,
              onPlaybackChainFinished: () => {
                void postMultimodalPlaybackDone();
              },
            });
            setLastAgentJson(JSON.stringify(r.output, null, 2));
          }
        }
      } catch (e) {
        if (!cancelled) {
          const msg = e instanceof Error ? e.message : String(e);
          setBoardPollErr(msg.includes("Failed to fetch") ? "Failed to fetch（无法连接后端）" : msg);
        }
      }
    };
    void tick();
    const id = window.setInterval(() => void tick(), 400);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, [boardAutoFollow, ctx, bearPayloadNavOptions, applyLiveBoardPerception, topNav]);

  useEffect(() => {
    if (!import.meta.env.DEV) return;
    (window as unknown as { __demoAgentJson?: () => void }).__demoAgentJson = () => {
      handleAgentJson(
        JSON.stringify({
          smpl_streaming_path: "SmplhRetarget/挥手致意.json",
          speech: "嘿！你好呀！",
          emotion: "smile",
          interaction_type: "story_interaction",
        }),
        ctx
      );
    };
  }, [ctx]);

  return (
    <div className="flex h-[100dvh] w-full max-w-[100vw] flex-col overflow-hidden bg-gradient-to-br from-slate-900/5 via-cream to-sky-light/35 text-forest-deep">
      <div
        className="pointer-events-none fixed inset-0 opacity-30"
        style={{
          backgroundImage:
            "radial-gradient(ellipse 80% 50% at 20% 10%, rgba(34,197,94,0.15), transparent 50%), radial-gradient(ellipse 60% 40% at 90% 20%, rgba(6,182,212,0.2), transparent 50%)",
        }}
        aria-hidden
      />
      <div className="relative z-10 flex min-h-0 flex-1 flex-col">
        <TopMenu active={topNav} onSelect={onTopNav} />
        <div className="min-h-0 flex-1 px-2 py-2 md:px-4 md:py-3">
          <div className="mx-auto flex h-full min-h-0 min-w-0 max-w-[min(100%,1400px)] flex-1 flex-col gap-2 md:flex-row">
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="flex min-h-0 min-w-0 flex-1 flex-col"
            >
              <div className="mb-1 flex items-center justify-between text-[11px] text-slate-500 md:text-xs">
                <span>智慧乐园 · 终端</span>
                <span className="font-mono text-forest/80">
                  模式: <strong>{topNav}</strong>
                </span>
              </div>
              <div className="relative flex min-h-0 flex-1 flex-col">
                <div
                  className={topNav === "map" ? "hidden" : "flex min-h-0 flex-1 flex-col"}
                  aria-hidden={topNav === "map"}
                >
                  <UnityEmbed blockGamePointer={terminalIslandFocused} />
                </div>
                <div className={topNav === "map" ? "flex min-h-0 flex-1 flex-col" : "hidden"}>
                  <ParkMapPanel />
                </div>
              </div>
            </motion.div>
            {topNav === "story" ? (
              <aside className="flex max-h-[min(52vh,460px)] min-h-0 w-full shrink-0 flex-col border-t border-forest/10 bg-transparent md:max-h-none md:w-[292px] md:border-l md:border-t-0 md:bg-gradient-to-l md:from-white/55 md:to-transparent md:pl-2 md:backdrop-blur-[6px] lg:w-[308px]">
                <div className="flex flex-col items-stretch justify-start gap-2 overflow-y-auto overflow-x-hidden p-2 md:max-h-full md:p-2 md:pt-3">
                  <SmartParkTheaterPanel ctx={ctx} variant="sidebar" boardAutoSync={boardAutoFollow} />
                  <div
                    data-terminal-input-island
                    className="min-h-0 shrink-0 border-t border-dashed border-forest/15 pt-2"
                    onFocusCapture={onTerminalIslandFocusCapture}
                    onBlurCapture={onTerminalIslandBlurCapture}
                  >
                    <BearPipelineTestCard
                      emotion={bearEmotion}
                      gesture={bearGesture}
                      handGesture={bearHandGesture}
                      personDetected={bearPersonDetected}
                      onEmotionChange={setBearEmotion}
                      onGestureChange={setBearGesture}
                      onHandGestureChange={setBearHandGesture}
                      onPersonDetectedChange={setBearPersonDetected}
                      agentLoading={agentLoading}
                      agentErr={agentErr}
                      lastAgentJson={lastAgentJson}
                      onResetAgent={onResetAgent}
                      boardAutoFollow={boardAutoFollow}
                      onBoardAutoFollowChange={(v) => {
                        setBoardAutoFollow(v);
                        if (v) prepareBearAudioPlayback();
                      }}
                      boardPollErr={boardPollErr}
                      liveBoardPerception={boardBridgePerception}
                      liveBoardAsr={boardLiveAsr}
                      theaterAgentByVoice={boardAutoFollow}
                    />
                  </div>
                </div>
              </aside>
            ) : (
              <div
                data-terminal-input-island
                className="flex max-h-full min-h-0 w-full min-w-0 shrink-0 flex-col gap-2 overflow-y-auto md:w-56 lg:w-64"
                onFocusCapture={onTerminalIslandFocusCapture}
                onBlurCapture={onTerminalIslandBlurCapture}
              >
                <BearPipelineTestCard
                  emotion={bearEmotion}
                  gesture={bearGesture}
                  handGesture={bearHandGesture}
                  personDetected={bearPersonDetected}
                  onEmotionChange={setBearEmotion}
                  onGestureChange={setBearGesture}
                  onHandGestureChange={setBearHandGesture}
                  onPersonDetectedChange={setBearPersonDetected}
                  agentLoading={agentLoading}
                  agentErr={agentErr}
                  lastAgentJson={lastAgentJson}
                  onResetAgent={onResetAgent}
                  boardAutoFollow={boardAutoFollow}
                  onBoardAutoFollowChange={setBoardAutoFollow}
                  boardPollErr={boardPollErr}
                  liveBoardPerception={boardBridgePerception}
                  liveBoardAsr={boardLiveAsr}
                />
                {topNav === "map" ? (
                  agentPipelineDebugUi ? (
                    <p className="rounded-xl border border-dashed border-emerald-400/40 bg-emerald-50/50 px-3 py-2 text-[11px] leading-snug text-emerald-900">
                      地图模式下已隐藏「动作试播」按钮。问路请用底部输入框或「语音(模拟)」，逻辑来自 bear_agent{" "}
                      <code className="rounded bg-white/80 px-0.5">map_guide.MapGuide</code>。
                    </p>
                  ) : (
                    <p className="rounded-xl border border-dashed border-emerald-400/30 bg-emerald-50/40 px-3 py-2 text-[11px] leading-snug text-emerald-900">
                      地图模式下专注于问路，请用底部输入框或「语音(模拟)」。
                    </p>
                  )
                ) : (
                  <ActionPanel onSelectSmpl={onSelectSmpl} />
                )}
              </div>
            )}
          </div>
        </div>
        <div
          data-terminal-input-island
          className="shrink-0"
          onFocusCapture={onTerminalIslandFocusCapture}
          onBlurCapture={onTerminalIslandBlurCapture}
        >
          <BottomCommandBar
            guestInput={guestInput}
            onGuestInputChange={setGuestInput}
            onSend={onSend}
            onVoiceMock={onVoiceMock}
            subtitle={subtitle}
            currentSmplPath={currentSmplPath}
            unityStatusText={unityStatusText}
            variant={topNav === "map" ? "map" : "default"}
            boardBridgeAutoSync={boardAutoFollow}
            theaterVoiceOnly={topNav === "story" && boardAutoFollow}
            sendDisabled={agentLoading}
            agentHintExtra={
              topNav === "story"
                ? boardAutoFollow
                  ? agentPipelineDebugUi
                    ? "后端剧情：麦克风 ASR → board_bridge → speech_text。右侧卡片「本地演示」与 Bear Agent 无关。"
                    : "对着麦克风说口令与选项即可；熊大播台词时也可继续说下一句（由后端识别）。"
                  : agentPipelineDebugUi
                    ? "未开板端同步时可用底部输入框模拟语音；开启后建议仅用麦克风。"
                    : "未开板端同步时可用底部输入框说「剧情互动」并选择答案。"
                : undefined
            }
          />
        </div>
      </div>
    </div>
  );
}
