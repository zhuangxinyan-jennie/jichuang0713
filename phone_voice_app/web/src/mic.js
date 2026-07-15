/**
 * 手机麦克风 → 16kHz float32 → WebSocket 二进制帧（流式）
 */

const TARGET_RATE = 16000;
const CHUNK_MS = 200;

function downsample(input, inRate, outRate) {
  if (inRate === outRate) return Float32Array.from(input);
  const ratio = inRate / outRate;
  const newLen = Math.max(1, Math.floor(input.length / ratio));
  const out = new Float32Array(newLen);
  for (let i = 0; i < newLen; i++) {
    const start = Math.floor(i * ratio);
    const end = Math.min(input.length, Math.floor((i + 1) * ratio));
    let sum = 0;
    let n = 0;
    for (let j = start; j < end; j++) {
      sum += input[j];
      n += 1;
    }
    out[i] = n ? sum / n : input[start] || 0;
  }
  return out;
}

export class StreamMic {
  constructor(onChunk) {
    this.onChunk = onChunk;
    this.ctx = null;
    this.stream = null;
    this.processor = null;
    this.source = null;
    this.pending = new Float32Array(0);
    this.active = false;
  }

  async start() {
    if (this.active) return;
    const insecure =
      typeof window !== "undefined" &&
      window.isSecureContext === false &&
      location.hostname !== "localhost" &&
      location.hostname !== "127.0.0.1";
    if (insecure || !navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      throw new Error(
        "当前是 HTTP，手机禁止开麦。请改用 https:// 打开（例 https://192.168.50.134:8788/），首次点「继续访问」"
      );
    }
    this.stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        channelCount: 1,
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
      },
      video: false,
    });
    this.ctx = new (window.AudioContext || window.webkitAudioContext)();
    if (this.ctx.state === "suspended") await this.ctx.resume();
    this.source = this.ctx.createMediaStreamSource(this.stream);
    // ScriptProcessor 兼容性优于部分手机上的 AudioWorklet 部署复杂度
    const bufferSize = 4096;
    this.processor = this.ctx.createScriptProcessor(bufferSize, 1, 1);
    const outSamples = Math.floor((TARGET_RATE * CHUNK_MS) / 1000);
    this.processor.onaudioprocess = (ev) => {
      if (!this.active) return;
      const input = ev.inputBuffer.getChannelData(0);
      const down = downsample(input, this.ctx.sampleRate, TARGET_RATE);
      const merged = new Float32Array(this.pending.length + down.length);
      merged.set(this.pending, 0);
      merged.set(down, this.pending.length);
      let offset = 0;
      while (merged.length - offset >= outSamples) {
        const slice = merged.subarray(offset, offset + outSamples);
        this.onChunk(slice.slice());
        offset += outSamples;
      }
      this.pending = merged.subarray(offset);
    };
    this.source.connect(this.processor);
    this.processor.connect(this.ctx.destination);
    this.active = true;
  }

  async stop() {
    this.active = false;
    this.pending = new Float32Array(0);
    try {
      this.processor?.disconnect();
    } catch (_) {}
    try {
      this.source?.disconnect();
    } catch (_) {}
    try {
      this.stream?.getTracks().forEach((t) => t.stop());
    } catch (_) {}
    try {
      await this.ctx?.close();
    } catch (_) {}
    this.processor = null;
    this.source = null;
    this.stream = null;
    this.ctx = null;
  }
}
