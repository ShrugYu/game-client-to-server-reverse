#!/usr/bin/env bash
# 一键部署脚本（Ubuntu/Debian 服务器）
# 用法: sudo bash deploy.sh [install_dir]
set -euo pipefail

APP_DIR="${1:-/opt/gsrv}"
SRC_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "=== [1/6] 安装系统依赖 ==="
if ! command -v python3 >/dev/null; then
  apt-get update && apt-get install -y python3 python3-venv python3-pip
fi

echo "=== [2/6] 创建用户与目录 ==="
id -u gsrv >/dev/null 2>&1 || useradd -r -s /usr/sbin/nologin gsrv
mkdir -p "$APP_DIR"/{data,logs,config}

echo "=== [3/6] 拷贝程序 ==="
cp -r "$SRC_DIR/app" "$APP_DIR/"
cp "$SRC_DIR/requirements.txt" "$APP_DIR/"
cp "$SRC_DIR/client_test.py" "$APP_DIR/" 2>/dev/null || true
if [ ! -f "$APP_DIR/config/config.yaml" ]; then
  cp "$SRC_DIR/config/config.yaml" "$APP_DIR/config/config.yaml"
fi

echo "=== [4/6] 建立虚拟环境并安装依赖 ==="
python3 -m venv "$APP_DIR/venv"
"$APP_DIR/venv/bin/pip" install --upgrade pip
"$APP_DIR/venv/bin/pip" install -r "$APP_DIR/requirements.txt"

echo "=== [5/6] 权限 ==="
chown -R gsrv:gsrv "$APP_DIR"

echo "=== [6/6] 安装 systemd 服务 ==="
cp "$SRC_DIR/deploy/gsrv.service" /etc/systemd/system/gsrv.service
systemctl daemon-reload
systemctl enable --now gsrv

echo
echo "[x] 部署完成"
echo "   状态: systemctl status gsrv"
echo "   日志: journalctl -u gsrv -f"
echo "   配置: $APP_DIR/config/config.yaml"
echo "   测试: $APP_DIR/venv/bin/python $APP_DIR/client_test.py --host 127.0.0.1"