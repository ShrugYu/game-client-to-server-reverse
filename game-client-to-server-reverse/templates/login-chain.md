# 登录链条（Login Chain）— <游戏名>

> **用途**：把"客户端从启动到进主场景"的每一步**登清楚**，作为**补包顺序**的依据。
> **规则**：必须按**工作区实际目标**填写，**不要照抄示例**；每步记 5 项
> （谁发起 / 发什么 / 期待什么回包 / 证据 / 状态）。
> **配套**：`references/workflow-roadmap.md` 阶段 1、`templates/mock_server.py`。

- 项目：`<游戏名 / 包名>`
- 输入：`<apk / dump.cs / lua / pcap …>`
- 登录类型：`渠道 SDK / 直接账号 / 游客`
- 更新时间：`YYYY-MM-DD`

---

## 0. 链条总览（一句话版）

> 按实际目标调整——**下面只是形状示例，不是答案**。

```
SDK login → getServerList → getLastServerList → 选服
→ player.GetUserList → player.Login → Connect(host,port) → getHash
→ [player.CreateUser] → user.UserLogin → user.GetUserInfo → Loginok → 主场景
```

**分界**：`Connect(host,port)` 之前多为 **HTTP(S) 接口**；之后是 **长连接二进制协议**。

---

## 1. 分步明细

| # | 阶段 | 发起方 | 请求（协议号 / URL / 方法） | 期待响应 | 关键字段 | 证据 | 状态 |
|---|------|--------|---------------------------|---------|---------|------|------|
| 1 | 启动/公告 | client | `GET /notice` | 公告 + 版本 | `version` | E01 | [ ] |
| 2 | SDK 登录 | client | `sdk.login()` | 平台 token | `openid`, `token` | E02 | [ ] |
| 3 | 服务器列表 | client | `getServerList` | 区服数组 | `id,name,addr,port,state` | E03 | [ ] |
| 4 | 上次选服 | client | `getLastServerList` | 上次区服 | `last_server` | E04 | [ ] |
| 5 | 选服 | client | `player.GetUserList` | 角色列表 | `char_list[]` | E05 | [ ] |
| 6 | 登录 | client | `player.Login` | 登录结果 | `uid, token` | E06 | [ ] |
| 7 | 建连 | client | `Connect(host,port)` | TCP 建连 | — | E07 | [ ] |
| 8 | 握手 | client | `<0x0001> HandshakeReq` | `<0x0002> HandshakeRes` | `ver, nonce, key` | E08 | [ ] |
| 9 | 取 hash | client | `getHash` | hash 值 | `hash` | E09 | [ ] |
| 10 | 建角（首登） | client | `[player.CreateUser]` | 建角结果 | 略 | E10 | [ ] |
| 11 | 用户登录 | client | `user.UserLogin` | 登录会话 | `session` | E11 | [ ] |
| 12 | 拉用户信息 | client | `user.GetUserInfo` | 角色/背包/任务… | 大量字段 | E12 | [ ] |
| 13 | 登录完成 | server | `Loginok` | 进主场景 | — | E13 | [ ] |

> 状态：`[x] 已通 / [~] 部分 / [ ] 未做 / [?] 未验证 / [-] 该游戏没有`

---

## 2. 关键字段与取值

| 字段 | 来源 | 类型 | 取值示例 | 备注 |
|------|------|------|---------|------|
| `version` | 客户端内置 | str | `1.8.1` | 服务端需匹配 |
| `token` | SDK | str | — | 是否需服务端二次校验 |
| `addr/port` | 服务器列表 | str/u16 | `127.0.0.1:8888` | 重定向落点 |
| `hash` | 握手后 | 整数 | — | 用途待定 → unresolved |

---

## 3. 接口分类（HTTP vs 长连接）

```
HTTP(S) 接口：  <列表>
长连接二进制：  <列表>
其他（CDN/热更/支付）：  <列表>
```

---

## 4. 未解决项（unresolved）

```
1. <某字段含义未知，缺什么证据>
2. <某步骤的协议号未确认>
3. <是否走热更程序集未验证>
```

---

## 5. 备注

- **SDK**：`<渠道名 / 是否可离线 / dummy 开关>`
- **热更**：`<方案 / 目录 / 是否覆盖内置>`
- **加密**：`<已知的加密/压缩层>`
- **重定向落点**：`<hosts / 私有目录文件 / DNAT / 改包>`

---

> 注意: **链条整理不清 = 补包没有顺序**。这份文档每通一步就更新一次状态，
> 并同步到 `TRACKER.md` 与 `function-checklist.md`。