# Phone Voice App — 手机流式语音 → 昇腾板端 ASR

界面简洁（深色 Cursor 风格）。手机浏览器即可使用，无需上架 App Store。

## 目录

```text
phone_voice_app/
├── README.md
├── start.bat / start.ps1     # 一键启动
├── server/
│   ├── bridge.py             # PC 桥接：WS ↔ 板端 18081/18083
│   ├── stream_protocol.py
│   └── requirements.txt
└── web/
    ├── index.html
    └── src/
        ├── styles.css
        ├── app.js
        └── mic.js            # 流式采麦 + 重采样 16kHz
```

## 数据流（流式）

```text
手机麦（边录边发）
  → WebSocket /ws（每 200ms float32）
  → PC bridge.py
  → 板端 TCP 18081（与 pc_audio_sender 同协议）
  → 板端 CTC 流式识别
  → 板端连回 PC 18083
  → bridge 推送到手机（partial / final）
```

## 使用前

1. **板子已接电脑**，板端运行时已启动（会开 `18081` 收音、并向 PC `18083` 推结果）。
2. 手机和**电脑在同一 WiFi**（USB 共享网一般是电脑 `192.168.137.1`、板子 `192.168.137.100`；手机需能访问电脑局域网 IP）。
3. **先关掉**其它占用 `18083` 的程序（如 `pc_asr_terminal` / `board_bridge`），否则本桥接收不到回传字。若只要推音频、由主链路收识别，可加 `--no-asr-listen`。

## 启动

```powershell
cd F:\jichuang2026\clean_0606\phone_voice_app
.\start.bat
```

或：

```powershell
cd server
pip install -r requirements.txt
python bridge.py --board-host 192.168.137.100
```

手机与电脑同一 WiFi，打开控制台里的地址，例如：

- `https://127.0.0.1:8788/`（本机试）
- `https://<电脑局域网IP>:8788/`（**手机必须用 https**）

> iPhone / 多数手机在 **http://** 下会禁止麦克风（你看到的 `getUserMedia` 报错就是这个原因）。  
> 第一次打开 https 会提示「证书不受信任」→ 点 **高级 → 继续访问**。

手机页面：**按住说话** → 松手停止。上方「识别中」为流式 partial，「已确认」为整句 final。  
**电脑黑窗口**会同步打印：`[bridge] partial: …` / `[bridge] final: …`。

## 常用参数

| 参数 | 默认 | 说明 |
|------|------|------|
| `--board-host` | `192.168.137.100` | 板子 IP |
| `--http-port` | `8788` | 手机访问端口 |
| `--no-asr-listen` | 关 | 不占用 18083 |
| `--skip-board-connect` | 关 | 只测网页 UI |

环境变量：`PHONE_VOICE_BOARD_HOST`、`PHONE_VOICE_PORT`。

## 注意

- **流式**：是的，分片实时上传，不是录完再传。
- **iPhone**：部分机型要求 HTTPS 才能开麦；可先用 Android / 电脑 Chrome 验证链路。
- 防火墙若拦 8788，请放行入站，或临时关防火墙试一次。
