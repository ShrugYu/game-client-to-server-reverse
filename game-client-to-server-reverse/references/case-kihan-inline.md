# 真实案例：Unity IL2CPP + 平台 SDK 的「内联服务端」

> 目标：腾讯系 Unity IL2CPP 手游（`com.tencent.KiHan`，arm64）。
> 做法：**不改协议、不起外部服务端**，在客户端进程内拦截网络门面合成响应，
> 让客户端在本地模式下走完登录 → 进场景 → 局内。
>
> 规则同 `case-ninja3-ecdh.md`：**没在真实客户端上确认过的，一律不写 [x]**。

---

## 1. 事实清单（可验证的输入）

| 项 | 值 |
|----|----|
| 包名 / 引擎 | `com.tencent.KiHan` / Unity **IL2CPP** |
| 分析产物 | `dump.cs`、`libil2cpp.so`（含 IDA 数据库） |
| 注入方式 | 原生注入 + **Dobby** 内联 hook（非 Frida） |
| 业务命名空间 | `KH`、`KH.Network`、`KH.Remote`、`KHSceneConnectHelper` 等 |
| 协议形态 | 强类型协议类（对象级读写）+ **Lua 通道**（字节 / 表） |
| 账号体系 | 平台 SDK（MSDK 系）→ 目录服 → 区服 |

---

## 2. 内联截获的落点

拦截 `NetworkManager` 的四个方法（**两个命名空间各装一遍**）：

```
KH.NetworkManager.SendMessage / SendUnicast / AddMessageCallback / RemoveMessageCallback
KH.Network.NetworkManager.*        ← 实测活的是这一份，两份都装
```

| 机制 | 实现 |
|------|------|
| 请求 → 合成响应 | 一张 `cmd → 构造函数` 总表，每条一个函数 |
| 响应投递 | `std::deque<PendingUnicast>`（存 gchandle）+ 主线程 tick 泵 |
| 重入 | `thread_local int g_networkSendDepth`；`> 0` 时放行原函数 |
| 广播 | `cmd → 回调 gchandle 列表` 的表，注册 / 注销都要管 |
| 延迟派发 | 帧计数器（`2` 帧；未就绪改 `30` 帧重试） |

---

## 3. 登录 / 进入链路（观测到的顺序）

```
平台 SDK 登录态 → 目录服进入 → 区服登录 → 取登录后信息 → 建角 / 选角 → 进场景
```

| 阶段 | 观察到的东西 |
|------|-------------|
| 目录服进入 | `DirCSEnterZoneReq`（cmd `134217731`） |
| 区服登录后取信息 | 相关 cmd `51384528` |
| 客户端本地路径 | `KHZoneConnection.ZoneLogin`、`DoReqLoginServer`、`GetInfoAfterLoginReq` |

实测做法：**复用客户端的原生登录路径**（构造登录响应后调用客户端自己的
`OnLoginDataSucc`），而不是绕开它自己怼一个界面 —— 后者会漏掉后续状态机。

---

## 4. 账号桥接（取官方数据）

见 `platform-sdk-and-admission.md` §2。实测形态：

- 动态建 `OfficialNinjaBridge` GameObject，挂客户端自己的 `ConnectorComponent`
- 逐字段复制官方实例的 `DH` / `Uin` / `Password` / `Url` / `VersionServerUrl` /
  `EncryptMethod` / `KeyMaking`，**只改 `ZoneUrl`**
- 调用官方 `Connect`（非默认 connId），用 `ApolloConnection.IsConnected` 判就绪
- 有超时（实测约 900 帧）与三态日志（进行中 / 已连接 / 超时）

---

## 5. 已证伪 / 已踩的坑

| 结论 | 证据 |
|------|------|
| 「客户端资源检查放行 = 能进服」**错误** | 资源检查改为恒真后，仍卡在目录服准入 |
| 「提示维护中」**不是**客户端资源逻辑产生 | 该阶段只有目录服请求，无 ZoneLogin |
| 门面有**两个命名空间副本**，只装一处会漏请求 | 安装清单里两份都在 |
| 回调**不能**在拦截函数里同步调用 | 改为入队 + 主线程泵后才稳定 |
| 进场广播**不能**随响应立即发 | 需延迟数帧，且先确认监听方已注册 |

---

## 6. 当前状态（按三轴记）

口径见 `verification-and-status.md`。

| 项 | 实现 | 自动测试 | 客户端验收 |
|----|------|---------|-----------|
| 进程内拦截 + 合成响应框架 | [x] | [ ] | [~] 局内路径已到位 |
| 本地登录 / 进入链路 | [x] | [ ] | [~] |
| 账号桥接连接 | [x] | [ ] | [?] 连接探测通过，业务取数未验 |
| 官方区服准入 | [-] | [-] | [x] 已证伪（见 §5） |
| wire 级协议规格 | [ ] | [ ] | [-] 本路线不急 |

> 这份状态表的用途：**别把 [~] 当 [x] 往外交付**。

---

## 7. 这个案例教会 skill 什么

1. 反推服务端有**第二条路**：不起服务端，在进程内合成响应（`inline-server.md`）
2. 对象级比 wire 级**先跑通**更划算（`runtime-object-synthesis.md`）
3. 大厂账号体系要按**三段**分别定位卡点（`platform-sdk-and-admission.md`）
4. 验收必须落在**网络 / 状态层完成点**，界面截图不算
