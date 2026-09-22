# 示例 B：UE5 + KCP + 自定义二进制

> **注意：这是推演示例，不是通用结论。**

## 1. 用户给了什么
- `FModel` 导出目录（`uasset`/`uexp`）
- Dumper-7 生成的 `SDK.hpp` / `SDK.cpp`
- `capture.pcap`（对战中的抓包）
- 说明：PC 端游，UE5

## 2. 证据清单

```
[E01] 目录有 *.utoc/*.ucas + libUnreal → UE5 IoStore                     高
[E02] SDK.hpp 有 NetDriver / PacketHandler 类                           高
[E03] SDK.hpp 有 class FPacketHeader { uint32 Id; uint32 Size; }        高
[E04] pcap: UDP 到 *:7777，每包前 4 字节几乎相同(conv)                    高
[E05] 包结构符合 KCP: conv/cmd/frg/wnd/ts/sn/una/len                     高
[E06] 剥掉 KCP 后负载高熵，16字节对齐                                     中→疑似 AES
[E07] SDK 里搜到 FString Length 前置 int32 用法                          高 → 自定义二进制
[E08] 密钥未在 SDK 明文中出现                                             低
```

## 3. 逐层决策

| 层 | 树节点 | 结论 |
|----|--------|------|
| 引擎 | *.utoc + libUnreal | unreal(UE5) |
| 传输 | UDP + conv 头 | udp → kcp |
| 封装 | KCP 头 + 内层 FPacketHeader | KCP 外层 + UE FPacketHeader 内层 |
| 加密 | 高熵 + 16 对齐 + 无明文 key | 疑似 AES，key 需动态 dump |
| 序列化 | FString/FPacketHeader 特征 | 自定义二进制（小端） |
| 消息号 | SDK PacketHandler | 从 SDK 抄 |

## 4. 产出 Spec 关键片段

```yaml
transport: {type: kcp, port: 7777, confidence: high, evidence:[E04,E05]}
frame:
  mode: length_prefix
  length_size: 4
  length_endian: little
  opcode_size: 4          # FPacketHeader.Id 是 uint32
  note: "KCP 外层 + UE 内层包头"
  confidence: medium
  evidence: [E03, E05]
crypto:
  enabled: true
  algorithm: aes
  key_source: derived     # 需动态 dump
  key: null
  confidence: low
  evidence: [E06, E08]
serialize: {format: binary, endian: little, confidence: high, evidence:[E07]}
opcodes: {source: sdk.h, confidence: medium, evidence:[E02]}
unresolved:
  - {item: "AES key", need: "运行时内存扫描(AES_finder)或 hook 解密函数", blocking: true}
  - {item: "KCP conv 来源", need: "抓握手包", blocking: false}
```

## 5. 参考实现要改哪里

| 位置 | 改动 |
|------|------|
| `net/server.py` | **TCP → UDP/KCP**：引入 kcp 库，改事件循环 |
| `config.yaml` frame | `opcode_size: 4`，明确"KCP 外层 + UE 内层"两级 |
| `net/crypto.py` | 实现 AES（key 从 dump 来）+ 逐连接 key 逻辑 |
| `proto/opcodes.py` | 从 SDK 抄 FPacketHandler 的 Id 表 |
| `proto/messages.py` | 按 UE FString/TArray 规则实现（int32 长度、UTF-16 负长度） |
| 技术栈 | 性能要求高 → 建议 **C++/Rust** 重写，贴近 UE 语义 |

## 6. 闭环验证路径
```
先只做 KCP 握手回包 → 客户端能建立连接
→ 再解第一个明文包（登录）→ 确认 AES 参数
→ 逐步扩展
```
**难度提示**：UE 原生 Replication 很难整体复现，优先 **Mock 关键包**让客户端过流程。

## 7. 坑与回退
- AES key 拿不到 → 先只做「解密可读的握手/登录包」，其余透传。
- KCP 与 TCP 混淆 → 看 cmd 字段取值与重传行为。
- UE 版本差异 → FProperty 链跨版本不同，以 SDK dump 为准。
- 若发现不是 KCP → 可能是自定义 UChannel，回退到纯二进制分析。