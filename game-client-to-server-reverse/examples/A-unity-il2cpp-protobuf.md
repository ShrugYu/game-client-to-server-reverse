# 示例 A：Unity IL2CPP + protobuf + TCP

> **注意：这是推演示例，不是通用结论。** 你的项目未必长这样。

## 1. 用户给了什么
- `dump.cs`（Il2CppDumper 产物，~8 万行）
- 一份 `capture.pcap`（登录时的抓包）
- 说明：安卓手游，Unity

## 2. 证据清单

```
[E01] dump.cs 有 class NetManager { void Send(int msgId, IMessage msg) }   -> 有独立 msgId     高
[E02] dump.cs 有 ProtoBuf.Serializer.Deserialize<T>() 调用                -> 序列化=protobuf   高
[E03] dump.cs 有 enum MsgId { Login=1001, CharList=1002, ... }             -> 消息号表可直接抄   高
[E04] pcap: TCP 到 124.x.x.x:9400，负载前 4 字节 = 长度(大端)              -> 4字节大端长度头    高
[E05] 负载去掉长度头后首 2 字节 = 0x03E9(=1001)                            -> opcode 2字节小端   高
[E06] 负载熵值低，无压缩特征                                               -> 无压缩             高
[E07] 负载里 protobuf 字段可见                                             -> 无加密             高
[E08] 未抓到选角后的包                                                     -> 后续消息未知        低
```

## 3. 逐层决策（走决策树）

| 层 | 树节点 | 结论 |
|----|--------|------|
| 引擎 | 有 libil2cpp.so + global-metadata.dat | unity-il2cpp |
| 传输 | pcap 有 TCP 握手 | tcp |
| 封装 | 第1字段=长度，合理值≤MTU | length_size=4, endian=big, includes_self=false |
| 封装 | 去头后首2字节=0x03E9 | opcode_size=2, opcode_endian=little |
| 加密 | 熵低 + protobuf 可见 | 无加密 |
| 压缩 | 无 78 9C/1F 8B | 无压缩 |
| 序列化 | 有 ProtoBuf.Serializer | protobuf |

## 4. 产出 Spec 关键片段

```yaml
transport: {type: tcp, port: 9400, confidence: high, evidence:[E04]}
frame:
  mode: length_prefix
  length_size: 4
  length_endian: big
  includes_self: false
  opcode_size: 2
  opcode_endian: little
  confidence: high
  evidence: [E04, E05]
crypto: {enabled: false, confidence: high, evidence:[E07]}
compress: {enabled: false, confidence: high, evidence:[E06]}
serialize: {format: protobuf, confidence: high, evidence:[E02]}
opcodes:
  source: dump.cs
  table: [{value: 1001, name: Login}, {value: 1002, name: CharList}]
  confidence: high
  evidence: [E03]
unresolved:
  - {item: "选角后的消息", need: "抓取一次选角操作", blocking: false}
```

## 5. 参考实现要改哪里

| 位置 | 改动 |
|------|------|
| `config.yaml` frame | `length_size: 4`、`length_endian: big`、`opcode_size: 2` |
| `config.yaml` crypto | `enabled: false` |
| `config.yaml` serialize | `format: protobuf`（启用 protobuf 分支） |
| `proto/opcodes.py` | 用 E03 的表整表替换 |
| `proto/messages.py` | 改成 `.proto` 生成类（protobuf）或手写 |
| `codec.py` | 参数驱动，已支持；protobuf 分支走 `SerializeToString()` |
| 新增 | 放 `.proto` 文件并生成 Python 类 |

**技术栈建议**：继续用 Python 参考实现即可（协议简单、明文）。

## 6. 闭环验证路径
```
连接 → 握手(如有) → 登录(1001) → 收 1002 角色列表 → 建角 → 选角
```
先用 `templates/mock_server.py` 造对应帧验证长连接，再落到 `server/`。

## 7. 坑与回退
- 大端/小端判错 → 用「长度值 ≤ 实际负载」验证，两种都试。
- 长度是否含头部 → 用两条不同长度包反算。
- protobuf 字段名丢失（只有 tag）→ 对照 `dump.cs` 里 IMessage 定义还原名字。
- 若某段包熵突然变高 → 可能登录后启用了加密，回退决策树第 4 节重判。