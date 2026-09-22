# 改包名 / 重打包 / 资源与签名（实战清单）

> 目的：**改包名（便于双开）** 或 **让客户端默认连自建服**。
> 改包名会触发**一串**连锁问题，按下面的顺序一次修完，否则就是无限"秒退"。

---

## 1. 改包名要动的地方（缺一个就崩）

| # | 位置 | 怎么改 | 不改的后果 |
|---|---|---|---|
| 1 | `AndroidManifest.xml` 的 `package` 属性 | AXML 字符串池，**等长原地替换**（**只改 package，别批量替换类名！**） | Activity/组件找不到 → 闪退 |
| 2 | `resources.arsc` 的 `ResTable_package.name` | UTF-16LE 等长替换 + 修 local/CD **两处 CRC32** | `getIdentifier(..., getPackageName())` 返回 0 → SDK 初始化失败 |
| 3 | "包名派生密钥"加密过的资源 | 用新包名**重新加密**（见 §3） | 解密失败 `BadPaddingException: BAD_DECRYPT` |
| 4 | 权限名 / provider `authorities` | AXML 里含旧包名的字符串 | 安装冲突 / provider 崩溃 |
| 5 | 签名 | 改包后原签名失效 → 重签，或按 `anticheat.md` §4 保留原签名 | 装不上 / 被自校验杀 |

> 注意: **坑**：`AndroidManifest.xml` 在 zip 里通常是 **deflate 压缩**的，直接读 ZIP 数据看不到明文。
> 想**保持文件偏移不变**：解压 → 改 → 重压 → **补齐到原压缩长度**（后面追加空 stored block：`00 00 00 FF FF`）。
> 长度补不上时可换压缩级别重试；**如果压缩后比原来大**，就只能整包重建（偏移会变）。

---

## 2. 等长替换技巧（保持 zip 偏移、保留原签名有效范围）

```python
# resources.arsc 的包名在 ResTable_package 里，UTF-16LE
i = data.find(OLD.encode('utf-16-le'))
assert i > 0
data[i:i+len(OLD)*2] = NEW.encode('utf-16-le')   #  必须等长！
# 之后更新该 entry 的 CRC32（local header +14 / central directory +16 两处都要改）
```
- **为什么要等长**：名字变长会移动后面所有字节 → zip 偏移全乱、原签名彻底废掉。
- 目标包名长度对不上时，挑一个**同长度的替代包名**（例：31 字符 → 31 字符）。
- 改完用 `zipfile.ZipFile(p).testzip()` 应该返回 `None`。

---

## 3. 资源是「包名派生密钥」加密的（YH SDK 实例）

```python
S    = 包名 + "#@()!%&#' + <版本串>          # 版本串取自资源 yhdataset_YHCORESDKVERSION
key  = SHA256(S)      # 32B → AES-256
iv   = MD5(S)         # 16B
算法  = AES/CBC/PKCS7Padding
资源值 = "//$yhdataset$//" + Base64(密文)
```

**排查流程**
1. 遍历同类资源，看**哪些值以 `//$yhdataset$//` 开头** —— 只有少数是密文，其余是明文。
2. 用**原包名**解出明文 → 用**新包名**重新加密 → 写回该资源。
3. 密文长度通常不变（同明文 + PKCS7），所以能**等长原地替换**，偏移不变。

**找不到 KDF 怎么办**
- 反汇编提供该 native 方法的 so（本例 `libyhcomponent.so`），看
  `strings` 里的 **格式串**（`%s%s%s%s`）、**盐**（`#@()!%&#'`）、调用的 Java helper 名（`sha256`/`md5`/`getAesP`）。
- 拿 **`getPackageName()` + 版本串 + 盐** 做排列组合 × 常见哈希 ×（key/iv 取法）×（密文自带 IV / 固定 IV），
  用小脚本爆破；判定成功的条件：**解密结果能通过 PKCS7 且是合法 JSON/文本**。

---

## 4. 签名：想保留"原证书指纹"

1. 构建时**不要用自己的签名**（或签完再替换掉）。
2. 从原包取出 `META-INF/*.RSA`、`*.SF`、`MANIFEST.MF` 塞进新包。
   > 证书文件名**可能是非标准的**（例子见 `anticheat.md`），别只找 `CERT.RSA`。
3. **删掉 APK Signing Block（v2/v3）** —— 否则系统报告的仍是你的新证书。
4. 前提：目标设备**已禁用签名校验**（否则装不上）。装完立刻用
   `dumpsys package <新包名> | grep -i sig` 或 `MT 的 mt_apk_read_signature` 确认证书摘要是不是原包的。

---

## 5. 重打包的正确姿势（2GB 包秒级完成）

