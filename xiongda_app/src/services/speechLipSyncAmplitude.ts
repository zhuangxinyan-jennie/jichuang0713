/**
 * TTS 播放时从 Web Audio 读取音量振幅，驱动 Unity 熊大嘴型（A/O）。
 * 无法接入音频图的路径（浏览器 SpeechSynthesis、服务端 sounddevice 播音）回退为正弦振荡。
 */
import {
  sendUnitySpeechLipSyncLevel,
  startUnitySpeechLipSync,
  stopUnitySpeechLipSync,
} from "./unitySendClip";

type LipSyncSession = {
  id: number;
  analyser: AnalyserNode | null;
  rafId: number;
  smoothedLevel: number;
};

let activeSession: LipSyncSession | null = null;
let sessionCounter = 0;

let cachedMediaElement: HTMLAudioElement | null = null;
let cachedMediaSource: MediaElementAudioSourceNode | null = null;
let cachedMediaContext: AudioContext | null = null;

let streamTapGain: GainNode | null = null;
let streamTapContext: AudioContext | null = null;

const TIME_DOMAIN = new Uint8Array(2048);

function stopActiveSession(): void {
  sessionCounter += 1;
  if (activeSession) {
    if (activeSession.rafId) {
      cancelAnimationFrame(activeSession.rafId);
    }
    activeSession = null;
  }
  stopUnitySpeechLipSync();
}

function computeRmsLevel(analyser: AnalyserNode): number {
  analyser.getByteTimeDomainData(TIME_DOMAIN);
  let sum = 0;
  for (let i = 0; i < TIME_DOMAIN.length; i++) {
    const sample = (TIME_DOMAIN[i] - 128) / 128;
    sum += sample * sample;
  }
  const rms = Math.sqrt(sum / TIME_DOMAIN.length);
  const normalized = (rms - 0.018) / 0.22;
  return Math.min(1, Math.max(0, normalized));
}

function startAmplitudeLoop(analyser: AnalyserNode | null): void {
  stopActiveSession();
  const sessionId = sessionCounter;
  const session: LipSyncSession = {
    id: sessionId,
    analyser,
    rafId: 0,
    smoothedLevel: 0,
  };
  activeSession = session;
  startUnitySpeechLipSync();

  const tick = (): void => {
    if (!activeSession || activeSession.id !== sessionId) return;

    let target = 0;
    if (activeSession.analyser) {
      target = computeRmsLevel(activeSession.analyser);
    }
    activeSession.smoothedLevel = activeSession.smoothedLevel * 0.62 + target * 0.38;
    const level = Math.pow(activeSession.smoothedLevel, 0.82);
    sendUnitySpeechLipSyncLevel(level);

    activeSession.rafId = requestAnimationFrame(tick);
  };

  session.rafId = requestAnimationFrame(tick);
}

function ensureAnalyser(ctx: AudioContext): AnalyserNode {
  const analyser = ctx.createAnalyser();
  analyser.fftSize = 2048;
  analyser.smoothingTimeConstant = 0.35;
  return analyser;
}

/** HTMLAudioElement / 预烘焙 WAV / 完整 WAV blob 播放 */
export function beginSpeechLipSyncForAudioElement(audio: HTMLAudioElement, ctx: AudioContext): void {
  try {
    void ctx.resume().catch(() => {
      /* ignore */
    });

    if (cachedMediaElement !== audio || cachedMediaContext !== ctx || !cachedMediaSource) {
      if (cachedMediaSource) {
        try {
          cachedMediaSource.disconnect();
        } catch {
          /* ignore */
        }
      }
      cachedMediaElement = audio;
      cachedMediaContext = ctx;
      cachedMediaSource = ctx.createMediaElementSource(audio);
    }

    const analyser = ensureAnalyser(ctx);
    try {
      cachedMediaSource.disconnect();
    } catch {
      /* ignore */
    }
    cachedMediaSource.connect(analyser);
    analyser.connect(ctx.destination);
    startAmplitudeLoop(analyser);
  } catch (e) {
    console.warn("[speechLipSync] 无法接入 HTMLAudio 振幅分析，回退振荡口型", e);
    beginSpeechLipSyncFallback();
  }
}

/** 流式 PCM 播放：返回应 connect 的节点（所有 BufferSource 接此处） */
export function getSpeechLipSyncStreamDestination(ctx: AudioContext): AudioNode {
  if (streamTapGain && streamTapContext === ctx) {
    return streamTapGain;
  }

  if (streamTapGain) {
    try {
      streamTapGain.disconnect();
    } catch {
      /* ignore */
    }
  }

  streamTapContext = ctx;
  streamTapGain = ctx.createGain();
  const analyser = ensureAnalyser(ctx);
  streamTapGain.connect(analyser);
  analyser.connect(ctx.destination);
  startAmplitudeLoop(analyser);
  return streamTapGain;
}

/** 浏览器 SpeechSynthesis、服务端本机播音等无 Web Audio 接入 */
export function beginSpeechLipSyncFallback(): void {
  stopActiveSession();
  startUnitySpeechLipSync();
}

/** 停止口型驱动（TTS 打断或播完） */
export function stopSpeechLipSync(): void {
  stopActiveSession();
  sendUnitySpeechLipSyncLevel(0);
}

/** TTS 打断时清理图节点（保留 AudioContext 本身，避免 MediaElementSource 无法重建） */
export function resetSpeechLipSyncAudioGraph(): void {
  stopActiveSession();
  streamTapGain = null;
  streamTapContext = null;
}
