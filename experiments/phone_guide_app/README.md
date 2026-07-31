# Phone Guide App — 直连板子版

## 直连链路

```text
iPhone App
  → wss://192.168.137.100:8788/ws   （板子上的 phone_ws_bridge）
  → 板子本地 TCP 18081               （CTC 识别，不用板载麦）
  → 识别结果 → 手机界面
  → 同时镜像到电脑 192.168.137.1:18084  （PC 终端可看）
```

## 重要：做完直连 ≠ 自动装到 iPhone

还需要用 **HBuilderX**：

1. 安装 HBuilderX  
2. 导入本目录 `phone_guide_app`  
3. 用数据线「运行到 iPhone」或云打包 IPA  

没有苹果开发者账号时，可用 HBuilderX 真机运行调试；正式分发再云打包。

## 电脑上看识别结果

```powershell
cd F:\jichuang2026\clean_0606\phone_voice_app\server
python pc_asr_mirror_terminal.py
```

窗口会打印 `识别中>` / `最终>>`。

## 网络要求（直连关键）

手机必须能 ping 通板子 `192.168.137.100`。

若手机在普通 WiFi、板子在 USB 共享网，通常不通。常见做法：

1. 电脑开热点，手机连电脑热点  
2. 把「USB 以太网 / Remote NDIS」共享给该热点（Windows：网络适配器 → 共享）  
3. 手机浏览器或 App 连接页填：`192.168.137.100`

## 板端服务（已支持标准库直连，不装 aiohttp）

```powershell
# 电脑上执行：上传并启动板端 ASR + phone_ws_bridge
python logs\_deploy_stdlib_direct.py
# 若 ASR 后就绪、桥短暂连不上，再执行：
python logs\_restart_phone_ws.py
```

自检：板子上 `https://127.0.0.1:8788/api/info` 应返回 `"board_audio_connected": true`。

默认 HTTPS 自签证书；HBuilder 真机调试请勾选不校验证书。

## 改动反思 / 常见坑

1. **直连改完了，手机仍装不上？** 正常：App 要用 HBuilderX 单独安装，和板端服务是两件事。  
2. **手机连不上板子 IP？** 多数是 WiFi 与 USB 共享网不通，需电脑热点 + 网卡共享。  
3. **板子不能 pip？** 已改用仅标准库的 `phone_ws_bridge.py`，勿再依赖 aiohttp。
