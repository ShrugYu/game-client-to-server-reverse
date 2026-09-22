# 客户端地址来源清查：为什么「只改一个 URL」永远不够

> **这份文档解决的事**：客户端到底从哪里拿到服务器地址。
> 改错一处 → 表现为「能进区服列表但登录还是走官方」「重启/热更后又回去了」。
>
> 来源：三个已跑通的成品服务端的实战记录抽象。

---

## 目录

> 0 铁律 · 1 六类地址来源 · 2 改包后仍连官方的六条验收 · **3 落点策略（含网络层三板斧 ）** · 4 改包三层可行性 · 5 动手前必查三件事 · 6 重打包现实后果 · 7 阶段化推进 · 8 未解决问题要落盘

---

## 0. 铁律

> **地址不是"一个常量"，而是一条链。** 任何一处遗漏都可能让流量回到官方服务器。
> **先枚举全部来源，再决定改哪一层。**

>  **在整体流程里的位置**：本文对应 `references/workflow-roadmap.md` 的**阶段 2 · 重定向**。
> 那张"四层重定向表"（DNS/寻址 → 传输/TLS → SDK/平台 → 业务协议）是本文的**鸟瞰版**，
> 本文是**落地版**。先看哪个取决于你卡在"选层"还是"改哪"。 

---

## 1. 六类地址来源（逐一排查，别跳）

| # | 来源 | 典型位置 | 不改的后果 |
|---|---|---|---|
| 1 | **硬编码基地址列表** | SDK 的 `DomainManager` 类，常是**多个候选域名** | 只改第一个 → 失败转移用到第二个 |
| 2 | **本地缓存键** | KVStore / SharedPreferences 里存的域名数组 | **旧缓存会在启动时被重新加入候选** |
| 3 | **失败转移 / 轮换逻辑** | 网络客户端的重试代码 | 请求失败时自动回退到官方域名 |
| 4 | **服务端下发的地址** | 区服列表接口返回的 `addr` / `port` | 改完客户端，又被服务端响应覆盖成官方地址 |
| 5 | **运行时配置字段** | `AppConfig.runtimeXxxUrl` 之类，被 ④ 覆盖 | 你改的静态值在运行时被冲掉 |
| 6 | **native / 热更 DLL** | `libil2cpp.so`、`global-metadata.dat`、热更程序集 | 静态搜索找不到，改完无效果 |

**附：URL 规范化差异**（尾部斜杠、`https` vs `http`、大小写）也会让"改了但没生效"。

### 排查命令

```bash
# 明文域名/IP/端口
grep -a -E '([0-9]{1,3}\.){3}[0-9]{1,3}|https?://' <binary_or_so>
# smali / 反编译源码里搜域名管理类
grep -rn "DomainManager\|baseUrl\|ServerListUrl\|apiHost" <decompiled_dir>
# 缓存键
grep -rn "sdk_domains\|domain_cache\|serverlist" <decompiled_dir>
# 资源/热更目录（改包后可能被覆盖）
ls assets/bin/Data/Managed/  assets/**/DLL/*.bytes 2>/dev/null
```

### 清点表（填进项目档案）

```
[ ] 1 硬编码基地址列表：<文件:行> = <域名们>
[ ] 2 缓存键：<名称> 清空方式：<...>
[ ] 3 失败转移：<文件:行> 是否可禁用：
[ ] 4 区服列表响应字段：<接口> → addr/port
[ ] 5 运行时字段：<名称> 被谁写：
[ ] 6 native/热更：<是否含地址> 判定依据：
```

---

## 2. 「改包之后还是连官方」的六条验收

改包前把这张表填满；**有一条不满足就还会回到官方**：

```
[ ] SDK 登录基址        -> 本地 HTTP 端口
[ ] 区服列表接口        -> 返回本机 TCP 地址 + 端口
[ ] 游戏 TCP            -> 本地端口
[ ] 启动数据             -> 与客户端实际消息顺序一致
[ ] 支付/订单接口        -> 能识别游戏订单
[ ] 落库                -> 结算与货币变更可持久化
```

