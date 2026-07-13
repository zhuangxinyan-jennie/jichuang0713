/**
 * 熊大语音：优先请求 cosyvoice_live_release 的 `tts_server.py`（CosyVoice），
 * 失败则回退浏览器 SpeechSynthesis（与原益智小剧场一致）。
 *
 * 环境变量：
 * - `VITE_XIONGDA_TTS_URL`（默认 http://127.0.0.1:9890）
 * - `VITE_XIONGDA_TTS_DEVICE`：可选 `cpu` | `cuda`，写入 POST body，便于无显卡时合成
 * - `VITE_XIONGDA_TTS_STREAM_DISABLED=1`：禁用 CosyVoice 流式播放，回到完整 WAV
 * - `VITE_XIONGDA_TTS_SERVER_PLAY=1`：启用服务端 sounddevice 直接播放（延迟最优，
 *   要求 TTS 服务在本机；前端通过 /api/tts-play 阻塞等待播完后再触发 onEnded）
 *
 * 浏览器长时间 await 合成后会丢掉「用户手势」，导致 `audio.play()` 被拒。
 * 请在**同一次点击**里先调用 `prepareBearAudioPlayback()`（再发 Agent / 再等 TTS）。
 */
import { createTtsLatencyProbe } from "./ttsLatencyProbe";

const DEFAULT_TTS_BASE = "http://127.0.0.1:9890";
const FETCH_TIMEOUT_MS = 180_000;

/** 极短静音 WAV，用于在同一 `<audio>` 上解锁自动播放策略 */
const SILENT_WAV =
  "data:audio/wav;base64,UklGRigAAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQQAAAAAAA==";

let sharedAudio: HTMLAudioElement | null = null;
let sharedAudioContext: AudioContext | null = null;
let currentTtsAbortController: AbortController | null = null;
let currentObjectUrl: string | null = null;
let currentPlaybackFinish: (() => void) | null = null;

/** 打断在线 TTS blob 播放与「预烘焙 WAV 队列」共用同一代号 */
let playbackSession = 0;

function notifyPlaybackActuallyStarted(): void {
  void import("../bear_pipeline/handleBearAgentPayload")
    .then((m) => m.notifyPlaybackStart())
    .catch(() => {
      /* ignore */
    });
}

function getSharedAudio(): HTMLAudioElement {
  if (typeof window === "undefined") {
    throw new Error("no window");
  }
  if (!sharedAudio) {
    sharedAudio = new Audio();
    sharedAudio.preload = "auto";
    sharedAudio.setAttribute("playsInline", "true");
  }
  return sharedAudio;
}

