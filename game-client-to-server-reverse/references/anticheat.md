# 反作弊 / 自校验 对抗手册（ACE / TSS / TPRT / FairGuard …）

> 什么时候会用到：**改包名、重签名、注入**之后客户端「秒退 / 黑屏卡死 / native 崩溃」。
> 这块不解决，后面的协议分析和服务端都白做 —— 所以优先级最高。

---

## 0. 定位：我们主动改客户端去对接自建服务端

> 目标很明确：**把客户端对接上我们的服务端**，并**优先让它跑起来**。
> 做法遵循 skill 的「**第三步 重定向**」四层表（详见 `client-address-sources.md`、`workflow-roadmap.md`）：

| 层 | 手段 | 用在哪 | 代价 |
|---|---|---|---|
| DNS / 寻址 | 对取地址函数注入，域名 → `127.0.0.1` | 地址来自域名，端口可覆盖 | 最低 |
| 传输 / TLS | HTTPS 降级 HTTP、阻断客户端证书校验、本地 CA 注入、TLS 代理 | 原协议是 TLS 且无本地证书 | 中 |
| SDK / 平台 | inline hook 登录函数，伪造成功回调 | 平台登录无法离线 | 中高 |
| 业务协议 | 服务端按真实 wire format 应答 | 始终需要 | 高（但必须） |

- 同机 → `127.0.0.1`；手机连电脑 → 电脑的局域网 IP。
- 阶段目标：**搭一个能监听、能记日志的基础服务端，让客户端请求先到达我们这边**；
  然后**从登录链最上游往下游补回包**（先服务器列表 → 再登录握手 → 最后游戏数据），
  **以"客户端能走到下一步"为通过标准**，循环「测试 → 日志 → 定位 → 修改 → 再测试」，直到进主场景。

**反作弊 / 自校验是这条路上的"拦路虎"，不是第一步要解决的问题。** 处理顺序：

1. 先按上面的四层表 + 补包循环，把客户端尽量往前推。
2. 一旦出现**秒退 / 黑屏 / native 崩溃**，用下面 §1~§2 判断"是谁在拦"。
3. 定位到拦路者后，用 §3~§9 处理（空壳化 / 关掉开关 等）。
> 对 ACE 这类硬骨头，先看 §0.1 有个预期。

---

## 0.1 ACE（腾讯）有多难？—— 一个真实逆向结论

来源：对 Free Fire 内置 ACE 的逆向分析（`Lixense/ff-ace-anticheat-analysis`）。

- **不是"一个东西"，是两库互守 + 一个看不见的服务端**：
  `libanogs.so`（对外引擎，导出 `AnoSDK*`）+ `libanort.so`（守卫：**114 处裸 ARM SVC 系统调用**、
  自校验自身 `.text` 校验和、被改动即 `kill(getpid(), 9)` 自杀）。
- **判定结果走"游戏自己的网络回调"**（`tss_sdk_send_data_to_svr`）→ 服务端**关联异常上报 → 封的是账号，不是进程**。
  所以"**屏蔽 ACE 域名**"这类教程**没用** —— 报告本来就走游戏自己的服务器。
- **SVC 系统调用在 libc 之下** → 你在 `open`/`read`/`mmap`/`connect` 上打的 PLT / inline hook **会被绕过**。
- **自校验严格到"改一个字节就自杀"** → 无法 patch、无法隐形 hook。

> 结论：对 ACE，**剥离极难但可尝试**（§3~§9）。策略上**先把四层表里代价最低的 DNS/寻址层用满**
> （hosts / DNAT / 注入），只要请求能到达我们的服务端就继续往下推进；
> 确实卡死在 ACE 本身时，再对保护 so 做空壳化，并**做好封号预期**。

---

## 1. 先分清「是谁在拦」

| 症状 | 大概率原因 | 去哪看 |
|---|---|---|
| `UnsatisfiedLinkError: dlopen failed: library "x.so" not found` | 删掉了别人 `DT_NEEDED` 的 so | logcat FATAL |
| 启动即退，**没有** Java 异常、**没有** tombstone | native 自校验主动 `exit()` | `ApplicationExitInfo` |
| 主线程卡死 / 黑屏（进程还活着） | 半初始化的保护运行时在 `sem_wait` 死等 | `debuggerd -b <pid>` |
| `java.lang.ExceptionInInitializerError` | Java 层 SDK 初始化失败（配置缺失/解密失败） | logcat `Caused by` |
| 跑几十秒才退（不是秒退） | **延迟校验**（联网回执超时后才杀） | 拉长观察窗口 |

