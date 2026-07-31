#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
WORKSPACE_DIR="$(cd "${PROJECT_DIR}/.." && pwd)"
REQUIRED_EDITOR_VERSION="2018.4.35f1"

launch_hub() {
  local hub_path="$1"
  echo "Unity Editor not found. Launching Unity Hub: ${hub_path}"
  if [[ "${hub_path}" == *.AppImage ]]; then
    exec env APPIMAGE_EXTRACT_AND_RUN=1 "${hub_path}"
  fi
  exec "${hub_path}"
}

if [[ -n "${UNITY_EDITOR:-}" && -x "${UNITY_EDITOR}" ]]; then
  exec "${UNITY_EDITOR}" -projectPath "${PROJECT_DIR}"
fi

for candidate in \
  "$HOME/Unity/Hub/Editor"/*/Editor/Unity \
  "$HOME/UnityHub/Editor"/*/Editor/Unity \
  "/opt/Unity/Hub/Editor"/*/Editor/Unity \
  "/opt/UnityHub/Editor"/*/Editor/Unity \
  "/usr/local/Unity/Editor/Unity"
do
  if [[ -x "${candidate}" ]]; then
    exec "${candidate}" -projectPath "${PROJECT_DIR}"
  fi
done

if [[ -n "${UNITY_HUB:-}" && -x "${UNITY_HUB}" ]]; then
  launch_hub "${UNITY_HUB}"
fi

for hub_candidate in \
  "${WORKSPACE_DIR}/tools/unityhub/run-unityhub.sh" \
  "${WORKSPACE_DIR}/tools/unityhub/UnityHub.AppImage" \
  "$HOME/Applications/UnityHub.AppImage" \
  "$HOME/Downloads/UnityHub.AppImage"
do
  if [[ -x "${hub_candidate}" ]]; then
    launch_hub "${hub_candidate}"
  fi
done

echo "Unity Editor not found."
echo "No Unity Hub AppImage was found either."
echo "This project expects Unity Editor ${REQUIRED_EDITOR_VERSION}."
echo "Set UNITY_EDITOR=/path/to/Unity to open an installed editor,"
echo "or set UNITY_HUB=/path/to/UnityHub.AppImage and rerun this script."
exit 1
