<template>
  <view class="page">
    <view class="section-head">
      <text class="section-title">设备连接</text>
      <text :class="['status', connected ? 'online' : 'offline']">
        {{ connected ? "已连接" : "未连接" }}
      </text>
    </view>

    <view class="card">
      <text class="label">板端 Gateway</text>
      <view class="endpoint-row">
        <input class="input host-input" v-model="host" placeholder="192.168.137.100" />
        <input class="input port-input" v-model="port" type="number" placeholder="8788" />
      </view>
      <button class="primary-btn" :disabled="connectBusy" @click="connectManual">
        {{ connectBusy ? "连接中" : "连接板子" }}
      </button>
      <button class="secondary-btn" :disabled="connectBusy" @click="scan">
        扫描连接二维码
      </button>
      <text class="tip">iOS、Android 使用同一码。仅支持板子所在局域网。</text>
    </view>

    <view class="card device-card">
      <view class="row">
        <text class="muted">用户 ID</text>
        <text class="mono">{{ userId || "—" }}</text>
      </view>
      <view class="row">
        <text class="muted">板端服务</text>
        <text class="value">{{ runtimeText }}</text>
      </view>
      <view class="row">
        <text class="muted">PC Agent</text>
        <text class="value">{{ agentOnline ? "在线" : "离线" }}</text>
      </view>
      <text v-if="message" class="message">{{ message }}</text>
    </view>

    <view class="card debug-card">
      <view class="debug-head">
        <view>
          <text class="debug-title">调试模式</text>
          <text class="debug-sub">管理员控制板端全部程序</text>
        </view>
        <text v-if="debugMode" class="debug-badge">调试模式</text>
      </view>

      <template v-if="!debugMode">
        <input
          class="input pin-input"
          v-model="pin"
          type="number"
          password
          maxlength="12"
          placeholder="管理员 PIN"
        />
        <button class="debug-entry" :disabled="!connected || debugBusy" @click="enterDebugMode">
          进入调试模式
        </button>
      </template>

      <template v-else>
        <view class="runtime-state">
          <text class="muted">当前状态</text>
          <text class="runtime-value">{{ runtimeText }}</text>
        </view>
        <button class="start-btn" :disabled="debugBusy || runtimeState === 'RUNNING'" @click="startAll">
          {{ debugBusy && operationAction === "start" ? "启动中" : "启动全部" }}
        </button>
        <button class="stop-btn" :disabled="debugBusy || runtimeState === 'MAINTENANCE'" @click="confirmStopAll">
          {{ debugBusy && operationAction === "stop" ? "停止中" : "停止全部" }}
        </button>
        <text v-if="lastOperation" class="operation-result">{{ lastOperation }}</text>
        <button class="exit-btn" @click="exitDebugMode">退出调试模式</button>
      </template>
    </view>
  </view>
</template>

<script>
import {
  clearGatewayIdentity,
  fetchGatewayState,
  fetchRuntimeOperation,
  getBridgeHost,
  getBridgePort,
  getGatewayIdentity,
  loginDebugMode,
  pairGateway,
  parseJoinCode,
  setBridgeEndpoint,
  startBoardRuntime,
  stopBoardRuntime,
} from "../../utils/asrBridge.js";
import { scanJoinCode } from "../../utils/browserMedia.js";

