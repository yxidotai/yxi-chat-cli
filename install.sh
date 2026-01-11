#!/bin/sh
set -e

REPO_URL="https://github.com/yxidotai/yxi-chat-cli.git"
REPO_DIR="yxi-chat-cli"

need_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 1
  fi
}

need_cmd git
need_cmd curl
need_cmd python3

if ! python3 - <<'PY'
import sys
sys.exit(0 if sys.version_info >= (3, 11) else 1)
PY
then
  echo "Python 3.11+ is required" >&2
  exit 1
fi

# Clone if not already inside the repo
if [ ! -f "pyproject.toml" ] || [ ! -d ".git" ]; then
  if [ ! -d "$REPO_DIR" ]; then
    git clone "$REPO_URL" "$REPO_DIR"
  fi
  cd "$REPO_DIR"
fi

# Install uv if missing
if ! command -v uv >/dev/null 2>&1; then
  echo "Installing uv..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi

# Install dependencies
if command -v uv >/dev/null 2>&1; then
  uv sync
else
  need_cmd pip3
  pip3 install -r requirements.txt
fi

# Optional: create a user-level launcher if bin/yxi exists
if [ -x "bin/yxi" ]; then
  mkdir -p "$HOME/.local/bin"
  ln -sf "$(pwd)/bin/yxi" "$HOME/.local/bin/yxi"
  echo "Linked yxi to $HOME/.local/bin/yxi"
fi

cat <<'EOF'

Install complete.
- Activate env (uv handles venv automatically):
    uv run python chatbot.py
- Set API key if needed:
    export YXI_API_KEY=your-key
- Optional: build MCP Docker images (run from repo root):
    docker build -f tasks/word_table_export/Dockerfile -t yxi-word-mcp .
    docker build -f tasks/json_to_java/Dockerfile -t yxi-json-to-java .
- Agent example (services running on host ports 8000/8030):
    /agent doc2java /data/demo.docx --word-url http://localhost:8000 --java-url http://localhost:8030 --package com.example.demo --class-name Root --output-path /out/Output.java
EOF