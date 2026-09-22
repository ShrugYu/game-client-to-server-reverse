#!/usr/bin/env bash
# 本地一键启动（开发用）
set -e
cd "$(dirname "$0")"

if [ ! -d venv ]; then
  echo "[*] 创建虚拟环境..."
  python3 -m venv venv
  ./venv/bin/pip install -U pip
  ./venv/bin/pip install -r requirements.txt
fi

mkdir -p data logs
echo "[*] 启动服务端..."
exec ./venv/bin/python -m app.main -c ./config/config.yaml