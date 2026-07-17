#!/bin/bash
set -euo pipefail
source /usr/local/Ascend/ascend-toolkit/set_env.sh
export ASCEND_HOME=/usr/local/Ascend/ascend-toolkit/latest

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

rm -f op_host/aclnn_*.cpp op_host/aclnn_*.h
rm -rf build_out
mkdir -p build_out
cd build_out
cmake .. --preset=default
# impl .py must exist before binary (opc compile reads tbe/dynamic/*.py)
cmake --build . --target ascendc_impl_gen -j8
cmake --build . --target binary -j8 || echo "WARN: ascendc binary target failed (check CANN vs SoC, e.g. 310B4 needs dav-m300)"
cmake --build . --target package -j8

for f in custom_opp_*.run; do
  [[ -e "$f" ]] || continue
  "./$f" --install-path=/home/HwHiAiUser/custom_opp
  break
done

VPF_DIR="$(cd "$ROOT/../.." && pwd)"
if [[ -f "$VPF_DIR/build_npu_runner.sh" ]]; then
  /bin/bash "$VPF_DIR/build_npu_runner.sh"
fi

echo "BOARD_BUILD_OK"
