# 反推主流程（阶段 1~10 · 详细版）

> 本文件是 `SKILL.md §1~§10` 的**详细版**：每步的命令、工具、判断与常见坑。
> 只用骨架时看 SKILL.md 的对应小节；要动手时打开这里。

---

## 1. 输入分类与预处理

> 本步属工作流「第 0~1 步」。**先扫描、先建档，再进分支**；不要一上来就套参考实现。

**按输入判定引擎/语言** → 完整判定表见 `client-languages.md §0`：
`dump.cs/libil2cpp.so`=IL2CPP ｜ `Assembly-CSharp.dll`=Mono(可出源码) ｜ `*.lua/luac`=Lua 热更 ｜
`*.usmap/.pak/.utoc`=UE ｜ `classes.dex`=Java ｜ `*.js/webpack`=JS ｜ 只有 APK/EXE/IPA=未知 → §2。

**三条预处理原则**：
- `dump.cs` 是 IL2CPP 的"地图"：先 grep 网络关键词（`Socket/Send/Recv/Message/Proto/Packet/Cmd/MsgId`）建索引，再精读。
- Lua 先判加密（`luac` 头 `1B 4C 75 61`=明文）→ 再 unluac/luadec 反编译。
- `.usmap` 恢复 FModel 的 unversioned 结构；SDK dump 直接给类偏移。

---

---

## 2. 阶段一：侦察与引擎识别

**引擎判别**（解压看 `lib/` 或安装目录）：
```
Android(lib/)  libil2cpp.so+global-metadata.dat → IL2CPP ｜ libmono.so+Assembly-CSharp.dll → Mono
               libUE4.so → UE ｜ libcocos2d*.so → Cocos（见 cocos2d.md）
Windows        Game_Data/Managed → Unity ｜ */Binaries/Win64+Engine → UE ｜ GameAssembly.dll → IL2CPP
```
**网络情报**：`grep -a -E '([0-9]{1,3}\.){3}[0-9]{1,3}|https?://|ws://' <binary>`；抓一次启动流量看连了哪些 host → 判 HTTP / 长连接 / KCP / QUIC。
**产出**：`recon/engine.md`、`recon/endpoints.md`。

---

---

## 3. 阶段二：流量获取

1. 起代理（mitmproxy/Charles）并配置客户端。
2. **握手失败** → 有证书固定：Frida hook `SSL_CTX_set_verify` / `X509TrustManager` / `CertificatePinner`；桌面 hook `WinHttpQueryOption` / `libssl`；自测可重打包注入信任。
3. **流量乱码** → 记原始字节，进入 §4 分层。
4. 经验：UE 常见自研 UDP + 自定义序列化；Unity 常见 TCP/WS + protobuf。
**产出**：`capture/*.pcap`、`capture/flows/`。

---

---

## 4. 阶段三：协议分层识别

按顺序剥离，每层写证据：
```
[1] 传输    TCP / UDP / KCP(conv头+快重传) / QUIC / WebSocket
[2] 封装    长度前缀(LE/BE) / 分隔符 / protobuf tag / UE FPacketHeader
[3] 加解密  ent/直方图高熵→压缩或加密；RC4 / XOR / AES(块对齐16) / UE CRC+XXTEA
[4] 压缩    zlib(78 9C) / lz4 / gzip   ← 注意: raw-deflate 最易被误判成加密，先过 decision-tree §4.0 快筛
[5] 序列化  JSON / protobuf / MessagePack / 自定义二进制
```
**关键判定**：KCP 头 `u32 conv + u8 cmd + u8 frg + u16 wnd`(UDP)；protobuf tag `(field<<3)|wire_type`（`protoc --decode_raw` 试解）；UE 用 `FArchive` 小端 + 字符串带 int32 长度。
**产出**：`protocol/layers.md`（每层：字节样本 + 判定理由）。

---

---

## 5. 阶段四：客户端静态分析（分引擎）

> 各引擎的完整命令与坑见 `client-languages.md`、`unity.md`、`unreal.md`、`from-installer.md`。这里只留要点。

