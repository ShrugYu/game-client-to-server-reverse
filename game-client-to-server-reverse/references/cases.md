# 真实案例研究（Case Studies）

> 两个**公开的、成功的**第三方服务端实现。用于理解「通用 skill 落到真实项目」的形态。
> 本文件只做**事实性归纳**与**方法论提炼**，不复制其代码。请遵守各自许可证：
> `项目B` = PolyForm Noncommercial 1.0.0；`项目C` = GPL-3.0。

---

## 案例 A：项目B（某 Unity 手游 CN）

- 仓库：https://github.com/kuuhaku1314/项目B
- 客户端：Unity（Android APK，网易，`com.netease.ma.netease`）
- 服务端语言：**Go**（含 Windows C# WinForms 启动器）
- 资源：`resource-set/` 本地目录，或 Cloudflare R2 / S3 兼容 CDN

### 关键工程事实

| 维度 | 做法 |
|------|------|
| 服务端语言 | **Go**（不是 Python） |
| 启动器 | **C# WinForms** GUI，选"模拟器/局域网"，填地址后一键启停 |
| 端口约定 | 主 `TCP 26020`；战斗 `26021`(=主+1)；后台 `26022`(=主+2，仅本机) |
| 客户端对接 | **改配置文件**：`Android/data/com.netease.ma.netease/files/local_server.txt` 写 `IP:PORT` |
| 存档 | `_local/data/cn602-save-state.sqlite3` |
| 后台 | HTTP `127.0.0.1:26022`，运营台可配卡池/活动/掉落/商店/发礼/账号绑定 |
| 资源分发 | 本地 `resource-set/` 或自建 CDN（`cdn-sync.json` → `cdn.json`） |
| 发布形态 | 预编译三端（Win x64 / Linux x64 / ARM64），**用户无需装 Go/Python/Unity** |

### 对 skill 的启发

1. **服务端语言由协议与发布需求决定**，Go 完全合理（→ `codegen.md` A 节）。
2. **"配置文件法"是最省事的客户端对接**：不改客户端二进制，只写一个 txt。
3. **端口三件套约定**（主/战斗/后台）值得写成规范。
4. **发布要预编译**：给最终用户的是一键包，不是源码。
5. **付费/水晶**：README 明确写「购买默认返回成功但不增加水晶，管理员可在运营设置开启」
   —— 与 §15 的 `pay_auto_success` 模式完全一致。
6. **CDN 分离**：登录/战斗连自建服务端，资源可走独立 CDN。

---

## 案例 B：项目C（某 Cocos 手游 CN）

- 仓库：https://github.com/DontBeAlarmed/项目C
- 客户端：**ActionScript3 / Flash**（`pinball/config/.../DevConfig.as`）
- 服务端语言：**TypeScript / Node.js**（>= 20.12）
- 存储：SQLite（`.database/`）
- 资源：官方 CDN 放 `.cdn/cn/`，含 Content Sync 与增量补丁 Overlay

### 关键工程事实

| 维度 | 做法 |
|------|------|
| 服务端语言 | **Node/TypeScript** |
| 客户端语言 | **AS3/Flash**（非常见 Unity/UE！） |
| 客户端补丁 | 改 `.as` 源码 **重新编译**：`client-patch/apply.sh <AS3_EXPORT_DIR> <HOST>:8001` |
| 跳过登录 | 在 `DevConfig.as` 启用 **SDK Dummy** |
| 改地址 | `DevConfig_gf_android.as` 改 API 地址 |
| 端口 | HTTP `8001`；游戏 TCP `8003`；多人 Hub `8004` |
| 抓包 | 仓库带 `.mitmproxy/` 配置，说明**基于抓包驱动开发** |
| 后台 | React SPA，挂 `/admin/` |
| 多语言支持 | CN / 全球服（`starpoint`）双实现 |

### 对 skill 的启发

1. **客户端语言判定是第一步**：AS3 用 FFDec，而不是 dnSpy（→ `client-languages.md`）。
2. **"源码重编译法"**：能拿到 AS3 源码时，改源码重编比二进制 patch 干净。
3. **抓包驱动**：`.mitmproxy/` 说明整个开发是 **capture-first**（与 §3 一致）。
4. **路由即消息号**：HTTP 游戏里 `/api/login`、`/api/pull` 就是消息号，不需要 opcode 表。
5. **内容/资源同步**是独立子系统（Content Sync + patch overlay），值得单列。

---

## 横向对比：同一个 skill，两种落地

| 维度 | 案例 A | 案例 B |
|------|--------|--------|
| 客户端语言 | C# / Unity | AS3 / Flash |
| 传输 | TCP 长连接（+战斗端口） | HTTP + TCP |
| 服务端语言 | Go | Node/TS |
| 客户端对接 | 配置文件法 | 源码重编译法 |
| 存档 | SQLite | SQLite |
| 后台 | 内置 HTTP 运营台 | React `/admin/` |
| 资源 | 本地/CDN | CDN + 增量补丁 |

**共同点（= 通用规律）**：
- 服务端都有：账号/存档（SQLite）、后台、资源分发、端口约定
- 客户端对接非侵入（配置或最小 patch）
- 都以**抓包 + 反编译**为证据来源

**差异点（= 必须由 Spec 决定的）**：
- 语言、传输、帧格式、序列化、客户端补丁方式

---

## 补充参考项目（相关）

| 项目 | 说明 |
|------|------|
| `Duosion/starpoint` | 全球服服务端基础 |
| `wdfp-extractor` | 资源提取 |
| `wfax` | 资源转换与修改 |
| `starview` | APK 补丁工具 |

> 这些都印证了通用 skill 需要的**工具链广度**：提取、转换、补丁、服务端、后台缺一不可。

---

## 怎么用这些案例（给 AI 的指令）

1. **不要照搬**案例的技术选型 —— 它们只是证明"选型可以很不同"。
2. 用它们对照检查自己的 Spec 是否遗漏了这些**通用子系统**：
   账号、存档、后台、资源分发、端口约定、客户端补丁、发布打包。
3. 遇到同类游戏时，可以引用它们的**方法论**（capture-first、最小 patch、预编译发布）。
4. 使用任何参考代码前**先看许可证**。