---

## 2. 诊断三件套（必用，不用猜）

```bash
# ① 主线程 native 栈 —— 卡死/黑屏时最有价值
debuggerd -b <pid>

# ② 崩溃现场（SIGSEGV/SIGBUS/SIGABRT）
ls -lt /data/tombstones | head
grep -A 20 'backtrace:' /data/tombstones/tombstone_XX
#   · pc = 0x0000000000000000  → 跳转到空指针（函数指针表没填！）
#   · 看 #00/#01 是哪几个 so

# ③ 系统记录的退出原因（最关键，一步定位性质）
logcat -d | grep ApplicationExitInfo | grep <包名>
```

**ApplicationExitInfo 解码表**

| reason | status | 含义 | 应对 |
|---|---|---|---|
| 0 | — | UNKNOWN（常见于"自杀"） | 查 native 自校验 |
| 1 | 25 等 | **EXIT_SELF** ← 主动 `exit()` | 还有别的保护在，继续空壳化 |
| 2 | 信号号 | SIGNALED（7=SIGBUS / 11=SIGSEGV / 6=SIGABRT） | 看 tombstone 栈 |
| 4 | — | APP CRASH(EXCEPTION) | 看 Java 异常栈 |
| 5 | 11 | APP CRASH(NATIVE) | 看 tombstone 栈 |

---

## 3. ACE（腾讯）结构地图

```
com.ace.gshell.AceApplication            ← Application 基类（游戏自己的 Application 继承它）
  ├─ <clinit>: System.loadLibrary("tersafe2"); System.loadLibrary("tprt")
  ├─ attachBaseContextShell() → native initialize(pkg, nativeLibDir, filesDir, sourceDir, splits)
  └─ native: initialize / ioctl / gp6ioctl / gp7ioctl / handleLoad / handleLoadV22
libtersafe2.so    ← TSS Java 层的 JNI 实现
libtprt.so        ← 保护运行时（ELF hook / 反调试 / 完整性 & 签名校验）
```

**两条必须记住的硬事实**

1. **`libunity.so` 直接 `DT_NEEDED libtprt.so`** → **so 不能删**（删了 `dlopen libunity` 直接失败 →
   `JNI FatalError` → SIGABRT）。要"剥离"只能**换空壳**。
2. **`libtprt.so` 里硬编码原包的证书指纹**（rodata 里能看到明文 `SHA-1` / `SHA-256` 十六进制串），
   运行期读 APK 证书比对 → 不符就杀进程。

> 定位手法：`strings -a libtprt.so | grep -iE '^[0-9A-Fa-f]{40,64}$'`
> 再拿它和 `MT / apksigner / keytool` 报告的证书摘要对一下就明白了。

---

## 4. 三种应对（按推荐度）

### [x] 方案 A：把保护 so **空壳化**（首选）

```bash
cd /tmp && python3 -c "import zipfile;z=zipfile.ZipFile('game.apk');open('libtprt.so','wb').write(z.read('lib/arm64-v8a/libtprt.so'))"

# 1) 摸清依赖与符号
readelf -d libunity.so | grep NEEDED                 # 谁依赖谁
readelf --dyn-syms --wide libtprt.so   | awk '$7!="UND"{print $4,$7,$8}'   # 原库导出
readelf --dyn-syms --wide libunity.so  | grep UND    # ← 注意 FUNC 和 OBJECT 都要看！

# 2) 生成 + 编译空壳（本 skill 自带脚本：自动读原库的全部导出符号，
#    按原始大小复刻数据符号/函数指针表并填有效指针，soname 也照抄原库）
python3 tools/make_stub_so.py libtprt.so libtprt_stub.so \
        --extra-jni Java_com_ace_gshell_AceApplication_initialize
#    （也可以自己写 stub.c 再 gcc）
```

**空壳必须做到（少一条就会崩）**

- [x] 文件名 / `SONAME` 与原库一致（DT_NEEDED 靠 soname 解析）
- [x] 导出**原库所有符号**：FUNC **和 OBJECT**（漏一个就可能 SIGSEGV）
- [x] **复刻数据符号**，尤其是**函数指针表**
      例：`g_tprt_pfn_array` = 432B（54 项）、`g_tprt_ori_array` = 168B（21 项）
      → 必须**填上有效函数指针**（填 0 → 调用方 `blr x0` 跳到 0 → SIGSEGV）
- [x] 补上 Java 层要的 **JNI 函数**：按 `Java_<下划线化类名>_<方法名>` 导出，返回中性值
      （`initialize` 返回 0 表示成功；`JNI_OnLoad` 返回 `0x00010006`）
