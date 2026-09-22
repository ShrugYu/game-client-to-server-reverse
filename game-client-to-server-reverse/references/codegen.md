# 由 Spec 生成/改造服务端（Codegen & Adaptation）

> 原则：**参考实现提供套路，Spec 提供答案。**
> 不同游戏 → 不同语言、不同结构、不同协议参数。

---

## A. 先选技术栈（不要默认 Python）

| 目标特征 | 推荐栈 | 现实参考 |
|---------|--------|---------|
| 快速验证 / 脚本化 | Python (asyncio) | 本仓库 `server/` |
| 高并发长连接 / 要发布二进制 | Go | **案例 A**（某 Unity 手游，Go 服务端 + 预编译三端） |
| HTTP + 内容分发 / 前后端同栈 | Node.js / TypeScript | **案例 B**（某 Cocos 手游，Node/TS + React 后台） |
| 极致性能 / 二进制协议复杂 | Rust / C++ | 与 UE/C++ 客户端语义贴近 |
| 客户端是 Java 生态 | Java/Kotlin (Netty) | 复用客户端协议库 |
| 已有 C# 资产 / 桌面启动器 | C# (.NET) | 案例 A 的 WinForms 启动器即 C# |

> 参考实现 `server/` 是 **Python/asyncio** 的一种落地；换成 Go/TS/Rust 时，
> **分层结构与 Spec 不变**，只是语法和并发模型不同。
> 两个真实案例见 `cases.md` —— 它们证明"选型可以完全不同"。

---

## B. 通用分层（任何语言都按这个骨架搭）

```
接入层  监听 / 连接限制 / 心跳清理
会话层  每连接状态机 + 上下文（uid/cid/state）
分发层  opcode -> handler 路由
编解码  长度头 + opcode + 解密 + 解压 + 反序列化
协议层  opcodes 表 + message encode/decode
逻辑层  各业务 handler
存储层  账号/角色/存档
运维层  日志 / 指标
```

**换游戏时，只有「编解码参数」和「协议层内容」变，骨架不变。**

---

## C. 从 Spec 生成代码的步骤

1. **读 Spec** → 生成 `opcodes` 常量表
2. 生成 `messages` 的 encode/decode（按字段类型映射）
3. 生成 `codec`（按 frame/crypto/compress）
4. 生成 `state_machine` 骨架 → 每个状态注册 handler 桩
5. 填业务逻辑（登录/角色/场景…）
6. 跑闭环验证 → 回填 Spec

### C1. 字段类型映射表

| Spec type | Python | Go | Rust | Node |
|-----------|--------|----|------|------|
| u8/i8 | `B`/`b` | uint8/int8 | u8/i8 | Buffer.readUInt8 |
| u16/i16 | `H`/`h` | uint16/int16 | u16/i16 | readUInt16LE |
| u32/i32 | `I`/`i` | uint32/int32 | u32/i32 | readUInt32LE |
| u64/i64 | `Q`/`q` | uint64/int64 | u64/i64 | readBigUInt64LE |
| f32/f64 | `f`/`d` | float32/64 | f32/f64 | readFloatLE |
| str(len-prefix) | 手写 | 手写 | 手写 | 手写 |
| bytes(fixed) | slice | []byte | &[u8] | slice |

### C2. 服务端骨架生成（伪代码）
```
for op in spec.opcodes.table:
    if op.dir == c2s:
        register_handler(op.value, handler_stub(op.name))
```

---

## D. 改造参考实现的「影响矩阵」

| 你若改了 Spec 的… | 就要动参考实现的… |
|------------------|-----------------|
| transport.type | `net/server.py`（换协议栈） |
| frame.length_size / endian | `config.yaml` + `codec.py` |
| frame.opcode_size | `config.yaml` + `codec.py` + `messages` 的 opcode 常量 |
| crypto.algorithm / key_source | `net/crypto.py` + 握手/登录逻辑 |
| compress.* | `codec.py` |
| serialize.format | `codec.py` + `messages.py` |
| opcodes.table | `proto/opcodes.py` 整表 |
| messages.* | `proto/messages.py` 逐条 |
| state_machine | `logic/handlers/*` 注册与状态校验 |

---

## E. 增量策略（强烈建议）

```
阶段1  连接 + 握手 + 心跳          ← 先确认 frame/crypto 正确
阶段2  登录 + 账号                 ← 确认鉴权与 token
阶段3  角色列表 + 选角             ← 确认长连接消息序
阶段4  进场景 + 移动 + 广播        ← 确认状态机与并发
阶段5  充值 + 邮件 + 商店          ← 业务闭环
```

每个阶段：改 Spec → 改代码 → 跑 `client_test.py` 式的联调 → 回填置信度。

---

## F. 多语言参考实现路线（建议）

| 参考 | 语言 | 适用 | 状态 |
|------|------|------|------|
| `server/` | Python/asyncio | 通用、快速 | [x] 已提供并实测 |
| `server-go/` | Go | 高并发/预编译发布 | 按需生成（参考案例 A） |
| `server-ts/` | Node/TypeScript | HTTP + 后台 | 按需生成（参考案例 B） |
| `server-cs/` | C#/.NET | 客户端同生态 | 按需生成 |

> AI 应根据 Spec 的 `transport` 与 `serialize` 选择最合适的参考，
> 必要时**新建**一个该语言的实现，而不是硬套 Python。
> 真实世界的选型差异见 `cases.md`。
>
> **发布形态提示**：若目标是给普通用户使用，应构建**预编译多平台二进制 + 启动器**，
> 而不是让用户装运行时（案例 A 的做法）。

---

## G. 自律条款

1. 不把参考实现的**协议常量**当作目标的协议常量。
2. 生成代码前必须先有 Spec（哪怕是占位版的）。
3. 每次代码变更，同步更新 Spec 的 `confidence` 与 `evidence`。
4. 交付物 = Spec + 代码 + 验证记录 + 回滚方案。