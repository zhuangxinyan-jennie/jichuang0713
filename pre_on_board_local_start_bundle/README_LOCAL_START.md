本包只包含本地启动与本地显示/发送所需内容。

## Windows：PC 端离线 ASR（FunASR）环境

系统自带的 Python 3.13 在 Windows 上安装 `funasr` 常会因 `editdistance` 无预编译包而编译失败。建议在**项目根目录**创建可写的 Conda 环境（需已安装 [Miniconda](https://docs.conda.io/en/latest/miniconda.html) 或 Anaconda）：

```text
conda create -y -p .conda_env python=3.11 editdistance -c conda-forge
.\.conda_env\python.exe -m pip install torch torchaudio funasr opencv-python pillow numpy paramiko sounddevice
```

安装完成后直接运行下面的 `run_all.py`：启动器会**自动优先使用** `.conda_env` 下的 Python（常见为 `Scripts\python.exe`，部分环境仅有根目录 `python.exe`）拉起本机的 viewer / sender，字幕窗口即可加载 FunASR。

**PC 整句离线推理**：默认开启（收到板端 `asr_final` 且带音频时会用本机 FunASR 再跑一遍）。需将模型缓存放到  
`sound_to_text/voice_asr/.cache/modelscope/models/iic/speech_seaco_paraformer_large_asr_nat-zh-cn-16k-common-vocab8404-pytorch`  
（可与 ModelScope / FunASR 文档中的同名模型目录一致）。缺少目录时日志会 WARN，此时「整句」仍以板端流式结果为准。

禁用离线推理：`python run_all.py --no-pc-offline-asr`，或直接运行字幕 viewer 时加 `--no-offline-asr`。

可选：安装 [ffmpeg](https://ffmpeg.org/) 并加入 PATH，可改善音频读取相关提示。

## 启动

建议启动方式：
  python3 start_all.py

也可用：
  python3 run_all.py

### Bear Agent + 网页熊大（与 board_bridge 共用端口）

板端回连 PC 使用 **TCP 18082（画面）**、**18083（语音）**。  
本包自带的 **`pc_result_viewer` / `pc_asr_result_viewer`** 与 **`bear_agent/board_bridge`** 会**争夺同一端口**，不能同时监听。

- **只要本地 OpenCV 预览窗口**：`python run_all.py`（默认）。
- **要走 Agent → xiongda_app 全自动**：先在本机启动 `bear_agent/integration_test/server.py`，再执行：

```text
python run_all.py --bear-bridge
```

可选：`--bear-agent-root F:\path\to\bear_agent` 或环境变量 **`BEAR_AGENT_ROOT`**；会自动在上级目录中查找 `bear_agent`。  
`board_bridge` 日志：`logs/bear_board_bridge.log`；落盘 JSON 默认在 **`pc_received_output/`**。

**结束本机进程**：启动器用后台进程拉起 viewer/sender/board_bridge，脚本会很快退出。要在 PC 上关掉摄像头推流、预览和 board_bridge，可在本包根目录执行：`python run_all.py --stop`（不会通过 SSH 停板端服务）。

然后用 **`npm run dev`** 打开前端，勾选「板端自动同步 WebGL」。详见 **`bear_agent/README.md`**。

包含：
- Python 启动器
- 本地视频/字幕 viewer
- 本地音频/视频 sender
- stream_protocol
- PC 端整句增强需要的最小 ASR 源码与离线模型缓存

不包含：
- 板端 .om 模型
- 板端 runtime 脚本
- 模型导出环境
- 中间 ONNX/训练文件
