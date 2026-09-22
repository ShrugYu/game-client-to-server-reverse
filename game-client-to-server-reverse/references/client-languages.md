# 客户端语言分支：不同语言怎么读协议、怎么改客户端

> 客户端**不一定**是 Unity/C#，也**不一定**是 UE。先把语言判对，再选工具。
> 判定方法：看 `assets` / `lib` / 文件扩展名 / 字符串。

---

## 0. 语言判定速查

| 线索 | 客户端语言 | 主工具 |
|------|-----------|--------|
| `Assembly-CSharp.dll` / `*.dll` + `Managed/` | C# (Unity Mono / .NET) | dnSpy / ILSpy |
| `global-metadata.dat` + `libil2cpp.so` | C#→IL2CPP（无源码，只有签名） | Il2CppDumper + IDA |
| `*.swf` / `*.as` / `*.abc` / `Starling` | ActionScript3 / Flash | JPEXS FFDec |
| `*.luac` / `xlua` / `tolua` | Lua 热更 | unluac / luadec |
| `classes.dex` 业务重 | Java/Kotlin | jadx |
| `lib*.so` 主逻辑 + 大量 C++ 符号 | 原生 C++（含 UE） | IDA/Ghidra + SDK dump |
| `*.js` / `webpack` / `.h5` | JS/H5 | beautify + sourcemap |
| `*.wasm` | WebAssembly | wasm2wat / wasm-decompile |

---

## 1. C# 客户端（重点：可反编译出源码）

> 用户提到「游戏可能是 C# 的，能解出客户端 C# 源码」——这是**最舒服**的情况：
> 反编译接近原始源码，协议字段名、消息号、序列化逻辑几乎白给。

### 1.1 两种 C# 形态

| 形态 | 特征 | 能拿到什么 |
|------|------|-----------|
| **Mono / .NET** | `Assembly-CSharp.dll`（未加密） | **近乎完整源码**（dnSpy 反编译） |
| **IL2CPP** | `libil2cpp.so` + `global-metadata.dat` | 只有签名（dump.cs），函数体要看汇编 |

### 1.2 Mono/.NET 反编译流程

```bash
# 工具：dnSpy / ILSpy / dotPeek / JetBrains dotPeek
# 直接拖入 Assembly-CSharp.dll 即可
```
- 若被混淆（ConfuserEx 等）→ 先 `de4dot` 去混淆，再 dnSpy。
- 找网络层关键词：
```
Socket / TcpClient / UdpClient / NetworkStream
WebRequest / HttpClient / WebSocketSharp / BestHTTP
ProtoBuf / MessagePack / Newtonsoft.Json / LitJson
SendMessage / Send / Recv / Packet / Protocol / PacketHandler
opcode / msgId / protocolId / Cmd
```
- **重点**：C# 客户端里通常有
  - `PacketHandler` 字典 / `switch(msgId)` → **消息号全集**
  - `[ProtoContract]` / `[Message]` 标注 → 字段顺序
  - 序列化/加密工具类 → 算法与密钥来源

### 1.3 IL2CPP 反编译

```bash
Il2CppDumper.exe libil2cpp.so global-metadata.dat out/   # -> dump.cs
```
- `dump.cs` 只有「类/方法/字段签名」，**没有函数体**。
- 要看实现：IDA/Ghidra 加载 `.so` + `script.json` 恢复符号。
- 想还原成近似源码：`Il2CppInspector` 可生成伪 C# 桩；复杂逻辑仍需汇编。

### 1.4 从 C# 源码里「抄」什么

| 目标 | 在源码里找 |
|------|-----------|
| 传输 | `Socket`/`TcpClient` 初始化、`Connect(host,port)` |
| 帧封装 | `Write(byte[])`／自定义 `Packet` 类／长度写入处 |
| 加密 | `Encrypt`/`Decrypt` 工具类、密钥常量 |
| 压缩 | `GZipStream`/`DeflateStream`/`LZ4` |
| 序列化 | `ProtoBuf.Serializer`/`JsonConvert`/手写 `Write*` |
| 消息号 | `enum MsgId`／`Dictionary<ushort, Action<...>>` |
| 字段布局 | 消息类字段声明顺序（配合序列化方式判断 wire 顺序） |