只改区服列表 URL 的典型结果（都是实测过的现象）：

- 能看到本地区服，但 **SDK 登录仍访问原域名**；
- SDK 登录成功，但**失败转移又回原始候选域名**；
- TCP 已连上，但**启动数据缺失导致客户端断开**；
- 支付返回成功，但**角色没收到可识别的货币更新**；
- **重启或热更后恢复原地址**。

---

## 3. 重定向落点策略（从代价低的层往上做）

> **本节是「第三步 重定向」的落地。** 目标：**主动改 / 注入客户端，把请求引到我们的服务端**，
> 并**优先让客户端跑起来**。原则：从**代价最低的层**往上做（见下表），不追求一步到位。

| 优先级 | 落点 | 做法 | 代价 |
|---|---|---|---|
| **1（先做）** | 网络层重定向 | 见 §3.0 三板斧 | 要 root；不能与官服双开 |
| **1.5** | **Xposed / LSPatch 模块重定向** | 注入模块改请求目标（见 §3.0b） | 需框架；不改包，无 root 配 `LSPatch`/`NPatch` |
| **2** | **应用私有目录的地址文件** | 见 §3.1 | 需先让客户端生成目录 |
| **3** | 明文配置 / 脚本 / AS3 源码 | 直接改文本（注意包名连带） | 要重打包+重签 |
| **4** | smali / 托管程序集 | 改字节码 | 重签；可能被缓存/热更覆盖 |
| **5** | native | 逆向与 ABI 风险高 | 见 `repack-rename.md` |

### 手段全景（不止 Xposed）

> 把请求引到我们服务端的方法很多，按「要不要 root / 要不要改包」选。

**A. 不改客户端（纯网络层）**

| 手段 | 要 root | 说明 |
|---|---|---|
| hosts / DNS 重定向 | 多数要 | 地址是域名时最省事；Android 改 hosts 需 root/bind-mount |
| iptables DNAT（按 uid） | 是 | 全协议，只劫这一个游戏（§3.0 三板斧） |
| 透明代理（mitmproxy tproxy） | 是 | 按 Host 分发：游戏域名走本地、官方 OSS 透传 |
| **本地 VPN 重定向（Android VpnService）** | **否** | **免 root 首选**：自建只管目标包名的 VPN，把游戏流量转发本地 |
| 自建 DNS（DoT/DoH）/ 手机"私人 DNS" | 否 | 免 root 改域名解析 |
| TCP 中继 relay | 是 | 模拟器 NAT 坏掉时兜底 |
| 路由器 / 网关层 | 否 | 路由器改 DNS 或端口转发 |

**B. 运行时注入（不改包）**

| 手段 | 要 root | 说明 |
|---|---|---|
| Frida / objection | 否* | hook 取址/SSL/登录函数；免 root 需把 frida-gadget 打进 APK |
| Xposed / LSPosed | 是 | — |
| **LSPatch / NPatch** | **否** | **免 root 用 Xposed 模块**：把模块补进 APK（不需 root） |
| VirtualApp / VirtualXposed / 太极 | 否 | 应用虚拟化容器，在容器里 hook |
| Magisk / Zygisk 模块 | 是 | 系统级注入 |
| Shizuku | 否（授权） | 借用系统 API |

**C. 改包（重新打包）**：改 smali/dex、改托管程序集（dnSpy）、改 native so、改配置/资源（`serverlist.json`/`local_server.txt`/assets）、改包名/重签（`repack-rename.md`）、客户端自带测试开关（`sdkDummy`）。

**D. 端游 / PC 特有**：改 hosts / 改 exe 字符串、**DLL 注入 + Detours**（hook `connect`/`WS2_32`）、**WinDivert / npcap** 重定向、**LD_PRELOAD**（Linux）。

> 另有一条并列路线：**内联服务端（M11）**——不起外部服务端，在进程内合成响应 → `inline-server.md`。

### 3.0 网络层劫持三板斧（零改包，全部实测）

