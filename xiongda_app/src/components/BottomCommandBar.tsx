import { motion } from "framer-motion";
import { Mic, Send } from "lucide-react";

type BottomCommandBarProps = {
  guestInput: string;
  onGuestInputChange: (v: string) => void;
  onSend: () => void;
  onVoiceMock: () => void;
  subtitle: string;
  /** 保留兼容：地图模式文案略不同 */
  variant?: "default" | "map";
  sendDisabled?: boolean;
  agentHintExtra?: string;
  boardBridgeAutoSync?: boolean;
  theaterVoiceOnly?: boolean;
  /** @deprecated 界面已精简，保留参数以免调用方改动过多 */
  currentSmplPath?: string;
  unityStatusText?: string;
};

export function BottomCommandBar({
  guestInput,
  onGuestInputChange,
  onSend,
  onVoiceMock,
  subtitle,
  variant = "default",
  sendDisabled = false,
  agentHintExtra,
  boardBridgeAutoSync = false,
  theaterVoiceOnly = false,
}: BottomCommandBarProps) {
  const isMap = variant === "map";
  if (theaterVoiceOnly) {
    return (
      <footer className="shrink-0 border-t border-forest/10 bg-white/85 px-3 py-2 shadow-[0_-8px_30px_rgba(0,0,0,0.06)] backdrop-blur-md md:px-4 md:py-2.5">
        <div className="flex items-start gap-2">
          <span className="shrink-0 rounded-md bg-forest/10 px-2 py-0.5 text-[11px] font-bold text-forest">
            熊大
          </span>
          <p className="min-w-0 flex-1 text-sm font-semibold leading-snug text-forest-deep md:text-base">
            {subtitle || "等待熊大回复…"}
          </p>
        </div>
        <p className="mt-1.5 text-[11px] text-slate-500">
          剧情仅语音：对着麦克风说话即可
          {agentHintExtra ? ` · ${agentHintExtra}` : ""}
        </p>
      </footer>
    );
  }
  return (
    <footer className="shrink-0 space-y-1.5 border-t border-forest/10 bg-white/85 px-3 py-2 shadow-[0_-8px_30px_rgba(0,0,0,0.06)] backdrop-blur-md md:px-4 md:py-2.5">
      <div className="flex items-start gap-2">
        <span className="shrink-0 rounded-md bg-forest/10 px-2 py-0.5 text-[11px] font-bold text-forest">
          熊大
        </span>
        <p className="min-w-0 flex-1 text-sm font-semibold leading-snug text-forest-deep md:text-base">
          {subtitle || "等待熊大回复…"}
        </p>
      </div>
      <div className="flex flex-col gap-2 sm:flex-row sm:items-stretch">
        <motion.button
          type="button"
          whileHover={{ scale: 1.01 }}
          whileTap={{ scale: 0.99 }}
          disabled={sendDisabled}
          onClick={onVoiceMock}
          className="flex h-10 shrink-0 items-center justify-center gap-1.5 rounded-xl bg-gradient-to-r from-sky-500 to-sky-400 px-4 text-sm font-bold text-white shadow md:min-w-[7rem] disabled:opacity-50"
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
              ? "输入问路，例如：怎么去海螺湾"
              : boardBridgeAutoSync
                ? "也可在此输入想说的话（会覆盖本轮语音文字）"
                : "输入你想对熊说的话，或试试「剧情互动」"
          }
          className="min-w-0 flex-1 rounded-xl border-2 border-forest/15 bg-cream px-3 text-sm font-semibold shadow-inner outline-none focus:border-sky-500 disabled:opacity-60"
        />
        <motion.button
          type="button"
          whileHover={{ scale: 1.01 }}
          whileTap={{ scale: 0.99 }}
          disabled={sendDisabled}
          onClick={onSend}
          className="flex h-10 shrink-0 items-center justify-center gap-1.5 rounded-xl bg-gradient-to-r from-forest to-forest-light px-5 text-sm font-bold text-cream shadow md:min-w-[4.5rem] disabled:opacity-50"
        >
          <Send className="h-4 w-4" />
          发送
        </motion.button>
      </div>
    </footer>
  );
}