### 1.5 改 C# 客户端的三种方式

1. **配置法**（最轻）：把服务器地址写进客户端读的配置文件/ini/txt。
2. **重编译法**：反编译 → 改 → 用**同版本 .NET/Unity** 重新编译回 dll（需注意签名与版本）。
3. **运行时 Hook**：Frida（Unity）/ dnSpy 调试断点改内存 / Harmony 打补丁。

> 若客户端是 Unity，优先 `Frida` + `il2cpp` 模式；若 Mono，dnSpy 直接改 dll 更简单。

---

## 2. ActionScript3 / Flash 客户端

> 案例：`项目C`（某 Cocos 手游 CN）就是 AS3 客户端。

### 2.1 反编译
```bash
# JPEXS Free Flash Decompiler (FFDec)
# 打开 .swf / .abc，导出 ActionScript (.as) 源与资源
```
- 导出后可读 `.as` 源码 → 找 `URLRequest` / `URLLoader` / `Socket` / `NetConnection`。
- 配置类常见命名：`DevConfig`、`Config`、`ServerConfig`。

### 2.2 典型改动（参考 项目C 的做法）
```as
// pinball/config/core/DevConfig.as —— 启用 SDK Dummy，跳过官方登录
// pinball/config/gbits/DevConfig_gf_android.as —— 改 API 地址
public static const API_URL:String = "http://<你的服务端>:8001";
```
- 改完用 **Apache Flex / Animate** 重新编译 `.swf`。
- 仓库常提供补丁脚本：`client-patch/apply.sh <AS3_EXPORT_DIR> <SERVER_HOST>:8001`。

### 2.3 读协议
- 看 `.as` 里构造 `URLVariables` / `JSON` / `AMF` 的地方 → 请求字段。
- HTTP 路由即「消息号」（如 `/api/login`）。

---

## 3. Lua 热更客户端

- 判明文：`1B 4C 75 61`（luac 头）→ 直接 `unluac`。
- 加密/魔改 opcode → 先还原 opcode 表。
- 找 `sendMsg` / `Net.` / `Cmd` → 业务协议与字段名。

---

## 4. JS / H5 客户端

- 打包产物 → `webpack` 解包 / `beautify`。
- 有 sourcemap 更好（`*.js.map`）。
- 找 `fetch` / `XMLHttpRequest` / `WebSocket` / `socket.io`。
- 改动：直接改 js 或改运行时配置。

---

## 5. Java / Kotlin（原生 Android）

- `jadx -d out/ app.apk` → 读 Java 源码。
- 找 `OkHttp` / `Socket` / `WebSocket`。
- 改动：smali patch（apktool + baksmali），或 Frida hook。

---

## 6. 原生 C++ / UE

- SDK dump（Dumper-7 / UE4SS）→ 结构体与 RPC。
- 见 `unreal.md`。

---

## 7. 客户端补丁的四种通用手法（跨语言）

| 手法 | 适用 | 例子 |
|------|------|------|
| **配置文件法** | 客户端把地址放外部文件 | `local_server.txt` 填 `IP:PORT` |
| **源码重编译法** | 能拿到源码/伪源码 | 改 `.as` 重编；改 `.dll` 重编 |
| **二进制 Patch** | 只改常量/跳转 | smali patch、il2cpp patch、hex patch |
| **运行时 Hook** | 不落地改动 | Frida / dnSpy / Harmony |

> 优先顺序：**配置法 > 运行时 Hook > 二进制 Patch > 重编译**（越往后越重、越易踩版本坑）。

---

## 8. 常见坑

- **C# 混淆**：`de4dot` 未必能全还原，字段名可能变 `a`,`b`。
- **强名称签名**：改完 dll 需去掉强名称校验或重签。
- **Unity 版本**：重编译 dll 必须与目标 Unity 的 API 兼容。
- **AS3 版本**：不同 SDK 编译产物不互通，需匹配原工程。
- **混淆 vs 加密**：混淆是改名，加密是改字节，处理方式不同。
- **许可证**：参考项目可能带 Noncommercial / GPL 等限制，遵守其条款。