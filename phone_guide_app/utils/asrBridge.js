const CLIENT_TOKEN_KEY = "gateway_client_token";
const USER_ID_KEY = "gateway_user_id";
const BRIDGE_HOST_KEY = "pc_host";
const BRIDGE_PORT_KEY = "bridge_port";
const BRIDGE_INSECURE_KEY = "bridge_insecure";

/** 默认直连板端 Gateway；也可在连接页改成电脑中转地址。 */
export function getBridgeHost() {
  return String(uni.getStorageSync(BRIDGE_HOST_KEY) || "192.168.137.100").trim();
}

export function setBridgeHost(host) {
  uni.setStorageSync(BRIDGE_HOST_KEY, String(host || "").trim());
}

export function getBridgePort() {
  const value = Number(uni.getStorageSync(BRIDGE_PORT_KEY) || 8788);
  return Number.isInteger(value) && value > 0 && value <= 65535 ? value : 8788;
}

export function setBridgeEndpoint({ host, port = 8788, insecure = false }) {
  const cleanHost = String(host || "").trim();
  const cleanPort = Number(port);
  if (!cleanHost) throw new Error("缺少板子 IP");
  if (!Number.isInteger(cleanPort) || cleanPort <= 0 || cleanPort > 65535) {
    throw new Error("Gateway 端口无效");
  }
  uni.setStorageSync(BRIDGE_HOST_KEY, cleanHost);
  uni.setStorageSync(BRIDGE_PORT_KEY, cleanPort);
  if (insecure) uni.setStorageSync(BRIDGE_INSECURE_KEY, "1");
  else uni.removeStorageSync(BRIDGE_INSECURE_KEY);
}

/** @deprecated 兼容旧名 */
export function getPcHost() {
  return getBridgeHost();
}
/** @deprecated */
export function setPcHost(host) {
  setBridgeHost(host);
}

export function bridgeHttpBase() {
  const scheme = uni.getStorageSync(BRIDGE_INSECURE_KEY) ? "http" : "https";
  return `${scheme}://${getBridgeHost()}:${getBridgePort()}`;
}

export function bridgeWsUrl() {
  const token = getGatewayIdentity().token;
  if (!token) return "";
  const useSecure = !uni.getStorageSync(BRIDGE_INSECURE_KEY);
  const scheme = useSecure ? "wss" : "ws";
  return `${scheme}://${getBridgeHost()}:${getBridgePort()}/ws?token=${encodeURIComponent(token)}`;
}

export function previewSnapshotUrl(cacheKey = Date.now()) {
  const token = getGatewayIdentity().token;
  if (!token) return "";
  return `${bridgeHttpBase()}/api/v1/video/latest.jpg?token=${encodeURIComponent(token)}&t=${encodeURIComponent(cacheKey)}`;
}

export function previewMjpegUrl() {
  const token = getGatewayIdentity().token;
  if (!token) return "";
  return `${bridgeHttpBase()}/api/v1/video/preview.mjpg?token=${encodeURIComponent(token)}`;
}

export function getGatewayIdentity() {
  return {
    token: String(uni.getStorageSync(CLIENT_TOKEN_KEY) || ""),
    userId: String(uni.getStorageSync(USER_ID_KEY) || ""),
  };
}

export function clearGatewayIdentity() {
  uni.removeStorageSync(CLIENT_TOKEN_KEY);
  uni.removeStorageSync(USER_ID_KEY);
}

function gatewayRequest(path, { method = "GET", data, token, adminToken } = {}) {
  const headers = { "Content-Type": "application/json" };
  const clientToken = token === undefined ? getGatewayIdentity().token : token;
  if (clientToken) headers.Authorization = `Bearer ${clientToken}`;
  if (adminToken) headers["X-Admin-Token"] = adminToken;

  return new Promise((resolve, reject) => {
    uni.request({
      url: `${bridgeHttpBase()}${path}`,
      method,
      data,
      header: headers,
      timeout: 5000,
      success(response) {
        const status = Number(response.statusCode || 0);
        if (status >= 200 && status < 300) {
          resolve(response.data || {});
          return;
        }
        const body = response.data && typeof response.data === "object" ? response.data : {};
        const error = new Error(body.message || `Gateway 请求失败 (${status})`);
        error.code = body.code || "GATEWAY_ERROR";
        error.status = status;
        reject(error);
      },
      fail(error) {
        reject(new Error((error && error.errMsg) || "无法连接板端 Gateway"));
      },
    });
  });
}

export async function pairGateway() {
  const previous = getGatewayIdentity();
  const result = await gatewayRequest("/api/v1/pair", {
    method: "POST",
    token: "",
    data: previous.token ? { resume_token: previous.token } : {},
  });
  if (!result.token || !result.user_id) throw new Error("Gateway 配对响应不完整");
  uni.setStorageSync(CLIENT_TOKEN_KEY, result.token);
  uni.setStorageSync(USER_ID_KEY, result.user_id);
  return result;
}

export function heartbeatGateway() {
  return gatewayRequest("/api/v1/client/heartbeat", { method: "POST", data: {} });
}

export function fetchGatewayState() {
  return gatewayRequest("/api/v1/state");
}

export function joinConversationQueue() {
  return gatewayRequest("/api/v1/queue/join", { method: "POST", data: {} });
}

export function leaveConversationQueue() {
  return gatewayRequest("/api/v1/queue/leave", { method: "POST", data: {} });
}

