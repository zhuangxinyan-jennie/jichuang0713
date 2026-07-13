#!/usr/bin/env python3
import argparse
import json
import queue
import re
import shutil
import subprocess
import sys
import threading
import time
import types
from pathlib import Path

import soundfile as sf

from cosyvoice_reference_clone import (
    DEFAULT_MODEL_DIR,
    configure_runtime_env,
    disable_transformers_deepspeed_probe,
    ensure_cosyvoice_import,
    load_preset,
    register_cosyvoice_vllm,
    resolve_path,
)


class SoundDeviceStreamPlayer:
    def __init__(self, sample_rate: int):
        import queue

        import numpy as np
        import sounddevice as sd

        self.sd = sd
        self.np = np
        self.queue = queue.Queue()
        self.current = np.empty(0, dtype="float32")
        self.offset = 0
        self.stream = sd.OutputStream(
            samplerate=sample_rate,
            channels=1,
            dtype="float32",
            callback=self._callback,
        )
        self.stream.start()

    def _callback(self, outdata, frames, time_info, status):
        outdata.fill(0)
        filled = 0
        while filled < frames:
            if self.offset >= len(self.current):
                if len(self.current) > 0:
                    self.queue.task_done()
                try:
                    self.current = self.queue.get_nowait()
                except Exception:
                    self.current = self.np.empty(0, dtype="float32")
                    self.offset = 0
                    break
                self.offset = 0
            available = len(self.current) - self.offset
            if available <= 0:
                continue
            take = min(frames - filled, available)
            outdata[filled : filled + take, 0] = self.current[self.offset : self.offset + take]
            self.offset += take
            filled += take

    def write(self, speech) -> None:
        import numpy as np

        audio = speech.squeeze(0).detach().cpu().numpy().astype("float32")
        self.queue.put(np.ascontiguousarray(audio))

    def close(self) -> None:
        self.queue.join()
        while self.offset < len(self.current):
            self.sd.sleep(20)
        self.stream.stop()
        self.stream.close()


