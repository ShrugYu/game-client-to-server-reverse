# 案例：Unity IL2CPP + ECDH 登录服（项目A / 某 Unity IL2CPP 手游 官服）

> **这是什么**：一个**真实进行中**的项目档案，用来演示「分层结论长什么样」与
> 「卡点怎么复核」。**不是**答案——各游戏协议不同，请照流程自己推。
>
> 状态：服务端能跑、协议分层已实测、客户端对接**未闭环**。
> 相关：`closure-verification.md`（本案例的教训沉淀）、、`repack-rename.md`。

---

## 1. 项目档案（摘要）

| 项 | 值 |
|---|---|
| 客户端 | Unity **IL2CPP** + **xLua** 热更（C# + Lua） |
| 版本 | 官服 `2.0.109` |
| 已知输入 | `dump.cs`（49 万行签名）、`lua_src/`（2489 文件，全业务逻辑）、真机 `tcpdump` |
| 目标 | 本地自建服 + 客户端对接，跑通登录 |
| 方法 | `M1`（Lua 白盒）+ `M2`（抓包）+ `M3`（Hook/反汇编）+ `M9`（自环） |

> 有 Lua 源码 = opCode 与请求字段名可 100% 还原；
> 但**帧格式、密钥协商在 native**（`libil2cpp.so`）→ 必须 M2+M3 补。

---

## 2. 分层结论（每条都带证据类型）

```
[1] 传输   TCP（主通道/登录/资源/Node）+ KCP(UDP)（多人战）
[2] 封装   u32BE 长度前缀切帧；心跳 opCode = "NONE"（空包）
[3] 加密   AES-128-ECB + HMAC-SHA1（NetCrypter）；登录走 OpenSSL 变体
[4] 压缩   资源服 payload 为 gzip
[5] 序列化 protobuf，信封 GameMessage.Message（opCode 为 string）
```

**帧格式（真机 tcpdump，u32BE 切帧成功率 100%）**：

```
┌ u32 BE  totalLen            整帧长度（含自身）
├ u32 BE  0x0000000C         常量 12（头部长度）
├ u32 BE  0x01000000         常量
├ [u8 len + len bytes] * N   u8 长度前缀的字段串
│     客户端：字段1 = 0x5C(92B) 客户端公钥；字段2 = 0x0D(13B) 会话字段
│     服务端：字段1 = 0x00(空)；字段2 = 0x0D(13B)
│     字段2 = 9 字节 ASCII 数字 + 4 字节每帧变化（nonce?）
└ 剩余 = 高熵载荷（加密）
```

> 注意: 字段长度是 **u8**，不是 u16 —— 套参考实现的默认值必错。

---

## 3. 登录服（:8001）：**服务器先发包**的 ECDH 握手

很多项目默认“客户端先发”，这个项目是反的，**实测时序**：

```
1. S2C  [u16BE=12] 12B base64 token        ←  服务器先发（8B 随机 → base64）
2. C2S  [u16BE=92] 客户端 EC 公钥（X.509 SPKI, P-256）
3. S2C  [u16BE=91] 服务器 EC 公钥
4. S2C  [u16BE=56] 挑战  [16B 随机][16B 随机][16B 派生值][8B]
5. C2S  [u16BE=56] 确认  [16B 随机][16B 随机][16B 派生值][8B]  ← 派生值两端相同
6. C2S  [u16BE=456] 业务请求（加密）
7. S2C  [u16BE=90] 业务应答（含 base64 节点信息）
```

**SPKI 结构**（可直接构造，本项目用纯 Python 实现 P-256）：

```
3059 3013 0607 2a8648ce3d0201 0608 2a8648ce3d030107 0342 0004 <64B 点>
```

**56B 里的 16B 派生值 = 会话级**（两端相同），但**算法未解**：
已穷举 34 种 KDF 候选全部失败 → 下一步应读
`NetworkingClientNormal.ProcessHandShakeMessage`（dump 偏移 `0x40AFB58`）。

