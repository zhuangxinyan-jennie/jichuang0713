"""逆频率加权 CrossEntropy 对照实验：无加权 vs 加权（复现 train_gesture_mlp 协议）。"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import yaml
from torch.utils.data import DataLoader

GR = Path(
    r"F:\jichuang2026\CICC1007411+初赛+技术数据\CICC1007411_初赛+技术数据+第一部分"
    r"\board_model\gesture_recognition\gesture_recognition(2)\gesture_recognition"
)
OUT = Path(r"F:\jichuang2026\clean_0606\docs\ppt_figures\data")
sys.path.insert(0, str(GR))

from datasets.gesture_dataset import GestureFeatureDataset  # noqa: E402
from models.gesture_mlp import GestureMLP  # noqa: E402
from utils.checkpoint import load_checkpoint, save_checkpoint  # noqa: E402
from utils.label_map import load_label_map  # noqa: E402
from utils.metrics import confusion_matrix, evaluate, per_class_metrics  # noqa: E402


def class_weights(ds: GestureFeatureDataset, num_classes: int) -> torch.Tensor:
    counts = np.zeros((num_classes,), dtype=np.float64)
    for i in ds.indices:
        counts[int(ds.y[i])] += 1
    inv = 1.0 / np.maximum(counts, 1.0)
    w = inv / inv.mean()
    return torch.tensor(w.astype(np.float32))


def train_one(*, weighted: bool, epochs: int, seed: int = 42) -> dict:
    torch.manual_seed(seed)
    np.random.seed(seed)

    dcfg = yaml.safe_load((GR / "configs" / "dataset.yaml").read_text(encoding="utf-8"))
    tcfg = yaml.safe_load((GR / "configs" / "mlp_gesture.yaml").read_text(encoding="utf-8"))

    ds_npz = (GR / "artifacts" / "dataset" / "gesture_features.npz").resolve()
    train_split = (GR / "artifacts" / "splits" / "train.txt").resolve()
    val_split = (GR / "artifacts" / "splits" / "val.txt").resolve()
    test_split = (GR / "artifacts" / "splits" / "test.txt").resolve()

    train_ds = GestureFeatureDataset(ds_npz, train_split)
    val_ds = GestureFeatureDataset(ds_npz, val_split)
    test_ds = GestureFeatureDataset(ds_npz, test_split)

    labels = load_label_map((GR / "artifacts" / "label_map.json").resolve())["id_to_label"]
    input_dim = int(train_ds.x.shape[1])
    num_classes = len(labels)
    hidden = tuple(tcfg.get("hidden_dims", [128, 64]))
    bs = int(tcfg.get("batch_size", 256))

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = GestureMLP(
        input_dim=input_dim,
        num_classes=num_classes,
        hidden_dims=(int(hidden[0]), int(hidden[1])),
        dropout=float(tcfg.get("dropout", 0.2)),
    ).to(device)

    if weighted:
        cw = class_weights(train_ds, num_classes).to(device)
        criterion = nn.CrossEntropyLoss(weight=cw)
        tag = "weighted"
    else:
        criterion = nn.CrossEntropyLoss()
        tag = "unweighted"

    optimizer = torch.optim.Adam(
        model.parameters(),
        lr=float(tcfg.get("lr", 1e-3)),
        weight_decay=float(tcfg.get("weight_decay", 0.0)),
    )

    tr_loader = DataLoader(train_ds, batch_size=bs, shuffle=True, num_workers=0)
    va_loader = DataLoader(val_ds, batch_size=bs, shuffle=False, num_workers=0)
    te_loader = DataLoader(test_ds, batch_size=bs, shuffle=False, num_workers=0)

    out_dir = OUT / f"mlp_{tag}"
    out_dir.mkdir(parents=True, exist_ok=True)
    best_path = out_dir / "best.pt"
    best = -1.0
    t0 = time.time()

    for ep in range(1, epochs + 1):
        model.train()
        run_loss, seen = 0.0, 0
        for x, y in tr_loader:
            x, y = x.to(device), y.to(device)
            optimizer.zero_grad()
            logits = model(x)
            loss = criterion(logits, y)
            loss.backward()
            optimizer.step()
            run_loss += loss.item() * y.size(0)
            seen += y.size(0)
        tr_loss = run_loss / max(seen, 1)
        va_loss, va_acc, _, _ = evaluate(model, va_loader, criterion, device)
        print(f"[{tag} ep {ep:02d}] train_loss={tr_loss:.4f} val_acc={va_acc:.4f}", flush=True)
        if va_acc > best:
            best = va_acc
            save_checkpoint(
                best_path,
                {
                    "state_dict": model.state_dict(),
                    "model": "gesture_mlp",
                    "input_dim": input_dim,
                    "num_classes": num_classes,
                    "hidden_dims": list(hidden),
                    "dropout": float(tcfg.get("dropout", 0.2)),
                    "class_names": labels,
                },
            )

    state = load_checkpoint(best_path, map_location=device)
    model.load_state_dict(state["state_dict"])
    te_loss, te_acc, y_true, y_pred = evaluate(model, te_loader, criterion, device)
    cm = confusion_matrix(num_classes, y_true, y_pred)
    pcm = per_class_metrics(cm, labels)

    recalls = {k: v["recall"] for k, v in pcm.items()}
    f1s = {k: v["f1"] for k, v in pcm.items()}
    macro_recall = float(np.mean(list(recalls.values())))
    macro_f1 = float(np.mean(list(f1s.values())))
    worst_recall_cls = min(recalls, key=recalls.get)
    worst_f1_cls = min(f1s, key=f1s.get)

    summary = {
        "weighted": weighted,
        "best_val_acc": best,
        "test_acc": te_acc,
        "test_loss": te_loss,
        "macro_recall": macro_recall,
        "macro_f1": macro_f1,
        "worst_recall_class": worst_recall_cls,
        "worst_recall": recalls[worst_recall_cls],
        "worst_f1_class": worst_f1_cls,
        "worst_f1": f1s[worst_f1_cls],
        "per_class_metrics": pcm,
        "elapsed_sec": time.time() - t0,
        "epochs": epochs,
    }
    (out_dir / "train_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return summary


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=30)
    ap.add_argument("--only", choices=("unweighted", "weighted", "both"), default="unweighted")
    args = ap.parse_args()

    weighted_path = GR / "artifacts" / "mlp" / "train_summary.json"
    results: dict = {"existing_weighted": json.loads(weighted_path.read_text(encoding="utf-8"))}

    if args.only in ("unweighted", "both"):
        results["unweighted_run"] = train_one(weighted=False, epochs=args.epochs)
    if args.only in ("weighted", "both"):
        results["weighted_run"] = train_one(weighted=True, epochs=args.epochs)

    OUT.mkdir(parents=True, exist_ok=True)
    out_json = OUT / "gesture_class_weight_ablation.json"
    out_json.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {out_json}", flush=True)


if __name__ == "__main__":
    main()
