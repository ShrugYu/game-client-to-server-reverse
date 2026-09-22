# 零输入自举：只有一个安装包怎么办

> **最常见的情况**：用户只丢来一个 `.apk` / `.ipa` / `.exe`，什么都没给。
> 这时不能等证据 —— 要**自己把证据造出来**。
> 本文是完整的「安装包 → 证据 → Spec」流水线。

---

## 目录

> 0 总原则 · 1 隔离环境 · 2 解包 · 3 判引擎/语言 · **4 自产静态证据（核心）** · 5 运行抓包 · 6 动态 dump · 7 加壳/加固 · 8 跑不起来的降级 · **9 动作清单** · 10 常见卡点速查 · 11 给 AI 的行为约定

---

## 0. 总原则

```
安装包 ──① 解包 ──▶ 原始文件 ──② 判引擎/语言 ──▶ 选工具
      ──③ 静态产物(dump.cs/lua/asset) ──▶ 证据
      ──④ 运行抓包 ──▶ 协议证据
      ──⑤ 动态 dump ──▶ 密钥/运行时数据
      ──⑥ 汇总 ──▶ protocol.spec.yaml ──▶ 服务端
```

**关键心态**：用户给一个包 = 把「取证」这件事也交给了你。
不要反问"你能给我 dump.cs 吗"，而是**自己跑 Il2CppDumper**。

---

## 1. 准备工作（隔离环境）

| 类型 | 建议 |
|------|------|
| 运行环境 | **独立模拟器**（MuMu/雷电/Waydroid）或备用机；不要用主力机 |
| 抓包 | mitmproxy（HTTP/WS） + tcpdump/Wireshark（TCP/UDP） |
| 动态 | Frida（推荐）、x64dbg、IDA/Ghidra |
| 解包 | apktool、unzip、7z、AssetStudio、FModel、Il2CppDumper |
| 设备工具 | adb（安卓）、ideviceinstaller（iOS）、一切在虚拟机/沙箱 |

> 注意: 全程只在**自研/已授权/学习**目标上操作；隔离环境既为安全也为可回滚。

---

## 2. 第一步：解包

### 2.1 Android APK

```bash
# 基础解包
unzip -o game.apk -d game_apk/

# 看结构
ls game_apk/
#   AndroidManifest.xml   (可 apktool d 反编译)
#   classes*.dex          (Java/Kotlin 代码)
#   lib/<abi>/*.so        (原生库：il2cpp/UE/自研)
#   assets/               (资源、lua、配置)
#   res/
#   META-INF/
```

**分裂 APK / OBB**（很多大游戏）：
```
app.apk + split_config.arm64_v8a.apk + ... + main.obb
```
- 把所有 split 都解包，`lib/` 与 `assets/` 常在 split 里。
- OBB 是资源包，放到设备 `Android/obb/<pkg>/` 才能运行。

### 2.2 iOS IPA

```bash
unzip -o game.ipa -d game_ipa/
ls game_ipa/Payload/*.app/
#   主二进制（Mach-O）、Frameworks/、Assets.car、*.bundle
```

### 2.3 Windows EXE

- 直接看安装目录：`GameName_Data/`(Unity) / `Engine/`+`Binaries/`(UE) / `*.pak`
- 若是安装器，先安装到沙箱，再分析安装目录。

---

## 3. 第二步：判引擎 / 语言

对照 `client-languages.md` §0 与 `decision-tree.md` §1：

```bash
# Unity IL2CPP
ls game_apk/lib/*/libil2cpp.so
ls game_apk/assets/bin/Data/Managed/Metadata/global-metadata.dat

# Unity Mono
ls game_apk/assets/bin/Data/Managed/Assembly-CSharp.dll

# UE
ls game_apk/lib/*/libUE4.so ; ls game_apk/assets/*.pak

# Lua / 配置
find game_apk/assets -iname '*.lua*' -o -iname '*.luac' | head

# Flash/AS3 (少见但有)
find game_apk -iname '*.swf' -o -iname '*.abc'
```

---

## 4. 第三步：自产静态证据（核心）

### 4.1 Unity IL2CPP → dump.cs

IL2CPP 需要**两个文件配对**：`libil2cpp.so` + `global-metadata.dat`（都在包里）。

```bash
Il2CppDumper.exe game_apk/lib/arm64-v8a/libil2cpp.so \
                game_apk/assets/bin/Data/Managed/Metadata/global-metadata.dat \
                out/il2cpp/
# 产出：dump.cs / script.json / il2cpp.h / DummyDll/
```