> 教训：盲猜哈希 = 伪工作，见 `closure-verification.md` 假阳性 ⑥。

### 3.1 自建登录服的最小骨架（可复用）

```python
# 纯 Python P-256（无第三方依赖）：点加/倍乘/求逆 + SPKI 拼装
class ECDH:
    def pub_spki(self) -> bytes: ...        # 生成 91B X.509 SPKI
    def shared_secret(self, peer_spki) -> bytes:
        # 从对端 SPKI 找 b"\x03\x42\x00\x04" 或 b"\x04"，取 65B 点，算出 X 坐标
```

**必做的健壮性**（都是本项目踩过的）：

| 项 | 做法 | 不做的后果 |
|---|---|---|
| 会话态清理 | `finally: self.sessions.pop(peer, None)` | 客户端 3s 重连复用旧 secret |
| 异常可见 | `log.exception(...)` 带 step | `NameError` 被吞 → 误判成“算法不对” |
| 日志措辞 | 命中只写「候选命中（未认证）」 | 把“自己算的值相等”当成认证通过 |

---

## 4. 已证伪的结论（别重复踩）

| 曾以为 | 实际 | 证伪方式 |
|---|---|---|
| `:8081` 的 TUP/WUP 是本游戏的业务通道 | **不是** | APK 内 grep `bea_key/TYPE_COMPRESS/rsapost` **0 命中**；按 uid 看 `/proc/net/tcp` 无 8081 |
| 删掉保护 so 就能改包运行 | 不能 | 删 so / 留 so 两个对照**都秒退** → 不是缺库，是自校验 |
| 改包秒退是**唯一**卡点 | 不成立 | 复核服务端：登录响应**根本没实现**（见 §5） |

> **“证伪”也要落盘**：写在 Spec 的 `wup_business.status: NOT_THIS_GAME` 之类的位置，
> 避免下一个 AI 花同样的时间。

---

## 5. 接手时的真实缺陷清单（复核产出）

```
· login_server.py step==2 分支引用未定义变量 _h → 外层 except 吞成 warning
· 比较对象是“自己临时算的公式”，从未发给客户端 → 永远不等
· 第 3 包起只调用 _try_decrypt() 做“尝试解密 + 打日志”，全文件无业务响应构造
· sessions 在断开时未清理
```

**结论**：卡点是**两个**（客户端侧自校验 + 服务端侧登录响应未实现），
不是交接文档写的“唯一”。

---

## 6. 客户端对接的落点选择（本项目）

| 落点 | 做法 | 备注 |
|---|---|---|
| **不改包**（推荐先做） | 按 uid DNAT 到本地；或 hosts 重定向域名 | 不触发自校验；要 root |
| 改包内地址 | 地址在 Lua/明文配置里时直接改字节 | 包名变了要连带改 |

**登录服地址不在 APK 里**（Lua 运行时下载）→ 必须靠 **hosts / iptables 重定向**。

```sh
iptables -t nat -A OUTPUT -m owner --uid-owner <uid> -p tcp --dport <原端口> \
         -j DNAT --to-destination 127.0.0.1:<本地端口>
```

> 注意: 别把资源服/CDN 端口一起劫持（`repack-rename.md` §7）：首启要下载 Lua/资源，
> 劫持了会一直黑屏。

---

## 7. 可复用的产出物清单（本项目实际生成）

```
out/project-profile.yaml    读了什么/还缺什么
out/evidence-inventory.md   证据编号 + 置信度
out/protocol.spec.yaml      分层结论（帧/加密/序列化/状态机）
out/interfaces/opcodes_unique.txt   1788 个 opCode
out/interfaces/opcode_fields.md     逐接口请求字段名
verify/capture-analysis.md  真机抓包完整报告
verify/closure...           闭环与假阳性排查
```

> **1788 个 opCode 是怎么来的**：Lua 源码全量提取（`tools/extract_interfaces.py`）。
> 拿到清单后按前缀聚类 = 子系统划分，再按主流程排序实现。