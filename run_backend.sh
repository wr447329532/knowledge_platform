#!/bin/bash
# 使用已安装 uvicorn 的环境启动后端（当前检测到 finance_agent 有 uvicorn）
cd "$(dirname "$0")"
UVICORN_PYTHON="/opt/miniconda3/envs/finance_agent/bin/python"
if [ -x "$UVICORN_PYTHON" ]; then
  exec "$UVICORN_PYTHON" -m uvicorn backend.app.main:app --reload --host 0.0.0.0
else
  echo "未找到 finance_agent 环境，请先执行: conda activate finance_agent"
  exec python -m uvicorn backend.app.main:app --reload --host 0.0.0.0
fi