- `global-metadata.dat` 头不是 `AF 1B B1 FA` → 被加密，见 §6 动态 dump。
- 拿到 `dump.cs` 后按 `unity.md` §A4 搜网络关键词建索引。

### 4.2 Unity Mono → 直接反编译

```bash
# Assembly-CSharp.dll → dnSpy / ILSpy，几乎拿到源码
```

### 4.3 Unity 资源 / 配置表

```bash
# AssetStudio (GUI) 打开 assets/bin/Data/ 或 .bundle
#   导出：TextAsset、MonoBehaviour、配置(csv/json/bytes)
# 或 AssetRipper 导出工程
```
- 配置表常在 `assets/` 的 `TextAsset` 里，导出即得数值表。

### 4.4 Unreal → 资源与 SDK

```bash
AES_finder.exe            # 从运行中的进程找 pak AES key
# FModel 打开 .pak/.utoc，加载 .usmap 后导出
# UE4SS / Dumper-7 运行时 dump SDK（需要能跑起来）
```

### 4.5 原生 Android → jadx

```bash
jadx -d out/java/ game.apk     # 或对 apktool 后的 dex
```

### 4.6 Lua / 配置

```bash
# 先判是否加密
xxd assets/xxx.lua | head
# 明文 luac 头 1B 4C 75 61 → unluac
unluac assets/xxx.luac > xxx.lua
```

---

## 5. 第四步：运行抓包（协议证据的来源）

纯静态只能给你字段定义，**帧格式与消息序必须抓包**。

### 5.1 搭环境
```bash
# 模拟器里装游戏；PC 上起代理
mitmproxy -p 8080
# 模拟器 Wi-Fi 代理指向 PC:8080；安装 mitm CA 到系统信任
```

### 5.2 绕证书固定
```bash
frida -U -f <package> -l templates/frida_bypass_ssl.js
```

### 5.3 非 HTTP（TCP/UDP/KCP）抓包
```bash
# 模拟器/设备走 VPN 或 PC 热点，PC 上用 tcpdump
tcpdump -i any -w capture.pcap host <server_ip>
# 或 Android 上
adb shell tcpdump -i any -w /sdcard/c.pcap
adb pull /sdcard/c.pcap
```

### 5.4 操作清单（每次只改一个变量）
| 操作 | 目的 |
|------|------|
| 冷启动到登录页 | 抓握手/版本号 |
| 登录 | 抓鉴权与 token |
| 建角/选角 | 抓状态机 |
| 进场景/移动 | 抓长连接心跳与同步 |
| 点一次商店/充值 | 抓支付路由 |

> 把每次操作**单独抓一段**并命名，便于差分（见 `adaptation.md` §B）。

### 5.5 找不到服务器地址？
```bash
# 从 .so 里搜 IP/域名
grep -a -E '([0-9]{1,3}\.){3}[0-9]{1,3}|https?://|ws://' lib/*.so | head
# 或在抓包工具里看 DNS/SNI
```

---

## 6. 第五步：动态 dump（静态拿不到时的兜底）

| 目标 | 方法 |
|------|------|
| 加密的 `global-metadata.dat` | Frida hook `MetadataLoader::LoadMetadataFile` 出口，dump 明文 |
| pak AES key | AES_finder / hook `FAES::DecryptData` |
| XOR/RC4 密钥 | Frida hook `Encrypt`/`Decrypt` 或直接内存搜 |
| 解密后的 lua | hook lua 加载器 |
| 运行时结构体 | Frida + il2cpp 模式按类名读字段 |

```javascript
// 示例：hook 常见加解密函数
Interceptor.attach(Module.findExportByName(null, "XXTEA_Decrypt"), {
  onLeave(retval) { console.log(hexdump(retval)); }
});
```

---

## 7. 加壳 / 加固怎么办

原生 Android 游戏常见加固（360/腾讯乐固/梆梆/爱加密）：

1. 判断是否加固：看 `assets/` 是否有 `libjiagu*.so` / 壳特征 / dex 异常小。
2. 脱壳思路：
   - **Frida 脱壳**（内存 dump dex / 主动调用）
   - **静态脱壳机**（针对特定壳）
   - 直接找源 APK（很多游戏能下到未加固版本 —— 优先）
3. 若 `libil2cpp.so` 被加密 → 走 §6 动态 dump 内存中的 so。
4. 加固只影响 `dex`/`so` 提取，**不影响抓包**。

> 优先策略：**能抓到包 + 能拿到 metadata，就够起服务端**；不必强求完整脱壳。