| 引擎 / 语言 | 工具 | 要点 |
|-----------|------|------|
| Unity IL2CPP | Il2CppDumper(+IDA/Ghidra) | `global-metadata.dat` magic 应 `AF 1B B1 FA`；不符=加密，搜 `MetadataLoader::LoadMetadataFile` 回溯解密点。dump.cs 先 grep 网络/序列化关键词建索引 |
| Unity Mono | dnSpy / ILSpy | 近源码；加密则定位 Mono `image` 解密点 |
| Unity + Lua | unluac / luadec | 找 xlua/tolua/slua 加载器与解密；字节码魔改需先还原 opcode 表；Lua 常承载业务字段与消息号 → 与 dump.cs 交叉验证 |
| Unreal | FModel / UE4SS / Dumper-7 | pak 密钥用 AES_finder；UE5 unversioned 先出 `.usmap` 再喂 FModel；grep `NetDriver/Replication/RPC/SendPacket/PacketHandler`；`UPROPERTY(Replicated)` 属性顺序 = 序列化顺序 |
| Lua / JS 源码 | grep + `tools/extract_interfaces.py` | 拿到源码 ≈ 拿到接口总表 |

**脚本源码客户端（Lua/JS）**：`grep -rl "protobuf\|opCode\|SendMessage\|Socket" --include=*.lua` → 判协议模式 → 扒全部 opCode → 按前缀聚类 → 看 `msg.request.*` 得 payload 字段。
常见形态 `GetMessage("OPCODE") → msg.request → protobuf.encode()`；**opCode 可能是字符串也可能是数字，必须实测**。实例见 `examples/D-real-lua-client.md`。

**接口清单提取（必做一步）**：
```bash
python3 tools/extract_interfaces.py <源码目录> --out out/interfaces.md --json out/interfaces.json
```
支持字符串/数字 opCode、HTTP 路由、protobuf 信封、C2S_/S2C_ 方法名；产出**按子系统前缀分组**的清单。
拿到后：按前缀聚类得子系统 → 逐条登记 `TRACKER.md`（[x]/[~]/[ ]/[?]/[-]）→ **先做主流程，周边后置** → 清单里没有的（如人机）标 `[-]`，别凭空造。

**自研 C++ 引擎（无源码无符号）**：
```
1. 字符串侦察：提 so 可打印串按关键词分组（网络 / 会话类名 N7…Session / 加密 / 调试 printf 格式串）
2. typeinfo→vtable：文件里 vtable 全是 0（relocation 运行时填）→ 走 .rela.dyn 或 Ghidra（windows.md §I.3）
3. Ghidra headless 批量反编译（windows.md §I.2 有模板）；先探 image base
4. 传输层：先过 decision-tree §4.0 raw-deflate 快筛
5. opcode 表：反编译 opcode 分发 switch + 抓包聚类双向确认
```
> 这类游戏 Java 层常只剩渠道 SDK 壳；HTTP 登录的 appKey/secret 常明文在 `assets/channel_config.properties`。
**产出**：`reverse/` 下 opcodes、structs、crypto、sdk。

---

---

## 6. 阶段五：字段语义推断

对每个字段产出四元组 `offset / 类型 / 含义 / 证据`。方法：
1. **差分法**：一次只改一个变量（买 1 个 vs 5 个 / 走 1 步 vs 2 步）→ 对比字节差异。
2. **结构体对照**：客户端结构体字段顺序 + 序列化顺序 → 还原 wire 布局。
3. **回灌验证**：把真实抓包喂给客户端的解密/反序列化函数，看能否还原结构体。
4. **Lua/SDK 交叉**：配置表 + 热更脚本常直接暴露字段名。

---

---

## 7. 阶段六：服务端建模与实现

1. **建模**：建 opcode 配对表（`请求 → 响应` + 触发条件）；画状态机（`连接/握手 → 登录 → 选角 → 进场景 → 战斗 → 结算`，标每步 opcode 与前置状态）；标注长连接依赖（心跳、重连、序列号、时间戳）。
2. **工程化实现**：本 skill 自带可运行服务端 `server/`（已实测跑通 握手→登录→建角→选角→进场景→移动→心跳 + XOR + zlib）。**分层架构 / "适配目标游戏只改 4 处" / 必备能力清单** → 详见 `server/README.md`；由 Spec 派生的映射 → `protocol-spec.md §D`。


