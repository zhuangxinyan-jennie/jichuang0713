# Ascend C VideoPreFuse — 实现与编译说明

## 目录

```
ascendc/
├── VideoPreFuseCustom.json     # msopgen 算子定义
├── VideoPreFuseCustom/         # msopgen 工程（在板子上生成/编译）
├── impl/                       # 完整 kernel/host 实现（复制到工程中）
└── patches/                    # CANN opbuild aclnn 修复文件
```

## 在板子上生成工程

```bash
source /usr/local/Ascend/ascend-toolkit/set_env.sh
MSOPGEN=/usr/local/Ascend/ascend-toolkit/7.0.RC1/python/site-packages/bin/msopgen
cd /home/HwHiAiUser/HGBO/operators/video_pre_fuse/ascendc
$MSOPGEN gen -i VideoPreFuseCustom.json -f tf -c ai_core-Ascend310B -lan cpp -out VideoPreFuseCustom
```

## 替换为 HGBO 实现

1. 将 `impl/video_pre_fuse_custom_kernel.cpp` 复制到 `VideoPreFuseCustom/op_kernel/`
2. 将 `impl/video_pre_fuse_custom_host.cpp` 复制到 `VideoPreFuseCustom/op_host/`（覆盖 stub）
3. 将 `impl/video_pre_fuse_custom_tiling.h` 复制到 `VideoPreFuseCustom/op_host/`
4. 若 `aclnn_*.cpp` 编译报错，用 `patches/aclnn_video_pre_fuse_custom_fixed.cpp` 覆盖 `build_out/autogen/aclnn_*.cpp`

## 编译

```bash
source /usr/local/Ascend/ascend-toolkit/set_env.sh
cd VideoPreFuseCustom && bash build.sh
./build_out/custom_opp_*.run --install-path=/home/HwHiAiUser/custom_opp
```

## 当前板子状态（2026-07-06）

```bash
source /usr/local/Ascend/ascend-toolkit/set_env.sh
echo $ASCEND_HOME_PATH    # 正确变量，例如 /usr/local/Ascend/ascend-toolkit/latest
# 不要用 $ASCEND_HOME（CANN 7.0 未设置，会展开为空路径）
ls /usr/local/Ascend/ascend-toolkit/7.0.RC1/compiler/include/register/tilingdata_base.h
```

**注意**：板子默认 shell 可能是 fish，带 `$()`/`${}` 的命令请用 `/bin/bash -lc '...'` 执行。

**opbuild 常见坑**：不要把 `patches/aclnn_*.cpp` 放进 `op_host/`，否则 `aux_source_directory` 会把它编进 `libascend_all_ops.so` 并报 `NnopbaseRunForWorkspace` 未定义。

Windows 一键上传编译：`python scripts/build_ascendc_on_board.py`（2026-07-06 已在板子编译安装成功）
## HGBO 联调

`benchmark.py` 会写 `/tmp/hgbo_vpf_tiling.bin`，Host TilingFunc 读取该文件应用 HGBO 搜索参数。

```bash
python scripts/run_dse.py --operator video_pre_fuse --mode device --num 20 --alg tpe --fresh
```
