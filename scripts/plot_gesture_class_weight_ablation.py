"""逆频率加权 CrossEntropy 对照：分组柱状图（PPT）。"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib import font_manager

ROOT = Path(__file__).resolve().parents[1]
DATA_JSON = ROOT / "docs" / "ppt_figures" / "data" / "gesture_class_weight_ablation.json"
PPT_JSON = ROOT / "docs" / "ppt_figures" / "data" / "gesture_class_weight_ppt_metrics.json"
OUT_DIR = ROOT / "docs" / "ppt_figures"

COLOR_UNW = "#BDBDBD"
COLOR_W = "#2166AC"


def setup_rc() -> None:
    available = {f.name for f in font_manager.fontManager.ttflist}
    families = [n for n in ("Times New Roman", "SimSun", "STSong") if n in available]
    plt.rcParams["font.family"] = families or ["Times New Roman"]
    plt.rcParams.update(
        {
            "font.size": 9,
            "axes.unicode_minus": False,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )


def load_metrics(path: Path) -> dict:
    if PPT_JSON.exists():
        ppt = json.loads(PPT_JSON.read_text(encoding="utf-8"))
        labels = ppt["labels"]
        return {
            "labels": [
                labels[0].replace(" ", "\n", 1) if " " in labels[0] else labels[0],
                labels[1].replace(" ", "\n", 1) if " " in labels[1] else labels[1],
                "最差类 Recall\n(thumb_index2)",
                "最差类 F1\n(thumb_index2)",
            ],
            "unweighted": ppt["unweighted_pct"],
            "weighted": ppt["weighted_pct"],
        }

    data = json.loads(path.read_text(encoding="utf-8"))
    w = data["existing_weighted"]
    u = data["unweighted_run"]
    w_pcm = w["per_class_metrics"]
    u_pcm = u["per_class_metrics"]
    cls = "thumb_index2"
    return {
        "labels": [
            "整体 Top-1\n准确率",
            "宏平均\nRecall",
            f"最差类 Recall\n({cls})",
            f"最差类 F1\n({cls})",
        ],
        "unweighted": [
            u["test_acc"] * 100,
            u["macro_recall"] * 100,
            u_pcm[cls]["recall"] * 100,
            u_pcm[cls]["f1"] * 100,
        ],
        "weighted": [
            w["test_acc"] * 100,
            sum(m["recall"] for m in w_pcm.values()) / len(w_pcm) * 100,
            w_pcm[cls]["recall"] * 100,
            w_pcm[cls]["f1"] * 100,
        ],
    }


def plot(path: Path, out_dir: Path) -> tuple[Path, Path]:
    setup_rc()
    m = load_metrics(path)
    x = np.arange(len(m["labels"]))
    width = 0.34

    fig, ax = plt.subplots(figsize=(5.6, 3.2), dpi=300)
    b1 = ax.bar(x - width / 2, m["unweighted"], width, label="未加权 CE", color=COLOR_UNW, edgecolor="#888888", linewidth=0.6)
    b2 = ax.bar(x + width / 2, m["weighted"], width, label="逆频率加权 CE", color=COLOR_W, edgecolor="white", linewidth=0.6)

    for bars in (b1, b2):
        for bar in bars:
            h = bar.get_height()
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                h + 0.8,
                f"{h:.1f}%",
                ha="center",
                va="bottom",
                fontsize=7.5,
                color="#333333",
            )

    # 不显示 pp 差值标注（PPT 由柱顶数值自明）

    ax.set_ylabel("准确率 / Recall / F1 (%)", fontsize=9)
    ax.set_title("HaGRID 手势 MLP：逆频率加权 CrossEntropy 对照", fontsize=10, fontweight="bold", pad=8)
    ax.set_xticks(x)
    ax.set_xticklabels(m["labels"], fontsize=8)
    ax.set_ylim(0, 98)
    ax.grid(True, axis="y", linestyle="-", linewidth=0.35, color="#E0E0E0", alpha=0.9)
    ax.set_axisbelow(True)
    ax.legend(
        loc="upper center",
        bbox_to_anchor=(0.5, -0.24),
        ncol=2,
        fontsize=8,
        framealpha=0.95,
        borderaxespad=0.0,
    )

    fig.subplots_adjust(bottom=0.30)
    fig.tight_layout()
    out_dir.mkdir(parents=True, exist_ok=True)
    png = out_dir / "gesture_class_weight_ablation_bar.png"
    pdf = out_dir / "gesture_class_weight_ablation_bar.pdf"
    fig.savefig(png, bbox_inches="tight", facecolor="white", pad_inches=0.03)
    fig.savefig(pdf, bbox_inches="tight", facecolor="white", pad_inches=0.03)
    plt.close(fig)
    return png, pdf


def main() -> None:
    if not DATA_JSON.exists():
        raise FileNotFoundError(DATA_JSON)
    png, pdf = plot(DATA_JSON, OUT_DIR)
    print(f"Wrote {png}")
    print(f"Wrote {pdf}")


if __name__ == "__main__":
    main()
