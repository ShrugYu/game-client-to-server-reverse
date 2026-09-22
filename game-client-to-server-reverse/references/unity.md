# Unity 分支深潜（IL2CPP / Mono / Lua）

## A. IL2CPP

### A1. 结构
- `libil2cpp.so`（代码） + `global-metadata.dat`（元数据）必须配对。
- `global-metadata.dat` 标准 magic：`AF 1B B1 FA`（小端）。头 4 字节不符 = 加密/魔改。

### A2. Dump
```bash
Il2CppDumper.exe libil2cpp.so global-metadata.dat out/
# 产出: dump.cs / script.json / il2cpp.h / DummyDll/
```
- 自动检测 Unity 版本失败时用 `--select-mode` 手动指定。
- `dump.cs` 只有签名、函数体为空 → 用 IDA/Ghidra + `script.json` 看实现。

### A3. metadata 加密的定位
1. 搜字符串 `global-metadata.dat`。
2. 回溯调用链：`il2cpp_init → Runtime::Init → MetadataCache::Initialize → MetadataLoader::LoadMetadataFile`。
3. 在 `LoadMetadataFile` 前找解密/解压（常见：AES / XXTEA / 分块 XOR + 自定义头）。
4. 自测可 Frida hook 解密函数出口，dump 明文。

### A4. 定位网络层
```bash
grep -nE 'Send|Recv|Socket|Network|Message|Protocol|Packet|Cmd|MsgId|Opcode' out/dump.cs
grep -nE 'ProtoBuf|MessagePack|JsonUtility|Newtonsoft' out/dump.cs
```
- 找 `Dictionary<opcode, handler>` 或 `switch(msgId)` → 消息号全集。
- 找序列化属性标注 → 字段顺序。

### A5. 动态辅助
- Frida：`il2cpp` 模式直接按类名/方法名 hook。
- 常用：hook `Socket.Send/Recv` 或业务层 `NetManager.Send` 直接拿明文。

---

## B. Mono

1. 直接 dnSpy / ILSpy 打开 `Assembly-CSharp.dll`。
2. 加密时定位 Mono `image` 解密（`mono_image_open_from_data` 附近）。
3. 网络库常见：`System.Net.Sockets`、`WebSocketSharp`、`BestHTTP`。

---

## C. Lua 热更（xLua / tolua / slua）

### C1. 判定
```bash
grep -rl 'xlua\|tolua\|slua' <assets>/
```
- 明文 luac 头：`1B 4C 75 61`。
- 否则找解密函数（常是异或/RC4 + 文件头）。

### C2. 反编译
```bash
unluac file.luac > file.lua
luadec -dis file.luac
```
- 魔改字节码 → 先 dump 自定义 opcode 表再喂工具。

### C3. 价值
- Lua 常直接写业务协议：`sendMsg(cmd, {field=...})` → 字段名与语义白给。
- 与 `dump.cs` 交叉验证 opcode 与字段。

---

## D. Unity 网络协议常见形态

| 形态 | 特征 | 处理 |
|------|------|------|
| TCP + 长度前缀 + protobuf | 前 2/4 字节长度 | protoc --decode_raw |
| WebSocket + JSON | 明文可读 | 直接读 |
| UDP + KCP | conv 头 | kcp_sniff.py |
| 自定义 | 头+加密体 | 分块分析 |