> 来源：自研 C++ 引擎 MMO（无任何客户端配置可改）的全链路实战。
> 适用前提：模拟器/设备有 root。**这是优先级 1 的完整展开——零改动客户端、
> 零触发签名/完整性校验、随时可回滚（删规则即回滚）。**

**先拿到游戏 uid**（DNAT 按它过滤，不伤系统其它流量）：
```sh
adb shell stat -c %u /data/data/<包名>          # 例: 10052
```

**板斧一：iptables 按 uid DNAT（TCP/UDP 全协议，最常用）**
```sh
# 把游戏的 80/10001/9541 端口流量全部转到 PC 侧 (10.0.2.2 = Android 模拟器的宿主机)
adb root
adb shell "iptables -t nat -A OUTPUT -p tcp --dport 80   -m owner --uid-owner 10052 -j DNAT --to-destination 10.0.2.2:80"
adb shell "iptables -t nat -A OUTPUT -p tcp --dport 10001 -m owner --uid-owner 10052 -j DNAT --to-destination 10.0.2.2:10001"
# 查看与回滚：
adb shell "iptables -t nat -L OUTPUT -n"
adb shell "iptables -t nat -F OUTPUT"     # 全清 = 回滚
```
PC 侧再起一个 **transparent HTTP 代理**（读原始 `Host` 头按域名分发：
游戏域名→本地 mock、官方 OSS→透传），就同时解决了「劫持自己 + 放行官方」。
> 实测要点：代理必须**按 Host 分发**——被 DNAT 后目标 IP 已丢失，但 Host 头还在；
> 转发上游时要显式连「域名解析出的 IP + 带 Host 头」（http.client 直连 IP，勿让
> urllib 走系统代理）。

**板斧二：TCP 中继 relay（模拟器 NAT 数据面异常时的兜底）**
> 真实事故：模拟器直连某官方端口被 RST（PC 直连同端口正常）——
> 模拟器**用户态 NAT 对特定端口的数据面会坏**。表现：`Connection::ConnectServer
> success` 后协议超时、抓包只见 ACK 无数据。对策：PC 起双向透传中继，DNAT 指中继：
```python
# relay.py 核心: 每连接双向 pump, 双线程
import socket, threading
def pump(a, b):
    try:
        while (d := a.recv(65536)): b.sendall(d)
    finally: a.close(); b.close()
def handle(c, real):
    up = socket.create_connection(real, timeout=10)
    threading.Thread(target=pump, args=(c, up), daemon=True).start()
    pump(up, c)
# listen 10001 → ('官方center_ip', 10001)；9541 同理
```
> 附带红利：中继位置天然是**抓包/改包注入点**（mock 过渡期用它录「官方标准答案」，
> 与自建实现对拍）。

**板斧三：bind mount 覆盖只读分区的 hosts**
> `/system/etc/hosts` 在 ro 分区 + AVB，`mount -o remount,rw` 必失败。但 **bind mount
> 可以覆盖只读文件**（同分区可写路径即可）：
```sh
adb root
adb shell "echo '10.0.2.2 user-v4.example.com oss.example.com' > /data/local/tmp/hosts"
adb shell "mount -o bind /data/local/tmp/hosts /system/etc/hosts"
# 回滚: umount /system/etc/hosts 或直接重启
```
> 适用：客户端连的是**域名**而非 IP（DNAT 板斧一管不到 UDP DNS）。
> 但注意：**很多模拟器（MuMu 等）的用户态 NAT 自带 DNS 代理**，会先于 hosts 劫持
> UDP:53（内核 iptables 计数器在涨、包却进了 NAT 上游）。此时改 hosts 也没用，
> 要么走 DNAT（TCP 层），要么起自己的 DNS（UDP+TCP 53，可用 5353/15353 测试后切换）。

**三板斧组合的典型拓扑**（实测全链路）：
```
模拟器游戏(uid 10052)
  ├─ DNS(53)      → [模拟器NAT自带代理,不可改] → 用 bind-mount hosts 或自建DNS
  ├─ HTTP(80)     → DNAT → PC transparent proxy (按Host分发: mock登录/OSS透传)
  └─ TCP(10001/9541) → DNAT → PC relay / PC mock server
```

