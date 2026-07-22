import { Globe2, Sparkles, Theater } from "lucide-react";
import type { TopNavId } from "../types";

const items: { id: TopNavId; label: string; icon: typeof Globe2 }[] = [
  { id: "world", label: "全图互动", icon: Globe2 },
  { id: "story", label: "益智小剧场", icon: Theater },
  { id: "recommend", label: "项目推荐", icon: Sparkles },
];

type TopMenuProps = {
  active: TopNavId;
  onSelect: (id: TopNavId) => void;
};

export function TopMenu({ active, onSelect }: TopMenuProps) {
  return (
    <header className="shrink-0 border-b border-forest/10 bg-gradient-to-r from-white/95 via-cream/90 to-sky-light/30 shadow-md backdrop-blur-md">
      <div className="mx-auto flex h-12 max-w-[100vw] items-stretch overflow-x-auto px-1 md:px-2">
        {items.map(({ id, label, icon: Icon }) => {
          const isOn = active === id;
          return (
            <button
              key={id}
              type="button"
              onClick={() => onSelect(id)}
              className={`inline-flex min-w-0 shrink-0 items-center gap-1.5 border-b-4 px-3 text-sm font-extrabold transition md:px-4 md:text-base ${
                isOn
                  ? "border-forest bg-forest/5 text-black"
                  : "border-transparent text-black hover:bg-white/60 hover:text-black"
              }`}
            >
              <Icon className="h-4 w-4 shrink-0 md:h-5 md:w-5" strokeWidth={2.2} aria-hidden />
              <span className="truncate">{label}</span>
            </button>
          );
        })}
      </div>
    </header>
  );
}
