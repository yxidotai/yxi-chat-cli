#!/bin/sh
set -e

UPDATE_URL="${YXI_UPDATE_URL:-https://raw.githubusercontent.com/yxidotai/yxi-chat-cli/refs/heads/main/install.sh}"
TMP_FILE="$(mktemp -t yxi-update.XXXXXX)"

cleanup() {
  [ -f "$TMP_FILE" ] && rm -f "$TMP_FILE"
}
trap cleanup EXIT INT TERM

echo "Fetching latest yxi installer..."
curl -fsSL "$UPDATE_URL" -o "$TMP_FILE"
chmod +x "$TMP_FILE"

echo "Running installer (you may be prompted for sudo)..."
ORIGINAL_USER_HOME="${ORIGINAL_USER_HOME:-$HOME}" "$TMP_FILE"