**三个坑提前说**：
1. 模拟器重启后 iptables/挂载**全丢**——把设置命令写成脚本，重启后重跑。
2. DNAT 的目标写 `10.0.2.2`（标准模拟器宿主地址）；真机场景写局域网 PC IP。
3. 模拟器自带的 adb 与系统 adb **server 版本互杀**（32/41 互不兼容）——统一用
   模拟器自带 adb，否则设备频繁掉线。

### 3.0b Xposed / LSPatch 模块重定向（不改包，免 root 也能用）

> 在 Zygote 层 hook 目标游戏的网络层，把请求目标改到我们的服务端。
> 代表项目：面向手游的代理模块（面向动漫手游的代理模块）。

- **能做什么**（按游戏分别打补丁，都封装在模块里）：
  - 把登录 / 游戏请求**重定向到指定私服**；
  - 需要时顺带**禁用该游戏的完整性校验**（具体做法按目标游戏而定）。
- **用法**：装模块 → 匹配游戏包名 → 菜单「配置管理」填写我们的服务器地址 →（固定场景）导出配置。
  **静默模式**：把 `agp_config.xml` 放进 APK 的 `assets/`，再用 **LSPatch** 修补 APK → 不弹窗、始终按配置连我们的服。
- **无 root 可用**：`LSPatch` / `NPatch（推荐）`。
- 注意：**不支持 PC 模拟器**；部分功能在模拟器会失效。

> 适用：想"让客户端像连官方一样连我们服务端"、又不想反编译改 so 时，这是**最贴近目标**的一类手法。
> （第三方代理模块 已内置多款游戏的禁用校验补丁 —— 说明这条路是**业界已验证**的。）

> **可直接用的模板**（本 skill 自带）：
> - `templates/xposed-redirect/` —— LSPosed 模块骨架（**Java / OkHttp 客户端**：hook `okhttp3.Request$Builder.url` / `java.net.URL`），
>   配置走 `/data/local/tmp/redirect_config.txt`；无 root 用 LSPatch/NPatch。
> - `templates/frida-redirect.js` —— **native / il2cpp / Unity 客户端**：hook `getaddrinfo` / `connect`。
>
> 无 root 用 **LSPatch / NPatch** 修补时会**重签名** → 在 LSPatch 里把 **Signature Bypass 调到等级 2**
> （`repack-rename.md §8`）让校验仍看到原签名；不够再用签名破解/虚拟容器。

### 3.1  应用私有目录地址文件（最容易忽略的落点）

有的客户端把服务器地址放在**自己 `files/` 目录下的一个文本文件**里，格式极简：

```text
192.168.1.100:26020
```

路径形如：

```text
Android/data/<包名>/files/local_server.txt
```

**操作顺序很关键**：

1. **先安装并启动一次游戏**，让它自动创建 `Android/data/<包名>/` 目录；
2. **退出游戏**；
3. 把地址文件写进去（覆盖同名文件）；
4. 重新打开游戏。

> 放在 `Download/` 或 `sdcard/` 根目录**无效** —— 客户端只读自己 `files/` 下的那个文件。
> 手机文件管理器访问不了 `Android/data/` 时用 ADB：
> ```sh
> adb push local_server.txt /sdcard/Android/data/<包名>/files/local_server.txt
> ```

**优点**：完全不动 APK，不触发签名/完整性校验。

### 3.2 免登录（比伪造登录更简单）

有些客户端（尤其 AS3/Flash 打包的）带一个开发开关，直接跳过平台 SDK：

```as3
// 反编译出的配置类
public static var sdkDummy:Boolean = false;   →   true
```

效果：跳过 SDK 登录、使用假 userId；支付/推送/实名等真实 SDK 功能变为 stub。
配合把域名 + 协议（`https` → `http`）改成自建地址即可。

> 思路：**能"关掉"就不要"骗过"**。伪造登录态容易在后续接口被校验掉。

---

## 4. 改包的三层可行性（先分级再动手）

