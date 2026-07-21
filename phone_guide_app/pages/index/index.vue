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

    <view v-if="safetyCritical" class="safety-banner">
      <text class="safety-title">安全提示</text>
      <text>当前区域人流较密，互动已暂停。</text>
    </view>

    <view class="card connection-card">
      <view class="row">
        <text class="muted">用户 ID</text>
        <text class="mono">{{ userId || "未配对" }}</text>
      </view>
      <view class="row">
        <text class="muted">对话状态</text>
        <text class="msg">{{ queueText }}</text>
      </view>
      <view class="row">
        <text class="muted">智能服务</text>
        <text class="msg">{{ agentOnline ? "在线" : "离线" }}</text>
      </view>
      <view v-if="queueStatus === 'ACTIVE'" class="row">
        <text class="muted">本轮额度</text>
        <text class="msg">剩余 {{ remainingTurns }} 次 · {{ remainingSeconds }} 秒</text>
      </view>
      <button class="queue-btn" :disabled="!gatewayConnected || safetyCritical" @click="onQueueAction">
        {{ queueButtonText }}
      </button>
    </view>

    <view class="card">
      <text class="label">识别中</text>
      <text class="partial">{{ partialText || "等待说话…" }}</text>
      <view class="divider" />
      <text class="label">已确认</text>
      <text class="final">{{ finalText || "—" }}</text>
      <view class="divider" />
      <text class="label">熊大回复</text>
      <text :class="['reply', { waiting: agentBusy }]">
        {{ agentBusy ? "正在回复…" : replyText || "—" }}
      </text>
    </view>

    <view class="card meta">
      <view class="row">
        <text class="muted">Gateway</text>
        <text class="mono">{{ pcHost }}:{{ bridgePort }}</text>
      </view>
      <view class="row">
        <text class="muted">状态</text>
        <text class="msg">{{ statusText }}</text>
      </view>
    </view>

    <view class="card controls-card">
      <view class="control-row">
        <view>
          <text class="control-title">视频解析结果</text>
          <text class="control-sub">人数、表情、手势只在手机显示</text>
        </view>
        <switch :checked="videoAnalysis" color="#82aaff" @change="onVideoAnalysisChange" />
      </view>
      <view class="control-row">
        <view>
          <text class="control-title">视频预览</text>
          <text class="control-sub">局域网预览，不传给 Agent</text>
        </view>
        <switch :checked="videoPreview" color="#82aaff" @change="onVideoPreviewChange" />
      </view>
      <view class="control-row">
        <view>
          <text class="control-title">手机声音</text>
          <text class="control-sub">大屏声音始终开启</text>
        </view>
        <switch :checked="!phoneMuted" color="#82aaff" @change="onPhoneSoundChange" />
      </view>
      <view v-if="videoAnalysis" class="analysis-box">
        <text class="label">现场解析</text>
        <text class="analysis-text">{{ analysisText }}</text>
      </view>
      <view v-if="videoPreview" class="preview-box">
        <image
          v-if="previewUrl"
          class="preview-image"
          :src="previewUrl"
          mode="aspectFit"
          @error="onPreviewError"
        />
        <text class="preview-tip">{{ previewStatus }}</text>
      </view>
    </view>

    <view class="dock">
      <view
        class="talk"
        :class="{ active: speaking, disabled: !canTalk }"
        @touchstart.prevent="onDown"
        @touchend.prevent="onUp"
        @touchcancel.prevent="onUp"
        @mousedown.prevent="onDown"
        @mouseup.prevent="onUp"
      >
        <text class="talk-text">{{ speaking ? "正在听取…" : canTalk ? "按住说话" : "先申请对话" }}</text>
      </view>
      <text class="hint">{{ canTalk ? "松手停止" : "获得对话权后可输入" }}</text>
    </view>
  </view>
</template>

<script>
import {
  acceptConversation,
  createAsrSocket,
  endConversation,
  fetchGatewayState,
  getBridgeHost,
  getBridgePort,
  getGatewayIdentity,
  int16ToFloat32,
  joinConversationQueue,
  leaveConversationQueue,
  pairGateway,
  previewSnapshotUrl,
  startGatewayHeartbeat,
  touchConversation,
} from "../../utils/asrBridge.js";

