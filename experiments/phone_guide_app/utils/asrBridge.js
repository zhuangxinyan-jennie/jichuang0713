/**
 * 默认直连板子 WSS；也可在连接页改成电脑 IP。
 */
export function getBridgeHost() {
  return (uni.getStorageSync("pc_host") || "192.168.137.100").trim();
}

export function setBridgeHost(host) {
  uni.setStorageSync("pc_host", String(host || "").trim());
}

/** @deprecated 兼容旧名 */
export function getPcHost() {
  return getBridgeHost();
}
/** @deprecated */
export function setPcHost(host) {
  setBridgeHost(host);
}

export function bridgeWsUrl() {
  const host = getBridgeHost();
  // 板子直连默认 wss；若连不上可在连接页改电脑 IP 走中转
  const useSecure = uni.getStorageSync("bridge_insecure") ? false : true;
  const scheme = useSecure ? "wss" : "ws";
  return `${scheme}://${host}:8788/ws`;
}

export function createAsrSocket({ onStatus, onPartial, onFinal, onError }) {
  let socketTask = null;
  let opened = false;

  function connect() {
    const url = bridgeWsUrl();
    onStatus && onStatus("connecting", `连接 ${url}`);
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
      else if (msg.type === "status")
        onStatus && onStatus(msg.board_connected ? "board_ok" : "board_warn", msg.message || "");
      else if (msg.type === "error") onError && onError(msg.message || "错误");
    });

    socketTask.onClose(() => {
      opened = false;
      onStatus && onStatus("closed", "连接已断开，正在重连…");
      setTimeout(connect, 2500);
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