- [x] 不要 apktool 全解全 build：慢，而且会把所有条目重压一遍（偏移全变）。
- [x] **ZIP 原样复制**：
  1. 解析原 **Central Directory** 拿到每条 entry 的 `header_offset` / `compress_size`；
  2. 逐条把**压缩数据原样搬运**（不重压），只**替换目标条目**；
  3. 重写 CD + EOCD（注意 `flg & ~0x8` 清掉 data-descriptor 位，长度按自己写的填）。
- 参考实现（本 skill 自带）：
```bash
# 把保护库换成空壳
python3 tools/repack_zip.py game.apk game_stub.apk \
    --replace lib/arm64-v8a/libtprt.so=libtprt_stub.so

# 塞回原包签名、顺手删掉自己的签名
python3 tools/repack_zip.py mod.apk mod_origsig.apk \
    --delete META-INF/ANDROID.RSA --delete META-INF/ANDROID.SF --delete META-INF/MANIFEST.MF \
    --add-from orig.apk META-INF/NINJAMUS.RSA \
    --add-from orig.apk META-INF/NINJAMUS.SF \
    --add-from orig.apk META-INF/MANIFEST.MF
# 结束后它会打印 testzip（None 才对）和"是否含 Signing Block"
```

---

## 6. 验证清单

- [ ] `zipfile.testzip()` 返回 `None`（CRC 全对）
- [ ] `pm install -r -d <apk>` 成功
- [ ] 启动后立刻看 `ApplicationExitInfo`（见 `anticheat.md` §2）判断是"能跑/被保护杀/Java 异常"
- [ ] 装机前先 `pm uninstall` 旧包：避免旧数据/旧 uid 造成误判
- [ ] **每轮只改一个变量**，并记录：改了什么 → 新症状 → 结论

---

## 7. 让客户端连自建服的落点（按代价从低到高）

| 落点 | 做法 | 适用 |
|---|---|---|
| **网络层重定向**（代价最低） | `iptables -t nat -A OUTPUT -m owner --uid-owner <uid> -p tcp --dport <p> -j DNAT --to-destination 127.0.0.1:<lp>`；或 hosts 重定向域名 | 只要 root；不触发自校验 |
| **LSPatch / NPatch 模块 + Signature Bypass** | 注入"重定向模块"改请求目标；同时用 **Signature Bypass** 骗过签名校验（见 §8） | 无 root / 想模块化 |
| **改包内地址** | 若地址在**明文配置文件/Lua**里（例：Unity 的 `ab_lua`、`gameversion.lua`），直接改字节；注意**包名变了要连带** | 想做成独立安装包 |

> 注意: **别把资源服/CDN 端口也劫持**（例：`:9999`、`443`）—— 首启要下载 Lua/资源，劫持了会**一直黑屏**。

---

## 8. 签名校验与绕过（重签名 / 无 root 场景）

> 重签名后，若游戏校验签名 → **秒退**。两条路：**让校验"看到原签名"**，或 **根本不改签名**。

### 8.1 LSPatch 自带 Signature Bypass（首选）

LSPatch 修补 APK 时会**保存原签名信息**，运行时按等级 hook，让系统/应用读到的**仍是原签名**：

| 等级 | 值 | 做什么 |
|------|----|--------|
| Off | 0 | 不绕过 |
| Bypass PM | 1 | hook `PackageParser.generatePackageInfo` + 替换 `PackageInfo.CREATOR`，改写返回的签名 |
| **Bypass PM + openat** | **2** | 再加 **native `openat` hook**：把对 patched APK 的读取重定向到 cache 里的**原 APK**，文件级签名读取也拿到原块 |

> **用 LSPatch 时优先把 Signature Bypass 调到等级 2**（多数签名校验直接过）。
> 这正是"LSPatch 免 root 注入还能绕过签名"的原因；对应的类在 LSPatch 源码 `SigBypass.java`。

### 8.2 不依赖 LSPatch：独立"签名破解"

- `L-JINBIN/ApkSignatureKiller` —— 往 `Application` 入口插代码，**hook `PackageManager.getPackageInfo`**，把签名改回原包。
- Xposed 模块 **核心破解（CorePatch）** —— 去系统签名校验、直装改包、降级安装。
- 自己写：hook `PackageInfo.signatures` / `Signature.toByteArray()` / `getPackageInfo(..., GET_SIGNATURES)`。

### 8.3 真正"不改签名"：虚拟容器（VirtualApp 系）

- **VirtualXposed / 太极(TaiChi) / 应用转生**：把 App 装进**虚拟空间**运行，**APK 本身不被改动** → 签名不变，模块在容器内注入。
- 代价：**兼容性有限**（新版 Android / 重 native / 强反作弊的游戏常跑不起来）。
- 对 Unity/il2cpp + ACE 这类，**通常不如"LSPatch + Signature Bypass"稳**。

> **选型**：先试 **LSPatch（Sig Bypass 等级 2）** → 不行再独立签名破解 → 虚拟容器兜底。
> 判断"是不是还在下载"：看 `files/` 下有没有生成热更目录（如 `lua_src`），以及是否还有到 CDN 的连接。