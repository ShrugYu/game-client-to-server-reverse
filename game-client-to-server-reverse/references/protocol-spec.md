# 协议规格（Protocol Spec）：语言无关的中间表示

> **Spec 是整个流程的唯一事实来源。** 先有 Spec，再有代码。
> 换游戏 = 换一份 Spec，而不是重写一堆散代码。

---

## A. 为什么要 Spec

1. **可追溯**：每个字段都挂 `evidence` 编号与 `confidence`。
2. **可评审**：人类能直接读，AI 能直接生成代码。
3. **可增量**：没证据的先写 `TODO_EVIDENCE`，不阻塞后续。
4. **可验证**：闭环验证的结果回填到 Spec，形成闭环。

模板见 `schema/protocol.spec.yaml`。

---

## B. Spec 结构总览

```yaml
meta:          # 项目/引擎/来源
project:       # 引擎、平台、客户端语言
transport:     # tcp/udp/kcp/quic/ws/http
frame:         # 长度头、消息号、字节序
crypto:        # 加密算法、密钥来源、是否逐连接
compress:      # 压缩算法、阈值
serialize:     # json/protobuf/binary/msgpack + 字段定义
opcodes:       # 消息号表（数值 → 名称/方向/结构）
state_machine: # 连接→握手→登录→选角→进场景…
messages:      # 每条消息的字段布局
unresolved:    # 未确认项 + 需要的证据
```

---

## C. 各段填写要点

### C1. frame（封装层）
```yaml
frame:
  length_size: 2            # 1/2/4
  length_endian: little     # little/big
  includes_self: false      # 长度是否含头部自身
  opcode_size: 2            # 0 = 无独立消息号
  opcode_endian: little
  evidence: [E03, E07]
  confidence: high
```

### C2. crypto / compress
```yaml
crypto:
  enabled: true
  algorithm: xor            # none/xor/rc4/aes/custom
  key_source: hardcoded     # hardcoded/handshake/login/derived
  key: "0x11223344"         # 已知则写，未知写 null
  per_connection: false
  evidence: [E09]
  confidence: medium
compress:
  enabled: false
  algorithm: zlib           # zlib/gzip/lz4
  min_size: 256
```

### C3. serialize（两种写法）
**结构化（推荐）**——字段有名字和类型：
```yaml
serialize:
  format: binary
  endian: little
  strings: length_prefixed_u16   # 或 fixed / cstring
```

**声明式**——用 `fields` 描述固定布局（适合简单消息）：
```yaml
messages:
  LoginReq:
    opcode: 0x0101
    fields:
      - {name: username, type: str}      # 长度前缀字符串
      - {name: password, type: str}
      - {name: client_ver, type: u32}
```

### C4. opcodes
```yaml
opcodes:
  source: dump.cs            # dump.cs / lua / sdk.h / inferred
  table:
    - {value: 0x0001, name: HANDSHAKE_REQ, dir: c2s, msg: HandshakeReq}
    - {value: 0x0002, name: HANDSHAKE_RES, dir: s2c, msg: HandshakeRes}
    - {value: 0x0101, name: LOGIN_REQ,     dir: c2s, msg: LoginReq}
    # ...
  evidence: [E02]
  confidence: high
```

### C5. state_machine
```yaml
state_machine:
  - name: CONNECT
    on: [HANDSHAKE_REQ] -> HANDSHAKED
  - name: HANDSHAKED
    on: [LOGIN_REQ] -> LOGGED_IN
  - name: LOGGED_IN
    on: [CHAR_SELECT_REQ] -> IN_GAME
  - name: IN_GAME
    on: [MOVE_REQ, ENTER_SCENE_REQ]
  evidence: [E12]
  confidence: medium
```

### C6. unresolved
```yaml
unresolved:
  - item: crypto.key
    need: 二进制内 XOR 密钥常量 / 握手包中的 key 字段
    blocking: true
  - item: 消息 0x0305 的字段布局
    need: 抓取一次触发该操作
    blocking: false
```

### C7. client（客户端语言与打补丁方式）
```yaml
client:
  language: csharp          # csharp | il2cpp | as3 | lua | js | java | cpp
  source_available: true    # 能否反编译出源码（Mono/AS3=true, IL2CPP=false）
  decompiler: dnSpy         # dnSpy | jadx | FFDec | unluac | ida
  patch_method: config_file # config_file | source_rebuild | binary_patch | runtime_hook
  patch_target: "Android/data/<pkg>/files/local_server.txt"
  skip_login: false         # 是否需要跳过官方登录（如 SDK Dummy）
```