export function acceptConversation() {
  return gatewayRequest("/api/v1/session/accept", { method: "POST", data: {} });
}

export function touchConversation() {
  return gatewayRequest("/api/v1/session/activity", { method: "POST", data: {} });
}

export function completeConversationTurn() {
  return gatewayRequest("/api/v1/session/turn-complete", { method: "POST", data: {} });
}

export function endConversation() {
  return gatewayRequest("/api/v1/session/end", { method: "POST", data: {} });
}

export function loginDebugMode(pin) {
  return gatewayRequest("/api/v1/admin/login", {
    method: "POST",
    token: "",
    data: { pin: String(pin || "") },
  });
}

export function startBoardRuntime(adminToken) {
  return gatewayRequest("/api/v1/admin/runtime/start", { method: "POST", data: {}, adminToken });
}

export function stopBoardRuntime(adminToken) {
  return gatewayRequest("/api/v1/admin/runtime/stop", { method: "POST", data: {}, adminToken });
}

export function fetchRuntimeOperation(adminToken, operationId) {
  return gatewayRequest(`/api/v1/admin/runtime/operations/${encodeURIComponent(operationId)}`, {
    adminToken,
  });
}

export function startGatewayHeartbeat({ onState, onError, intervalMs = 3000 } = {}) {
  let stopped = false;
  let timer = null;

  const poll = async () => {
    if (stopped) return;
    try {
      await heartbeatGateway();
      const state = await fetchGatewayState();
      if (!stopped && onState) onState(state);
    } catch (error) {
      if (!stopped && onError) onError(error);
    } finally {
      if (!stopped) timer = setTimeout(poll, intervalMs);
    }
  };

  void poll();
  return () => {
    stopped = true;
    if (timer) clearTimeout(timer);
  };
}

export function parseJoinCode(rawValue) {
  const raw = String(rawValue || "").trim();
  if (!raw) throw new Error("二维码为空");
  const normalized = raw.startsWith("xiongda://")
    ? raw.replace(/^xiongda:\/\//, "https://xiongda.local/")
    : raw;
  let parsed;
  try {
    parsed = new URL(normalized);
  } catch (_) {
    throw new Error("二维码格式无效");
  }
  const host = parsed.searchParams.get("host") || parsed.hostname;
  const port = Number(parsed.searchParams.get("port") || parsed.port || 8788);
  if (!host) throw new Error("二维码缺少板子 IP");
  return { host, port, insecure: parsed.searchParams.get("secure") === "0" };
}

export function createAsrSocket({ onStatus, onPartial, onFinal, onAgentResponse, onSessionEnd, onError }) {
  let socketTask = null;
  let opened = false;
  let stopped = false;
  let reconnectTimer = null;

  function connect() {
    if (stopped) return;
    const url = bridgeWsUrl();
    if (!url) {
      onStatus && onStatus("unpaired", "请先在设备页连接板子");
      reconnectTimer = setTimeout(connect, 2500);
      return;
    }
    onStatus && onStatus("connecting", `连接 ${getBridgeHost()}:${getBridgePort()}`);
    socketTask = uni.connectSocket({
      url,
      // 自签证书：App 端常需在 manifest 放行；HBuilder 真机调试请勾选不校验
      success() {},
    });

    socketTask.onOpen(() => {
      opened = true;
      onStatus && onStatus("open", "已连接（直连板子或电脑桥接）");
      try {
        socketTask.send({ data: JSON.stringify({ type: "ping" }) });
      } catch (_) {}
    });

    socketTask.onMessage((res) => {
      let data = res.data;
      if (typeof data !== "string") return;
      let msg;
      try {
        msg = JSON.parse(data);
      } catch (_) {
        return;
      }
      if (msg.type === "partial") onPartial && onPartial(msg.text || "");
      else if (msg.type === "final") onFinal && onFinal(msg.text || "");
      else if (msg.type === "agent_response") {
        onAgentResponse && onAgentResponse(msg.payload, msg);
        if (msg.session_ended) onSessionEnd && onSessionEnd(msg);
      }
      else if (msg.type === "status")
        onStatus && onStatus(msg.board_connected ? "board_ok" : "board_warn", msg.message || "");
      else if (msg.type === "error") onError && onError(msg.message || "错误");
    });

    socketTask.onClose(() => {
      opened = false;
      if (stopped) return;
      onStatus && onStatus("closed", "连接已断开，正在重连…");
      reconnectTimer = setTimeout(connect, 2500);
    });

    socketTask.onError((e) => {
      onError && onError((e && e.errMsg) || "WebSocket 错误（请确认电脑已开 bridge 且用 wss）");
    });
  }

  connect();

  return {
    sendPcmFloat32(float32Array) {
      if (!opened || !socketTask) return;
      // uni App 可直接发 ArrayBuffer
      const buf = float32Array.buffer.slice(
        float32Array.byteOffset,
        float32Array.byteOffset + float32Array.byteLength
      );
      socketTask.send({ data: buf });
    },
    close() {
      stopped = true;
      opened = false;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      try {
        socketTask && socketTask.close({});
      } catch (_) {}
    },
  };
}

/** Int16 PCM → Float32 [-1,1] */
export function int16ToFloat32(int16) {
  const out = new Float32Array(int16.length);
  for (let i = 0; i < int16.length; i++) {
    out[i] = Math.max(-1, Math.min(1, int16[i] / 32768));
  }
  return out;
}
