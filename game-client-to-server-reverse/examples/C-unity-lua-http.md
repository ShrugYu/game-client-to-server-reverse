# 示例 C：Unity + Lua 热更 + HTTP

> **注意：这是推演示例，不是通用结论。**

## 1. 用户或我们解析出来了什么
- 一堆 `.lua`
- `mitm` 抓包（HTTP）
- 说明：休闲手游，Unity，业务逻辑在 Lua

## 2. 证据清单

```
[E01] assets 里有 xlua 相关 so/字符串                         高
[E02] lua 里 Net.send("login", {user=..., pwd=...})           高 → 消息名即语义
[E03] 抓包 HTTP POST /api/login，body 是 JSON                 高
[E04] 响应 JSON {code:0, token:"...", uid:123}                高
[E05] 后续请求带 Header Authorization: Bearer <token>         高
[E06] 有个轮询 /api/pull 每 3 秒                              高
[E07] 未发现长连接                                            中
```

## 3. 逐层决策

| 层 | 树节点 | 结论 |
|----|--------|------|
| 引擎 | 有 xlua + Unity | unity-lua |
| 传输 | HTTP | http |
| 封装 | HTTP 本身 | 无自定义长度头 |
| 加密 | 明文 JSON | 无（HTTPS 层另说） |
| 序列化 | JSON | json |
| 消息号 | 用路径/动作名 | `login` / `pull` / ... |
| 架构 | HTTP + 轮询 | HTTP 网关，无长连接 |

## 4. 产出 Spec 关键片段

```yaml
transport: {type: http, port: 443, tls: true, confidence: high, evidence:[E03]}
frame: {mode: "http_body", opcode_size: 0, confidence: high}   # 无自定义帧
crypto: {enabled: false, confidence: high, evidence:[E04]}
serialize: {format: json, confidence: high, evidence:[E03,E04]}
opcodes:
  source: lua
  table:
    - {name: login,  route: "POST /api/login",  dir: c2s}
    - {name: pull,   route: "POST /api/pull",   dir: c2s}
  confidence: high
  evidence: [E02]
state_machine:
  - {state: LOGGED_IN, on: [pull], next: IN_GAME}
auth: {type: bearer_token, from: "login response .token", evidence:[E04,E05]}
```

## 5. 参考实现要改哪里

| 位置 | 改动 |
|------|------|
| `net/server.py` | **不用 TCP 长连接** → 换成 **HTTP 服务**（FastAPI/Express） |
| `net/codec.py` | 不需要（HTTP + JSON） |
| `proto/opcodes.py` | 换成 **路由表** `{"login": "/api/login", ...}` |
| `logic/handlers/` | 每个路由一个 handler，返回 JSON |
| 鉴权 | 增加 Bearer token 校验中间件 |
| 参考实现 | `server/` 的**会话/心跳/广播**基本用不上，只用它的**分层思路** |

**技术栈建议**：Python **FastAPI** 或 Node **Express**，而不是 asyncio TCP。

## 6. 闭环验证路径
```
改 hosts → /api/login 返回我们造的 {code:0, token, uid}
→ 客户端进入主界面 → /api/pull 返回场景数据
→ 打通主流程
```

## 7. 坑与回退
- HTTPS + 证书固定 → 自签 CA 或 Frida 绕过（自测）。
- Token 校验逻辑在 Lua 里 → 先读 Lua 的 `Net` 封装，照它的字段做。
- 若其实还有长连接 → 补抓包，回到决策树判断是否要 TCP 网关。
- 若响应有签名/时间戳校验 → 按抓包实现同样签名算法。