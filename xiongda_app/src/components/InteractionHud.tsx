import { labelBodyGesture, labelEmotion, labelHandGesture } from "../bear_pipeline/boardLabels";
import type { BoardAsrLiveFields, PerceptionPayload } from "../bear_pipeline/bearAgentTypes";

export type InteractionHudProps = {
  /** 板端实时 ASR（底部字幕，识别过程） */
  liveAsr: BoardAsrLiveFields | null;
  /** 本轮实际送进 Agent 的多模态（右上角） */
  lastSentPerception: PerceptionPayload | null;
  /** Agent 忙时轻微提示 */
  agentLoading?: boolean;
};

/**
 * 叠在熊大/地图视口上：
 * - 右上角：本轮送入 Agent 的多模态输入（不是实时帧）
 * - 底部：ASR 字幕（实时识别过程）
 */
export function InteractionHud({
  liveAsr,
  lastSentPerception,
  agentLoading = false,
}: InteractionHudProps) {
  const partial = (liveAsr?.asr_partial ?? "").trim();
  const finalText = (liveAsr?.asr_normalized ?? liveAsr?.asr_final ?? "").trim();
  const sentSpeech = (lastSentPerception?.speech_text ?? "").trim();
  const subtitleLine = partial || finalText;
  const isPartial = Boolean(partial);

  const emotionCn = labelEmotion(lastSentPerception?.emotion);
  const handCn = labelHandGesture(lastSentPerception?.hand_gesture);
  const actionCn = labelBodyGesture(lastSentPerception?.gesture);

  return (
    <div className="pointer-events-none absolute inset-0 z-20 overflow-hidden" aria-live="polite">
      {/* 右上角：本轮送入 Agent 的输入 */}
      <div className="absolute right-3 top-3 max-w-[min(88vw,17rem)] md:right-4 md:top-4">
        <div className="rounded-xl border border-white/25 bg-black/60 px-3 py-2.5 text-[11px] leading-relaxed text-white shadow-lg backdrop-blur-md md:text-xs">
          <p className="mb-1 font-bold tracking-wide text-sky-200">
            本轮送入 Agent
            {agentLoading ? <span className="ml-1 font-normal text-amber-200">· 处理中</span> : null}
          </p>
          {lastSentPerception ? (
            <ul className="space-y-0.5 text-white/95">
              <li>
                <span className="text-white/60">表情：</span>
                {emotionCn}
              </li>
              <li>
                <span className="text-white/60">手势：</span>
                {handCn}
              </li>
              <li>
                <span className="text-white/60">动作：</span>
                {actionCn}
              </li>
              <li>
                <span className="text-white/60">语音：</span>
                {sentSpeech || "—"}
              </li>
            </ul>
          ) : (
            <p className="text-white/55">还没有送出过一轮。说完一句后约 1 秒会收束并更新这里。</p>
          )}
        </div>
      </div>

      {/* 底部 ASR 字幕（实时） */}
      <div className="absolute inset-x-0 bottom-3 flex justify-center px-4 md:bottom-4 md:px-8">
        <div
          className={[
            "max-w-[min(92%,42rem)] rounded-xl px-4 py-2.5 text-center shadow-lg backdrop-blur-md transition-opacity",
            subtitleLine ? "bg-black/55 text-white" : "bg-black/25 text-white/70",
          ].join(" ")}
          role="status"
        >
          <p
            className={[
              "text-sm font-semibold leading-snug tracking-wide md:text-base",
              isPartial ? "opacity-90" : "opacity-100",
            ].join(" ")}
          >
            {subtitleLine || "对着麦克风说话，识别结果会出现在这里…"}
          </p>
          {isPartial ? (
            <p className="mt-0.5 text-[10px] font-medium uppercase tracking-wider text-sky-200/90">
              识别中
            </p>
          ) : null}
        </div>
      </div>
    </div>
  );
}
