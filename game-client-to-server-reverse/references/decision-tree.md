# 决策树：逐层判定协议

> 用法：对目标项目逐层走树，把结果写进 `protocol.spec.yaml`。
> 每个节点都是「若…则…」，**不要默认套用参考实现**。

---

## 0. 路径分叉：外部服务端还是内联服务端

```
能注入 / 能改客户端（DBG / MANIP）?
 ├─ 是 ──▶ 目标只是单机化 / 离线可玩?
 │           ├─ 是 ──▶ 【内联服务端】inline-server.md（不起外部服务端）
 │           └─ 否 ──▶ 【外部服务端】继续走 §1
 └─ 否 ──▶ 【外部服务端】继续走 §1
```

> 内联路线**跳过 §2~§4**（不碰传输 / 封装 / 加密），直接从 §5 的「业务协议层」切入。
> 判据与取舍见 `inline-server.md` §0；响应对象怎么造见 `runtime-object-synthesis.md`。

---

## 1. 引擎 / 客户端语言层

```
有 libil2cpp.so 或 GameAssembly.dll ? ──是──▶ Unity IL2CPP（C#，只有签名）
    └ 有 global-metadata.dat ? 是→标准; 否→metadata 加密，需解密
    └ 有 Assembly-CSharp.dll ? ──是──▶ Unity Mono（C#，可反编译出源码）
有 *.swf / *.abc / Starling 痕迹 ? ──是──▶ ActionScript3 / Flash（JPEXS FFDec）
有 libUE4.so / libUnreal.so / *.pak / *.utoc ? ──是──▶ Unreal Engine
    └ 有 .usmap / SDK dump ? 是→直接用; 否→需 Dumper-7/UE4SS
有大量 .lua/.luac ? ──▶ Unity + Lua 热更（业务可能在 Lua）
有 classes.dex 且业务在 Java/Kotlin ? ──▶ 原生 Android（jadx）
有 *.js/webpack/sourcemap ? ──▶ JS / H5
有 libcocos2d*.so / assets/src/*.js ? ──▶ Cocos
*.dll 但非 Unity（Xamarin/.NET 应用）? ──▶ C# 桌面/移动（dnSpy 直读）
都没有 ? ──▶ 自研引擎，走纯抓包 + 二进制分析
```

> 客户端语言直接决定**反编译工具**与**能否拿到源码**。
> 详见 `client-languages.md`。C# Mono / AS3 是「能拿到源码」的两种最舒服情况。

## 2. 传输层

```
抓包有 TCP 三次握手 ? ──是──▶ TCP
    └ 有明显 UDP 流 ? ──是──▶ 看第 3 节 KCP 判定
有 TLS ClientHello ? ──是──▶ HTTPS/WSS（需处理证书固定）
端口 80/443 且负载文本 ? ──▶ HTTP/WS，优先直接抓明文
```

## 3. 封装层（帧边界）

```
UDP 流，且每包前 4 字节像是 conv ? ──是──▶ 极可能 KCP（见 3.1）
TCP 流，第 1 个字段是长度 ?
    ├─ 1/2/4 字节 ?         → frame.length_size = 1/2/4
    ├─ 大端还是小端 ?        → 用数值合理性判定（长度<负载）
    └─ 长度是否含头部自身 ?   → 用两条不同长度包反推
无显式长度，用分隔符(如 \r\n) ? ──▶ frame.delimiter
protobuf 无长度前缀（流式）?    → 需 varint 解析
```

### 3.1 KCP 判定特征
- 头 24 字节：`conv(u32) cmd(u8) frg(u8) wnd(u16) ts(u32) sn(u32) una(u32) len(u32)`
- cmd ∈ {81=push,82=ack,83=wask,84=win,85=cmd}
- 频繁小包、快速重传、ts 递增

## 4. 加密 / 压缩层

