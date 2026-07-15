import { StreamMic } from "./mic.js";

const els = {
  connPill: document.getElementById("connPill"),
  partialText: document.getElementById("partialText"),
  finalText: document.getElementById("finalText"),
  boardLabel: document.getElementById("boardLabel"),
  statusLabel: document.getElementById("statusLabel"),
  urlLabel: document.getElementById("urlLabel"),
  talkBtn: document.getElementById("talkBtn"),
  talkLabel: document.getElementById("talkLabel"),
};

function setPill(kind, text) {
  els.connPill.className = `pill pill-${kind}`;
  els.connPill.textContent = text;
}

function wsUrl() {
  const proto = location.protocol === "https:" ? "wss:" : "ws:";
  return `${proto}//${location.host}/ws`;
}

let socket = null;
let speaking = false;
const mic = new StreamMic((chunk) => {
  if (socket && socket.readyState === WebSocket.OPEN) {
    socket.send(chunk.buffer);
  }
});

async function refreshInfo() {
  try {
    const res = await fetch("/api/info", { cache: "no-store" });
    const data = await res.json();
    els.boardLabel.textContent = `${data.board_host}:${data.board_audio_port}`;
    els.urlLabel.textContent = (data.phone_urls && data.phone_urls[0]) || location.href;
    if (!data.board_audio_connected) {
      els.statusLabel.textContent = "桥接在线，板端音频未连接";
    }
  } catch (_) {
    /* ignore */
  }
}

function connectWs() {
  setPill("muted", "连接中…");
  els.statusLabel.textContent = "正在连接桥接服务";
  socket = new WebSocket(wsUrl());
  socket.binaryType = "arraybuffer";

  socket.onopen = () => {
    setPill("ok", "已连接");
    els.statusLabel.textContent = "WebSocket 已连接";
    socket.send(JSON.stringify({ type: "ping" }));
  };

  socket.onclose = () => {
    setPill("warn", "已断开");
    els.statusLabel.textContent = "连接断开，3 秒后重试…";
    setTimeout(connectWs, 3000);
  };

  socket.onerror = () => {
    setPill("err", "连接错误");
  };

  socket.onmessage = (ev) => {
    let data;
    try {
      data = JSON.parse(ev.data);
    } catch (_) {
      return;
    }
    if (data.type === "partial") {
      els.partialText.textContent = data.text || "…";
    } else if (data.type === "final") {
      els.finalText.textContent = data.text || "—";
      els.partialText.textContent = "等待说话…";
    } else if (data.type === "status") {
      els.statusLabel.textContent = data.message || "就绪";
      if (data.board_host) {
        els.boardLabel.textContent = String(data.board_host);
      }
      if (data.board_connected === false) {
        setPill("warn", "板端未连");
      } else if (data.board_connected === true) {
        setPill("ok", "板端就绪");
      }
    } else if (data.type === "error") {
      els.statusLabel.textContent = data.message || "错误";
      setPill("err", "转发失败");
    }
  };
}

async function startTalk() {
  if (speaking) return;
  speaking = true;
  els.talkBtn.classList.add("is-active");
  els.talkBtn.setAttribute("aria-pressed", "true");
  els.talkLabel.textContent = "正在听取…";
  try {
    await mic.start();
    els.statusLabel.textContent = "流式发送中";
  } catch (e) {
    speaking = false;
    els.talkBtn.classList.remove("is-active");
    els.talkLabel.textContent = "按住说话";
    els.statusLabel.textContent = `无法开麦: ${e && e.message ? e.message : e}`;
    setPill("err", "麦权限");
  }
}

async function stopTalk() {
  if (!speaking) return;
  speaking = false;
  els.talkBtn.classList.remove("is-active");
  els.talkBtn.setAttribute("aria-pressed", "false");
  els.talkLabel.textContent = "按住说话";
  await mic.stop();
  els.statusLabel.textContent = "已停止发送";
}

function bindTalk() {
  const btn = els.talkBtn;
  btn.addEventListener("pointerdown", (e) => {
    e.preventDefault();
    btn.setPointerCapture?.(e.pointerId);
    void startTalk();
  });
  const end = (e) => {
    e.preventDefault();
    void stopTalk();
  };
  btn.addEventListener("pointerup", end);
  btn.addEventListener("pointercancel", end);
  btn.addEventListener("pointerleave", (e) => {
    if (speaking) end(e);
  });
}

els.urlLabel.textContent = location.href;
bindTalk();
connectWs();
void refreshInfo();
setInterval(() => void refreshInfo(), 8000);
