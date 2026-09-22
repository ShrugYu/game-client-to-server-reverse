@echo off
REM Windows 一键启动（开发用）
REM 用法: 双击 或 cmd 里运行 start_windows.bat
chcp 65001 >nul
cd /d "%~dp0"

if not exist venv (
    echo [*] 创建虚拟环境...
    python -m venv venv
    venv\Scripts\pip install -U pip
    venv\Scripts\pip install -r requirements.txt
)

if not exist data mkdir data
if not exist logs mkdir logs

echo [*] 启动服务端...
venv\Scripts\python -m app.main -c config\config.yaml
pause
