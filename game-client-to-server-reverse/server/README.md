# Game Mock Server — 参考实现（长连接二进制协议）

> 注意: **这是参考实现，不是对某个游戏的答案。**
> 它提供的是**分层结构和套路**；协议参数（长度头/消息号/加密/序列化/字段布局）
> 必须按 `../schema/protocol.spec.yaml` 重新填。详见 `../templates/README.md`。
>
> 已实测：`python -m app.main` 启动 → 客户端跑通 握手→登录→建角→选角→进场景→移动→心跳，
> 并验证 XOR 加密 + zlib 压缩 + GM 控制台 + 充值/邮件发放。

## 目录

```
server/
├── app/
│   ├── main.py            入口（-c 指定配置）
│   ├── config.py          配置加载（yaml + 环境变量覆盖）
│   ├── log.py             日志（控制台 + 轮转）
│   ├── net/
│   │   ├── server.py      asyncio 服务器主循环
│   │   ├── session.py     会话（状态/发送/心跳）
│   │   ├── dispatcher.py  opcode 路由
│   │   ├── codec.py       帧编解码（长度头/opcode/加密/压缩/序列化）
│   │   └── crypto.py      加解密（xor/rc4/aes）
│   ├── proto/
│   │   ├── opcodes.py     消息号表（反推结果落点）
│   │   └── messages.py    消息结构
│   ├── logic/
│   │   ├── state.py       在线玩家/场景
│   │   ├── security.py    密码哈希/token/限流
│   │   └── handlers/      auth / char / scene / mail / pay
│   ├── store/
│   │   ├── db.py          数据库（aiosqlite，可换 MySQL）
│   │   └── models.py      表结构 + 游戏配置表 + 充值商品表
│   └── gm/console.py      GM 运维控制台
├── config/config.yaml     协议+业务配置（改这里适配目标）
├── client_test.py         联调测试客户端
├── test_pay_mail.py       充值+邮件联调测试
├── test_bots.py            人机（假玩家）联调测试（拓展，可选）
├── test_battle.py         房间+战斗+掉落 联调测试（双客户端）
├── deploy/                Docker / systemd / Windows(NSSM) / 一键部署
├── start.sh               本地一键启动（Linux/Mac）
├── start_termux.sh        手游(Termux) 一键启动（含 wake-lock + tmux）
└── requirements.txt
```

## 快速开始（本地）

```bash
chmod +x start.sh
./start.sh
# 或手动：
python3 -m venv venv && ./venv/bin/pip install -r requirements.txt
./venv/bin/python -m app.main -c ./config/config.yaml
```

启动后监听 `0.0.0.0:8888`，GM 控制台 `127.0.0.1:9900`。

## 联调测试

```bash
./venv/bin/python client_test.py --host 127.0.0.1 --port 8888 \
    --user alice --password 123456 --name Hero01
```

输出应包含 `[+] full flow OK`。

## GM 控制台

```bash
python3 -c "import socket;s=socket.create_connection(('127.0.0.1',9900));print(s.recv(999))"
# 或用任意 tcp 客户端（telnet/nc/socat）
```
命令：`help stats online kick <uid> ban <name> setlevel <cid> <lvl> givegold <cid> <n> cfg <k> setcfg <k> <v> broadcast <op-hex> <hex> stop`

## 部署

### Docker
```bash
cd deploy && docker compose up -d --build
docker compose logs -f gsrv
```

### 服务器（systemd）
```bash
sudo bash deploy/deploy.sh           # 默认装到 /opt/gsrv
systemctl status gsrv
journalctl -u gsrv -f
```

### 端口 / 防火墙
- 游戏端口：8888/tcp（用 KCP 则同时放行 8888/udp）
- GM 端口：9900 **仅本机**，不要对外暴露

## 适配你的目标游戏（核心 4 步）

1. **协议层** → 改 `config/config.yaml` 的 `frame / crypto / compress / serialize`
2. **消息号** → 填 `app/proto/opcodes.py` 的 `OP`
3. **消息结构** → 在 `app/proto/messages.py` 实现 `encode/decode`
4. **业务逻辑** → 在 `app/logic/handlers/` 注册 `@dispatch(OP.xxx)`

改完重启即可。

## 生产建议
- 数据库换 MySQL：`database.url = mysql://user:pass@host/db`
- 密码哈希换 bcrypt/argon2
- 多进程/多节点：网关与逻辑分离，用 Redis 做共享会话
- 客户端保护：开启 `game.server_authoritative`，所有客户端数值服务端重算

---

## 充值 / 邮件发放

- **发放模式**：`config.yaml` → `game.pay_grant_mode`
  - `direct` 直发：充值成功货币直接进角色
  - `mail` 邮件：充值成功发带附件邮件，玩家自行领取
- **私服支付**：`game.pay_auto_success: true` → 点击购买直接成功（不接真实渠道）
- **商品表**：`app/store/models.py` 的 `PAY_PRODUCTS`，键 = 客户端真实 `product_id`
- **幂等**：`recharge_order.order_no` 唯一，重复回调只发一次
- **GM 直发**：`give <cid> <gold|diamond> <n>` / `mail <cid> <title> <text> <type> <count>`

联调测试：
```bash
./venv/bin/python test_pay_mail.py --user u1 --name H1 --product com.demo.diamond_60
# 切换发放模式： GSRV_GAME__PAY_GRANT_MODE=mail ./venv/bin/python ...
```

---

## 平台支持

| 平台 | 启动方式 | 常驻方案 |
|------|---------|---------|
| Linux 服务器 | `deploy/deploy.sh` | systemd |
| Docker | `deploy/docker-compose.yml` | 容器 restart 策略 |
| Windows(端游) | `deploy/start_windows.bat` | NSSM / WinSW / 计划任务 |
| Android(手游) | `start_termux.sh` | termux-wake-lock + tmux |

详见 `../references/windows.md` 与 `../references/termux.md`。