def build_model(args, preset):
    use_accelerated_backend = args.fp16 or args.load_jit or args.load_trt or args.load_vllm
    configure_runtime_env(force_cpu=not use_accelerated_backend)
    disable_transformers_deepspeed_probe()
    ensure_cosyvoice_import(args.cosyvoice_repo)
    if args.load_vllm:
        register_cosyvoice_vllm()

    from cosyvoice.cli.cosyvoice import AutoModel

    model_dir = args.model_dir or preset.get("model_dir") or DEFAULT_MODEL_DIR
    started = time.perf_counter()
    model_kwargs = {
        "model_dir": model_dir,
        "load_jit": args.load_jit,
        "load_trt": args.load_trt,
        "load_vllm": args.load_vllm,
        "fp16": args.fp16,
        "trt_concurrent": args.trt_concurrent,
    }
    model = AutoModel(**model_kwargs)
    model.model.clear_cuda_cache_after_tts = args.clear_cuda_cache_after_tts
    model.model.stream_poll_interval = args.stream_poll_interval
    model.model.flow.inference_n_timesteps = args.flow_steps
    if args.stream_token_hop_len is not None:
        model.model.token_hop_len = args.stream_token_hop_len
        model.model.token_max_hop_len = max(args.stream_token_hop_len, args.stream_token_max_hop_len)
    model.model._repl_initial_token_hop_len = getattr(model.model, "token_hop_len", None)
    model.model._repl_initial_token_max_hop_len = getattr(model.model, "token_max_hop_len", None)
    try:
        import torch

        device_info = {
            "cuda_available": torch.cuda.is_available(),
            "device": getattr(model.model, "device", None).type if getattr(model, "model", None) is not None else None,
            "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        }
    except Exception as exc:
        device_info = {"device_probe_error": str(exc)}
    print(
        json.dumps(
            {"event": "model_loaded", "seconds": time.perf_counter() - started, **device_info},
            ensure_ascii=False,
        ),
        flush=True,
    )
    install_profile_hooks(model)
    return model


def install_profile_hooks(model) -> None:
    backend = model.model
    if getattr(backend, "_repl_profile_hooks_installed", False):
        return

    backend._repl_profile_events = []
    backend._repl_profile_lock = threading.Lock()

    def record_event(name, seconds, **extra):
        with backend._repl_profile_lock:
            backend._repl_profile_events.append({"name": name, "seconds": seconds, **extra})

    original_frontend_zero_shot = model.frontend.frontend_zero_shot

    def frontend_zero_shot_wrapper(*args, **kwargs):
        started = time.perf_counter()
        result = original_frontend_zero_shot(*args, **kwargs)
        record_event("frontend_zero_shot", time.perf_counter() - started)
        return result

    model.frontend.frontend_zero_shot = frontend_zero_shot_wrapper

    original_llm_job = backend.llm_job

    def llm_job_wrapper(self, *args, **kwargs):
        request_id = args[-1] if args else kwargs.get("uuid")
        started = time.perf_counter()
        try:
            return original_llm_job(*args, **kwargs)
        finally:
            token_count = len(self.tts_speech_token_dict.get(request_id, [])) if request_id else None
            record_event("llm_job", time.perf_counter() - started, tokens=token_count)

    backend.llm_job = types.MethodType(llm_job_wrapper, backend)

    original_token2wav = backend.token2wav

    def token2wav_wrapper(self, *args, **kwargs):
        started = time.perf_counter()
        result = original_token2wav(*args, **kwargs)
        record_event("token2wav", time.perf_counter() - started)
        return result

    backend.token2wav = types.MethodType(token2wav_wrapper, backend)
    backend._repl_profile_hooks_installed = True


def reset_profile_events(model) -> None:
    backend = model.model
    if hasattr(backend, "_repl_profile_events"):
        with backend._repl_profile_lock:
            backend._repl_profile_events = []


def get_profile_events(model) -> list[dict]:
    backend = model.model
    if not hasattr(backend, "_repl_profile_events"):
        return []
    with backend._repl_profile_lock:
        return list(backend._repl_profile_events)


def reset_stream_hop(model) -> None:
    backend = model.model
    initial_hop = getattr(backend, "_repl_initial_token_hop_len", None)
    initial_max_hop = getattr(backend, "_repl_initial_token_max_hop_len", None)
    if initial_hop is not None and hasattr(backend, "token_hop_len"):
        backend.token_hop_len = initial_hop
    if initial_max_hop is not None and hasattr(backend, "token_max_hop_len"):
        backend.token_max_hop_len = initial_max_hop


def start_stream_player(sample_rate: int):
    aplay = shutil.which("aplay")
    if aplay:
        return subprocess.Popen(
            [aplay, "-q", "-t", "raw", "-f", "S16_LE", "-r", str(sample_rate), "-c", "1"],
            stdin=subprocess.PIPE,
        )
    if sys.platform == "win32":
        try:
            return SoundDeviceStreamPlayer(sample_rate)
        except Exception as exc:
            print(
                json.dumps(
                    {"event": "stream_play_unavailable", "reason": str(exc)},
                    ensure_ascii=False,
                ),
                flush=True,
            )
    return None


def write_stream_audio(process, speech) -> None:
    if process is None:
        return
    if hasattr(process, "write"):
        process.write(speech)
        return
    if process.stdin is None:
        return
    import numpy as np

    audio = speech.squeeze(0).detach().cpu().numpy()
    pcm = (np.clip(audio, -1.0, 1.0) * 32767.0).astype("<i2")
    process.stdin.write(pcm.tobytes())
    process.stdin.flush()


def close_stream_player(process) -> None:
    if process is None:
        return
    if hasattr(process, "close"):
        process.close()
        return
    if process.stdin is not None:
        process.stdin.close()
    process.wait()


def synthesize(
    model,
    text,
    output_path,
    ref_text,
    ref_audio,
    spk_id,
    cached_spk,
    speed,
    stream,
    text_frontend,
    profile,
    stream_play,
    stream_player=None,
    on_stream_audio_seconds=None,
):
    reset_profile_events(model)
    if stream:
        reset_stream_hop(model)
    started = time.perf_counter()
    first_chunk_seconds = None
    if cached_spk:
        result_iter = model.inference_zero_shot(
            text,
            "",
            "",
            zero_shot_spk_id=spk_id,
            stream=stream,
            speed=speed,
            text_frontend=text_frontend,
        )
    else:
        result_iter = model.inference_zero_shot(
            text,
            ref_text,
            ref_audio,
            stream=stream,
            speed=speed,
            text_frontend=text_frontend,
        )
    chunks = []
    owns_stream_player = False
    if stream_play and stream_player is None:
        stream_player = start_stream_player(model.sample_rate)
        owns_stream_player = True
    import torch

    try:
        streamed_audio_seconds = 0.0
        for result in result_iter:
            if first_chunk_seconds is None:
                first_chunk_seconds = time.perf_counter() - started
            if "tts_speech" not in result:
                continue
            speech = result["tts_speech"]
            if not isinstance(speech, torch.Tensor):
                speech = torch.as_tensor(speech)
            if speech.dim() == 1:
                speech = speech.unsqueeze(0)
            speech = speech.cpu()
            chunks.append(speech)
            streamed_audio_seconds += speech.shape[1] / model.sample_rate
            if stream_play:
                write_stream_audio(stream_player, speech)
            if on_stream_audio_seconds is not None:
                on_stream_audio_seconds(streamed_audio_seconds)
    finally:
        if owns_stream_player:
            close_stream_player(stream_player)

    if not chunks:
        raise RuntimeError("CosyVoice did not return a tts_speech result.")
    speech = torch.cat(chunks, dim=1).squeeze(0).numpy()
    sf.write(str(output_path), speech, model.sample_rate)
    wall_seconds = time.perf_counter() - started
    info = sf.info(str(output_path))
    audio_seconds = info.frames / info.samplerate
    result = {
        "event": "generated",
        "text": text,
        "output": str(output_path),
        "wall_seconds": wall_seconds,
        "first_chunk_seconds": first_chunk_seconds,
        "audio_seconds": audio_seconds,
        "rtf": wall_seconds / audio_seconds if audio_seconds else None,
        "cached_spk": cached_spk,
        "stream": stream,
        "stream_play": stream_play,
    }
    if profile:
        result["profile"] = get_profile_events(model)
    return result


def split_text_units(text: str, min_chars: int) -> list[str]:
    parts = [m.group(0).strip() for m in re.finditer(r"[^。！？!?；;\r\n]+[。！？!?；;]*", text)]
    parts = [part for part in parts if part]
    if len(parts) <= 1:
        return parts or [text]

    units = []
    current = ""
    for part in parts:
        current += part
        if len(current) >= min_chars:
            units.append(current)
            current = ""
    if current:
        if units and len(current) < min_chars:
            units[-1] += current
        else:
            units.append(current)
    return units or [text]


def split_text_by_punctuation(text: str) -> list[str]:
    parts = [m.group(0).strip() for m in re.finditer(r"[^，,。！？!?；;\r\n]+[，,。！？!?；;]*", text)]
    return [part for part in parts if part] or [text]


def find_player(preferred_player: str | None) -> list[str] | None:
    def command_for_player(player: str, extra_args: list[str] | None = None) -> list[str]:
        name = Path(player).name.lower()
        if name in {"ffplay", "ffplay.exe"}:
            return [player, "-nodisp", "-autoexit", "-loglevel", "error"]
        return [player, *(extra_args or [])]

    if preferred_player:
        player = shutil.which(preferred_player)
        if player:
            return command_for_player(player)
        raise SystemExit(f"Audio player not found: {preferred_player}")

    for name, args in (
        ("paplay", []),
        ("aplay", ["-q"]),
        ("ffplay", ["-nodisp", "-autoexit", "-loglevel", "error"]),
    ):
        player = shutil.which(name)
        if player:
            return command_for_player(player, args)
    if sys.platform == "win32":
        return ["python-winsound"]
    return None


def play_audio(path: Path, player_cmd: list[str] | None, async_play: bool) -> None:
    if player_cmd is None:
        print(json.dumps({"event": "play_skipped", "reason": "no audio player found"}, ensure_ascii=False), flush=True)
        return
    started = time.perf_counter()
    if player_cmd == ["python-winsound"]:
        import winsound

        winsound.PlaySound(str(path), winsound.SND_FILENAME)
        print(
            json.dumps(
                {
                    "event": "played",
                    "output": str(path),
                    "player": "winsound",
                    "returncode": 0,
                    "seconds": time.perf_counter() - started,
                },
                ensure_ascii=False,
            ),
            flush=True,
        )
        return
    if async_play:
        process = subprocess.Popen([*player_cmd, str(path)])
        print(
            json.dumps(
                {
                    "event": "play_started",
                    "output": str(path),
                    "player": Path(player_cmd[0]).name,
                    "pid": process.pid,
                },
                ensure_ascii=False,
            ),
            flush=True,
        )
        return

    completed = subprocess.run([*player_cmd, str(path)], check=False)
    print(
        json.dumps(
            {
                "event": "played",
                "output": str(path),
                "player": Path(player_cmd[0]).name,
                "returncode": completed.returncode,
                "seconds": time.perf_counter() - started,
            },
            ensure_ascii=False,
        ),
        flush=True,
    )


class QueuedAudioPlayer:
    def __init__(self, player_cmd: list[str] | None):
        self.player_cmd = player_cmd
        self.queue: queue.Queue[Path | None] = queue.Queue()
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _run(self) -> None:
        while True:
            path = self.queue.get()
            try:
                if path is None:
                    return
                play_audio(path, self.player_cmd, async_play=False)
            finally:
                self.queue.task_done()

    def play(self, path: Path) -> None:
        self.queue.put(path)

    def close(self) -> None:
        self.queue.join()
        self.queue.put(None)
        self.thread.join()


def iter_input_lines(input_file):
    source = sys.stdin if input_file == "-" else open(input_file, "r", encoding="utf-8")
    try:
        for line in source:
            text = line.strip()
            if not text:
                continue
            if text in {":q", ":quit", "exit", "quit"}:
                break
            yield text
    finally:
        if source is not sys.stdin:
            source.close()


def iter_interactive_lines(prompt: str):
    while True:
        try:
            text = input(prompt).strip()
        except EOFError:
            break
        if not text:
            continue
        if text in {":q", ":quit", "exit", "quit"}:
            break
        yield text


def main() -> int:
    parser = argparse.ArgumentParser(description="Keep CosyVoice loaded and synthesize local stdin lines.")
    parser.add_argument("--preset", default="scripts/presets/xiongda_fish_cosyvoice.json")
    parser.add_argument("--model-dir")
    parser.add_argument("--cosyvoice-repo", default="third_party/CosyVoice")
    parser.add_argument("--ref-audio")
    parser.add_argument("--ref-text")
    parser.add_argument("--spk-id", default="xiongda_cached")
    parser.add_argument("--no-cache-spk", action="store_true")
    parser.add_argument("--save-spk-cache", action="store_true", help="Persist cached speaker info into model_dir/spk2info.pt.")
    parser.add_argument("--input-file", default="-", help="Text file with one utterance per line, or '-' for stdin.")
    parser.add_argument("--interactive", action="store_true", help="Show an input prompt and synthesize one line at a time.")
    parser.add_argument("--output-dir", default="outputs/cosyvoice_repl")
    parser.add_argument("--prefix", default="utt")
    parser.add_argument("--start-index", type=int, default=0)
    parser.add_argument("--stream", action="store_true")
    parser.add_argument("--stream-play", action="store_true", help="Play streaming chunks as soon as CosyVoice yields them. Implies --stream.")
    parser.add_argument("--low-latency", action="store_true", help="Minimize text-to-first-audio latency. Implies --stream-play and smaller stream chunks.")
    parser.add_argument("--profile", action="store_true", help="Print frontend/LLM/token2wav timing for each utterance.")
    parser.add_argument("--speed", type=float, default=1.0)
    parser.add_argument("--no-text-frontend", action="store_true")
    parser.add_argument("--fp16", action="store_true")
    parser.add_argument("--load-jit", action="store_true")
    parser.add_argument("--load-trt", action="store_true")
    parser.add_argument("--load-vllm", action="store_true")
    parser.add_argument("--trt-concurrent", type=int, default=1)
    parser.add_argument("--vllm-gpu-memory-utilization", type=float, default=0.7)
    parser.add_argument("--vllm-max-num-seqs", type=int, default=1)
    parser.add_argument("--vllm-enforce-eager", action="store_true")
    parser.add_argument("--clear-cuda-cache-after-tts", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--stream-poll-interval", type=float, default=0.02)
    parser.add_argument("--stream-token-hop-len", type=int)
    parser.add_argument("--stream-token-max-hop-len", type=int, default=100)
    parser.add_argument("--flow-steps", type=int, default=10)
    parser.add_argument("--split-punctuation", action="store_true", help="Split text at commas and sentence-ending punctuation without min-length merging.")
    parser.add_argument("--split-sentences", action=argparse.BooleanOptionalAction, default=False, help="Split long input into sentence-sized units and synthesize them in sequence.")
    parser.add_argument("--split-min-chars", type=int, default=16, help="Minimum characters to keep each split unit from becoming too tiny.")
    parser.add_argument("--play", action=argparse.BooleanOptionalAction, default=True, help="Play each generated wav.")
    parser.add_argument("--queued-playback", action="store_true", help="Play completed wav segments in a background queue while generating later segments.")
    parser.add_argument("--hybrid-playback", action="store_true", help="Stream-play the first segment, then queue later generated wav segments.")
    parser.add_argument("--hybrid-prefetch-after-seconds", type=float, default=2.0, help="In hybrid playback, start generating later segments after this much first-segment audio has been produced.")
    parser.add_argument("--player", help="Audio player command name, e.g. paplay, aplay, or ffplay.")
    parser.add_argument("--async-play", action="store_true", help="Start playback in the background.")
    args = parser.parse_args()
    if args.low_latency:
        args.stream_play = True
        if args.stream_token_hop_len is None:
            args.stream_token_hop_len = 12
        args.flow_steps = min(args.flow_steps, 6)
        args.stream_poll_interval = min(args.stream_poll_interval, 0.01)
    if args.stream_play:
        args.stream = True
    if args.queued_playback:
        args.play = True
        args.stream_play = False
    if args.hybrid_playback:
        args.play = True
        args.stream = True
        args.stream_play = False
        args.split_sentences = True

    repo_root = Path(__file__).resolve().parent.parent
    preset = load_preset(Path(args.preset))
    ref_audio = resolve_path(args.ref_audio or preset["ref_audio"], repo_root)
    ref_text = args.ref_text or preset["ref_text"]
    output_dir = Path(args.output_dir).expanduser()
    if not output_dir.is_absolute():
        output_dir = repo_root / output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    print(json.dumps({"event": "loading_model"}, ensure_ascii=False), flush=True)
    model = build_model(args, preset)

    cached_spk = False
    if not args.no_cache_spk:
        if args.spk_id in model.frontend.spk2info:
            cached_spk = True
            print(json.dumps({"event": "speaker_cache_loaded", "spk_id": args.spk_id}, ensure_ascii=False), flush=True)
        else:
            print(json.dumps({"event": "caching_speaker", "spk_id": args.spk_id}, ensure_ascii=False), flush=True)
            started = time.perf_counter()
            model.add_zero_shot_spk(ref_text, ref_audio, args.spk_id)
            cached_spk = True
            print(json.dumps({"event": "speaker_cached", "seconds": time.perf_counter() - started}, ensure_ascii=False), flush=True)
            if args.save_spk_cache:
                model.save_spkinfo()
                print(json.dumps({"event": "speaker_cache_saved", "spk_id": args.spk_id}, ensure_ascii=False), flush=True)

    player_cmd = find_player(args.player) if args.play else None
    if args.interactive:
        print("CosyVoice ready. 输入文本后回车生成并播放；输入 :q 退出。", flush=True)
        line_iter = iter_interactive_lines("> ")
    else:
        print(json.dumps({"event": "ready", "input": args.input_file}, ensure_ascii=False), flush=True)
        line_iter = iter_input_lines(args.input_file)

    shared_stream_player = start_stream_player(model.sample_rate) if args.stream_play else None
    queued_player = QueuedAudioPlayer(player_cmd) if args.queued_playback else None
    try:
        for offset, text in enumerate(line_iter, start=args.start_index):
            if args.split_punctuation:
                parts = split_text_by_punctuation(text)
            elif args.split_sentences:
                parts = split_text_units(text, args.split_min_chars)
            else:
                parts = [text]
            if args.hybrid_playback:
                tail_parts = parts[1:]
                background_queue: queue.Queue[tuple[str, object, Path | None]] = queue.Queue()
                background_started = threading.Event()

                def generate_later_segments() -> None:
                    try:
                        for later_index, later_text in enumerate(tail_parts, start=1):
                            later_output = output_dir / f"{args.prefix}_{offset:04d}_{later_index:02d}.wav"
                            later_result = synthesize(
                                model,
                                later_text,
                                later_output,
                                ref_text,
                                ref_audio,
                                args.spk_id,
                                cached_spk,
                                args.speed,
                                False,
                                not args.no_text_frontend,
                                False,
                                False,
                            )
                            later_result["source_text"] = text
                            later_result["segment_index"] = later_index
                            later_result["segment_count"] = len(tail_parts) + 1
                            background_queue.put(("result", later_result, later_output))
                        background_queue.put(("done", None, None))
                    except Exception as exc:
                        background_queue.put(("error", exc, None))

                background_thread = threading.Thread(target=generate_later_segments, daemon=True)

                def start_background_generation() -> None:
                    if not background_started.is_set():
                        background_started.set()
                        background_thread.start()

                def maybe_start_background_generation(streamed_audio_seconds: float) -> None:
                    if tail_parts and streamed_audio_seconds >= args.hybrid_prefetch_after_seconds:
                        start_background_generation()

                first_output = output_dir / f"{args.prefix}_{offset:04d}_00.wav"
                first_result = synthesize(
                    model,
                    parts[0],
                    first_output,
                    ref_text,
                    ref_audio,
                    args.spk_id,
                    cached_spk,
                    args.speed,
                    True,
                    not args.no_text_frontend,
                    False,
                    True,
                    None,
                    maybe_start_background_generation,
                )
                first_result["source_text"] = text
                first_result["segment_index"] = 0
                first_result["segment_count"] = len(tail_parts) + 1
                print(json.dumps(first_result, ensure_ascii=False), flush=True)
                if tail_parts and not background_started.is_set():
                    start_background_generation()

                later_player = QueuedAudioPlayer(player_cmd) if args.play and tail_parts else None
                try:
                    remaining = len(tail_parts)
                    while remaining > 0:
                        kind, payload, output_path = background_queue.get()
                        if kind == "error":
                            raise payload
                        if kind == "done":
                            break
                        result = payload
                        print(json.dumps(result, ensure_ascii=False), flush=True)
                        if later_player is not None and output_path is not None:
                            later_player.play(output_path)
                        elif args.play and output_path is not None:
                            play_audio(output_path, player_cmd, args.async_play)
                        remaining -= 1
                finally:
                    if later_player is not None:
                        later_player.close()
                    if background_thread.is_alive():
                        background_thread.join()
                continue

            for part_index, part in enumerate(parts):
                output_path = output_dir / f"{args.prefix}_{offset:04d}_{part_index:02d}.wav" if len(parts) > 1 else output_dir / f"{args.prefix}_{offset:04d}.wav"
                result = synthesize(
                    model,
                    part,
                    output_path,
                    ref_text,
                    ref_audio,
                    args.spk_id,
                    cached_spk,
                    args.speed,
                    args.stream,
                    not args.no_text_frontend,
                    args.profile,
                    args.stream_play,
                    shared_stream_player,
                )
                result["source_text"] = text
                result["segment_index"] = part_index
                result["segment_count"] = len(parts)
                print(json.dumps(result, ensure_ascii=False), flush=True)
                if queued_player is not None:
                    queued_player.play(output_path)
                elif args.play and not args.stream_play:
                    play_audio(output_path, player_cmd, args.async_play)
    finally:
        if shared_stream_player is not None:
            close_stream_player(shared_stream_player)
        if queued_player is not None:
            queued_player.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
