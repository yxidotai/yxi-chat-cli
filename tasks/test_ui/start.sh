#!/bin/bash
Xvfb :1 -screen 0 1024x768x16 &> xvfb.log &
export DISPLAY=:1.0
fluxbox &> fluxbox.log &
# CLI-C2/M6: 默认生成随机密码并仅监听回环;可用 VNC_PASSWORD 覆盖
VNC_PASSWORD="${VNC_PASSWORD:-$(head -c 18 /dev/urandom | base64 | tr -d '/+=' )}"
x11vnc -display :1 -passwd "$VNC_PASSWORD" -listen 127.0.0.1 -xkb -forever &> x11vnc.log &
echo "VNC listening on 127.0.0.1:5900 (password generated, set VNC_PASSWORD to override)" >&2
# 容器内绑定所有接口供 docker 端口转发使用;对外暴露由 docker run -p 控制
# (建议 -p 127.0.0.1:8040:8040 避免意外公开)
exec uvicorn tasks.test_ui.mcp_service:app --host 0.0.0.0 --port 8040