```
负载熵值 ?
  ├─ 接近 8 bits/byte（高熵） → 加密 或 已压缩
  └─ 有明显结构（低熵）       → 明文，直接看序列化
头字节特征 ?
  ├─ 78 9C / 78 01 / 78 DA → zlib 压缩，先解压
  ├─ 1F 8B                 → gzip
  └─ 无规律                → 疑似「加密 或 raw-deflate」→ 先走 4.0 快筛
加密算法猜测顺序（用已知明文/长度关系验证）:
  单字节 XOR → RC4 → AES-CBC/ECB → 自定义(XXTEA/魔改)
密钥来源判定:
  ├─ 硬编码常量        → 从二进制/Lua 里找
  ├─ 握手协商          → 看握手包是否传 key/种子
  ├─ 登录返回          → 登录响应里含密钥字段
  └─ 设备指纹派生      → 少见，需动态 dump
```

> 注意: 「高熵」不等于加密，也可能是压缩；**先试解压，再试解密**。

### 4.0  raw deflate 快筛（谈加密之前必做，血泪教训）

**真实事故**：一条 TCP 长连接流被判定为「流加密」——首包头 14B + 尾 57B 跨会话
完全相同（"静态密钥填充"）、中段 37B 每会话变化（"会话密钥交换"）；RC4 置换表
内存扫描 0 命中、全部候选密钥试解失败。**最终答案：raw deflate（zlib `wbits=-15`），
根本没有加密。**"静态头尾" = 相同明文前缀/后缀的固定压缩输出；
"变化中段" = 压缩过程对变化内容（token/时间戳）的正常响应。

游戏客户端压缩最常用的就是 **raw deflate（无 78 9C magic 头）**，
表现与流加密几乎一模一样。30 秒排除它：

```python
import zlib
stream = open('reverse/world_C2S.bin','rb').read()
plain = zlib.decompressobj(-15).decompress(stream)   # wbits=-15 = raw deflate
# 解出来了 → 没有加密；抛 zlib.error → 再按下面的表试其他无 magic 压缩
```

zlib 失败后的其他无 magic 压缩候选（按序试）：

| 格式 | 判定法 |
|------|--------|
| raw deflate | `decompressobj(-15)`（多数引擎首选） |
| zlib 带 preset dict | `decompressobj()` 抛 `need dictionary` → 从握手包/客户端找 dict |
| LZ4 block | 无 magic；python-lz4 `decompress` 试解 |
| snappy | 无 magic；python-snappy 试解 |
| zstd | v0.9+ 有 magic `28 B5 2F FD`；老格式无 magic，用 zstd 库试解 |

**确认为双向压缩流后，服务端 codec 三要点**：
1. **decompressobj 全程增量喂**（`dec.decompress(chunk)` 逐段调用）——zlib 流跨
   TCP 段，不能攒整包解；中途出错**不能重建 decompressor**（流状态已毁）。
2. 压缩侧 `compressobj(wbits=-15)` 输出累积后直接 send，**不要逐帧 flush**
   （会切断压缩上下文、效率也差）。
3. 解压出的明文再按封装层切帧。注意：**同游戏多类服务器常共用同一种帧格式，
   只有传输层滤镜不同**（本例：center=明文，world=raw-deflate，帧格式完全一致）。

### 4.1 加密假信号（别被差分分析骗了）

跨会话差分（两次连接的密文 XOR 对比）是判定加密的常用手段，但以下情形制造假信号：

| 假信号 | 真相 | 识别 |
|--------|------|------|
| 头尾跨会话相同 | 压缩输出：相同明文前缀压出相同字节 | 4.0 快筛 |
| 中段每会话变化 | 压缩对变化内容（token/时间戳）的正常响应 | 解压成功 |
| 内存搜到"密钥样"字节串 | 时区库/资源表等无关数据（实测踩坑） | 用已知明文（角色名/域名）验证 |

真正的流加密差分特征：**连固定结构字段（长度头）每次都不同**；
压缩流的小包压缩后依然短小、且与明文结构相关。
**任何"疑似加密"先过 4.0 快筛，再上 Ghidra/动态分析。**

