<template>
  <view class="page">
    <view class="head">
      <view class="brand">
        <view class="dot" />
        <view>
          <text class="title">Phone Guide</text>
          <text class="sub">流式语音 → 板端 ASR → PC 终端</text>
        </view>
      </view>
      <view :class="['pill', pillClass]">{{ pillText }}</view>
    </view>

    <view class="card">
      <text class="label">识别中</text>
      <text class="partial">{{ partialText || "等待说话…" }}</text>
      <view class="divider" />
      <text class="label">已确认</text>
      <text class="final">{{ finalText || "—" }}</text>
    </view>

    <view class="card meta">
      <view class="row">
        <text class="muted">电脑</text>
        <text class="mono">{{ pcHost }}:8788</text>
      </view>
      <view class="row">
        <text class="muted">状态</text>
        <text class="msg">{{ statusText }}</text>
      </view>
    </view>

    <view class="dock">
      <view
        class="talk"
        :class="{ active: speaking }"
        @touchstart.prevent="onDown"
        @touchend.prevent="onUp"
        @touchcancel.prevent="onUp"
        @mousedown.prevent="onDown"
        @mouseup.prevent="onUp"
      >
        <text class="talk-text">{{ speaking ? "正在听取…" : "按住说话" }}</text>
      </view>
      <text class="hint">松手停止 · 识别字会同步打在电脑 bridge 黑窗口</text>
    </view>
  </view>
</template>

<script>
import { createAsrSocket, getPcHost, int16ToFloat32 } from "../../utils/asrBridge.js";

export default {
  data() {
    return {
      pcHost: getPcHost(),
      partialText: "",
      finalText: "",
      statusText: "初始化…",
      pillText: "连接中",
      pillClass: "muted",
      speaking: false,
      socket: null,
      recorder: null,
    };
  },
  onShow() {
    this.pcHost = getPcHost();
    if (!this.socket) this.setupSocket();
  },
  onUnload() {
    this.stopRec();
    if (this.socket) this.socket.close();
  },
  methods: {
    setupSocket() {
      this.socket = createAsrSocket({
        onStatus: (k, msg) => {
          this.statusText = msg || k;
          if (k === "open" || k === "board_ok") {
            this.pillText = "已连接";
            this.pillClass = "ok";
          } else if (k === "board_warn") {
            this.pillText = "板端未连";
            this.pillClass = "warn";
          } else if (k === "closed" || k === "connecting") {
            this.pillText = "连接中";
            this.pillClass = "muted";
          }
        },
        onPartial: (t) => {
          this.partialText = t;
        },
        onFinal: (t) => {
          this.finalText = t;
          this.partialText = "等待说话…";
        },
        onError: (m) => {
          this.statusText = m;
          this.pillText = "错误";
          this.pillClass = "err";
        },
      });
    },
    onDown() {
      this.startRec();
    },
    onUp() {
      this.stopRec();
    },
    startRec() {
      if (this.speaking) return;
      this.speaking = true;
      // 使用录音管理器；部分机型用 frameSize 拿 PCM 帧
      const recorder = uni.getRecorderManager();
      this.recorder = recorder;
      recorder.onFrameRecorded((res) => {
        if (!this.speaking || !this.socket) return;
        const ab = res.frameBuffer;
        if (!ab) return;
        const int16 = new Int16Array(ab);
        const f32 = int16ToFloat32(int16);
        this.socket.sendPcmFloat32(f32);
      });
      recorder.onError((e) => {
        this.statusText = (e && e.errMsg) || "录音失败";
        this.pillText = "麦权限";
        this.pillClass = "err";
        this.speaking = false;
      });
      recorder.start({
        duration: 600000,
        sampleRate: 16000,
        numberOfChannels: 1,
        encodeBitRate: 48000,
        format: "PCM",
        frameSize: 4, // KB，约产生帧推流
      });
      this.statusText = "流式发送中";
    },
    stopRec() {
      if (!this.speaking) return;
      this.speaking = false;
      try {
        this.recorder && this.recorder.stop();
      } catch (_) {}
      this.statusText = "已停止发送";
    },
  },
};
</script>

<style scoped>
.page {
  min-height: 100vh;
  padding: 20rpx 28rpx 40rpx;
  box-sizing: border-box;
  background: radial-gradient(800rpx 400rpx at 20% -10%, #152033 0%, transparent 55%), #0a0a0a;
}
.head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 24rpx;
}
.brand {
  display: flex;
  gap: 16rpx;
  align-items: center;
}
.dot {
  width: 16rpx;
  height: 16rpx;
  border-radius: 50%;
  background: #82aaff;
  box-shadow: 0 0 0 8rpx rgba(130, 170, 255, 0.15);
}
.title {
  display: block;
  font-size: 34rpx;
  font-weight: 650;
}
.sub {
  display: block;
  margin-top: 4rpx;
  font-size: 22rpx;
  color: #8b8b8b;
}
.pill {
  font-size: 22rpx;
  padding: 10rpx 18rpx;
  border-radius: 999rpx;
  border: 1px solid #2a2a2a;
  background: #141414;
}
.pill.ok {
  color: #7fd99a;
  border-color: rgba(127, 217, 154, 0.35);
}
.pill.warn {
  color: #e6c07b;
}
.pill.err {
  color: #ef6b6b;
}
.pill.muted {
  color: #8b8b8b;
}
.card {
  background: linear-gradient(180deg, #1a1a1a, #141414);
  border: 1px solid #2a2a2a;
  border-radius: 24rpx;
  padding: 24rpx;
  margin-bottom: 20rpx;
}
.label {
  display: block;
  font-size: 20rpx;
  color: #8b8b8b;
  letter-spacing: 0.08em;
  margin-bottom: 12rpx;
}
.partial {
  display: block;
  min-height: 88rpx;
  font-size: 34rpx;
  line-height: 1.45;
  color: #c9d7ff;
  font-family: ui-monospace, monospace;
}
.final {
  display: block;
  min-height: 72rpx;
  font-size: 30rpx;
  font-family: ui-monospace, monospace;
}
.divider {
  height: 1px;
  background: #2a2a2a;
  margin: 24rpx 0;
}
.row {
  display: flex;
  justify-content: space-between;
  padding: 12rpx 0;
  font-size: 24rpx;
  border-bottom: 1px dashed #2a2a2a;
}
.row:last-child {
  border-bottom: 0;
}
.muted {
  color: #8b8b8b;
}
.mono {
  font-family: ui-monospace, monospace;
  font-size: 22rpx;
}
.msg {
  max-width: 65%;
  text-align: right;
  font-size: 22rpx;
}
.dock {
  margin-top: 40rpx;
  align-items: center;
  display: flex;
  flex-direction: column;
}
.talk {
  width: 360rpx;
  height: 360rpx;
  border-radius: 50%;
  border: 1px solid #333;
  background: radial-gradient(circle at 35% 30%, #2a3142, #171a20 62%, #101114);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 20rpx 60rpx rgba(0, 0, 0, 0.45);
}
.talk.active {
  border-color: rgba(130, 170, 255, 0.55);
  background: radial-gradient(circle at 35% 30%, #3a4a66, #1c2433 62%, #12151c);
}
.talk-text {
  font-size: 32rpx;
  font-weight: 600;
}
.hint {
  margin-top: 20rpx;
  font-size: 22rpx;
  color: #8b8b8b;
  text-align: center;
}
</style>
