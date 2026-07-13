from __future__ import annotations

import argparse
import sys
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT.parent))

from motion.temporal_models.holistic_stgcn import HolisticLiteSTGCN, NUM_NODES


def main() -> None:
    parser = argparse.ArgumentParser(description="Export HolisticLiteSTGCN to ONNX for ATC->OM.")
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--opset", type=int, default=11, help="Ascend ATC: prefer 11 or 12.")
    args = parser.parse_args()

    ckpt = torch.load(args.checkpoint, map_location="cpu", weights_only=False)
    class_names = ckpt.get("class_names", [])
    target_frames = int(ckpt.get("target_frames", 48))
    in_channels = int(ckpt.get("input_channels", 10))
    channels = tuple(int(x) for x in ckpt.get("channels", [32, 64, 64, 128]))
    temporal_kernel = int(ckpt.get("temporal_kernel", 9))
    dropout = float(ckpt.get("dropout", 0.3))

    model = HolisticLiteSTGCN(
        in_channels=in_channels,
        num_classes=len(class_names),
        channels=channels,
        num_nodes=int(ckpt.get("num_nodes", NUM_NODES)),
        temporal_kernel=temporal_kernel,
        dropout=0.0,  # export/infer without dropout randomness
    )
    model.load_state_dict(ckpt["state_dict"])
    model.eval()

    dummy = torch.zeros((1, in_channels, target_frames, NUM_NODES), dtype=torch.float32)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    torch.onnx.export(
        model,
        dummy,
        str(args.output),
        input_names=["features"],
        output_names=["logits"],
        opset_version=args.opset,
        do_constant_folding=True,
        dynamo=False,
    )
    print(f"[DONE] {args.output}")
    print(f"  input: [1,{in_channels},{target_frames},{NUM_NODES}]")
    print(f"  classes: {class_names}")
    print("  next: atc --model=... --framework=5 --output=action_stgcn --input_shape=\"features:1,10,48,75\" --soc_version=Ascend310B4")


if __name__ == "__main__":
    main()
