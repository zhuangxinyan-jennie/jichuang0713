# CosyVoice Live Release

这是一个轻量转交包，只包含我们写的实时 TTS 程序、默认音色 preset 和参考音频。它不包含 20G 的 Python 环境和模型，接收方需要按下面说明安装运行环境。

## 目录内容

```text
cosyvoice_live_release/
  start.sh                         # 交互式启动入口
  check_env.sh                     # 环境检查
  requirements-tested.txt          # 本机测试过的关键版本
  scripts/cosyvoice_repl.py         # 常驻模型、输入一句生成一句
  scripts/cosyvoice_reference_clone.py
  scripts/presets/xiongda_live.json
  assets/ref_audio/xiongda_fish.wav
  outputs/cosyvoice_live/           # 默认输出目录
```

## 接收方需要安装

推荐环境：

- Linux / Ubuntu
- Python 3.10
- NVIDIA GPU 和可用驱动
- `git`
- `ffmpeg` 或 `alsa-utils` / `pulseaudio-utils`，用于播放音频
- CosyVoice 源码
- CosyVoice2-0.5B 模型
- Python 依赖：PyTorch、torchaudio、modelscope、CosyVoice requirements、vLLM、TensorRT 相关包

## 推荐目录结构

把本目录放在工程根目录下，然后让 CosyVoice 和模型位于相邻目录：

```text
project/
  cosyvoice_live_release/
  third_party/CosyVoice/
  pretrained_models/CosyVoice2-0.5B/
```

如果目录不是这个结构，也可以用环境变量指定路径，见后文。

## 安装 CosyVoice

```bash
mkdir -p third_party
git clone git@github.com:FunAudioLLM/CosyVoice.git third_party/CosyVoice
cd third_party/CosyVoice
git checkout ace7c47
cd ../..
```

`ace7c47` 是当前这套脚本测试过的 CosyVoice 提交。新版 CosyVoice 也可能可用，但如果出现接口变化，优先回到这个提交。

## 创建 Python 环境

```bash
python3.10 -m venv third_party/CosyVoice/.venv-clean
third_party/CosyVoice/.venv-clean/bin/python -m pip install -U pip "setuptools<81" wheel
```

安装 CosyVoice 依赖：

```bash
third_party/CosyVoice/.venv-clean/bin/python -m pip install \
  -r third_party/CosyVoice/requirements.txt \
  -i https://mirrors.aliyun.com/pypi/simple/ \
  --trusted-host=mirrors.aliyun.com
```

安装 vLLM 加速依赖：

```bash
third_party/CosyVoice/.venv-clean/bin/python -m pip install \
  vllm==0.9.0 transformers==4.51.3 numpy==1.26.4 \
  -i https://mirrors.aliyun.com/pypi/simple/ \
  --trusted-host=mirrors.aliyun.com
```

如果依赖冲突，参考 `requirements-tested.txt` 里的关键版本。本地验证环境使用的是 `torch==2.7.0`、`torchaudio==2.7.0`、`vllm==0.9.0`、`transformers==4.51.3`。

## 下载模型

```bash
mkdir -p pretrained_models
third_party/CosyVoice/.venv-clean/bin/python - <<'PY'
from modelscope import snapshot_download
snapshot_download(
    "iic/CosyVoice2-0.5B",
    local_dir="pretrained_models/CosyVoice2-0.5B",
)
PY
```

需要的核心模型文件包括：

```text
cosyvoice2.yaml
llm.pt
flow.pt
hift.pt
campplus.onnx
speech_tokenizer_v2.onnx
CosyVoice-BlankEN/
```

如果要启用最快模式，还需要：

```text
vllm/model.safetensors
flow.decoder.estimator.fp16.mygpu.plan
```

这两个文件可以在首次启动 `--load-vllm` / `--load-trt` 时由程序生成。TensorRT 的 `.plan` 和目标机器的 GPU / TensorRT 版本相关，换机器后建议重新生成。

## 检查环境

在 `cosyvoice_live_release` 目录里执行：

```bash
./check_env.sh
```

如果 CosyVoice 或模型不在推荐目录结构里，用环境变量指定：

```bash
COSYVOICE_REPO=/path/to/CosyVoice \
COSYVOICE_MODEL_DIR=/path/to/CosyVoice2-0.5B \
COSYVOICE_PYTHON=/path/to/python \
./check_env.sh
```

## 启动实时交互

```bash
cd cosyvoice_live_release
./start.sh
```

启动后输入中文文本并回车，会生成并播放一条语音。输入 `:q` 退出。

默认启动的是最快模式：

```text
fp16 + JIT + TensorRT + vLLM + low-latency streaming
```

如果显存不够：

```bash
./start.sh --vllm-gpu-memory-utilization 0.65
```

如果 TensorRT 或 vLLM 没装好，先用安全模式验证：

```bash
COSYVOICE_ACCEL=safe ./start.sh
```

如果没有 GPU，只做 CPU 验证：

```bash
COSYVOICE_ACCEL=cpu ./start.sh --no-play
```

## 常用环境变量

```bash
COSYVOICE_REPO=/path/to/CosyVoice
COSYVOICE_MODEL_DIR=/path/to/CosyVoice2-0.5B
COSYVOICE_PYTHON=/path/to/CosyVoice/.venv-clean/bin/python
COSYVOICE_OUTPUT_DIR=/path/to/outputs
COSYVOICE_ACCEL=full   # full / safe / cpu
```

## 打包给别人

只需要打包这个轻量目录：

```bash
tar -czf cosyvoice_live_release.tar.gz cosyvoice_live_release
```

接收方解压后，按本文安装 CosyVoice 源码、Python 依赖和 CosyVoice2-0.5B 模型即可运行。