function getSharedAudioContext(): AudioContext {
  const AudioContextCtor =
    window.AudioContext ||
    (window as Window & { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
  if (!AudioContextCtor) {
    throw new Error("AudioContext is not supported");
  }
  if (!sharedAudioContext || sharedAudioContext.state === "closed") {
    sharedAudioContext = new AudioContextCtor();
  }
  return sharedAudioContext;
}

function revokeCurrentUrl(): void {
  if (currentObjectUrl) {
    URL.revokeObjectURL(currentObjectUrl);
    currentObjectUrl = null;
  }
}

function resolveCurrentPlayback(): void {
  const cb = currentPlaybackFinish;
  currentPlaybackFinish = null;
  cb?.();
}

/** 停止 CosyVoice 播放与浏览器 TTS */
export function stopBearSpeech(): void {
  if (typeof window === "undefined") return;
  resolveCurrentPlayback();
  playbackSession += 1;
  try {
    window.speechSynthesis?.cancel();
  } catch {
    /* ignore */
  }
  try {
    currentTtsAbortController?.abort();
    currentTtsAbortController = null;
  } catch {
    /* ignore */
  }
  revokeCurrentUrl();
  try {
    const a = sharedAudio;
    if (a) {
      a.onended = null;
      a.onerror = null;
      a.pause();
      a.volume = 1;
      a.removeAttribute("src");
      a.load();
    }
  } catch {
    /* ignore */
  }
  try {
    void sharedAudioContext?.close();
    sharedAudioContext = null;
  } catch {
    /* ignore */
  }
}

/**
 * 在用户点击（同一同步调用栈）里调用一次，解锁后续长时间异步合成完的 `audio.play()`。
 */
export function prepareBearAudioPlayback(): void {
  if (typeof window === "undefined") return;
  try {
    const p = getSharedAudio();
    const unlockSession = playbackSession;
    revokeCurrentUrl();
    p.pause();
    p.volume = 0;
    p.src = SILENT_WAV;
    void p
      .play()
      .then(() => {
        p.volume = 1;
        if (unlockSession !== playbackSession) return;
        p.pause();
        p.removeAttribute("src");
        p.load();
      })
      .catch(() => {
        p.volume = 1;
      });
  } catch {
    /* ignore */
  }
  try {
    void getSharedAudioContext().resume();
  } catch {
    /* ignore */
  }
}

/** 浏览器原生朗读（不受多数环境下的音频 autoplay 策略限制，适合剧情固定台词兜底） */
export function speakBrowserFallback(text: string, onEnded?: () => void): void {
  if (typeof window === "undefined" || !window.speechSynthesis) {
    onEnded?.();
    return;
  }
  try {
    window.speechSynthesis.cancel();
    notifyPlaybackActuallyStarted();
    let finished = false;
    const finish = () => {
      if (finished) return;
      finished = true;
      window.clearTimeout(fallbackTid);
      onEnded?.();
    };
    const fallbackTid = window.setTimeout(
      finish,
      Math.min(45_000, Math.max(6_000, text.length * 450))
    );
    const u = new SpeechSynthesisUtterance(text.replace(/\n+/g, " "));
    u.lang = "zh-CN";
    u.rate = 1;
    u.onend = finish;
    u.onerror = finish;
    window.speechSynthesis.speak(u);
  } catch {
    onEnded?.();
  }
}

function ttsBaseUrl(): string {
  const raw = (import.meta.env.VITE_XIONGDA_TTS_URL as string | undefined)?.trim();
  return (raw || DEFAULT_TTS_BASE).replace(/\/$/, "");
}

function ttsDeviceBody(): Record<string, string> {
  const raw = (import.meta.env.VITE_XIONGDA_TTS_DEVICE as string | undefined)?.trim().toLowerCase();
  if (raw === "cpu" || raw === "cuda") {
    return { device: raw };
  }
  return {};
}

function streamingTtsEnabled(): boolean {
  const raw = (import.meta.env.VITE_XIONGDA_TTS_STREAM_DISABLED as string | undefined)?.trim().toLowerCase();
  return raw !== "1" && raw !== "true";
}

function serverPlayEnabled(): boolean {
  const raw = (import.meta.env.VITE_XIONGDA_TTS_SERVER_PLAY as string | undefined)?.trim().toLowerCase();
  return raw === "1" || raw === "true";
}

type StreamPlayResult = "ended" | "unsupported" | "http_error" | "stream_error" | "partial_error" | "stale";

function base64ToBytes(b64: string): Uint8Array {
  const bin = atob(b64);
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  return bytes;
}

function pcm16ToAudioBuffer(ctx: AudioContext, bytes: Uint8Array, sampleRate: number): AudioBuffer {
  const frames = Math.floor(bytes.byteLength / 2);
  const buffer = ctx.createBuffer(1, frames, sampleRate);
  const out = buffer.getChannelData(0);
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  for (let i = 0; i < frames; i++) {
    out[i] = Math.max(-1, view.getInt16(i * 2, true) / 32768);
  }
  return buffer;
}

async function playServerSideTts(
  text: string,
  controller: AbortController,
  probe: ReturnType<typeof createTtsLatencyProbe>
): Promise<"ended" | "http_error" | "unsupported"> {
  if (!serverPlayEnabled()) return "unsupported";

  const body = { text, ...ttsDeviceBody() };
  probe?.mark("server_play_fetch_start");
  try {
    const res = await fetch(`${ttsBaseUrl()}/api/tts-play`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal: controller.signal,
    });
    probe?.mark("server_play_response", { ok: res.ok, status: res.status });
    if (!res.ok) return "http_error";

    const result = await res.json();
    probe?.mark("server_play_completed", {
      segments: result.segments,
      audio_seconds: result.audio_seconds,
      first_chunk_seconds: result.first_chunk_seconds,
    });
    notifyPlaybackActuallyStarted();
    return "ended";
  } catch (e) {
    if (controller.signal.aborted) return "unsupported";
    probe?.mark("server_play_error", { reason: String(e) });
    return "http_error";
  }
}

async function playStreamingTts(
  text: string,
  session: number,
  controller: AbortController,
  probe: ReturnType<typeof createTtsLatencyProbe>
): Promise<StreamPlayResult> {
  if (!streamingTtsEnabled()) return "unsupported";
  if (typeof window === "undefined" || typeof atob === "undefined") return "unsupported";

  let ctx: AudioContext;
  try {
    ctx = getSharedAudioContext();
    if (ctx.state === "suspended") await ctx.resume();
  } catch {
    return "unsupported";
  }

  const body = { text, ...ttsDeviceBody() };
  probe?.mark("stream_fetch_start");
  const res = await fetch(`${ttsBaseUrl()}/api/tts-stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal: controller.signal,
  });
  probe?.mark("stream_response_headers", { ok: res.ok, status: res.status });
  if (!res.ok || !res.body) return "http_error";

  const reader = res.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let pendingText = "";
  let nextStart = ctx.currentTime + 0.03;
  let pendingSources = 0;
  let streamEnded = false;
  let started = false;
  let failed = false;

  return await new Promise<StreamPlayResult>((resolve) => {
    let resolved = false;
    const finish = (result: StreamPlayResult) => {
      if (resolved) return;
      resolved = true;
      resolve(result);
    };
    const maybeFinish = () => {
      if (!streamEnded || pendingSources > 0) return;
      finish(failed ? (started ? "partial_error" : "stream_error") : "ended");
    };

    const scheduleChunk = (pcm16B64: string, sampleRate: number) => {
      if (session !== playbackSession) {
        finish("stale");
        return;
      }
      const buffer = pcm16ToAudioBuffer(ctx, base64ToBytes(pcm16B64), sampleRate);
      const source = ctx.createBufferSource();
      source.buffer = buffer;
      source.connect(ctx.destination);
      const startAt = Math.max(nextStart, ctx.currentTime + 0.01);
      nextStart = startAt + buffer.duration;
      pendingSources++;
      source.onended = () => {
        pendingSources--;
        maybeFinish();
      };
      source.start(startAt);
      if (!started) {
        started = true;
        probe?.mark("stream_play_started");
        notifyPlaybackActuallyStarted();
      }
    };

    const handleLine = (line: string) => {
      const trimmed = line.trim();
      if (!trimmed || resolved) return;
      const evt = JSON.parse(trimmed) as Record<string, unknown>;
      if (evt.type === "chunk" && typeof evt.pcm16_b64 === "string") {
        const sr = typeof evt.sample_rate === "number" ? evt.sample_rate : ctx.sampleRate;
        scheduleChunk(evt.pcm16_b64, sr);
      } else if (evt.type === "error") {
        failed = true;
        streamEnded = true;
        maybeFinish();
      } else if (evt.type === "end") {
        streamEnded = true;
        maybeFinish();
      }
    };

    const pump = async () => {
      try {
        while (true) {
          if (session !== playbackSession) {
            finish("stale");
            return;
          }
          const { value, done } = await reader.read();
          if (done) break;
          pendingText += decoder.decode(value, { stream: true });
          let newline = pendingText.indexOf("\n");
          while (newline >= 0) {
            const line = pendingText.slice(0, newline);
            pendingText = pendingText.slice(newline + 1);
            handleLine(line);
            newline = pendingText.indexOf("\n");
          }
        }
        pendingText += decoder.decode();
        if (pendingText.trim()) handleLine(pendingText);
        streamEnded = true;
        maybeFinish();
      } catch (e) {
        if (controller.signal.aborted) {
          finish("stale");
          return;
        }
        failed = true;
        streamEnded = true;
        probe?.mark("stream_read_error", { reason: String(e) });
        maybeFinish();
      }
    };

    void pump();
  });
}

/**
 * 按顺序播放 `public/` 下的静态 WAV（如 `/theater_voice/tp_*.wav`），用于剧情预烘焙，避免每次跑 SoVITS。
 * 任一文件加载失败则改用 `fallbackSpeak` 整段在线/浏览器 TTS（若提供）。
 */
export function playPrebakedWavSequence(
  urls: string[],
  fallbackSpeak?: string,
  onSequenceEnded?: () => void,
  /** story 等「非用户点击瞬间触发」场景用 browser，避免 SoVITS 异步返回后 audio.play 被拦截 */
  fallbackMode: "tts" | "browser" = "tts"
): void {
  const probe = createTtsLatencyProbe("prebaked_wav_sequence", {
    urls,
    fallbackTextLength: fallbackSpeak?.trim().length ?? 0,
    text: fallbackSpeak?.replace(/\n+/g, " ").trim().slice(0, 160) || "",
  });
  probe?.mark("function_enter");
  if (typeof window === "undefined") {
    probe?.finish("no_window");
    onSequenceEnded?.();
    return;
  }
  let ended = false;
  let fallbackTimer: number | null = null;
  const fireEnd = () => {
    if (ended) return;
    ended = true;
    probe?.mark("sequence_finish");
    if (fallbackTimer !== null) {
      window.clearTimeout(fallbackTimer);
      fallbackTimer = null;
    }
    if (currentPlaybackFinish === fireEnd) {
      currentPlaybackFinish = null;
    }
    onSequenceEnded?.();
  };

  const list = urls.map((u) => u.trim()).filter(Boolean);
  if (list.length === 0) {
    const fb = fallbackSpeak?.trim();
    if (fb) {
      probe?.mark("empty_urls_fallback", { mode: fallbackMode });
      if (fallbackMode === "browser") speakBrowserFallback(fb.replace(/\n+/g, " "), fireEnd);
      else announceBearSpeech(fb, fireEnd);
      probe?.finish("delegated_fallback", { mode: fallbackMode });
    } else {
      fireEnd();
      probe?.finish("empty_urls_no_fallback");
    }
    return;
  }

  probe?.mark("stop_previous_speech");
  stopBearSpeech();
  const session = playbackSession;
  currentPlaybackFinish = fireEnd;
  const queue = [...list];
  const audio = getSharedAudio();
  audio.volume = 1;
  const fallbackTextLen = fallbackSpeak?.trim().length ?? 0;
  fallbackTimer = window.setTimeout(
    fireEnd,
    Math.min(90_000, Math.max(8_000, fallbackTextLen * 450))
  );

  const failAll = () => {
    if (session !== playbackSession) return;
    const fb = fallbackSpeak?.trim();
    if (fb) {
      probe?.mark("fail_all_fallback", { mode: fallbackMode });
      if (fallbackMode === "browser") speakBrowserFallback(fb.replace(/\n+/g, " "), fireEnd);
      else announceBearSpeech(fb, fireEnd);
      probe?.finish("delegated_fallback", { mode: fallbackMode });
    } else fireEnd();
  };

  const playNext = (): void => {
    if (session !== playbackSession) return;
    const url = queue.shift();
    if (!url) {
      try {
        audio.removeAttribute("src");
        audio.load();
      } catch {
        /* ignore */
      }
      fireEnd();
      probe?.finish("ended");
      return;
    }

    audio.onerror = () => {
      audio.onerror = null;
      audio.onended = null;
      console.warn("[xiongdaTts] 预烘焙音频加载失败，改用朗读兜底:", url);
      probe?.mark("audio_error", { url });
      failAll();
    };

    audio.onended = () => {
      audio.onended = null;
      audio.onerror = null;
      probe?.mark("audio_ended", { url });
      playNext();
    };

    try {
      probe?.mark("set_audio_src", { url });
      audio.src = url;
      audio.setAttribute("playsInline", "true");
      void audio
        .play()
        .then(() => {
          probe?.mark("play_started", { url });
          notifyPlaybackActuallyStarted();
        })
        .catch(() => {
          probe?.mark("play_rejected", { url });
          failAll();
        });
    } catch {
      probe?.mark("play_throw", { url });
      failAll();
    }
  };

  playNext();
}

/**
 * 朗读熊大台词（异步合成 + 播放）；重复调用会先打断上一次。
 * @param onEnded 本条朗读自然结束（或失败转浏览器朗读已派发）后回调，用于串行多模态闸门。
 */
export function announceBearSpeech(text: string, onEnded?: () => void): void {
  const t = text.replace(/\n+/g, " ").trim();
  const probe = createTtsLatencyProbe("online_tts", {
    text: t.slice(0, 160),
    textLength: t.length,
    ttsUrl: ttsBaseUrl(),
  });
  probe?.mark("function_enter");
  if (typeof window === "undefined") {
    probe?.finish("no_window");
    onEnded?.();
    return;
  }
  if (!t) {
    probe?.finish("empty_text");
    onEnded?.();
    return;
  }

  const disabled = (import.meta.env.VITE_XIONGDA_TTS_DISABLED as string | undefined)?.trim();
  if (disabled === "1" || disabled?.toLowerCase() === "true") {
    probe?.mark("browser_fallback_disabled");
    speakBrowserFallback(t, onEnded);
    probe?.finish("delegated_browser_fallback");
    return;
  }

  probe?.mark("stop_previous_speech");
  stopBearSpeech();
  const session = playbackSession;
  currentPlaybackFinish = onEnded ?? null;

  const controller = new AbortController();
  currentTtsAbortController = controller;
  const tid = window.setTimeout(() => controller.abort(), FETCH_TIMEOUT_MS);

  void (async () => {
    try {
      if (serverPlayEnabled()) {
        const serverResult = await playServerSideTts(t, controller, probe);
        if (serverResult === "ended") {
          window.clearTimeout(tid);
          if (currentTtsAbortController === controller) {
            currentTtsAbortController = null;
          }
          if (currentPlaybackFinish === onEnded) {
            currentPlaybackFinish = null;
          }
          onEnded?.();
          probe?.finish("server_play_ended");
          return;
        }
        probe?.mark("server_play_fallback", { reason: serverResult });
      }

      const streamResult = await playStreamingTts(t, session, controller, probe);
      if (streamResult === "ended") {
        window.clearTimeout(tid);
        if (currentTtsAbortController === controller) {
          currentTtsAbortController = null;
        }
        if (currentPlaybackFinish === onEnded) {
          currentPlaybackFinish = null;
        }
        onEnded?.();
        probe?.finish("stream_ended");
        return;
      }
      if (streamResult === "partial_error") {
        window.clearTimeout(tid);
        if (currentTtsAbortController === controller) {
          currentTtsAbortController = null;
        }
        if (currentPlaybackFinish === onEnded) {
          currentPlaybackFinish = null;
        }
        onEnded?.();
        probe?.finish("stream_partial_error");
        return;
      }
      if (streamResult === "stale") {
        window.clearTimeout(tid);
        if (currentTtsAbortController === controller) {
          currentTtsAbortController = null;
        }
        probe?.finish("stale_session_stream");
        return;
      }
      probe?.mark("stream_fallback_to_wav", { reason: streamResult });

      const body = { text: t, ...ttsDeviceBody() };
      probe?.mark("fetch_start");
      const res = await fetch(`${ttsBaseUrl()}/api/tts`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
        signal: controller.signal,
      });
      probe?.mark("response_headers", { ok: res.ok, status: res.status });
      window.clearTimeout(tid);
      if (!res.ok) {
        const errText = await res.text().catch(() => "");
        throw new Error(`TTS HTTP ${res.status}${errText ? `: ${errText.slice(0, 200)}` : ""}`);
      }
      const blob = await res.blob();
      probe?.mark("blob_received", { bytes: blob.size, type: blob.type });
      if (currentTtsAbortController === controller) {
        currentTtsAbortController = null;
      }
      if (session !== playbackSession) {
        resolveCurrentPlayback();
        probe?.finish("stale_session_after_blob");
        return;
      }
      const objUrl = URL.createObjectURL(blob);
      currentObjectUrl = objUrl;

      const audio = getSharedAudio();
      audio.volume = 1;
      audio.src = objUrl;
      audio.onended = () => {
        probe?.mark("audio_ended");
        if (currentPlaybackFinish === onEnded) {
          currentPlaybackFinish = null;
        }
        revokeCurrentUrl();
        try {
          audio.removeAttribute("src");
          audio.load();
        } catch {
          /* ignore */
        }
        onEnded?.();
        probe?.finish("ended");
      };

      try {
        await audio.play();
        probe?.mark("play_started");
        notifyPlaybackActuallyStarted();
      } catch (playErr: unknown) {
        probe?.mark("play_rejected");
        revokeCurrentUrl();
        try {
          audio.onended = null;
          audio.removeAttribute("src");
          audio.load();
        } catch {
          /* ignore */
        }
        console.warn(
          "[xiongdaTts] 音频播放被浏览器拦截或未就绪，已改用系统朗读。若需要克隆音色，请在点击「发送」等按钮后保持页面在前台并等待合成完成；合成较慢时请留意控制台。",
          playErr
        );
        speakBrowserFallback(t, onEnded);
        probe?.finish("delegated_browser_fallback", { reason: String(playErr) });
      }
    } catch (e) {
      window.clearTimeout(tid);
      if (currentTtsAbortController === controller) {
        currentTtsAbortController = null;
      }
      revokeCurrentUrl();
      console.warn(
        `[xiongdaTts] 请求 ${ttsBaseUrl()}/api/tts 失败（将使用浏览器朗读）。请确认已启动 tts_server.py，且无显卡时服务端设置 XIONGDA_TTS_DEVICE=cpu 或在前端 .env 设置 VITE_XIONGDA_TTS_DEVICE=cpu。`,
        e
      );
      speakBrowserFallback(t, onEnded);
      probe?.finish("delegated_browser_fallback", { reason: String(e) });
    }
  })();
}