**产出**：`server/`、`docs/statemachine.md`、`docs/protocol.md`。

---

---

## 8. 阶段七：部署（本地 / 服务器 / 容器）

### 8.1 本地 / 服务器 / 容器（细节见 `server/README.md`）

| 方式 | 命令 | 说明 |
|------|------|------|
| 本地 | `cd server && ./start.sh` | 看 `listening on ('0.0.0.0', 8888)` + `handlers loaded: N opcodes` |
| 联调自测 | `python client_test.py --host 127.0.0.1 --port 8888 --user alice --password 123456 --name Hero01` | 期望结尾 `[+] full flow OK` |
| systemd | `sudo bash server/deploy/deploy.sh` | 自动建用户/venv/服务；`journalctl -u gsrv -f` |
| Docker | `cd server/deploy && docker compose up -d --build` | — |

- **端口**：游戏 `8888/tcp`（KCP 再放行 `udp`）；云上需放行安全组。
- **数据库**：默认 SQLite（`data/game.db`）→ 生产改 MySQL（`database.url`）。
- **端游/手游运行环境差异**（Termux 保活 / Windows NSSM）→ `references/termux.md`、`references/windows.md`；**发布/端口族/配置冻结/备份** → `references/release-and-ops.md`。

### 8.6 客户端对接（让原版客户端连上自建服务端）
| 客户端校验 | 处理方式 |
|-----------|---------|
| 硬编码 IP/域名 | 改 `hosts`（Android 需 root 或用 Frida/模块重定向 DNS） |
| 服务端列表文件 | 改客户端配置副本里的 `serverlist.json` |
| 域名解析 | iptables DNAT / nginx 四层转发：`iptables -t nat -A OUTPUT -d 原IP -j DNAT --to-dest 自建IP` |
| 证书固定 | 自签 CA 让客户端信任；或 Frida 绕过（自测） |
| 版本号校验 | 改 `config.yaml` 的 `game.expected_version` 匹配客户端 |
| 资源/热更 URL | 重定向到自建 HTTP，提供客户端需要的资源清单 |
| **改包名 / 重打包 / 签名** | 见 `references/repack-rename.md`（AXML + arsc 等长替换、包名派生密钥资源、保留原签名） |

> 注意: **动手改包之前，先读 **。
> **推荐顺序：先"不改包 + 端口劫持"把协议跑通，最后再考虑改包。**
### 8.7 验证与回归
1. 启动服务端 → 启动原版客户端 → 观察到「成功握手 / 进入登录界面 / 进入游戏」。
2. 服务端日志逐包对照，确认 opcode 与字段解析正确。
3. 关键数值操作（买药、移动、升级）走一遍，核对服务端落库。
4. 断开重连、切换角色、多开，验证状态机完整。

**产出**：`deploy/`（Dockerfile / docker-compose / systemd / deploy.sh）、`verify/log.md`。

---

---

## 9. 阶段八：验证与回滚

- **验证记录** `verify/log.md`：命令 + 输入 + 原始输出 + 退出码。
- **回滚方案**：
  - 客户端原文件先做哈希备份，所有改动在副本上进行。
  - 服务端用配置开关，可一键回到"透传/只读"模式。
  - 记录每个修改点与还原命令。

---

---

## 10. 输出物清单（交付模板）

```
recon/engine.md            引擎与端点评测
recon/endpoints.md         服务器地址
capture/flows/             原始流量
protocol/layers.md         协议分层 + 证据
reverse/dump.cs            或 sdk.h（IL2CPP / UE dump）
reverse/opcodes.json       消息号表
reverse/structs.md         结构体定义
reverse/crypto.md          加解密说明
docs/protocol.md           协议文档
docs/statemachine.md       状态机
server/mock/               最小可运行服务端
deploy/                    systemd / docker / 部署脚本
verify/log.md              验证与回滚记录
```

---
