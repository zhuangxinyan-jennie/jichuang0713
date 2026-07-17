# 在 Windows 电脑上使用 CANN/ATC 编译 310B OM

## 1. 当前环境结论

- 板端芯片：`Ascend310B4`。
- 板端 CANN：目录版本为 `8.0.0`，内部 toolkit/compiler 版本为 `7.6.0.1.220`，时间戳为 `2024-12-31`。
- 电脑 WSL2：Ubuntu 22.04.5 LTS、x86_64。
- ATC 是离线模型编译器，电脑不需要昇腾 NPU，也不需要安装 NPU 驱动。
- Windows 不能直接运行 Linux 版 ATC，应在 WSL2 Ubuntu 中安装 x86_64 CANN Toolkit。
- 2026-07-17 检查时板端没有仍在运行的 ATC 进程。

## 2. CANN 下载位置

昇腾官方社区下载页：

<https://www.hiascend.com/developer/download/community/result?module=cann>

板端时间戳对应社区版 CANN `8.0.0.alpha003`。官方下载接口确认需要：

1. `Ascend-cann-toolkit_8.0.0.alpha003_linux-x86_64.run`
2. `Ascend-cann-kernels-310b_8.0.0.alpha003_linux-x86_64.run`

本次使用的官方 OBS 目录为：

```text
https://ascend-repo.obs.cn-east-2.myhuaweicloud.com/Milan-ASL/Milan-ASL%20V100R001C20SPC703/
```

必须选择两个 `x86_64` 包，不能把板端使用的 `aarch64` 包安装到电脑。

不建议直接安装比板端更新很多的 CANN 版本。新版 ATC 生成的 OM 不保证能被板端 CANN 8.0.0 runtime 加载。

## 3. 安装 WSL2 Ubuntu

在用户自己的管理员 PowerShell 中执行：

```powershell
wsl --install -d Ubuntu-22.04
```

若 Microsoft Store 路径不可用，可尝试：

```powershell
wsl --install --web-download -d Ubuntu-22.04
```

按提示重启，然后从开始菜单打开 Ubuntu，创建 Linux 用户名和密码。验证：

```powershell
wsl -d Ubuntu-22.04 -- bash -lc "uname -m; cat /etc/os-release"
```

预期架构为 `x86_64`。

## 4. 安装 CANN Toolkit

假设两个安装包已下载到 Windows 的 `C:\Users\tanza\Downloads`，在 Ubuntu 终端执行：

```bash
sudo apt update
sudo apt install -y build-essential cmake python3 python3-pip zlib1g-dev \
  libsqlite3-dev libssl-dev libffi-dev libbz2-dev liblzma-dev pciutils

cd /mnt/c/Users/tanza/Downloads
chmod +x Ascend-cann-toolkit_8.0.0.alpha003_linux-x86_64.run
sudo ./Ascend-cann-toolkit_8.0.0.alpha003_linux-x86_64.run --quiet --install --install-for-all
```

然后按实际下载文件名安装 310B kernels 包：

```bash
chmod +x Ascend-cann-kernels-310b_8.0.0.alpha003_linux-x86_64.run
sudo ./Ascend-cann-kernels-310b_8.0.0.alpha003_linux-x86_64.run --quiet --install --install-for-all
```

验证安装：

```bash
source /usr/local/Ascend/ascend-toolkit/set_env.sh
atc --version
ls /usr/local/Ascend/ascend-toolkit/latest/opp/built-in/op_impl/ai_core/tbe/kernel/config/ascend310b
```

电脑没有昇腾驱动是正常情况。脚本会把 Toolkit 的 `devlib/linux/x86_64` 加入 `LD_LIBRARY_PATH`，供 ATC 离线编译使用。

本机第一次使用默认 8 个 TBE 编译进程时触发 WSL OOM。脚本现默认设置 `MAX_COMPILE_CORE_NUMBER=2`，并启用持久算子缓存；在 7.6GiB WSL 内存环境下已成功编译。

## 5. 在电脑上编译 AIPP + DFL 改写模型

项目已经提供：

```text
pre_on_board/board_deploy/compile_pose_aipp_in_wsl.sh
```

在 Ubuntu 终端中进入 Windows 工程。由于父目录包含中文、空格和感叹号，推荐先用资源管理器定位目录，再在 Ubuntu 中使用带引号的 `/mnt/c/...` 路径。执行：

```bash
cd "/mnt/c/Users/tanza/Desktop/快点学习！/第十届集创赛/board_full_project"
chmod +x pre_on_board/board_deploy/compile_pose_aipp_in_wsl.sh
bash pre_on_board/board_deploy/compile_pose_aipp_in_wsl.sh
```

脚本会先把 ONNX 和 AIPP 配置复制到 WSL 的纯 Linux 路径，再执行：

```text
ATC target: Ascend310B4
input: NCHW 1,3,640,640
AIPP input: uint8 BGR
```

默认输出：

```text
pre_on_board/models_om/yolo11n_pose_640_aipp_dfl_rewrite_pc.om
```

它不会覆盖当前稳定模型 `yolo11n_pose_640_aipp.om`。

## 6. 上传板子

在 Windows PowerShell 执行：

```powershell
scp -i $env:USERPROFILE\.ssh\atlas310b_codex `
  "board_full_project\pre_on_board\models_om\yolo11n_pose_640_aipp_dfl_rewrite_pc.om" `
  root@192.168.1.108:/home/HwHiAiUser/pre_on_board/models_om/
```

上传后必须先做 golden 输入精度验证和独立延迟测试，再接入完整 runtime。不能仅凭 ATC 编译成功替换生产模型。

## 7. 2026-07-17 实际执行状态

- Toolkit 和 310B kernels 均安装成功：`/usr/local/Ascend/ascend-toolkit`。
- AIPP + DFL 改写 OM 编译成功：`yolo11n_pose_640_aipp_dfl_rewrite_pc.om`。
- 同编译器 A/B 基线编译成功：`yolo11n_pose_640_aipp_pc_baseline.om`。
- 两个 OM 均已上传板端并通过加载、golden 精度和 100 次延迟测试。
- 详细算子级结果见 `POSE_DFL_OPERATOR_OPTIMIZATION_20260717.md`。