---

## 8. 完全跑不起来（无法动态）时的降级路径

```
1. 静态解包 → 拿 dump.cs / assets / 配置
2. 若 metadata 加密且无法动态 → 目标改为「只还原可读的部分」
3. 用客户端字符串/资源里的协议名反推路由
4. 服务端先做「能连上+握手」，用占位字段推进
5. 在 Spec 里把未确认项标 unresolved，阻塞项说明
```

**仍然能产出**：project-profile + 部分 spec + 服务端骨架。不阻塞交付。

---

## 9. 从安装包到 Spec：动作清单

```
[ ] 1. 解包（含 split/obb）
[ ] 2. 判引擎与客户端语言
[ ] 3. 自产静态证据：dump.cs / dll / lua / 资源 / 配置
[ ] 4. 搭抓包环境，绕 pinning
[ ] 5. 按操作清单抓包（每操作一段）
[ ] 6. 需要时动态 dump 密钥/metadata
[ ] 7. 填 out/project-profile.yaml（含 needs）
[ ] 8. 填 out/evidence-inventory.md
[ ] 9. 走 decision-tree 填 out/protocol.spec.yaml
[ ] 10. 进 codegen 写服务端
```

---

## 10. 常见卡点速查

| 现象 | 原因 | 对策 |
|------|------|------|
| `global-metadata.dat` 头不对 | 加密 | §6 动态 dump |
| 抓包全是乱码 | 加密/压缩 | **先过 raw-deflate 快筛**（`decision-tree` §4.0，30 秒排除压缩），再谈加密 |
| 装上就闪退 | 模拟器检测/加固 | 用真机或换模拟器；脱壳 |
| 连不上服务器 | 有版本强制更新 | 抓更新接口，Mock 它返回当前版本 |
| 冷启动卡更新/闪退回桌面 | **官方 OSS 删了热更版本文件（404）** | transparent proxy mock 该文件（如 `*.zipver`）返回 APK 内置版本号，其余透传官方（实测：官方删档 ≠ 官方全下架，逐个文件探） |
| 模拟器连官方端口被 RST（PC 直连正常） | 模拟器用户态 NAT 对特定端口数据面坏 | PC 起 TCP 中继 + DNAT 指中继（`client-address-sources.md` §3.0） |
| 只有 OBB 没主包 | 分裂 APK | 补下 split |
| 抓不到包 | 证书固定 | `frida_bypass_ssl.js` |
| 游戏要求登录 | 有 SDK | Mock 登录接口 或 patch 客户端跳过（`client-languages.md` §7） |
| 资源下载失败 | CDN 校验 | 本地起资源服务，或关掉校验 |

### 10.1  先探「官方基础设施还活着吗」（能省一半工作）

停服游戏 ≠ 服务器全关。实测一例：游戏停运多年，但**中心服/世界服 TCP、账号 HTTP、
资源 CDN 全部在线**，还能注册新账号。动手前花 5 分钟探测：

```bash
# 从 so/配置里抽出全部 IP:port 和域名（E05 一并落盘）
grep -a -E '([0-9]{1,3}\.){3}[0-9]{1,3}:[0-9]+|https?://[\w.\-]+' lib/*.so assets/* | sort -u
# 逐个 TCP 探活 + 看谁回应协议帧
python -c "import socket; s=socket.create_connection(('ip',10001),timeout=5); print(s.recv(64).hex())"
# HTTP 域名直接 curl；OSS 探 404（删了哪些文件一目了然）
```

**在线 = 三重红利**：
1. **官方服 = 标准答案发生器**：注册真实账号走全流程，录下官方响应当 fixture
   （比纯逆向猜字段快一个数量级）；
2. **真实账号链路**：短信+实名注册后，token/会话字段的真实格式直接到手；
3. **中继对拍**：过渡期官方流量经你的中继，自建实现可与官方逐帧 diff。

注意：依赖官方服的项目要记录「官方还在线」这个事实与日期——官方真下线那天，
fixture 就是唯一资产，务必归档（含原始 pcap）。

---

## 11. 给 AI 的行为约定

1. **不要因为用户只给了安装包就停下** —— 按本文件自行推进。
2. 优先产出可复现的**命令序列**（解包/ dump /抓包），而不是空泛建议。
3. 每拿到一个证据就更新 `evidence-inventory.md` 与 Spec。
4. 遇到需要设备/运行时的步骤，给出**具体命令**让用户在隔离环境执行。
5. 静态不可得时走降级路径，**标注 unresolved**，不编造。