- [x] 别在空壳里做任何 `exit()`

**故障 → 原因 对照**

| 现象 | 原因 |
|---|---|
| `No implementation found for ... AceApplication.initialize` | 空壳少了这个 JNI 函数 |
| `SIGSEGV, fault addr 0x0, pc 0x0` | 函数指针表没填（或漏了 OBJECT 符号） |
| `EXIT_SELF status=25` | **还有另一个保护模块**（把剩下的也空壳化） |
| `JNI FatalError: Unable to load library: ...libunity.so` | 依赖的 so 被删了/名字不对 |

> 实践顺序：**一次只换一个 so**，每换一个立刻装测，看退出原因是否变化 —— 这样能快速定位"还剩谁在拦"。

### [~] 方案 B：保留**原包签名**（仅当校验只读证书，不重算摘要）
1. 构建时**不要用自己签名**（或签完再换）
2. 从原包取出 `META-INF/*.RSA` / `*.SF` / `MANIFEST.MF` 塞回新包
3. **删掉 APK Signing Block（v2/v3）**，否则系统报的仍是你的新证书
4. 前提：目标设备已禁用签名校验（否则装不上）
> 注意：证书名可能是非标准的（例：`NINJAMUS.RSA`），别只找 `CERT.RSA`。

### [~] 方案 C：**完全不动包**（最稳的保底）
```bash
# 按 uid 精确劫持，只影响这一个游戏
iptables -t nat -A OUTPUT -m owner --uid-owner <游戏uid> -p tcp --dport <原端口> \
         -j DNAT --to-destination 127.0.0.1:<本地端口>
# 用完记得 -D 还原
```
优点：不触发任何自校验；缺点：要 root，不能与官服双开。

---

## 5. 其它常见保护速查

| 名字 | 文件特征 | 备注 |
|---|---|---|
| FairGuard | `libFairGuard.so` | 独立库；**若无人 DT_NEEDED**，删掉通常无碍 |
| TSS | `libtersafe2.so` | 与 libtprt 配合；**JNI 层在这里**，单独空壳会导致 UI 层 UnsatisfiedLinkError |
| TPRT | `libtprt.so` | 校验主力；libunity 直接依赖 |
| 字节 Zeus / packer | `.zeus_d` `.zeus_p` `zeus_gbsdk.plugin.*` | 首启会解包插件目录，**别删它生成的目录** |
| CrashSight / APM | `libCrashSight.so` `libapm*.so` | 崩溃/性能上报，一般无害 |
| OAID | `libmsaoaidsec.so` | 一般无害 |

---

## 6. 环境与注意事项

- ACE 会检测注入类模块（Frida / LSPosed / Zygisk），**测试期先关掉相关模块**，否则会把变量搅混。
- 有些校验是**延迟触发**的（联网回执 / 定时线程）→ 观察窗口至少 60~90 秒，别只看头 5 秒。
- 内存吃紧的机器上，Unity + 保护库可能被 LMK 杀 → 别把它误判成"自校验"：
  看 `ApplicationExitInfo` 的 `reason` 是 `SIGNALED(9)` 还是别的。
- 每改一个变量（换包名 / 换签名 / 换 so），**只改一个**，否则无法归因。
---
## 9. 「空壳 so」完整实战流程（ACE/libtprt 版，已实测）

> 比「哄保护库开心」简单得多：**把保护库换成空壳**。
> 前提：它被别的库 `DT_NEEDED` 依赖，**不能删**。

### 9.1 先判断能不能删
```bash
readelf -d libunity.so | grep NEEDED        # 看有没有 libtprt.so
readelf --dyn-syms --wide libunity.so | grep UND | grep tprt
```
- `NEEDED` 有 → **不能删**，只能换空壳（删了 `JNI FatalError: Unable to load library ... libunity.so` → SIGABRT）。
- 顺便注意：**UND 里可能只导入“数据符号”**（如 `g_tprt_pfn_array`），容易被误判成“不依赖”。

### 9.2 生成空壳（本项目 `tools/make_stub_so.py`）
必须处理 **3 类导出符号**：

| 类型 | 例子 | 怎么处理 |
|---|---|---|
| FUNC / NOTYPE | `ELF_HOOK_STUB_stub0` `xx0~xxf` `unwind_xx_ioctl` | 生成空函数 `return 0` |
| OBJECT（**函数指针表**） | `g_tprt_pfn_array`(432B=54项) `g_tprt_ori_array`(168B=21项) | **按原始字节大小复刻数组，整表填上有效函数指针** |
| JNI native | `Java_com_ace_gshell_AceApplication_initialize` 等 | 手写同名 C 函数返回中性值（**这些 native 就在保护库里**） |