| 层次 | 位置 | 可行性 | 主要风险 |
|---|---|---|---|
| Java/Kotlin（smali） | SDK 域名、缓存键、故障转移 | **高** | 域名缓存与回退仍可能覆盖修改 |
| 托管程序集 | 区服发现、登录流程 | **中** | 定义位置可能在热更资源里 |
| native（IL2CPP / UE） | `libil2cpp.so`、metadata | **低** | 重定位与 ABI 风险，改动面大 |
| 热更资源（DLL/Bundle） | 下载得到的程序集 | **不建议** | 会被下一次热更覆盖 |

---

## 5. 动手前必查的三件事

### 5.1 能不能用明文 HTTP？

```xml
<!-- AndroidManifest.xml -->
android:usesCleartextTraffic="true"
android:networkSecurityConfig="@xml/network_security_config"
```

```xml
<!-- res/xml/network_security_config.xml -->
<base-config cleartextTrafficPermitted="true" />
```

允许 → 可以直接用 `http://<局域网IP>:<端口>/`，不必折腾 TLS。
另外顺手确认有没有对目标域名做**证书固定（pinning）**——有的话要先解决，否则抓包和自建 HTTPS 都会失败。

### 5.2 当前运行的到底是哪个版本？

若客户端带 **HybridCLR / 热更 DLL**（程序集清单里出现 `HotUpdate.dll` 之类）：

- 你改 APK **内置** 的程序集，可能被下载的新版覆盖；
- 设备**已有热更缓存**时，改内置资源**完全无效**。

> 判定方法：对比「首次启动」与「已有缓存启动」的行为；看 `files/` 下有没有生成热更目录。
> **结论没拿到之前，不要动 CDN。**

### 5.3 热更/CDN 要不要一起改？

**不要。** 热更资源（Manifest/Bundle/版本目录）与业务 API 是**不同协议、不同故障边界**：

- 热更保留原站 → 客户端能正常拿到资源和代码；
- 只有认证/业务走本地 → 范围可控、可回滚。

> 只改业务地址而保留热更原站，是**第一阶段的正解**，不是妥协。

---

## 6. 重打包的现实后果（先说清楚，别事后发现）

| 情况 | 结果 |
|---|---|
| **同包名**重签 | 通常**装不上**已装的原包 → 需先卸载 → **可能丢应用数据** |
| **异包名** | 可并行安装；但 `Android/data/<包名>`、缓存、部分 SDK 绑定状态**不复用** |

重签流程固定四步：

```bash
zipalign -p 4 in.apk aligned.apk
apksigner sign --ks <keystore> --out signed.apk aligned.apk
apksigner verify --verbose signed.apk
# 装到设备后逐条对 §2 的清单
```

> 「静态搜索没找到签名校验」**不能**说明没有校验 —— 只能说明搜索范围里没有。
> 仍然要实机验证。

---

## 7. 阶段化推进（每阶段只判定一件事）

```
阶段 0  保留原始输入：APK 副本 + SHA-256；只在副本上改
阶段 1  定位托管代码里的地址定义（确认是不是热更版本）
阶段 2  最小改动：把所有 SDK 候选基地址收敛到本地
阶段 3  区服发现：/server/list 返回本机 addr:port
阶段 4  重打包安装，按顺序观察：区服列表 → SDK 登录 → TCP 连接 → 登录请求 → 启动序列
阶段 5  确认热更影响（对比首次启动 vs 有缓存启动）
```

**第一阶段的验收只应判定到「TCP 连接 + 收到登录请求 + 启动数据按序发送」**，
不要在这一步就要求支付/钻石到账闭环。

---

## 8. 未解决问题要显式落盘

这份文档的末尾必须留一节「当前未解决」，例如：

```
1. 某地址的定义与最终赋值位置尚未定位
2. 当前设备加载的是 APK 内置程序集还是热更程序集，未确认
3. 重签测试包是否触发签名/包名校验，未实机验证
4. 修改后是否会被域名缓存/失败转移覆盖，未实机验证
```

> 写下来 = 下一个接手的人不用重新发现一遍。