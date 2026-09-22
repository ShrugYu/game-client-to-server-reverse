# 手游环境：Android / Termux 运行服务端

> 场景：把手机本身当作服务端跑游戏服务端，客户端（同一台或局域网）连它。
> 免 root 可行；有 root 则更方便（直接改 hosts）。

## A. 两种运行方式

| 方式 | 适用 | 说明 |
|------|------|------|
| **纯 Termux** | 依赖少（纯 Python + sqlite） | 最快，`pkg install python` 直接用 |
| **Termux + proot-distro Ubuntu** | 需要完整 Linux 工具链 / 编译原生库 | 等价于一台 Ubuntu，`pip` 兼容性最好 |

本工程只用 `PyYAML + aiosqlite`，**纯 Termux 即可**；若要编 AES(`cryptography`) 或跑其它 Linux 工具，用 proot Ubuntu。

## B. 纯 Termux 部署

```bash
# 1. 装 Termux（从 F-Droid 或 GitHub 官方，不要用 Play 商店旧版）
pkg update && pkg upgrade -y
pkg install -y python git tmux openssh

# 2. 拿代码（示例：从手机存储拷过来）
cp -r /sdcard/服务端反推/server ~/gsrv
cd ~/gsrv

# 3. 建 venv 装依赖
python -m venv venv
./venv/bin/pip install -U pip
./venv/bin/pip install PyYAML aiosqlite

# 4. 起服务端
./venv/bin/python -m app.main -c ./config/config.yaml
```

启动后监听 `0.0.0.0:8888`。

## C. Termux + proot-distro Ubuntu（需要完整环境时）

```bash
pkg install -y proot-distro
proot-distro install ubuntu
proot-distro login ubuntu
# —— 进入 Ubuntu 后 ——
apt update && apt install -y python3 python3-venv python3-pip git
cp -r /sdcard/服务端反推/server /root/gsrv && cd /root/gsrv
python3 -m venv venv && ./venv/bin/pip install -r requirements.txt
./venv/bin/python -m app.main -c ./config/config.yaml
```
> proot 内可见 `/sdcard`（需先在 Termux 里 `termux-setup-storage`）。

## D. 常驻与保活（关键！）

Android 会杀后台，必须三件套：

```bash
# 1. 申请唤醒锁，阻止 CPU 休眠
termux-wake-lock

# 2. 用 tmux 让进程不随会话退出
tmux new -s gsrv
cd ~/gsrv && ./venv/bin/python -m app.main -c ./config/config.yaml
# 按 Ctrl-B 再按 D 脱离；重连： tmux attach -t gsrv

# 3. 关闭系统对 Termux 的电池优化
#    设置 → 应用 → Termux → 电池 → 无限制 / 允许后台运行
```

**开机自启**（可选，需 Termux:Boot 插件）：
```bash
mkdir -p ~/.termux/boot
cat > ~/.termux/boot/start-gsrv.sh <<'EOF'
#!/data/data/com.termux/files/usr/bin/sh
termux-wake-lock
tmux new-session -d -s gsrv 'cd ~/gsrv && ./venv/bin/python -m app.main -c ./config/config.yaml >> ~/gsrv/logs/boot.log 2>&1'
EOF
chmod +x ~/.termux/boot/start-gsrv.sh
```

## E. 远端访问服务端

| 需求 | 做法 |
|------|------|
| 同一台手机上的客户端 | 连 `127.0.0.1:8888` |
| 局域网内其它设备 | 连手机局域网 IP（`ifconfig` 看 wlan0），路由器需允许 |
| 公网访问 | 路由器端口转发 8888，或用内网穿透：`cloudflared` / `frp` / `ngrok` |
| 需要 SSH 管理 | `pkg install openssh; passwd; sshd`（默认端口 8022） |

## F. 客户端对接到 Termux 服务端

- **同机客户端**：改 hosts 把游戏域名指向 `127.0.0.1`（需 root）。
  - 无 root：用抓包工具做 DNS 映射，或用支持 DNS 重定向的模块（Frida / LSPosed）。
- **局域网**：改 hosts → 手机局域网 IP。
- **公网穿透**：把客户端域名解析到穿透域名。

## G. 可被 agent 驱动的 Termux 工具

| 工具 | 用途 |
|------|------|
| `termux-wake-lock` | 保活 |
| `tmux` | 常驻会话，agent 可 attach/发送命令 |
| `sshd` | 让 PC 上的 agent 通过 SSH 直接操作手机 |
| `termux-api` | 调用手机能力（通知、电量、短信…） |
| `code-server` | 手机浏览器里跑 VS Code，agent 可改代码 |

> Operit 的 `super_admin:terminal` 本身就运行在 proot Ubuntu 中，可直接驱动同一套流程。

## H. 常见坑

- 用 Play 商店版 Termux → 包源失效，务必用 F-Droid 版。
- 忘了 `termux-wake-lock` → 锁屏后进程被杀。
- 电池优化没关 → 后台几分钟就断。
- 端口 8888 被占 → 改 `config.yaml` 的 `server.port`。
- proot 里看不到 /sdcard → 先在 Termux 执行 `termux-setup-storage`。