## 5. 序列化层

```
字符串可读(键值对) ? ──▶ JSON
字段 tag 形如 (field<<3|wire) ? ──▶ protobuf（用 protoc --decode_raw）
有 0x93 等 msgpack 标记 ? ──▶ MessagePack
定长字段、无分隔、含 int32 长度前缀字符串 ? ──▶ 自定义二进制
  └ 对照客户端结构体字段顺序还原
```

## 6. 消息号 / 分发

```
客户端有 switch(opcode)/Dictionary<id,handler> ? ──▶ 直接抄消息号表
Lua 里有 sendMsg(cmd, ...) ?                ──▶ 从 Lua 抄
UE 有 ProcessEvent / RPC 表 ?               ──▶ 从 SDK dump 抄
都拿不到 ?                                   ──▶ 由抓包首字段聚类反推
```

## 7. 架构层（服务端形态）

```
目标只是"能跑通" ? ──▶ 单进程 Python/Node（参考实现套路）
要长期在线/多人 ?   ──▶ Go/Rust + 网关/逻辑分离 + Redis
客户端强制 HTTP ?    ──▶ HTTP 网关（FastAPI/Express）+ 长连接网关混合
协议是 UE 原生复制 ? ──▶ 需实现 UE 的 NetDriver 语义（难度高，优先 Mock 关键包）
要发布给普通用户用 ? ──▶ **预编译多平台二进制 + GUI 启动器**（参考案例 A）
有战斗/大厅分离 ?    ──▶ 多端口（主端口+1 战斗，+2 后台）
```

### 7.1 通用子系统清单（无论什么游戏都要想）

| 子系统 | 说明 | 常见形态 |
|--------|------|---------|
| 账号 | 注册/登录/token | SQLite/MySQL |
| 存档 | 进度持久化 | SQLite 文件 |
| 后台 | 运营/发奖/封号 | HTTP，仅本机端口 |
| 资源分发 | 客户端下载资源 | 本地目录 / CDN |
| 端口约定 | 主/战斗/后台 | 主、主+1、主+2 |
| 客户端对接 | 改地址/跳过登录 | 配置文件 / 源码 patch |
| 发布打包 | 给用户的东西 | 预编译 exe + 启动器 |
| **人机(假玩家)** | **多人游戏凑人数** | 服务端内部逻辑 Bot（`bots.md`） |

> 详细案例见 `cases.md`（Go 服务端、Node 服务端各一例）。

### 7.2 人机（Bot）判定 ——  属后续拓展

> 人机**不影响核心运行**（见 §17）。这里只在"确认要做"时用。

```
目标游戏是否"必须多人才能开局" ?
   ├─ 否 ──▶ 不需要（核心链路里直接跳过）
   └─ 是 ──▶ 仍属拓展：先跑通核心，再做
              ├─ 客户端有 IsAI/robot 字段 ? ──有──▶ 可按官方字段复刻
              └─ 完全没有 AI 痕迹 ? ──▶ 降低开局门槛或 patch（标注）
              再判归属：客户端有决策代码 ? ──▶ 客户端AI（服务端只标记槽位）
                                          └──▶ 服务端AI（服务端驱动动作）
```

详见 `extensions/bot-reverse.md` 与 `extensions/bots.md`。

## 8. 决策输出模板

对每层写一行到 Spec：
```yaml
transport: { type: tcp, evidence: E03, confidence: high }
frame:     { length_size: 2, length_endian: little, includes_self: false,
             opcode_size: 2, evidence: [E03,E07], confidence: high }
crypto:    { enabled: true, algorithm: xor, key_source: hardcoded,
             evidence: E09, confidence: medium }
serialize: { format: binary, endian: little, evidence: E11, confidence: high }
opcodes:   { source: dump.cs, count: 137, evidence: E02, confidence: high }
```

> 任何 `confidence: low/medium` 的项，都必须在闭环验证阶段重点核对。