export default {
  data() {
    return {
      host: getBridgeHost(),
      port: String(getBridgePort()),
      connected: false,
      connectBusy: false,
      userId: getGatewayIdentity().userId,
      runtimeState: "UNKNOWN",
      agentOnline: false,
      message: "",
      pin: "",
      debugMode: false,
      debugBusy: false,
      adminToken: "",
      operationAction: "",
      lastOperation: "",
      operationTimer: null,
    };
  },
  computed: {
    runtimeText() {
      const labels = {
        UNKNOWN: "状态未知",
        STARTING: "启动中",
        RUNNING: "运行中",
        STOPPING: "停止中",
        MAINTENANCE: "已停止",
        FAILED: "启动失败",
      };
      return labels[this.runtimeState] || this.runtimeState;
    },
  },
  onShow() {
    this.host = getBridgeHost();
    this.port = String(getBridgePort());
    this.userId = getGatewayIdentity().userId;
    if (getGatewayIdentity().token) this.refreshState();
  },
  onUnload() {
    this.cancelOperationPoll();
    this.adminToken = "";
  },
  methods: {
    async connectManual() {
      await this.connectToEndpoint({ host: this.host, port: Number(this.port), insecure: true });
    },
    scan() {
      scanJoinCode()
        .then(async (rawValue) => {
          const endpoint = parseJoinCode(rawValue);
          this.host = endpoint.host;
          this.port = String(endpoint.port);
          await this.connectToEndpoint({ ...endpoint, insecure: true });
        })
        .catch((error) => {
          this.message = (error && error.message) || "扫码取消";
        });
    },
    async connectToEndpoint(endpoint) {
      if (this.connectBusy) return;
      this.connectBusy = true;
      this.message = "正在连接板端";
      try {
        const changed =
          getBridgeHost() !== String(endpoint.host || "").trim() || getBridgePort() !== Number(endpoint.port);
        setBridgeEndpoint(endpoint);
        if (changed) clearGatewayIdentity();
        const paired = await pairGateway();
        this.userId = paired.user_id || "";
        this.connected = true;
        this.message = `连接成功，用户 ID ${this.userId}`;
        await this.refreshState();
        uni.$emit("gateway-endpoint-changed", { host: endpoint.host, port: Number(endpoint.port) });
      } catch (error) {
        this.connected = false;
        this.message = (error && error.message) || "连接板端失败";
      } finally {
        this.connectBusy = false;
      }
    },
    async refreshState() {
      try {
        const state = await fetchGatewayState();
        this.connected = true;
        this.runtimeState = (state.runtime && state.runtime.state) || "UNKNOWN";
        this.agentOnline = Boolean(state.agent && state.agent.online);
        if (state.own && state.own.user_id) this.userId = state.own.user_id;
      } catch (error) {
        this.connected = false;
        this.message = (error && error.message) || "无法读取板端状态";
      }
    },
    async enterDebugMode() {
      if (!this.pin || this.debugBusy) return;
      this.debugBusy = true;
      try {
        const result = await loginDebugMode(this.pin);
        this.adminToken = result.admin_token || "";
        if (!this.adminToken) throw new Error("管理员登录响应无效");
        this.debugMode = true;
        this.pin = "";
        this.lastOperation = "调试模式已启用";
      } catch (error) {
        this.lastOperation = (error && error.message) || "PIN 验证失败";
      } finally {
        this.debugBusy = false;
      }
    },
    exitDebugMode() {
      this.cancelOperationPoll();
      this.adminToken = "";
      this.debugMode = false;
      this.lastOperation = "";
    },
    async startAll() {
      await this.runOperation("start");
    },
    confirmStopAll() {
      uni.showModal({
        title: "停止全部程序",
        content: "将停止安全监控、清空当前对话和排队队列。Gateway 保持运行。",
        confirmText: "停止全部",
        confirmColor: "#b94b4b",
        success: (result) => {
          if (result.confirm) void this.runOperation("stop");
        },
      });
    },
    async runOperation(action) {
      if (!this.adminToken || this.debugBusy) return;
      this.debugBusy = true;
      this.operationAction = action;
      this.lastOperation = action === "start" ? "正在启动板端程序" : "正在停止板端程序";
      try {
        const operation =
          action === "start"
            ? await startBoardRuntime(this.adminToken)
            : await stopBoardRuntime(this.adminToken);
        this.pollOperation(operation.operation_id, action, Date.now() + 60000);
      } catch (error) {
        this.debugBusy = false;
        this.lastOperation = (error && error.message) || "操作失败";
      }
    },
    pollOperation(operationId, action, deadline) {
      this.cancelOperationPoll();
      const poll = async () => {
        try {
          const operation = await fetchRuntimeOperation(this.adminToken, operationId);
          if (operation.state === "SUCCEEDED") {
            this.debugBusy = false;
            this.operationAction = "";
            this.lastOperation = action === "start" ? "启动成功" : "停止成功";
            await this.refreshState();
            return;
          }
          if (operation.state === "FAILED") {
            this.debugBusy = false;
            this.operationAction = "";
            this.lastOperation = operation.error || "操作失败";
            await this.refreshState();
            return;
          }
          if (Date.now() >= deadline) {
            this.debugBusy = false;
            this.operationAction = "";
            this.lastOperation = "操作仍在执行，可稍后刷新状态";
            await this.refreshState();
            return;
          }
          this.operationTimer = setTimeout(poll, 500);
        } catch (error) {
          this.debugBusy = false;
          this.operationAction = "";
          this.lastOperation = (error && error.message) || "查询操作状态失败";
        }
      };
      void poll();
    },
    cancelOperationPoll() {
      if (this.operationTimer) clearTimeout(this.operationTimer);
      this.operationTimer = null;
    },
  },
};
</script>

