#!/usr/bin/env python3
import argparse
import json
import os
import sys
from pathlib import Path

import soundfile as sf


def configure_runtime_env(force_cpu: bool = True) -> None:
    os.environ.setdefault("NUMBA_DISABLE_JIT", "1")
    os.environ.setdefault("NUMBA_CACHE_DIR", "/tmp/numba_cache")
    os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")
    os.environ.setdefault("TRITON_CACHE_DIR", "/tmp/triton_cache")
    os.environ.setdefault("XDG_CACHE_HOME", "/tmp/xdg_cache")
    os.environ.setdefault("HOME", "/tmp")
    os.environ.setdefault("VLLM_NO_USAGE_STATS", "1")
    os.environ.setdefault("VLLM_DO_NOT_TRACK", "1")
    if force_cpu:
        os.environ.setdefault("DS_ACCELERATOR", "cpu")


def disable_transformers_deepspeed_probe() -> None:
    try:
        import transformers.integrations.deepspeed as hf_deepspeed
    except Exception:
        return
    hf_deepspeed.is_deepspeed_available = lambda: False


def register_cosyvoice_vllm() -> None:
    try:
        from vllm import ModelRegistry
        from cosyvoice.vllm.cosyvoice2 import CosyVoice2ForCausalLM
    except ModuleNotFoundError as exc:
        raise SystemExit(
            "vLLM is not installed. Install a CosyVoice-supported vLLM version before using --load-vllm."
        ) from exc
    ModelRegistry.register_model("CosyVoice2ForCausalLM", CosyVoice2ForCausalLM)


def load_preset(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def resolve_path(path: str, repo_root: Path) -> str:
    expanded = Path(path).expanduser()
    if expanded.is_absolute():
        return str(expanded)
    return str((repo_root / expanded).resolve())


def ensure_cosyvoice_import(cosyvoice_repo: str | None) -> None:
    if cosyvoice_repo:
        sys.path.insert(0, str(Path(cosyvoice_repo).expanduser().resolve()))
        third_party = Path(cosyvoice_repo).expanduser().resolve() / "third_party" / "Matcha-TTS"
        if third_party.exists():
            sys.path.insert(0, str(third_party))

    try:
        import cosyvoice  # noqa: F401
    except ModuleNotFoundError as exc:
        raise SystemExit(
            "CosyVoice is not importable. Install CosyVoice or pass "
            "--cosyvoice-repo /path/to/CosyVoice. The GPT-SoVITS weights in this "
            "repo cannot be loaded directly by CosyVoice."
        ) from exc


DEFAULT_MODEL_DIR = "iic/CosyVoice2-0.5B"


def save_results(result_iter, output_path: Path, sample_rate: int) -> None:
    import torch

    chunks = []
    for result in result_iter:
        if "tts_speech" not in result:
            continue
        speech = result["tts_speech"]
        if not isinstance(speech, torch.Tensor):
            speech = torch.as_tensor(speech)
        if speech.dim() == 1:
            speech = speech.unsqueeze(0)
        chunks.append(speech.cpu())
    if not chunks:
        raise RuntimeError("CosyVoice did not return a tts_speech result.")
    speech = torch.cat(chunks, dim=1).squeeze(0).numpy()
    sf.write(str(output_path), speech, sample_rate)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run CosyVoice zero-shot reference cloning with a saved preset."
    )
    parser.add_argument("--preset", required=True, help="Path to preset JSON.")
    parser.add_argument("--text", required=True, help="Target text to synthesize.")
    parser.add_argument("--output", required=True, help="Output wav path.")
    parser.add_argument(
        "--model-dir",
        help="CosyVoice model directory or model id. Defaults to preset model_dir, COSYVOICE_MODEL_DIR, or iic/CosyVoice2-0.5B.",
    )
    parser.add_argument(
        "--cosyvoice-repo",
        default=os.environ.get("COSYVOICE_REPO"),
        help="Path to a local CosyVoice repository if the cosyvoice package is not installed.",
    )
    parser.add_argument("--ref-audio", help="Override reference audio path.")
    parser.add_argument("--ref-text", help="Override reference text.")
    parser.add_argument("--stream", action="store_true", help="Use CosyVoice streaming inference.")
    parser.add_argument("--fp16", action="store_true", help="Enable CosyVoice fp16 inference when supported.")
    parser.add_argument("--load-jit", action="store_true", help="Load exported TorchScript modules when available.")
    parser.add_argument("--load-trt", action="store_true", help="Use TensorRT for the flow decoder estimator.")
    parser.add_argument("--load-vllm", action="store_true", help="Use vLLM for the CosyVoice2 LLM backend.")
    parser.add_argument("--trt-concurrent", type=int, default=1, help="TensorRT concurrent context count.")
    parser.add_argument("--vllm-gpu-memory-utilization", type=float, default=0.7, help="Fraction of GPU memory vLLM may use.")
    parser.add_argument("--vllm-max-num-seqs", type=int, default=1, help="Maximum concurrent vLLM requests.")
    parser.add_argument("--vllm-enforce-eager", action="store_true", help="Disable vLLM CUDA graph capture.")
    parser.add_argument("--speed", type=float, default=1.0, help="CosyVoice speaking speed.")
    parser.add_argument(
        "--no-text-frontend",
        action="store_true",
        help="Disable CosyVoice text frontend normalization.",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent.parent
    use_accelerated_backend = args.fp16 or args.load_jit or args.load_trt or args.load_vllm
    configure_runtime_env(force_cpu=not use_accelerated_backend)
    disable_transformers_deepspeed_probe()
    preset = load_preset(Path(args.preset))
    model_dir = args.model_dir or preset.get("model_dir") or os.environ.get("COSYVOICE_MODEL_DIR") or DEFAULT_MODEL_DIR
    output_path = Path(args.output).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    ensure_cosyvoice_import(args.cosyvoice_repo)
    if args.load_vllm:
        register_cosyvoice_vllm()

    from cosyvoice.cli.cosyvoice import AutoModel

    ref_audio = resolve_path(args.ref_audio or preset["ref_audio"], repo_root)
    ref_text = args.ref_text or preset["ref_text"]

    model_kwargs = {
        "model_dir": model_dir,
        "load_jit": args.load_jit,
        "load_trt": args.load_trt,
        "load_vllm": args.load_vllm,
        "fp16": args.fp16,
        "trt_concurrent": args.trt_concurrent,
    }
    cosyvoice = AutoModel(**model_kwargs)
    result_iter = cosyvoice.inference_zero_shot(
        args.text,
        ref_text,
        ref_audio,
        stream=args.stream,
        speed=args.speed,
        text_frontend=not args.no_text_frontend,
    )
    save_results(result_iter, output_path, cosyvoice.sample_rate)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