### C8. subsystems（通用子系统，别漏）
```yaml
subsystems:
  account:   {enabled: true, store: sqlite}
  save:      {enabled: true, path: "./data/game.db"}
  admin:     {enabled: true, bind: "127.0.0.1", port: 0}   # 仅本机
  resources: {mode: local}   # local | cdn | hybrid
  ports:                     # 主端口 + 战斗 + 后台
    main: 0
    battle: 0                # 常用 main+1
    admin: 0                 # 常用 main+2
  client_patch: {method: config_file}
```

### C9. bots（服务端人机）——  可选拓展

> **不影响核心运行**，跑通之后再考虑。先反推（`extensions/bot-reverse.md`），再复刻。
> 不需要就整段留空。

```yaml
bots:
  # —— 反推结论（来自客户端）——
  needed: true                # 开局是否要求多人
  ownership: server           # server | client | hybrid | unsupported
  supported_by_client: true   # 客户端协议是否支持 AI
  ai_flag_field: "is_ai"      # 客户端里的"这是AI"标记字段
  ai_flag_values: {human: 0, ai: 1}
  identity_fields: ["name", "level", "job", "deck", "avatar", "title"]
  action_opcodes: [0x0303, 0x0304]   # AI 动作复用哪些 opcode
  flow_opcodes: [0x0201, 0x0203]     # 加入/准备/开始/离开
  min_players: 2              # 开局最少人数
  evidence: [E20, E21]        # 证据编号
  confidence: medium
  # —— 复刻配置 ——
  mode: logic                 # puppet | logic | fake_client | external
  auto_fill: 3                # 缺人时自动补几个
  difficulty: normal          # easy | normal | hard
  humanize: true              # 拟人化（延迟/抖动/失误）
  behaviors: [wander, follow, use_card]
  recycle: true               # 房间结束回收
```
> 详见 `extensions/bot-reverse.md`（怎么反推）与 `extensions/bots.md`（怎么实现）。

---

## D. 从 Spec 到代码的映射（速查）

| Spec 字段 | 参考实现位置 | 生成/改造动作 |
|-----------|-------------|--------------|
| `transport.type` | `net/server.py` | 换 asyncio TCP→UDP/WS |
| `frame.*` | `config.yaml` / `codec.py` | 直接改参数 |
| `crypto.*` | `net/crypto.py` | 实现对应算法/密钥来源 |
| `compress.*` | `codec.py` | 启用并选算法 |
| `serialize.format` | `codec.py` | 切 json/protobuf/binary |
| `opcodes.table` | `proto/opcodes.py` | 整表替换 |
| `messages.*` | `proto/messages.py` | 逐条实现 encode/decode |
| `state_machine` | `logic/handlers/` | 按状态注册 handler |

---

## E. 校验清单（Spec 完成度）

- [ ] `transport` / `frame` / `crypto` / `serialize` 四层都有结论
- [ ] `opcodes.table` 至少覆盖「连接→登录」所需消息
- [ ] 每条消息有字段布局（或标注 TODO）
- [ ] 每个结论有 `evidence` 且置信度标注
- [ ] `unresolved` 列清了还缺什么证据
- [ ] 能画出 `state_machine`

> 全部打勾 = 可以开始写服务端；否则先把 Spec 补完，或在闭环中回填。

---

## F. 配套：人类可读的协议文档（协议表）

> `protocol.spec.yaml` 是**机器可读**的；还需要一份**人可读**的协议文档，方便评审与交接。
> **格式参考**：`lan-dot-party/game-protocols` 的条目结构。

每条协议按此结构写（对应 `docs/protocol.md`）：

```
### <协议号> <名称>（方向 c2s/s2c）
- 默认端口：
- 触发条件：
- 包结构（hex + 字段表：偏移/长度/类型/字段/含义/证据）
- 请求 / 响应示例（hex dump）
- 实现备注（如：长度头含加密/压缩 flag）
- 证据编号 + 状态
```

**必备三块**：① 分层总览（传输/封装/加密/压缩/序列化）② 连接与握手 ③ 按子系统的协议表。
**验收**：这份文档能让人（或 AI）**照着复原一条消息的收发**，即达标。

> 注意: **先锁版本**：写进文档头部——`客户端版本 X.Y.Z`。
> 反推时**客户端↔服务端版本强绑定**（参考实现里 社区服务端实现 明确警告"不能混用"）。