<style scoped>
.page {
  min-height: 100vh;
  padding: 28rpx;
  box-sizing: border-box;
  background: #0a0a0a;
}
.section-head,
.debug-head,
.row,
.endpoint-row,
.runtime-state {
  display: flex;
  align-items: center;
}
.section-head,
.debug-head,
.row,
.runtime-state {
  justify-content: space-between;
}
.section-head {
  margin-bottom: 22rpx;
}
.section-title {
  font-size: 36rpx;
  font-weight: 650;
}
.status,
.debug-badge {
  padding: 8rpx 14rpx;
  border: 1px solid #333;
  border-radius: 10rpx;
  font-size: 21rpx;
}
.status.online {
  color: #7fd99a;
  border-color: rgba(127, 217, 154, 0.4);
}
.status.offline {
  color: #8b8b8b;
}
.card {
  margin-bottom: 22rpx;
  padding: 26rpx;
  border: 1px solid #2a2a2a;
  border-radius: 14rpx;
  background: #141414;
}
.label,
.muted,
.debug-sub,
.tip {
  color: #8b8b8b;
}
.label {
  display: block;
  margin-bottom: 16rpx;
  font-size: 22rpx;
}
.endpoint-row {
  gap: 14rpx;
}
.input {
  box-sizing: border-box;
  height: 80rpx;
  padding: 0 20rpx;
  border: 1px solid #333;
  border-radius: 10rpx;
  background: #0a0a0a;
  color: #e8e8e8;
  font-size: 25rpx;
}
.host-input {
  flex: 1;
}
.port-input {
  width: 180rpx;
}
.pin-input {
  width: 100%;
  margin: 22rpx 0 16rpx;
}
button {
  margin-top: 16rpx;
  border-radius: 10rpx;
  font-size: 26rpx;
}
.primary-btn,
.start-btn {
  background: #2a4060;
  color: #e6edff;
}
.secondary-btn,
.debug-entry,
.exit-btn {
  border: 1px solid #383838;
  background: #1a1a1a;
  color: #dedede;
}
.stop-btn {
  border: 1px solid #703d3d;
  background: #301919;
  color: #f2d7d7;
}
button[disabled] {
  opacity: 0.45;
}
.tip,
.message,
.operation-result {
  display: block;
  margin-top: 16rpx;
  font-size: 22rpx;
  line-height: 1.5;
}
.row {
  padding: 13rpx 0;
  border-bottom: 1px solid #272727;
  font-size: 24rpx;
}
.row:last-of-type {
  border-bottom: 0;
}
.mono {
  font-family: ui-monospace, monospace;
}
.value,
.runtime-value {
  color: #d8e2fa;
}
.message,
.operation-result {
  color: #c9d7ff;
}
.debug-title {
  display: block;
  font-size: 29rpx;
  font-weight: 600;
}
.debug-sub {
  display: block;
  margin-top: 6rpx;
  font-size: 21rpx;
}
.debug-badge {
  color: #e6c07b;
  border-color: rgba(230, 192, 123, 0.45);
}
.runtime-state {
  margin-top: 22rpx;
  padding: 18rpx 0;
  border-top: 1px solid #2a2a2a;
  border-bottom: 1px solid #2a2a2a;
  font-size: 24rpx;
}
</style>
