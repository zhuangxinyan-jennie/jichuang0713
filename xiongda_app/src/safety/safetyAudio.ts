import { isBearSpeechBusy, stopBearSpeech } from "../services/xiongdaTts";

const WARNING_WAV = "/safety_voice/crowd_warning.wav";
const CRITICAL_WAV = "/safety_voice/crowd_critical.wav";
const RECOVERED_WAV = "/safety_voice/crowd_recovered.wav";
const RETRY_MS = 15_000;

export class SafetyAudioController {
  private audio: HTMLAudioElement | null = null;
  private timer: number | null = null;
  private generation = 0;
  private playing = false;

  startCritical(): void {
    this.cancel();
    stopBearSpeech();
    const generation = this.generation;
    const attempt = () => {
      if (generation !== this.generation || this.playing) return;
      void this.play(CRITICAL_WAV);
    };
    attempt();
    this.timer = window.setInterval(attempt, RETRY_MS);
  }

  queueWarning(isStillWarning: () => boolean): void {
    this.cancel();
    const generation = this.generation;
    const attempt = () => {
      if (generation !== this.generation || !isStillWarning()) return;
      if (isBearSpeechBusy() || this.playing) {
        this.timer = window.setTimeout(attempt, 250);
        return;
      }
      void this.play(WARNING_WAV);
    };
    attempt();
  }

  startRecovery(onFinished: () => void): void {
    this.cancel();
    stopBearSpeech();
    const generation = this.generation;
    const attempt = async () => {
      if (generation !== this.generation || this.playing) return;
      const played = await this.play(RECOVERED_WAV);
      if (generation !== this.generation) return;
      if (played) {
        onFinished();
      } else {
        this.timer = window.setTimeout(() => void attempt(), RETRY_MS);
      }
    };
    void attempt();
  }

  cancel(): void {
    this.generation += 1;
    if (this.timer !== null) {
      window.clearTimeout(this.timer);
      window.clearInterval(this.timer);
      this.timer = null;
    }
    this.playing = false;
    if (this.audio) {
      this.audio.onended = null;
      this.audio.onerror = null;
      this.audio.pause();
      this.audio.removeAttribute("src");
      this.audio.load();
      this.audio = null;
    }
  }

  private play(url: string): Promise<boolean> {
    if (typeof window === "undefined") return Promise.resolve(false);
    const audio = new Audio(url);
    this.audio = audio;
    this.playing = true;
    audio.preload = "auto";
    audio.setAttribute("playsInline", "true");
    return new Promise((resolve) => {
      let done = false;
      const finish = (ok: boolean) => {
        if (done) return;
        done = true;
        this.playing = false;
        audio.onended = null;
        audio.onerror = null;
        if (this.audio === audio) this.audio = null;
        resolve(ok);
      };
      audio.onended = () => finish(true);
      audio.onerror = () => {
        console.error(`[safety] local audio failed: ${url}`);
        finish(false);
      };
      void audio.play().catch((error) => {
        console.error(`[safety] audio.play rejected: ${url}`, error);
        finish(false);
      });
    });
  }
}