> 注意: **最关键的坑**：指针表填 0 → 调用方 `blr x0` → `SIGSEGV, fault addr 0x0, pc=0x0`。
> tombstone 里会出现 `#00 pc 0x0 <unknown>` + `#01 pc xxx libunity.so`，看到这个就是“表没填”。

### 9.3 逐步验证（本项目的四次迭代，可当模板）
| 迭代 | 现象 | 原因 | 修法 |
|---|---|---|---|
| 1 | `SIGABRT` + `Unaable to load library libunity.so` | 删了 libtprt | 改“换空壳” |
| 2 | `UnsatisfiedLinkError: No implementation found for AceApplication.initialize` | native 在保护库里 | 空壳里补 JNI 函数 |
| 3 | `SIGSEGV, pc=0x0` | 函数指针表全 0 | 整表填有效指针 |
| 4 | 跑进初始化后 `exit(25)`（`reason=1 EXIT_SELF`） | 还有**第二个执法者**（如 libtersafe2 / 加固壳） | 继续对第二个库做同样处理 |

### 9.4 判断“还剩谁在拦”
```bash
# 退出原因（最有用）
logcat -d | grep ApplicationExitInfo | grep <pkg>
#   reason=1 EXIT_SELF          → 主动 exit（保护库自杀）
#   reason=5 APP CRASH(NATIVE)  → 看 /data/tombstones/ 最新一个
#   reason=4 APP CRASH(EXCEPTION) → 看 FATAL EXCEPTION 栈
#   reason=2 SIGNALED           → status 就是信号号（7=SIGBUS 11=SIGSEGV）
```
看 logcat 里**按顺序加载了哪些 so**，接着谁退出，就对谁下手。

### 9.5 经验值
- 保护库的**签名指纹 / 证书 hash 常以明文存在 .so 里**：
  `strings libtprt.so | grep -E '^[0-9A-Fa-f]{40}$|^[0-9A-Fa-f]{64}$'`
  → 命中就是它比对的证书指纹。
- 换空壳后 **签名/包名校验一起消失**，所以不必再折腾“保留原签名”。
- 空壳体积小、构建快（本机 aarch64 直接 `gcc -shared -fPIC -Wl,-soname,libtprt.so`）。
- 改完记得同步 `lib/armv7/` 等其他 ABI（本包只有 arm64）。

---

## 10. 参考资源 / 项目（维护时更新）

| 资源 | 是什么 | 用法 |
|------|--------|------|
| `Lixense/ff-ace-anticheat-analysis` | 腾讯 ACE 逆向分析（Free Fire；含 libanogs 导出/初始化/字符串解密/检测目标/击杀链） | 看懂 ACE 真实结构，判断"能不能剥离" |
| `Xuoos/AnimeGamesProxy` | **Xposed / LSPatch 模块：把游戏请求重定向到私服**（碧蓝档案禁用反作弊、明日方舟禁 `NetWorkConfig` 校验、原神 RSA Patch） | **免改包换服的现成范例**；无 root 配 `LSPatch` / `NPatch` |
| `gmh5225/awesome-game-security` | 游戏安全合集（含 Frida / Anti-Cheat 页） | 工具与资料索引 |
| `okankurtuluss/FridaBypassKit` | Frida 脚本：绕过常见 Android 安全检测 | 测试期让 Frida 不被检测 |
| `fairguard.github.io`（厂商博客） | 反 Frida 注入检测方案 | 了解检测方视角 |
| 看雪 `bbs.kanxue.com` / `UnknownCheats` | ACE / TSS / EAC 实战帖与绕过板块 | 卡住时搜同类案例 |
| `patricklarose/awesome-game-revivals` | 复活 / 私服 / 移植 / 重制项目合集 | 找同类项目的入口 |
| `eknight-eutopia.github.io`（崩坏3 私服实践） | mitmproxy + nginx 重定向实录 | 换服务端实战参考 |
| `333Networks MasterServer` | GameSpy 停运后的替代主服务器 | 老游戏联机复活的范例 |

> 找资源的关键词：**不要搜"反作弊剥离"**（太宽、多是游戏作弊向）。
> 按目标搜：**"免改客户端 / hosts 换服 / 重定向到私服 / Xposed 重定向 / 私服连接"** —— 这才是"换服务端"的正确入口。