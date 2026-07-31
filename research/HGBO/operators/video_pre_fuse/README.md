# VideoPreFuse 算子

## 组成

| 路径 | 说明 |
|------|------|
| `ascendc/VideoPreFuseCustom/` | **Ascend C 算子工程**（msopgen + kernel/host/tiling） |
| `benchmark.py` | HGBO device 入口：写 tiling → 尝试 NPU → 否则 Python reference |
| `tiling_io.py` | 将 HGBO 搜索参数写入 `/tmp/hgbo_vpf_tiling.bin` |
| `npu_runner.py` | 调用 `npu_run_stub.py`（不改 HGBO 主流程） |
| `npu_run_stub.py` | 子进程：先 `npu_run`(aclnn)，再 `npu_run_acl_op.py`(acl.op) |
| `npu_run_acl_op.py` | pyACL 单算子路径，绕过 aclnn（CANN 7.0 + 310B4 常用） |

## HGBO 调用链（保持不变）

```
run_dse.py → benchmark.py → npu_runner.py → npu_run_stub.py → NPU
                ↓
         benchmark_result.json  (backend: ascendc_npu | python)
```

Tiling 参数经 `tiling_io.py` 写入 `/tmp/hgbo_vpf_tiling.bin`，Host `TilingFunc` 在 NPU 执行时读取。

## Ascend C 编译（310B 板子）

```bash
source /usr/local/Ascend/ascend-toolkit/set_env.sh
cd operators/video_pre_fuse/ascendc/VideoPreFuseCustom
bash board_build.sh   # 含 binary + package + npu_run 编译
export ASCEND_CUSTOM_OPP_PATH=/home/HwHiAiUser/custom_opp/vendors/customize
source /home/HwHiAiUser/custom_opp/vendors/customize/bin/set_env.bash
```

Windows 侧一键上传编译：

```bash
python scripts/build_ascendc_on_board.py
python scripts/compile_kernel_b4.py   # 仅重试 kernel opc（SoC 已修正为 B4）
```

## CANN 7.0 RC1 + Ascend310B4 已知限制

| 现象 | 原因 |
|------|------|
| `backend: python`，`compile_status: python_fallback(...)` | NPU 路径未跑通，自动回退 Python |
| aclnn `NnopbaseInit` / `361001` | 可能未装 **kernels-310b**（aclnn/动态 shape 必需） |
| acl.op `100024` | `kernel/ascend310b/video_pre_fuse_custom/` 下无 `.o`/`.json` |
| `opc` 无输出、kernel 目录为空 | **310B4 需要 `dav-m300`，当前 tikcpp 仅有 `dav_c100/c220/m200`** |

### 第一步：补装 kernels-310b（7.0.RC1，与现有 Toolkit 同版本）

板端实测：`/usr/local/Ascend/` 下 **无 nnrt**，**未安装 kernels-310b**。

1. 浏览器登录 [昇腾社区软件下载](https://www.hiascend.com/developer/download/community/result)
2. 筛选 **CANN 7.0.RC1**、**AArch64**，下载：
   `Ascend-cann-kernels-310b_7.0.RC1_linux-aarch64.run`
3. 放到 PC 的 `HGBO/packages/` 目录
4. Windows 一键上传安装：

```bash
python scripts/install_kernels_310b.py
python scripts/verify_kernels_install.py   # 检查 dav_m300 + 重编 + benchmark
```

板端手动安装（若 run 包已在 `/tmp`）：

```bash
chmod +x /tmp/Ascend-cann-kernels-310b_7.0.RC1_linux-aarch64.run
./Ascend-cann-kernels-310b_7.0.RC1_linux-aarch64.run --install --install-for-all --quiet
source /usr/local/Ascend/ascend-toolkit/set_env.sh
```

**补装后预期**：aclnn 路径可能改善；若 `tikcfw/impl/` 仍无 `dav_m300`，自定义 kernel 仍编不出，需升到 CANN 8.0.0（驱动 23.0.rc3 可不动）。

**若补装仍失败**：将板端 CANN 升级到 **8.0.0 + kernels-310b 8.0.0**（官方兼容 Ascend HDK 23.0.X），然后重新 `board_build.sh`。架构侧代码已就绪，无需改 `run_dse.py`。

已做修正：

- `cmake/util/const_var.py`：`ascend310b` → `Ascend310B4`（原错误映射为 B1）
- `board_build.sh`：package 前先 `cmake --build . --target binary`
- `npu_run_stub.py`：aclnn 失败后自动尝试 acl.op

## HGBO 真机 DSE

```bash
python scripts/run_dse.py --operator video_pre_fuse --num 20 --alg tpe --mode device --fresh
```

`benchmark_result.json` 中 `backend`：

- `ascendc_npu`：NPU 实测（aclnn 或 acl.op）
- `python`：Python 参考实现（fallback，DSE 仍可继续搜参）

## 算子逻辑

- 输入：720×1280×3 fp16
- 输出：640×640×3 fp16
- 操作：nearest resize + /255 归一化
- Tiling：HGBO 搜索 `split_axis / tile_h / tile_w / tile_len / buffer_num`
