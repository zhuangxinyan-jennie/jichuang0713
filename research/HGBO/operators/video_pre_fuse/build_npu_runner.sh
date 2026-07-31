#!/bin/bash
set -eo pipefail
source /usr/local/Ascend/ascend-toolkit/set_env.sh
export ASCEND_CUSTOM_OPP_PATH=/home/HwHiAiUser/custom_opp/vendors/customize
set +u
source /home/HwHiAiUser/custom_opp/vendors/customize/bin/set_env.bash
set -u

ROOT="$(cd "$(dirname "$0")" && pwd)"
OPP_API="/home/HwHiAiUser/custom_opp/vendors/customize/op_api"
CANN="/usr/local/Ascend/ascend-toolkit/latest"

if [[ ! -f "${OPP_API}/lib/libcust_opapi.so" ]]; then
  echo "libcust_opapi.so not found under ${OPP_API}/lib" >&2
  exit 1
fi

g++ -O2 -std=c++17 "${ROOT}/npu_run.cpp" -o "${ROOT}/npu_run" \
  -I"${CANN}/include" \
  -I"${OPP_API}/include" \
  -L"${OPP_API}/lib" \
  -L"${CANN}/lib64" \
  -Wl,-rpath,"${OPP_API}/lib" \
  -Wl,-rpath,"${CANN}/lib64" \
  -lcust_opapi -lascendcl -lnnopbase

echo "Built ${ROOT}/npu_run"