export default {
  data() {
    return {
      pcHost: getBridgeHost(),
      bridgePort: getBridgePort(),
      partialText: "",
      finalText: "",
      statusText: "初始化…",
      pillText: "连接中",
      pillClass: "muted",
      speaking: false,
      socket: null,
      recorder: null,
      recorderBound: false,
      gatewayStop: null,
      endpointHandler: null,
      gatewayConnected: false,
      userId: getGatewayIdentity().userId,
      queueStatus: "CONNECTED",
      queuePosition: null,
      remainingTurns: 0,
      remainingSeconds: 0,
      agentOnline: false,
      agentBusy: false,
      replyText: "",
      replyAudio: null,
      safetyState: "NORMAL",
      videoAnalysis: false,
      videoPreview: false,
      phoneMuted: false,
      analysisText: "等待板端解析数据",
      previewUrl: "",
      previewStatus: "正在等待板端视频",
      previewTimer: null,
    };
  },
  computed: {
    safetyCritical() {
      return this.safetyState === "CRITICAL" || this.safetyState === "SAFETY_ALERT";
    },
    canTalk() {
      return this.queueStatus === "ACTIVE" && !this.safetyCritical && this.agentOnline && !this.agentBusy;
    },
    queueText() {
      if (!this.gatewayConnected) return "正在连接板端";
      if (this.queueStatus === "ACTIVE") return this.agentBusy ? "熊大回复中" : "当前对话用户";
      if (this.queueStatus === "WAITING_ACCEPT") return "轮到你了，请确认";
      if (this.queueStatus === "QUEUED") return `排队中，前方 ${Math.max(0, (this.queuePosition || 1) - 1)} 人`;
      return "未申请对话";
    },
    queueButtonText() {
      if (this.queueStatus === "ACTIVE") return "结束对话";
      if (this.queueStatus === "WAITING_ACCEPT") return "开始对话";
      if (this.queueStatus === "QUEUED") return "退出排队";
      return "申请对话";
    },
  },
  onLoad() {
    this.endpointHandler = () => this.reconnectGateway();
    uni.$on("gateway-endpoint-changed", this.endpointHandler);
  },
  onShow() {
    this.pcHost = getBridgeHost();
    this.bridgePort = getBridgePort();
    if (!this.socket) this.setupSocket();
    if (!this.gatewayStop) this.connectGateway();
  },
  onUnload() {
    this.stopRec();
    if (this.socket) this.socket.close();
    if (this.gatewayStop) this.gatewayStop();
    this.stopReplyAudio();
    this.stopPreviewRefresh();
    this.gatewayStop = null;
    if (this.endpointHandler) uni.$off("gateway-endpoint-changed", this.endpointHandler);
    this.endpointHandler = null;
  },
  methods: {
    reconnectGateway() {
      this.stopRec();
      if (this.socket) this.socket.close();
      if (this.gatewayStop) this.gatewayStop();
      this.socket = null;
      this.gatewayStop = null;
      this.gatewayConnected = false;
      this.pcHost = getBridgeHost();
      this.bridgePort = getBridgePort();
      this.setupSocket();
      void this.connectGateway();
    },
    async connectGateway() {
      this.statusText = "正在连接 Gateway";
      try {
        const paired = await pairGateway();
        this.applyGatewayClient(paired);
        const state = await fetchGatewayState();
        this.applyGatewayState(state);
        this.gatewayConnected = true;
        this.gatewayStop = startGatewayHeartbeat({
          onState: (next) => {
            this.gatewayConnected = true;
            this.applyGatewayState(next);
          },
          onError: (error) => {
            this.gatewayConnected = false;
            this.statusText = error.message || "Gateway 连接中断";
          },
        });
      } catch (error) {
        this.gatewayConnected = false;
        this.statusText = (error && error.message) || "Gateway 连接失败";
      }
    },
    applyGatewayClient(result) {
      this.userId = result.user_id || this.userId;
      this.queueStatus = result.status || this.queueStatus;
      this.queuePosition = result.queue_position;
    },
    applyGatewayState(state) {
      const own = state && state.own;
      if (own) this.applyGatewayClient(own);
      const conversation = (state && state.conversation) || {};
      this.remainingTurns = Number(conversation.remaining_turns || 0);
      this.remainingSeconds = Number(conversation.remaining_s || 0);
      this.agentBusy = Boolean(conversation.agent_busy);
      this.agentOnline = Boolean(state && state.agent && state.agent.online);
      const vision = (state && state.vision) || {};
      if (this.videoAnalysis) this.analysisText = this.formatVisionState(vision);
      const safety = state && state.safety;
      this.safetyState = (safety && (safety.state || safety.crowd_state)) || "NORMAL";
      if (this.safetyCritical && this.speaking) this.stopRec();
      if (this.safetyCritical) this.stopReplyAudio();
      if (this.safetyCritical) this.statusText = "安全预警：互动已暂停";
    },
    async onQueueAction() {
      try {
        let result;
        if (this.queueStatus === "ACTIVE") {
          this.stopRec();
          result = await endConversation();
        } else if (this.queueStatus === "WAITING_ACCEPT") {
          result = await acceptConversation();
        } else if (this.queueStatus === "QUEUED") {
          result = await leaveConversationQueue();
        } else {
          result = await joinConversationQueue();
        }
        this.applyGatewayClient(result);
        this.statusText = this.queueStatus === "ACTIVE" ? "对话已开始" : "状态已更新";
      } catch (error) {
        this.statusText = (error && error.message) || "队列操作失败";
      }
    },
    onVideoAnalysisChange(event) {
      this.videoAnalysis = Boolean(event && event.detail && event.detail.value);
      if (!this.videoAnalysis) {
        this.analysisText = "等待板端解析数据";
        return;
      }
      void fetchGatewayState().then((state) => this.applyGatewayState(state)).catch(() => {});
    },
    onVideoPreviewChange(event) {
      this.videoPreview = Boolean(event && event.detail && event.detail.value);
      if (this.videoPreview) this.startPreviewRefresh();
      else this.stopPreviewRefresh();
    },
    onPhoneSoundChange(event) {
      this.phoneMuted = !(event && event.detail && event.detail.value);
      if (this.phoneMuted) this.stopReplyAudio();
    },
    formatVisionState(vision) {
      if (!vision || !vision.timestamp) return "等待板端解析数据";
      const parts = [`人数 ${Number(vision.person_count || 0)}`];
      if (vision.emotion) parts.push(`表情 ${vision.emotion}`);
      if (vision.gesture) parts.push(`手势 ${vision.gesture}`);
      if (vision.action) parts.push(`动作 ${vision.action}`);
      if (vision.crowd_state) parts.push(`人流 ${vision.crowd_state}`);
      return parts.join(" · ");
    },
    startPreviewRefresh() {
      this.stopPreviewRefresh();
      const refresh = () => {
        if (!this.videoPreview) return;
        this.previewUrl = previewSnapshotUrl(Date.now());
        this.previewStatus = this.previewUrl ? "实时预览约 2 FPS" : "请先在设备页连接板子";
        this.previewTimer = setTimeout(refresh, 500);
      };
      refresh();
    },
    stopPreviewRefresh() {
      if (this.previewTimer) clearTimeout(this.previewTimer);
      this.previewTimer = null;
      this.previewUrl = "";
    },
    onPreviewError() {
      this.previewStatus = "视频预览尚未就绪";
    },
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
          this.agentBusy = true;
          this.statusText = "等待熊大回复";
        },
        onAgentResponse: (payload, meta) => {
          this.handleAgentResponse(payload, meta);
        },
        onSessionEnd: () => {
          this.agentBusy = false;
          this.queueStatus = "CONNECTED";
          this.statusText = "本轮对话已结束";
        },
        onError: (m) => {
          this.statusText = m;
          this.pillText = "错误";
          this.pillClass = "err";
        },
      });
    },
    handleAgentResponse(payload, meta) {
      const result = payload && typeof payload === "object" ? payload : {};
      this.agentBusy = false;
      this.replyText = String(result.speech || result.text || "").trim();
      this.statusText = meta && meta.session_ended ? "本轮对话已结束" : "回复完成";
      if (Array.isArray(result.path) && result.path.length) {
        uni.$emit("map-route", {
          destination: result.destination || result.path[result.path.length - 1],
          path: result.path,
          path_world: Array.isArray(result.path_world) ? result.path_world : [],
        });
        uni.switchTab({ url: "/pages/map/map" });
      }
      if (meta && meta.session_ended) this.queueStatus = "CONNECTED";
      this.playReplyAudio(result);
    },
    playReplyAudio(payload) {
      this.stopReplyAudio();
      if (this.phoneMuted) return;
      const source = String(payload.audio_url || payload.audio || "").trim();
      if (!source) return;
      const audio = uni.createInnerAudioContext();
      audio.src = source;
      audio.autoplay = true;
      audio.onEnded(() => this.stopReplyAudio());
      audio.onError(() => this.stopReplyAudio());
      this.replyAudio = audio;
    },
    stopReplyAudio() {
      if (!this.replyAudio) return;
      try {
        this.replyAudio.stop();
        this.replyAudio.destroy();
      } catch (_) {}
      this.replyAudio = null;
    },
    onDown() {
      if (!this.canTalk) {
        uni.showToast({ title: this.safetyCritical ? "安全预警中" : "请先获得对话权", icon: "none" });
        return;
      }
      this.startRec();
    },
    onUp() {
      this.stopRec();
    },
    startRec() {
      if (this.speaking) return;
      this.speaking = true;
      this.ensureRecorder();
      void touchConversation().catch(() => {});
      const recorder = this.recorder;
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
    ensureRecorder() {
      if (this.recorderBound) return;
      const recorder = uni.getRecorderManager();
      this.recorder = recorder;
      recorder.onFrameRecorded((res) => {
        if (!this.speaking || !this.socket) return;
        const ab = res.frameBuffer;
        if (!ab) return;
        this.socket.sendPcmFloat32(int16ToFloat32(new Int16Array(ab)));
      });
      recorder.onError((e) => {
        this.statusText = (e && e.errMsg) || "录音失败";
        this.pillText = "麦权限";
        this.pillClass = "err";
        this.speaking = false;
      });
      this.recorderBound = true;
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
  background: #0a0a0a;
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
.safety-banner {
  display: flex;
  flex-direction: column;
  gap: 8rpx;
  margin-bottom: 20rpx;
  padding: 20rpx 24rpx;
  border-left: 6rpx solid #b94b4b;
  background: #301919;
  color: #f2d7d7;
  font-size: 24rpx;
}
.safety-title {
  font-size: 26rpx;
  font-weight: 600;
}
.card {
  background: #141414;
  border: 1px solid #2a2a2a;
  border-radius: 24rpx;
  padding: 24rpx;
  margin-bottom: 20rpx;
}
.queue-btn {
  margin-top: 20rpx;
  background: #2a4060;
  color: #e6edff;
  border-radius: 12rpx;
  font-size: 26rpx;
}
.queue-btn[disabled] {
  background: #222;
  color: #666;
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
.reply {
  display: block;
  min-height: 72rpx;
  color: #e8e8e8;
  font-size: 29rpx;
  line-height: 1.5;
}
.reply.waiting {
  color: #e6c07b;
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
.control-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20rpx;
  padding: 18rpx 0;
  border-bottom: 1px solid #282828;
}
.control-row:last-of-type {
  border-bottom: 0;
}
.control-title,
.control-sub {
  display: block;
}
.control-title {
  font-size: 26rpx;
}
.control-sub {
  margin-top: 6rpx;
  color: #858585;
  font-size: 21rpx;
}
.analysis-box {
  margin-top: 18rpx;
  padding: 18rpx;
  background: #0d0d0d;
  border: 1px solid #272727;
  border-radius: 10rpx;
}
.analysis-text {
  font-size: 24rpx;
  color: #c9d7ff;
}
.preview-box {
  margin-top: 18rpx;
  padding: 12rpx;
  border: 1px solid #272727;
  border-radius: 10rpx;
  background: #0d0d0d;
}
.preview-image {
  display: block;
  width: 100%;
  height: 360rpx;
  background: #080808;
}
.preview-tip {
  display: block;
  margin-top: 10rpx;
  color: #858585;
  font-size: 20rpx;
  text-align: center;
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
.talk.disabled {
  opacity: 0.55;
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
