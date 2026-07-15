<template>
  <view class="page">
    <view class="card">
        <text class="label">板子 / 电脑 IP（默认直连板子）</text>
      <input class="input" v-model="host" placeholder="板子 192.168.137.100 或电脑 WiFi IP" />
      <button class="btn" type="primary" @click="save">保存</button>
      <text class="tip">
        【直连板子】默认填 192.168.137.100（需手机能访问该 IP，例如电脑开热点并把 USB 网共享出去）\n
        【走电脑中转】填电脑 WiFi IP，电脑需运行 phone_voice_app 桥接\n
        识别结果：电脑运行 server\\pc_asr_mirror_terminal.py（端口 18084）可在终端看字
      </text>
    </view>
    <view class="card">
      <text class="label">扫码连接（后续导览）</text>
      <button class="btn ghost" @click="scan">扫描大屏二维码</button>
      <text class="tip">二维码内容示例：phoneguide://join?host=192.168.50.134&port=8788</text>
    </view>
  </view>
</template>

<script>
import { getPcHost, setPcHost } from "../../utils/asrBridge.js";

export default {
  data() {
    return { host: getPcHost() };
  },
  methods: {
    save() {
      const h = (this.host || "").trim();
      if (!h) {
        uni.showToast({ title: "请填写 IP", icon: "none" });
        return;
      }
      setPcHost(h);
      uni.showToast({ title: "已保存", icon: "success" });
    },
    scan() {
      uni.scanCode({
        success: (res) => {
          const raw = String(res.result || "");
          let host = "";
          try {
            if (raw.startsWith("phoneguide://")) {
              const q = raw.split("?")[1] || "";
              const sp = new URLSearchParams(q);
              host = sp.get("host") || "";
            } else if (raw.startsWith("https://") || raw.startsWith("http://")) {
              host = raw.replace(/^https?:\/\//, "").split("/")[0].split(":")[0];
            }
          } catch (_) {}
          if (host) {
            this.host = host;
            setPcHost(host);
            uni.showToast({ title: "已写入电脑 IP", icon: "success" });
          } else {
            uni.showToast({ title: "无法解析二维码", icon: "none" });
          }
        },
      });
    },
  },
};
</script>

<style scoped>
.page {
  padding: 28rpx;
}
.card {
  background: #141414;
  border: 1px solid #2a2a2a;
  border-radius: 24rpx;
  padding: 28rpx;
  margin-bottom: 24rpx;
}
.label {
  display: block;
  color: #8b8b8b;
  font-size: 22rpx;
  margin-bottom: 16rpx;
}
.input {
  background: #0a0a0a;
  border: 1px solid #2a2a2a;
  border-radius: 12rpx;
  padding: 20rpx;
  color: #e8e8e8;
  margin-bottom: 20rpx;
}
.btn {
  background: #2a4060;
  color: #dce8ff;
  border-radius: 12rpx;
  margin-bottom: 16rpx;
}
.btn.ghost {
  background: #1a1a1a;
  border: 1px solid #333;
}
.tip {
  display: block;
  white-space: pre-line;
  color: #8b8b8b;
  font-size: 22rpx;
  line-height: 1.5;
}
</style>
