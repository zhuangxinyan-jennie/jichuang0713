#!/usr/bin/env bash
# 确保板端 HDMI/扩展屏图形显示可用（Ascend DRM + SDDM Xorg :0）
set +e

# 加载显示驱动（开机偶发缺符号时，这里再补一次）
if ! lsmod | grep -q '^ascend_vdp_drm'; then
  insmod /lib/modules/5.10.0+/ascend_vdp_drm.ko 2>/dev/null \
    || modprobe ascend_vdp_drm 2>/dev/null \
    || true
  sleep 1
fi

# 若还没有 :0，重启 sddm 拉起物理屏会话
if [[ ! -S /tmp/.X11-unix/X0 ]]; then
  systemctl restart sddm 2>/dev/null || true
  sleep 3
fi

AUTH=""
for f in /var/run/sddm/*; do
  if [[ -f "$f" ]]; then
    AUTH="$f"
    break
  fi
done

export DISPLAY="${DISPLAY:-:0}"
if [[ -n "$AUTH" ]]; then
  export XAUTHORITY="$AUTH"
fi
export QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-xcb}"

if [[ -n "$AUTH" ]] && DISPLAY=:0 XAUTHORITY="$AUTH" xrandr --query >/dev/null 2>&1; then
  # 防止 HDMI 息屏/节能把画面关掉
  DISPLAY=:0 XAUTHORITY="$AUTH" xset -dpms 2>/dev/null || true
  DISPLAY=:0 XAUTHORITY="$AUTH" xset s off 2>/dev/null || true
  DISPLAY=:0 XAUTHORITY="$AUTH" xset dpms force on 2>/dev/null || true
  DISPLAY=:0 XAUTHORITY="$AUTH" xrandr --output VGA-1 --mode 1920x1080 --primary 2>/dev/null \
    || DISPLAY=:0 XAUTHORITY="$AUTH" xrandr --auto 2>/dev/null \
    || true
  echo "[HDMI] ready DISPLAY=:0 XAUTHORITY=$AUTH"
  DISPLAY=:0 XAUTHORITY="$AUTH" xrandr --query | head -8
  exit 0
fi

echo "[HDMI] WARN: physical display not ready (check HDMI cable / monitor power)"
exit 1
