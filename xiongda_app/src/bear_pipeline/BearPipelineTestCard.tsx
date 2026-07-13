import { Bot, Loader2, RotateCcw } from "lucide-react";
import { agentPipelineDebugUi } from "./agentPipelineUi";
import { bearAgentBaseLabel } from "./bearAgentClient";
import { labelBodyGesture, labelEmotion, labelHandGesture } from "./boardLabels";
import type { BoardAsrLiveFields, PerceptionPayload } from "./bearAgentTypes";
import { preBoardStreamHintParagraph } from "./preBoardStreamHints";

const EMOTIONS = ["neutral", "happy", "sad", "surprised", "angry", "scared", "disgust"] as const;
const GESTURES = ["none", "wave_hand", "clapping"] as const;
const HAND = ["none", "like", "palm", "point", "heart", "ok", "fist"] as const;

function formatBbox(b: number[] | null | undefined): string {
  if (!Array.isArray(b) || b.length !== 4) return "—";
  return b.map((x) => Number(x).toFixed(0)).join(", ");
}

export type BearPerceptionProps = {
  emotion: string;
  gesture: string;
  handGesture: string;
  personDetected: boolean;
  onEmotionChange: (v: string) => void;
  onGestureChange: (v: string) => void;
  onHandGestureChange: (v: string) => void;
  onPersonDetectedChange: (v: boolean) => void;
  agentLoading: boolean;
  agentErr: string;
  lastAgentJson: string;
  onResetAgent: () => void | Promise<void>;
  /** 轮询 GET /api/board-auto/last，板端推理自动驱动 WebGL */
  boardAutoFollow: boolean;
  onBoardAutoFollowChange: (v: boolean) => void;
  /** 轮询失败（如未启动 server.py、端口不通） */
  boardPollErr?: string;
  /** board_bridge 最近一次 POST 附带的感知（含语音整句、人脸框） */
  liveBoardPerception?: PerceptionPayload | null;
  /** board_bridge 高频同步的 ASR：散句 partial + 定稿 final/normalized */
  liveBoardAsr?: BoardAsrLiveFields | null;
  /** 益智小剧场侧栏 + 板端同步：文案强调剧情仅由语音 speech_text 推进 */
  theaterAgentByVoice?: boolean;
};

type BearPipelineTestCardProps = BearPerceptionProps & {
  onEnterStoryTab?: () => void;
};

