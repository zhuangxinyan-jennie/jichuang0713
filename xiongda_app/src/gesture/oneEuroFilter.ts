/**
 * 1€ Filter — 交互式指针跟踪常用平滑算法（Casiez et al., CHI 2012）
 * 慢速时强平滑减抖动，快速移动时减少延迟。
 */
export class OneEuroFilter {
  freq: number;
  mincutoff: number;
  beta: number;
  dcutoff: number;
  xPrev: number | null = null;
  dxPrev = 0;
  tPrev: number | null = null;

  constructor({
    freq = 60,
    mincutoff = 1.0,
    beta = 0.007,
    dcutoff = 1.0,
  }: { freq?: number; mincutoff?: number; beta?: number; dcutoff?: number } = {}) {
    this.freq = freq;
    this.mincutoff = mincutoff;
    this.beta = beta;
    this.dcutoff = dcutoff;
  }

  alpha(cutoff: number, dt: number): number {
    const tau = 1.0 / (2 * Math.PI * cutoff);
    return 1.0 / (1.0 + tau / dt);
  }

  filter(x: number, timestampMs: number): number {
    if (this.xPrev === null) {
      this.xPrev = x;
      this.tPrev = timestampMs;
      return x;
    }
    const dt = Math.max((timestampMs - (this.tPrev as number)) / 1000, 1 / this.freq);
    const dx = (x - this.xPrev) / dt;
    const edx = this.alpha(this.dcutoff, dt);
    const dxHat = edx * dx + (1 - edx) * this.dxPrev;
    const cutoff = this.mincutoff + this.beta * Math.abs(dxHat);
    const ex = this.alpha(cutoff, dt);
    const xHat = ex * x + (1 - ex) * this.xPrev;
    this.xPrev = xHat;
    this.dxPrev = dxHat;
    this.tPrev = timestampMs;
    return xHat;
  }

  reset() {
    this.xPrev = null;
    this.dxPrev = 0;
    this.tPrev = null;
  }
}
