#!/data/data/com.termux/files/usr/bin/bash
# Termux 一键启动（Android）
# 用法: bash start_termux.sh
set -e
cd "$(dirname "$0")"

# 1) 唤醒锁，防止锁屏被杀
command -v termux-wake-lock >/dev/null 2>&1 && termux-wake-lock

# 2) 依赖
if [ ! -d venv ]; then
  echo "[*] 创建虚拟环境..."
  python -m venv venv
  ./venv/bin/pip install -U pip
  ./venv/bin/pip install PyYAML aiosqlite
fi

mkdir -p data logs

# 3) 优先用 tmux 常驻
if command -v tmux >/dev/null 2>&1; then
  if tmux has-session -t gsrv 2>/dev/null; then
    echo "[*] gsrv 会话已存在，attach： tmux attach -t gsrv"
    exit 0
  fi
  echo "[*] 在 tmux 会话 gsrv 中启动服务端"
  tmux new-session -d -s gsrv \
    "cd $(pwd) && ./venv/bin/python -m app.main -c ./config/config.yaml 2>&1 | tee -a logs/gsrv.log"
  echo "[+] 已启动。查看： tmux attach -t gsrv"
else
  echo "[*] 未装 tmux，前台运行（建议先 pkg install tmux）"
  exec ./venv/bin/python -m app.main -c ./config/config.yaml
fi