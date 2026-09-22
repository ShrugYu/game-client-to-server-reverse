# GM 后台模板（通用 · 响应式 · 带登录与权限）

成品页面：`index.html`（自包含，无 CDN）。后端：`server.py`（最小 Flask）。

## 登录（两套入口，与游戏账号体系区分）
1. **操作员登录**：`gm_operator` 表里的 **GM 操作员账号 + 密码**（PBKDF2 加盐存储）→ 按角色拿权限；
2. **玩家登录**：用**游戏账号 + 密码**（与注册站同一套客户端哈希）→ 只有 `player` 的**有限权限**
   （生成自己的邀请码 / 看自己的记录）。

首个超级管理员由环境变量创建：`GM_ROOT_USER` / `GM_ROOT_PASS`（**无默认口令**）。

## 角色 → 权限（`ROLE_PERMS`）
| 角色 | 权限 |
|------|------|
| player | `invite.self`, `records.self` |
| viewer | `player.query`, `records.view` |
| support | + `reward.send`, `invite.manage` |
| admin | + `announce`, `cmd`, `online` |
| super | `*` |

前端**按权限显示/隐藏导航与视图**；后端**每个动作都再校验一次权限**（前端隐藏 ≠ 安全）。

## 模块（导航，按权限出现）
概览（服务器状态 + 在线） · 玩家（查询 + 发奖励） · **服务器管理**（公告 + GM命令，**仅服务器管理员**） · 邀请码 · 发送记录 · **操作员管理**（**仅 super**：增删/改角色/启停/重置密码）

> **登录页**：未登录时后台整体隐藏，只显示登录页；登录后才进入控制台。
> **服务器管理**（原"公告 + 命令"合并）只有 **admin/super** 可见可用；前端隐藏 + 后端校验双保险。

## 两种鉴权同时存在
1. **操作员/玩家登录** —— 决定你**能进入哪些页、做哪些操作**；
2. **账号注册密码** —— 发奖励（货币/物品/邮件）时，还要输入**目标账号注册时的密码**（防越权给任意人发）。

## 留痕（审计）
- 每次发放写 `gm_send_log`（可在"发送记录"查）；
- 每次登录/发奖/公告/命令/邀请码操作写 `gm_audit`（含 **操作员、角色、动作、目标、IP**）。

## 安全要点（避免被利用）
- **仅绑定 127.0.0.1**（GM = 最高权限，绝不对外）；
- 操作员口令 **PBKDF2-SHA256 加盐**；比较用**常量时间**；
- **登录失败限流**（`GM_MAX_FAIL` 次后锁 `GM_LOCK_SEC` 秒）；
- **会话 token** 存服务端、有过期（`GM_SESSION_TTL`），前端用 **`X-GM-Token` 头**携带
  （自定义头 → 天然缓解 CSRF）；退出即删会话；
- **无默认口令**；未设 `GM_ROOT_USER/PASS` 时不会创建任何操作员；
- 参数全部走 SQL 占位符（防注入）；输出 `textContent`/转义（防 XSS）。

## 运行
```bash
pip install flask
GAME_DB=../server/data/game.db PWD_SALT=你的盐 \
  GM_ROOT_USER=admin GM_ROOT_PASS=一个强口令 \
  GM_HOST=127.0.0.1 GM_PORT=9900 python3 server.py        # 监听 127.0.0.1:8090
```
打开 `http://127.0.0.1:8090/` → 用操作员登录。
把 `gm_cmd()` / 各 `TODO` 换成你游戏服的 GM 通道（参考 `server/app/gm/console.py`）。

## 接口
```
POST /api/gm/login {type:"operator"|"player", username, password} -> {ok,token,subject,role,perms}
GET  /api/gm/me                                       -> {subject,role,perms}
POST /api/gm/logout
POST /api/gm {action,...}   头：X-GM-Token
  servers / query / items
  send_money|send_items|send_mail   （需 reward.send + 目标账号注册密码）
  announce|cmd|online               （需对应权限）
  logs / invite_gen / invite_list / invite_revoke
GET  /api/status
```

## 生产加固建议
- 反代加 HTTPS + IP 白名单/VPN；会话 TTL 调短；`gm_audit` 定期归档；
- 需要更细粒度时，把 `ROLE_PERMS` 换成数据库里的"角色-权限"表；
- 高价值操作（封号/清档）建议加**二次确认**与**双人复核**。

> 若你的面板要走 **AES-GCM 签名**（页面下发 key + csrf，前端封包后再提交），把 `api()` 换成"取 key+csrf 再封包"即可；
> 参考实测案例见 `references/release-and-ops.md §7`。