# 自适应方法论：从用户项目到方案

> 目标：**不同项目 → 不同方案**。本文件告诉 AI「怎么读项目、怎么形成证据、怎么决策」。

---

## A. 第 0 步：项目档案（Project Profile）

AI 拿到用户给的任何东西后，**先扫描、后推论**。按下面顺序探测：

### A1. 目录/文件级探测

```bash
# 1) 判断引擎
find <project> -maxdepth 4 -iname "*.pak" -o -iname "*.utoc" -o -iname "*.uasset" \
     -o -iname "global-metadata.dat" -o -iname "Assembly-CSharp.dll" \
     -o -iname "libil2cpp.so" -o -iname "libUE4.so" -o -iname "*.luac" | head -50

# 2) 判断语言/网络库（从文件名/字符串）
grep -rIl -E "protobuf|flatbuffers|msgpack|cbor|kcp|enet|raknet|lidgren|websocket|socket\.io" <project> | head
```

### A2. 要产出的档案字段

对照 `schema/project-profile.yaml` 填写，关键字段：

| 字段 | 取值示例 | 来源 |
|------|---------|------|
| `engine` | unity-il2cpp / unity-mono / unity-lua / unreal / cocos / custom | 文件特征 |
| `client_language` | csharp / cpp / lua / js | dump/SDK/资源 |
| `platform` | android / ios / windows | 用户说明/包类型 |
| `transport_hint` | tcp / udp / kcp / quic / ws / http | 抓包/字符串 |
| `serialize_hint` | protobuf / json / msgpack / binary / flatbuffers | 字符串/结构 |
| `crypto_hint` | none / xor / rc4 / aes / custom | 熵/字符串/代码 |
| `provided_artifacts` | dump.cs / lua / usmap / pcap / sdk.h / 截图 … | 用户实际给的 |
| `known_tools_output` | il2cppdumper / fmodel / ue4ss / wireshark … | 文件名/内容 |

> 关键：把「用户**给了什么**」和「我们**还需要什么**」分开列。
> 缺证据不要瞎猜，写成 `needs` 清单，或按占位符推进。

---

## B. 第 1 步：证据清单（Evidence Inventory）

每条证据一行，含：`来源 / 类型 / 能推出什么 / 置信度(高/中/低)`。

示例：
```
[E01] dump.cs 里 class LoginReq { string user; string pwd; }   -> 登录字段与顺序   置信度:高
[E02] dump.cs 里 switch(msgId) case 0x101 -> LoginHandler      -> LOGIN opcode=0x101 置信度:高
[E03] 抓包 长度头 2字节小端，值=负载长                        -> frame.length_size=2 LE 置信度:高
[E04] 抓包 payload 高熵、16字节对齐                           -> 可能 AES                 置信度:中
[E05] 未抓到登录后的包                                         -> 后续状态机               置信度:低(需补)
```

**规则**：
- 置信度「低」的结论，进入 Spec 的 `unresolved`，由第 5 步闭环验证纠正。
- 两个独立来源指向同结论 → 升为「高」。
- 流量证据与代码证据冲突 → 以**闭环验证**为准，先记冲突。

---

## C. 第 2 步：决策引擎

对**每个协议层**做一次决策，走 `references/decision-tree.md` 的对应分支。
禁止「因为参考实现是 X，所以用 X」。

决策记录格式：
```
决策点: frame.length_size
证据:   E03
结论:   2 (小端, 不含自身)
备选:   4字节大端(若不匹配再退回)
影响:   codec.len_size / len_endian / len_includes_self
```

---

## D. 第 3 步：产出协议规格

照 `references/protocol-spec.md` 与 `schema/protocol.spec.yaml` 填写。
**Spec 是唯一事实来源**；后续所有代码、文档、测试都从它派生。

---

## E. 第 4 步：由规格派生服务端

见 `references/codegen.md`。核心原则：

1. **选最贴近目标协议的技术栈**（不一定要 Python）：
   - 目标客户端是 C++/UE，且协议复杂 → 可用 C++/Rust/Go
   - 快速验证 → Python/Node
   - 高并发长连接 → Go/Rust
2. **参考实现只提供结构套路**：网关/会话/分发/编解码/逻辑/存储的分层照搬，
   但**所有协议参数、消息号、字段布局**按 Spec 重写。
3. **不要一次写全**：先跑通「连接+握手+登录」，再逐 opcode 扩展。

---

## F. 第 5 步：闭环验证与回填

每跑通一个状态，把 Spec 里对应的 `confidence: low` 升级为 `high`，
并修正被证伪的假设。若客户端在某步失败：

```
定位: 是哪个 opcode / 哪个字段导致的
回看: 对应 Spec 条目 + 它的证据
动作: 补证据（再抓包 / 再看代码）→ 修正 Spec → 再验证
```

---

## G. 常见「项目类型 → 方案」速查

> 完整推演见 `examples/`。这里是索引，不是结论。

| 项目特征 | 大概率方案方向 | 关键决策点 |
|---------|--------------|-----------|
| `libil2cpp.so`+`global-metadata.dat` | Unity IL2CPP → dump.cs → 找网络类 | 是否加密 metadata |
| `Assembly-CSharp.dll` | Unity Mono → dnSpy 直读 | 是否混淆 |
| 大量 `.luac` + xlua | 业务逻辑在 Lua | Lua 是否加密/魔改 opcode |
| `.pak`/`.utoc` + `libUE4.so` | UE → FModel/Dumper-7 → SDK | AES key / unversioned |
| 抓包全是二进制、高熵 | 自定义+加密 | 加密算法与密钥来源 |
| 抓包是明文 JSON + HTTP | 简单，直连 | 鉴权 token |
| UDP + conv 头 | KCP | 是否 KCP 上再加密 |
| 有 `.proto` 文件 | protobuf | .proto 可直接反序列化 |

---

## H. AI 行为约束（重要）

1. **禁止**在没有证据时直接套用 `server/` 的默认配置。
2. **必须**先产出 `project-profile.yaml` 与 `protocol.spec.yaml`，再动代码。
3. 用户只给了一部分 → 用**占位符**把 Spec 补全（`TODO_EVIDENCE`），并列出「还需什么证据」。
4. 用户没说游戏类型 → 按 A1 主动扫描，扫不出来就**列出探测命令**让用户跑。
5. 每个结论标注**置信度 + 证据编号**，可追溯。