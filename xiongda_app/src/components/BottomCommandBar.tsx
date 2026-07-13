import { motion } from "framer-motion";
import { Mic, Send, MessageSquareText } from "lucide-react";
import { agentPipelineDebugUi } from "../bear_pipeline/agentPipelineUi";

type BottomCommandBarProps = {
  guestInput: string;
  onGuestInputChange: (v: string) => void;
  onSend: () => void;
  onVoiceMock: () => void;
  subtitle: string;
  currentSmplPath: string;
  unityStatusText: string;
  /** 地图模式：不强调 SMPL / WebGL，突出文字与语音问路 */
  variant?: "default" | "map";
  /** Bear Agent 请求进行中 */
  sendDisabled?: boolean;
  /** 非地图模式下追加一行操作说明（如益智小剧场用文字推进后端剧情） */
  agentHintExtra?: string;
  /** 已开启「板端自动同步」：底部输入仅为补充/示例，真实 ASR 来自 board_bridge */
  boardBridgeAutoSync?: boolean;
  /** 益智小剧场 + 板端同步：不展示键盘/发送，剧情仅由麦克风 ASR 经 board_bridge 推进 */
  theaterVoiceOnly?: boolean;
};

export function BottomCommandBar({
  guestInput,
  onGuestInputChange,
  onSend,
  onVoiceMock,
  subtitle,
  currentSmplPath,
  unityStatusText,
  variant = "default",
  sendDisabled = false,
  agentHintExtra,
  boardBridgeAutoSync = false,
  theaterVoiceOnly = false,
}: BottomCommandBarProps) {
  const isMap = variant === "map";
  if (theaterVoiceOnly) {
    return (
      <footer className="shrink-0 space-y-2 border-t border-forest/10 bg-white/80 px-3 py-2 shadow-[0_-8px_30px_rgba(0,0,0,0.06)] backdrop-blur-md md:px-4 md:py-3">
        <div className="flex flex-wrap items-center gap-2 text-xs text-slate-600 md:text-sm">
          <span className="font-bold text-forest">熊大回复</span>
          <MessageSquareText className="h-3.5 w-3.5 text-sky-600" aria-hidden />
          <span className="min-w-0 flex-1 font-semibold text-forest-deep">
            {subtitle || "—"}
          </span>
        </div>
        <div
          className="rounded-xl border-2 border-sky-200/80 bg-sky-50/70 px-3 py-2.5 text-xs leading-relaxed text-sky-950 md:text-sm"
          role="status"
        >
          <strong className="text-sky-900">剧情互动 · 仅语音</strong>
          ：请对着麦克风说话。先说「剧情互动」进入剧本，再按提示用语音选（例如「先听听规则」「往左」「路线 B」或字母
          A/B/C）。底部键盘已关闭，避免与麦克风识别抢话；感知由板端 ASR 自动送给熊大。
        </div>
        <div className="flex flex-wrap items-baseline justify-between gap-2 text-xs text-slate-600">
          <p>
            状态：<span className="font-semibold text-forest">{unityStatusText}</span>
            {agentHintExtra ? (
              <>
                <br />
                <span className="mt-1 inline-block text-slate-600">{agentHintExtra}</span>
              </>
            ) : null}
          </p>
        </div>
      </footer>
    );
  }
  return (
    <footer className="shrink-0 space-y-2 border-t border-forest/10 bg-white/80 px-3 py-2 shadow-[0_-8px_30px_rgba(0,0,0,0.06)] backdrop-blur-md md:px-4 md:py-3">
      <div className="flex flex-wrap items-center gap-2 text-xs text-slate-600 md:text-sm">
        <span className="font-bold text-forest">熊大回复</span>
        <MessageSquareText className="h-3.5 w-3.5 text-sky-600" aria-hidden />
        <span className="min-w-0 flex-1 font-semibold text-forest-deep">
          {subtitle || "—"}
        </span>
      </div>
      <div className="flex flex-col gap-2 sm:flex-row sm:items-stretch">
        <motion.button
          type="button"
          whileHover={{ scale: 1.01 }}
          whileTap={{ scale: 0.99 }}
          disabled={sendDisabled}
          onClick={onVoiceMock}
          className="flex h-11 shrink-0 items-center justify-center gap-1.5 rounded-xl bg-gradient-to-r from-sky-500 to-sky-400 px-4 text-sm font-bold text-white shadow md:min-w-[7rem] disabled:opacity-50"
        >
          <Mic className="h-4 w-4" />
          {!isMap && boardBridgeAutoSync ? "示例一句" : "语音(模拟)"}
        </motion.button>
        <input
          type="text"
          value={guestInput}
          onChange={(e) => onGuestInputChange(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && !sendDisabled && onSend()}
          disabled={sendDisabled}
          placeholder={
            isMap
              ? "输入问路，例如：怎么去海螺湾、飞越极限怎么走"
              : boardBridgeAutoSync
                ? agentPipelineDebugUi
                  ? "发送：以你输入为 speech_text，并带上最新板端感知（表情/手势/人脸框）。ASR 仅作右侧参考；剧情互动等口令在此输入"
                  : "输入你想对熊说的话，或试试「剧情互动」「语音聊天」"
                : agentPipelineDebugUi
                  ? "模拟游客语音：剧情互动 → 益智小剧场；语音聊天 → 语音页；其它句子同样发给 Bear Agent"
                  : "输入你想对熊说的话，或试试「剧情互动」「语音聊天」"
          }
          className="min-w-0 flex-1 rounded-xl border-2 border-forest/15 bg-cream px-3 text-sm font-semibold shadow-inner outline-none focus:border-sky-500 disabled:opacity-60"
        />
        <motion.button
          type="button"
          whileHover={{ scale: 1.01 }}
          whileTap={{ scale: 0.99 }}
          disabled={sendDisabled}
          onClick={onSend}
          className="flex h-11 shrink-0 items-center justify-center gap-1.5 rounded-xl bg-gradient-to-r from-forest to-forest-light px-5 text-sm font-bold text-cream shadow md:min-w-[4.5rem] disabled:opacity-50"
        >
          <Send className="h-4 w-4" />
          发送
        </motion.button>
      </div>
      <div className="flex flex-wrap items-baseline justify-between gap-2 text-xs">
        {isMap ? (
          <p className="text-slate-600">
            <span className="font-bold text-emerald-800">地图模式</span>
            {agentPipelineDebugUi
              ? "：仅展示平面图与熊大文字回复；浏览器可朗读回复（与益智小剧场相同 TTS）。不发送 SMPL 到 Unity。"
              : "：看图问路，熊大会用文字回答你。"}
          </p>
        ) : agentPipelineDebugUi ? (
          <>
            <p className="min-w-0 break-all font-mono text-forest">
              当前 <span className="font-bold text-amber-800">SMPL</span>: {currentSmplPath}
            </p>
            <p className="text-slate-500">
              默认请求 Bear Agent <span className="font-mono">/api/process</span>（右侧为感知字段）；首次入园请先任意发一句再发「剧情互动」。
              状态：<span className="font-semibold text-forest">{unityStatusText}</span>
              {agentHintExtra ? (
                <>
                  <br />
                  <span className="mt-1 inline-block text-slate-600">{agentHintExtra}</span>
                </>
              ) : null}
            </p>
          </>
        ) : (
          <p className="text-slate-600">
            状态：<span className="font-semibold text-forest">{unityStatusText}</span>
            {agentHintExtra ? (
              <>
                <br />
                <span className="mt-1 inline-block">{agentHintExtra}</span>
              </>
            ) : null}
          </p>
        )}
      </div>
    </footer>
  );
}
