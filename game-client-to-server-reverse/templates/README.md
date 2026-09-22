# templates/ —— 参考实现与模板总览

> 注意: **本目录（以及 `server/`）里的所有代码都是「参考实现」，不是对某个游戏的答案。**
> 每个游戏的协议/字段/架构都不一样，**用它提供的"套路"，不要照抄它的"答案"**。

---

## 一、快速上手（注册站 + GM 后台 + 首个超管 + 用邀请码注册）

```bash
# 0) 依赖
pip install flask

# 1) 起「注册网站」（与游戏服共用同一 DB / 同一密码哈希）
cd templates/register-site
GAME_DB=../../server/data/game.db PWD_SALT=你的盐 VERIFY_MODE=invite ACCOUNT_PREFIX=svr_ \
  python3 server.py            # http://127.0.0.1:8080/

# 2) 起「GM 后台」（建首个超级管理员，其余操作员在页面里维护）
cd ../gm-admin
GAME_DB=../../server/data/game.db PWD_SALT=你的盐 \
  GM_ROOT_USER=admin GM_ROOT_PASS=一个强口令 \
  GM_HOST=127.0.0.1 GM_PORT=9900 python3 server.py   # http://127.0.0.1:8090/

# 3) 打开 GM 后台 → 登录(操作员) → 「邀请码」页生成一个码
# 4) 打开注册站 → 用该邀请码注册账号 → 客户端即可用该账号登录

# 5) 客户端“换服”可选：把请求重定向到自建服务端
#    Java/OkHttp 客户端 → templates/xposed-redirect/（LSPosed 模块骨架）
#    native/il2cpp 客户端 → templates/frida-redirect.js
```

> 详细用法看各自目录里的 `README.md`：`register-site/README.md`、`gm-admin/README.md`。

---

## 二、目录总览

### 脚本 / 桩（可执行）
| 文件 | 性质 | 用法 |
|------|------|------|
| `mock_server.py` | 极简单文件服务端桩 | 逆向早期验证"帧能不能收发" |
| `frida_bypass_ssl.js` | 证书固定绕过脚本 | 受控环境抓包用；类名/方法名按需替换 |
| `frida-redirect.js` | **客户端重定向**（native/il2cpp） | hook `getaddrinfo`/`connect` 把请求引到自建服 |
| `kcp_sniff.py` | KCP/UDP 流量还原骨架 | 按目标 KCP 头结构微调 |

### 界面模板（成品 HTML + 最小后端）
| 目录 | 是什么 | 用法 |
|------|--------|------|
| `register-site/` | **注册网站**（响应式，自包含） | 账号注册/登录，支持**邀请码 / QQ群 / 白名单 三选一**（`VERIFY_MODE`） |
| `gm-admin/` | **GM 后台**（响应式，自包含） | 操作员/玩家登录 + 角色权限 + 审计；发奖励 / 公告 / GM命令 / 在线 / 邀请码 / 操作员管理 |
| `xposed-redirect/` | **LSPosed 模块骨架**（Java/OkHttp） | 改写 URL 换服；无 root 用 LSPatch/NPatch |

### 文档模板
| 文件 | 是什么 | 何时用 |
|------|--------|--------|
| `AGENTS.md` | 工作区 AI 协作契约（范围/边界/目录分区/验证命令/收工状态） | **项目第 0 天**放到项目根 |
| `adr-template.md` | 架构决策记录（含"当前不做的事情"+回滚） | 决定「先做什么、不做什么、何时才动客户端」时 |
| `e2e-evidence-template.md` | 实机端到端证据（帧序表 + 差异解释 + 重连快照） | 每次宣称"跑通"时填一份 |
| `status-matrix.md` | 三轴状态矩阵（实现 / 自动测试 / 客户端验收） | 写进度时用 |
| `login-chain.md` | **登录链条**（启动到主场景每一步） | 进服阶段必产，是补包顺序的依据 |
| `function-checklist.md` | **功能清单**（按子系统登记实通/未通） | 持续迭代 |

> 文档模板配套 `../references/engineering-practices.md`；
> **验收钉在具名完成点 + 证据分档 + 主动解释帧长差异**。

---

## 三、为什么叫"参考"

不同游戏的协议**千差万别**：

- 长度头：1 / 2 / 4 字节，大端 / 小端，含 / 不含自身
- 消息号：0 / 1 / 2 / 4 字节，有的还带压缩标记位
- 加密：无 / XOR / RC4 / AES / 自定义
- 压缩：无 / zlib / lz4
- 序列化：JSON / protobuf / MessagePack / 自定义二进制
- 架构：TCP 长连接 / UDP+KCP / HTTP / WS

**把参考实现的默认值当成目标值 = 必错。**

## 四、正确用法

```
1) 先跑 references/adaptation.md 的流程，产出 protocol.spec.yaml
2) 用 spec 的值去"改"参考实现，而不是"用"参考实现
3) 参考实现只提供：
   - 分层结构（会话/分发/编解码/逻辑）
   - 参数化设计（哪些是配置项）
   - 踩坑经验（消息顺序、opcode 回包、幂等…）
```

## 五、举例

参考实现默认 `frame.opcode_size=2`。若你的目标游戏是 1 字节消息号：

- [x] 错：直接跑参考实现 → `struct.error: 'B' format requires 0 <= number <= 255`
- [x] 对：Spec 写 `opcode_size: 1` → 改 `config.yaml` → 跑通

## 六、完整列表

- 长连接二进制协议参考：`../server/`（Python/asyncio，已实测）
- 桩 / 脚本：`mock_server.py`、`frida_bypass_ssl.js`、`frida-redirect.js`、`kcp_sniff.py`
- 界面：`register-site/`、`gm-admin/`
- 重定向：`xposed-redirect/`、`frida-redirect.js`
- 文档模板：`AGENTS.md`、`adr-template.md`、`e2e-evidence-template.md`、`status-matrix.md`、`login-chain.md`、`function-checklist.md`

> 若你的目标协议差异过大（如 UE 原生复制、HTTP 网关），
> **应当新建一个该语言的实现**，而不是硬改 `server/`。
> 见 `../references/codegen.md` 的"多语言参考实现路线"。