export function BearPipelineTestCard(props: BearPipelineTestCardProps) {
  const {
    emotion,
    gesture,
    handGesture,
    personDetected,
    onEmotionChange,
    onGestureChange,
    onHandGestureChange,
    onPersonDetectedChange,
    agentLoading,
    agentErr,
    lastAgentJson,
    onResetAgent,
    boardAutoFollow,
    onBoardAutoFollowChange,
    boardPollErr = "",
    liveBoardPerception = null,
    liveBoardAsr = null,
    theaterAgentByVoice = false,
  } = props;

  const base = bearAgentBaseLabel();
  const speechLive = (liveBoardPerception?.speech_text ?? "").trim();
  const bboxLive = formatBbox(liveBoardPerception?.face_bbox ?? undefined);
  const liveEmotionCn = labelEmotion(liveBoardPerception?.emotion);
  const liveBodyCn = labelBodyGesture(liveBoardPerception?.gesture);
  const liveHandCn = labelHandGesture(liveBoardPerception?.hand_gesture);

  const partialLive = (liveBoardAsr?.asr_partial ?? "").trim();
  const normLive = (liveBoardAsr?.asr_normalized ?? "").trim();
  const finalLive = (liveBoardAsr?.asr_final ?? "").trim();
  const wholeSentencePrimary = normLive || finalLive || speechLive;
  const showRawFinal = Boolean(finalLive && normLive && finalLive !== normLive);

  return (
    <section className="rounded-2xl border-2 border-sky-400/30 bg-white/90 p-3 shadow-md ring-1 ring-sky-100">
      <div className="mb-2 flex items-center gap-2 text-xs font-extrabold text-sky-900">
        <Bot className="h-4 w-4 shrink-0" aria-hidden />
        {boardAutoFollow ? "游客感知" : "模拟感知"}
      </div>

      {agentPipelineDebugUi ? (
        <p className="mb-2 text-[10px] leading-snug text-slate-600">
          后端：<span className="font-mono">{base}</span>
          <br />
          {boardAutoFollow ? (
            theaterAgentByVoice ? (
              <>
                已开启板端同步（益智小剧场）：下方字段由{" "}
                <code className="rounded bg-slate-100 px-0.5 font-mono">GET /api/board-auto/last</code>{" "}
                刷新；<code className="rounded bg-slate-100 px-0.5 font-mono">speech_text</code> 来自麦克风 ASR，经{" "}
                <code className="rounded bg-slate-100 px-0.5 font-mono">board_bridge</code> 合并视觉后 POST 给熊大。
                <strong>剧情分支只认语音识别结果</strong>；本页底部键盘已隐藏，避免手动打字覆盖 ASR。
              </>
            ) : (
              <>
                已开启板端同步：下方字段由 <code className="rounded bg-slate-100 px-0.5 font-mono">GET /api/board-auto/last</code>{" "}
                中的 <code className="rounded bg-slate-100 px-0.5 font-mono">perception</code> 刷新（来自{" "}
                <code className="rounded bg-slate-100 px-0.5 font-mono">board_bridge</code> POST）。右侧「语音（识别整句）」为 ASR
                参考；你在<strong>底部输入框发送</strong>时，会把<strong>当前整份板端感知</strong>与<strong>你键入的文字</strong>合并：
                <code className="rounded bg-slate-100 px-0.5 font-mono">speech_text</code> 以键盘为准（ASR 不准时可只用打字驱动 Agent）。感知 JSON 与精简包经{" "}
                <code className="rounded bg-slate-100 px-0.5 font-mono">board_bridge</code> 汇总后的字段一致（
                <code className="rounded bg-slate-100 px-0.5 font-mono">emotion</code> /{" "}
                <code className="rounded bg-slate-100 px-0.5 font-mono">gesture</code> /{" "}
                <code className="rounded bg-slate-100 px-0.5 font-mono">hand_gesture</code> /{" "}
                <code className="rounded bg-slate-100 px-0.5 font-mono">speech_text</code>
                ）。
              </>
            )
          ) : (
            <>
              游客在<strong>底部输入框</strong>说话；此处可手动模拟摄像头字段，与语音一并发给{" "}
              <code className="rounded bg-slate-100 px-0.5 font-mono">POST /api/process</code>
              （地图模式仍走 <span className="font-mono">/api/map-query</span>）。
            </>
          )}
        </p>
      ) : (
        <p className="mb-2 text-[11px] leading-snug text-slate-600">
          {boardAutoFollow
            ? theaterAgentByVoice
              ? "剧情互动时请对着麦克风说：识别结果会自动送给熊大推进分支；本页不使用底部键盘。"
              : "开启后，熊大会根据识别结果自动说话、做动作；也可在底部输入框补充你想说的话。"
            : "在此调节表情与动作，会与底部输入框的文字一起发给熊大。"}
        </p>
      )}

      {boardAutoFollow && agentPipelineDebugUi ? (
        <div className="mb-2 rounded-lg border border-amber-200/90 bg-amber-50/90 px-2 py-1.5 text-[10px] leading-snug text-amber-950">
          <strong>真实采集不走浏览器网页：</strong>
          摄像头与麦克风由<strong>本机 Python</strong>{" "}
          <code className="rounded bg-white/80 px-0.5 font-mono">pc_video_sender.py</code> /{" "}
          <code className="rounded bg-white/80 px-0.5 font-mono">pc_audio_sender.py</code>{" "}
          读取（例如精简包里执行 <code className="rounded bg-white/80 px-0.5 font-mono">python run_all.py --bear-bridge</code>
          ，并与 <code className="rounded bg-white/80 px-0.5 font-mono">bear_agent/board_bridge</code>{" "}
          一起开）。板端回连本机 18082/18083 后，此处才会出现识别整句与感知字段。
        </div>
      ) : null}

      {boardAutoFollow && agentPipelineDebugUi ? (
        <div className="mb-2 rounded-lg border border-violet-200/90 bg-violet-50/80 px-2 py-2 text-[10px] leading-relaxed text-violet-950">
          <div className="font-bold text-violet-900">实时 ASR · 人脸框</div>
          <div className="mt-1 grid gap-1 font-mono text-[10px]">
            <div>
              <span className="text-violet-700">散句（流式 partial）</span>：
              <span className="break-all text-violet-950">
                {partialLive || "（暂无草稿；说话时会逐字更新）"}
              </span>
            </div>
            <div>
              <span className="text-violet-700">整句（定稿）</span>：
              <span className="break-all text-violet-950">
                {wholeSentencePrimary || "（暂无整句；说完一句后出现归一化/原始/final）"}
              </span>
            </div>
            {showRawFinal ? (
              <div className="text-violet-800/90">
                <span className="text-violet-600">└ 原始 final（未归一）</span>：
                <span className="break-all">{finalLive}</span>
              </div>
            ) : null}
            <div className="border-t border-violet-200/70 pt-1 text-violet-800/85">
              <span className="text-violet-600">送入 Agent 的 speech_text</span>（与 board_bridge 感知一致）：
              <span className="break-all text-violet-950">{speechLive || "—"}</span>
            </div>
            <div>
              <span className="text-violet-700">人脸框 x1,y1,x2,y2</span>：<span>{bboxLive}</span>
            </div>
            {liveBoardPerception ? (
              <div className="text-violet-900">
                <span className="text-violet-700">视觉标签（与 pc_result_viewer 叠加同源）</span>：表情 {liveEmotionCn}（
                {liveBoardPerception.emotion ?? "—"}）· 躯干 {liveBodyCn}（{liveBoardPerception.gesture ?? "—"}）· 手{" "}
                {liveHandCn}（{liveBoardPerception.hand_gesture ?? "—"}）· person_detected{" "}
                {liveBoardPerception.person_detected ? "是" : "否"}
              </div>
            ) : null}
          </div>
          <p className="mt-1.5 border-t border-violet-200/80 pt-1.5 text-[9px] leading-snug text-violet-800/90">
            {preBoardStreamHintParagraph()}
          </p>
          {!liveBoardPerception ? (
            <p className="mt-1 text-[10px] text-violet-700">等待 board_bridge 首次上报 perception…</p>
          ) : null}
        </div>
      ) : null}

      {boardAutoFollow && !agentPipelineDebugUi ? (
        <div className="mb-2 rounded-lg border border-sky-200/80 bg-sky-50/60 px-2 py-2 text-[11px] leading-relaxed text-sky-950">
          <div className="font-semibold text-sky-900">听到的内容</div>
          <div className="mt-1">
            <span className="text-sky-800/90">正在说：</span>
            <span className="break-all">{partialLive || "（安静中…）"}</span>
          </div>
          <div className="mt-0.5">
            <span className="text-sky-800/90">完整一句：</span>
            <span className="break-all">{wholeSentencePrimary || "（说完一句后会显示）"}</span>
          </div>
          {liveBoardPerception ? (
            <div className="mt-1 border-t border-sky-200/70 pt-1 text-sky-900">
              画面理解：{liveEmotionCn} · {liveBodyCn} · {liveHandCn}
            </div>
          ) : (
            <p className="mt-1 text-[10px] text-sky-800/80">识别就绪后，这里会显示你说的话和简单画面信息。</p>
          )}
        </div>
      ) : null}

      {boardPollErr ? (
        <pre className="mb-2 max-h-20 overflow-auto rounded-lg bg-amber-50 p-2 text-[10px] text-amber-950">
          {agentPipelineDebugUi ? (
            <>
              板端轮询：{boardPollErr}
              {"\n"}请确认已运行{" "}
              <code className="rounded bg-white/90 px-0.5">python integration_test/server.py</code>（默认 8765），且浏览器能访问{" "}
              <code className="rounded bg-white/90 px-0.5">{base}</code>
            </>
          ) : (
            <>暂时连不上服务，请稍后再试。{boardPollErr ? `（${boardPollErr}）` : ""}</>
          )}
        </pre>
      ) : null}

      <label className="mb-2 flex cursor-pointer items-start gap-2 rounded-lg border border-emerald-200/80 bg-emerald-50/70 px-2 py-1.5 text-[10px] leading-snug text-emerald-950">
        <input
          type="checkbox"
          checked={boardAutoFollow}
          onChange={(e) => onBoardAutoFollowChange(e.target.checked)}
          className="mt-0.5 rounded border-emerald-400"
        />
        <span>
          {agentPipelineDebugUi ? (
            <>
              <strong>板端自动同步 WebGL</strong>：定时请求{" "}
              <code className="rounded bg-white/90 px-0.5 font-mono">GET /api/board-auto/last</code>
              ；当本机 <code className="rounded bg-white/90 px-0.5 font-mono">board_bridge</code>{" "}
              把感知 POST 给 Agent 后，熊大会自动跟读/跟动作。默认开启；构建前可设{" "}
              <code className="rounded bg-white/90 px-0.5 font-mono">VITE_BOARD_AUTO_POLL=false</code>{" "}
              默认关闭。
            </>
          ) : (
            <>
              <strong>与熊大自动互动</strong>（推荐开启）：熊大会跟着识别结果自动说话、做动作。
            </>
          )}
        </span>
      </label>

      <div className="mb-2 grid grid-cols-2 gap-2">
        <div>
          <label className="mb-0.5 block text-[10px] font-bold text-slate-600">emotion</label>
          <select
            value={emotion}
            disabled={boardAutoFollow}
            onChange={(e) => onEmotionChange(e.target.value)}
            className="w-full rounded-lg border border-slate-200 bg-white px-2 py-1 text-[11px] disabled:cursor-not-allowed disabled:bg-slate-100 disabled:opacity-80"
          >
            {!EMOTIONS.includes(emotion as (typeof EMOTIONS)[number]) && emotion ? (
              <option value={emotion}>{emotion}</option>
            ) : null}
            {EMOTIONS.map((x) => (
              <option key={x} value={x}>
                {x}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="mb-0.5 block text-[10px] font-bold text-slate-600">gesture</label>
          <select
            value={gesture}
            disabled={boardAutoFollow}
            onChange={(e) => onGestureChange(e.target.value)}
            className="w-full rounded-lg border border-slate-200 bg-white px-2 py-1 text-[11px] disabled:cursor-not-allowed disabled:bg-slate-100 disabled:opacity-80"
          >
            {!GESTURES.includes(gesture as (typeof GESTURES)[number]) && gesture ? (
              <option value={gesture}>{gesture}</option>
            ) : null}
            {GESTURES.map((x) => (
              <option key={x} value={x}>
                {x}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="mb-0.5 block text-[10px] font-bold text-slate-600">hand_gesture</label>
          <select
            value={handGesture}
            disabled={boardAutoFollow}
            onChange={(e) => onHandGestureChange(e.target.value)}
            className="w-full rounded-lg border border-slate-200 bg-white px-2 py-1 text-[11px] disabled:cursor-not-allowed disabled:bg-slate-100 disabled:opacity-80"
          >
            {!HAND.includes(handGesture as (typeof HAND)[number]) && handGesture ? (
              <option value={handGesture}>{handGesture}</option>
            ) : null}
            {HAND.map((x) => (
              <option key={x} value={x}>
                {x}
              </option>
            ))}
          </select>
        </div>
        <div className="flex items-end">
          <label className="flex cursor-pointer items-center gap-2 text-[11px] font-medium text-slate-700">
            <input
              type="checkbox"
              checked={personDetected}
              disabled={boardAutoFollow}
              onChange={(e) => onPersonDetectedChange(e.target.checked)}
              className="rounded border-slate-300 disabled:opacity-60"
            />
            person_detected
          </label>
        </div>
      </div>

      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          disabled={agentLoading}
          onClick={() => void Promise.resolve(onResetAgent())}
          className="inline-flex items-center gap-1 rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-50"
        >
          {agentLoading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RotateCcw className="h-3.5 w-3.5" />}
          重置记忆 / 状态机
        </button>
      </div>

      {agentErr ? (
        <pre className="mt-2 max-h-24 overflow-auto rounded-lg bg-red-50 p-2 text-[10px] text-red-800">{agentErr}</pre>
      ) : null}
      {lastAgentJson && agentPipelineDebugUi ? (
        <details className="mt-2">
          <summary className="cursor-pointer text-[10px] font-bold text-slate-600">上次返回 JSON</summary>
          <pre className="mt-1 max-h-40 overflow-auto rounded-lg bg-slate-900/90 p-2 font-mono text-[10px] text-emerald-100">
            {lastAgentJson}
          </pre>
        </details>
      ) : null}
    </section>
  );
}
