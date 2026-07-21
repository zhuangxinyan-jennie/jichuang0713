#!/usr/bin/env bash
set -euo pipefail

SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_PATH=/etc/systemd/system/xiongda-app-gateway.service
RUNTIME_SERVICE_PATH=/etc/systemd/system/xiongda-board-runtime.service
ENV_PATH=/home/HwHiAiUser/jichuang/app_gateway.env
CERT_DIR=/home/HwHiAiUser/jichuang/app_gateway_certs

if [[ ! -f "${ENV_PATH}" ]]; then
  umask 077
  printf 'APP_GATEWAY_ADMIN_PIN=%s\n' "${APP_GATEWAY_ADMIN_PIN:-2468}" > "${ENV_PATH}"
fi

if [[ ! -f "${CERT_DIR}/cert.pem" || ! -f "${CERT_DIR}/key.pem" ]]; then
  mkdir -p "${CERT_DIR}"
  umask 077
  BOARD_IP="${APP_GATEWAY_BOARD_IP:-192.168.137.100}"
  openssl req -x509 -nodes -newkey rsa:2048 -sha256 -days 3650 \
    -keyout "${CERT_DIR}/key.pem" \
    -out "${CERT_DIR}/cert.pem" \
    -subj "/CN=xiongda-board.local" \
    -addext "subjectAltName=DNS:xiongda-board.local,IP:${BOARD_IP}"
fi

cp "${SOURCE_DIR}/app-gateway.service" "${SERVICE_PATH}"
cp "${SOURCE_DIR}/board-runtime.service" "${RUNTIME_SERVICE_PATH}"
systemctl daemon-reload
systemctl enable --now xiongda-app-gateway.service xiongda-board-runtime.service
systemctl --no-pager --full status xiongda-app-gateway.service || true
systemctl --no-pager --full status xiongda-board-runtime.service || true
