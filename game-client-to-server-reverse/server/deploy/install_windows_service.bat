@echo off
REM 用 NSSM 把服务端注册为 Windows 系统服务（需管理员运行）
REM 用法: 右键"以管理员身份运行"
chcp 65001 >nul
setlocal

set APP_DIR=%~dp0..
set PY=%APP_DIR%\venv\Scripts\python.exe
set CFG=%APP_DIR%\config\config.yaml

where nssm >nul 2>nul
if errorlevel 1 (
    echo [!] 未找到 nssm.exe，请先下载并放到 PATH 或本目录
    pause
    exit /b 1
)

nssm install gsrv "%PY%" "-m app.main -c \"%CFG%\""
nssm set gsrv AppDirectory "%APP_DIR%"
nssm set gsrv AppStdout "%APP_DIR%\logs\stdout.log"
nssm set gsrv AppStderr "%APP_DIR%\logs\stderr.log"
nssm set gsrv AppExit Default Restart
nssm set gsrv Start SERVICE_AUTO_START
nssm start gsrv

echo.
echo [+] 已注册为服务 gsrv
echo     状态: nssm status gsrv
echo     停止: nssm stop gsrv
echo     卸载: nssm remove gsrv confirm
pause