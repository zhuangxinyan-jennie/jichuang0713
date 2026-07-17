#!/bin/bash
set -e
REMOTE="/tmp/Ascend-cann-nnrt_7.0.RC1_linux-aarch64.run"
chmod +x "$REMOTE"
echo "=== installing nnrt ==="
"$REMOTE" --install --install-for-all --quiet
echo "=== post install ==="
ls -la /usr/local/Ascend/
test -d /usr/local/Ascend/nnrt && echo NNRT_YES || echo NNRT_NO
source /usr/local/Ascend/ascend-toolkit/set_env.sh
ls /usr/local/Ascend/ascend-toolkit/latest/aarch64-linux/tikcpp/tikcfw/impl/
find /usr/local/Ascend -name '*dav*m300*' 2>/dev/null | head -10
