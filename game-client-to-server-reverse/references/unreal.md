# Unreal 分支深潜（UE4 / UE5）

## A. 资源层（.pak / .utoc / .uasset）

### A1. 找 AES key
```bash
AES_finder.exe                 # 运行时内存扫描密钥
# 或：从 exe 里搜 32/64 字节疑似 key，用 FModel 试
```
- UE4 用 AES-256；UE5 IoStore 用 `.utoc + .ucas`。

### A2. 解包
- **FModel**：主力。加载 `.usmap` 后浏览导出。
- **UnrealPak.exe -Extract**：官方工具，需要 key。
- **umodel**：老版本兜底。

### A3. UE5 unversioned 包
- 现象：FModel 报无法解析属性。
- 解法：先用 **Dumper-7 / UE4SS / usmap dumper** 生成 `.usmap`（含类/结构体 schema），FModel 加载即可。

---

## B. 代码 / 网络层

### B1. SDK Dump
- **UE4SS**：注入，Lua/C++ 脚本枚举 `UObject`、hook `UFunction::ProcessEvent`。
- **Dumper-7**：运行时生成 SDK（类、结构体、成员偏移、函数签名）。
- 产出 `.h/.cpp`，等于拿到开发环境视图。

### B2. 网络定位（grep SDK / dump）
```
NetDriver / NetConnection / PacketHandler / SendPacket / ProcessPacket
Replication / Replicate / RPC
Server_* / Client_* / Multicast_*
FArchive / Serialize / NetSerialize
```

### B3. 字段语义金矿
- `UPROPERTY(Replicated)` 的属性在 SDK 里带标记 → 顺序即序列化顺序。
- RPC 函数参数 → 直接给出对应请求字段。
- `FPacketHandler` 子类 → packet id 与结构。

### B4. UE 序列化细节
- `FArchive` 小端。
- `FString`：int32 长度（含 null 终止），负数=UTF-16。
- `TArray`：int32 count + 元素。
- 压缩块：`FCompressedChunkHeader`。

---

## C. UE 自研协议常见形态

| 形态 | 特征 | 处理 |
|------|------|------|
| UE 原生 Replication | 二进制，NetGUID | 看 SDK + 抓包对照 |
| 自研 UDP | 自定义包头 + CRC | 找 SendPacket 实现 |
| HTTP/WS 网关 | 明文 | 直接抓 |
| KCP 之上再加密 | conv 头 + 密文 | 先剥 KCP 再解 |

---

## D. 与 Unity 的差异要点

- UE 强依赖运行时反射 → SDK dump 是首选，静态逆向次之。
- UE 网络字段顺序由 C++ 内存布局 + 序列化函数共同决定，不能只看声明顺序。
- UE5 的 IoStore(`.utoc/.ucas`) 与 unversioned 是新坑。
