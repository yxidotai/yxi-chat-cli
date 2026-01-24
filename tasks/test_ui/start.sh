#!/bin/bash
Xvfb :1 -screen 0 1024x768x16 &> xvfb.log &
export DISPLAY=:1.0
fluxbox &> fluxbox.log &
x11vnc -display :1 -nopw -listen 0.0.0.0 -xkb -forever &> x11vnc.log &
exec uvicorn tasks.test_ui.mcp_service:app --host 0.0.0.0 --port 8040