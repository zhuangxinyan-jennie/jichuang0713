# CosyVoice TTS 服务

安装与模型下载见 **[../docs/PC.md](../docs/PC.md)** § CosyVoice。

## 两种后端

| 后端 | 启动 | 说明 |
|------|------|------|
| **本地 GPU**（默认） | `.\start_tts_gpu.ps1` | 本机 CosyVoice，3050 上较慢 |
| **阿里云百炼**（推荐变快） | `.\start_tts_cloud.ps1` | 云端 CosyVoice + 熊大复刻音色，不占本机 GPU |

## 谁在调用谁？（重要）

**板子不会去调 TTS API。** 实际链路是：

```
PC 网页/脚本 → PC 上的 tts_server（本地或云端百炼）→ 合成 WAV
                    ↓
         POST 到板子 http://192.168.137.100:9891/play
                    ↓
              板子音箱播出
```

- 前端默认请求 PC：`http://127.0.0.1:9890/api/tts` 或 `/api/tts-play`
- 板子只负责 **播音服务**（`board_speaker_player.py`）

## 分段先出声（已接通）

设了 `BOARD_SPEAKER_URL` 时：

1. 按标点切句  
2. **每句合成完立刻推板子播**（不用等全文）  
3. 上一句播完再合成/推下一句（板子播音是阻塞的）

## 云端熊大声音：复刻 + 调用（一步步）

### 0. 准备 API Key

1. 打开 [阿里云百炼](https://bailian.console.aliyun.com/)
2. 创建 API Key
3. PowerShell：

```powershell
$env:DASHSCOPE_API_KEY = "sk-你的密钥"
$env:DASHSCOPE_COSYVOICE_MODEL = "cosyvoice-v3-flash"
```

也可参考 `env.dashscope.example`。

### 1. 声音复刻（只用做一次）

用本地熊大参考音 `assets/ref_audio/xiongda_fish.wav`：

```powershell
cd cosyvoice_live_release
$env:PYTHONPATH = "$pwd;$pwd\scripts"
# 需要 requests： pip install requests
python scripts\enroll_xiongda_dashscope.py
```

成功后会生成 `outputs/dashscope_xiongda_voice.json`（含 `voice_id`）。

若自动上传公网失败，可把 wav 传到 OSS/网盘拿到公网 URL 后：

```powershell
python scripts\enroll_xiongda_dashscope.py --url "https://你的公网地址/xiongda_fish.wav"
```

### 2. 启动云端 TTS 服务

```powershell
.\start_tts_cloud.ps1 -StopExisting -Background -Port 9890
```

### 3. 合成并推到板子播放

```powershell
$env:BOARD_SPEAKER_URL = "http://192.168.137.100:9891/play"
python scripts\cloud_tts_play.py --text "今天熊大来陪你玩"
```

或 HTTP：

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:9890/api/tts-play `
  -ContentType "application/json" `
  -Body '{"text":"今天熊大来陪你玩","device":"cloud"}'
```

## 本地 GPU 显存上限

| 环境变量 | 含义 | 默认 |
|----------|------|------|
| `COSYVOICE_GPU_MEMORY_FRACTION` | 本机进程最多占显存比例；`0`=不限制 | `0.3` |

仅对 **本地后端** 生效；云端后端不占本机显存。

## 注意

- 云端音色是 **复刻近似熊大**，不是保证与本地 100% 相同。
- 复刻时的 `DASHSCOPE_COSYVOICE_MODEL` 必须与后续合成一致。
- `DASHSCOPE_API_KEY` 不要提交到 Git。

## 可能的改进

- 把前端默认切到云端 TTS，本机 3050 只做显示。
- 复刻失败时提供 OSS 上传脚本（国内更稳）。
