import { motion } from "framer-motion";
import { Hand } from "lucide-react";
import { defaultSmplhActions, type SmplhActionItem } from "../data/smplhActions";

type ActionPanelProps = {
  onSelectSmpl: (item: SmplhActionItem) => void;
};

export function ActionPanel({ onSelectSmpl }: ActionPanelProps) {
  return (
    <aside className="flex w-full min-w-0 flex-col gap-2 overflow-hidden md:w-56 lg:w-64">
      <div className="flex items-center gap-2 rounded-t-2xl border-b border-forest/10 bg-forest/10 px-3 py-2 text-sm font-extrabold text-forest-deep">
        <Hand className="h-4 w-4" aria-hidden />
        动作控制（SMPL JSON）
      </div>
      <p className="px-1 text-[10px] leading-snug text-slate-600">
        列表与 <code className="rounded bg-black/5 px-0.5">clip_manifest</code> 对齐；新增动作固定在<strong>最上方</strong>。
      </p>
      <div className="grid min-h-0 flex-1 grid-cols-2 gap-2 overflow-y-auto p-1 md:grid-cols-1">
        {defaultSmplhActions.map((item, i) => (
          <motion.button
            key={item.streamingRelativePath}
            type="button"
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: Math.min(i * 0.015, 0.4) }}
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
            onClick={() => onSelectSmpl(item)}
            className="rounded-2xl border-2 border-forest/10 bg-gradient-to-br from-cream to-white py-3 text-sm font-bold text-forest-deep shadow-md ring-1 ring-white/60 hover:border-honey/80 hover:shadow-lg"
          >
            {item.label}
          </motion.button>
        ))}
      </div>
    </aside>
  );
}
