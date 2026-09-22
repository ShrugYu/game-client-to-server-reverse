# 最小必读路径：别把整个 skill 一次读完

> **任何模型（GLM / DeepSeek / Claude）都按本文件分派**：
> 打开本文件 → 选你的任务类型（§1）→ **按顺序打开并读完**指定的那 3~5 个文件 → 再动手。
> **多数模型不会自动加载文件，必须显式打开。**

> **这份文档解决的事**：这个 skill 有 37 篇参考 + 一份长主文档。
> 上下文有限的 AI **一次读完再动手**，结果通常是「读了前几节就开始写代码」。
> 正确做法：**按任务类型只读 3~5 个文件，其余按需查。**
>
> 用法：先在这里定位任务类型 → 按路径读 → 动手 → 宣称完成前过一遍「收工前必读」。

---

## 0. 三层清单

### 零层（第一次接触某客户端 / 不懂协议原理时，先读这 1 个）

| 文件 | 为什么必读 |
|---|---|
| `references/primer.md` | **原理层**：三要素（配置/协议/代码）、数据包协议本质、协议号与协议表、热更源码。**不懂"在反推什么"时，读它会省掉几周弯路。** |
| `references/server-architecture-basics.md` | **反推对象地图（逆向视角）**：你在还原哪几类服、网关的隐藏层、从包里认 Protobuf/KCP、同步模型决定"要还原多少逻辑"。**想知道"你在反推的东西由什么组成、去哪找证据"时读。** |

> 已懂原理 → 直接跳到「核心层」。第一次做、或对话里出现"看不懂数据包" → 先读它。

### 核心层（几乎所有任务都读，3 个）

| 文件 | 为什么必读 |
|---|---|
| `SKILL.md` §0（只读 §0.0~§0.6） | 方法选择、铁律、工作流主干、**阅读地图** |
| `references/workflow-roadmap.md` | **四阶段路线总纲**：先做什么、后做什么、每步在哪验收（+ 四层重定向表） |
| `schema/project-profile.yaml` | 填了它才知道"读了什么、还缺什么" |
| `references/ai-contract.md` | **AI 行为契约**：强制产物清单 + 硬性禁止 + 决策可追溯 + 终点/回滚（原 SKILL §13 的完整版） |

> 注意: **`SKILL.md` 其余章节按需读**，不要线性通读。

### 场景层（按任务类型挑，见 §1）

### 查阅层（遇到具体问题时再翻）

```
references/account.md            账号/注册/密码预处理/接口替换
references/combat.md             房间与战斗同步模型
references/drops.md              掉落表与入库
references/gacha.md              抽卡/保底/重复转换
references/codegen.md            由 Spec 生成服务端（多语言）
references/cases.md              真实项目取舍
references/unity.md / unreal.md  引擎深潜
references/unity.md / unreal.md / cocos2d.md  引擎深潜(cocos 含 §H2 Live 运营)
references/live-ops.md           进服后的运营手册(子系统次序/契约反推/双表差异)
references/inline-server.md      内联服务端(进程内合成响应)第二条路线
references/runtime-object-synthesis.md 运行时对象合成与字段发现
references/platform-sdk-and-admission.md 平台 SDK 登录态复用+两段准入
references/case-il2cpp-inline.md  真实案例:内联服务端
references/windows.md / termux.md 端游 / 手游运行环境
references/decision-tree.md      逐层决策树（拿不定主意时）
references/phases-detail.md      §1~§10 反推主流程详细版（命令/工具/判断/坑）
references/ai-contract.md        AI 行为契约（强制产物/禁止/终点/回滚）
references/primer.md             原理层（第一次接触某客户端时）
references/workflow-roadmap.md   四阶段路线总纲（先做什么后做什么）
extensions/                      可选拓展（不参与核心验收）
```

---

## 1. 按任务类型选路径

### ① 只有安装包，从零开始

```
SKILL §0 → from-installer.md → client-languages.md
→ adaptation.md（建档）→ methods.md（选方法）
```
产出：`project-profile.yaml`、引擎/语言判定、证据获取计划。

### ② 已有 dump/lua/抓包，要定协议

```
SKILL §0 → protocol-spec.md → decision-tree.md
→ （有 Lua/源码时）tools/extract_interfaces.py 扒接口清单
→ §4 分层 → §5 静态分析 → §6 字段语义
```
产出：`protocol.spec.yaml`、证据清单、未解决清单。

### ③ 要写服务端（最关键的分叉）

```
wire-level-patching.md   ←  先读这个再决定路线
→ protocol-spec.md（把确认的字段落进 Spec）
→ engineering-practices.md（fixture 回放 + 具名完成点）
→ combat.md / drops.md / gacha.md（对应子系统）
```
**它决定你的路线是「先跑起来」还是「先凑 schema」** —— 读错这一篇，后面全白干。

### ④ 要把客户端对接过来（改包/重定向）

```
client-address-sources.md   ←  先读这个（地址有六类来源）
→ anticheat.md（秒退/黑屏）
→ repack-rename.md（真要改包名/重签时）
```
**顺序很重要**：先做「不改包」的落点，再考虑改包。

### ⑤ 卡住了 / 客户端不进游戏

```
closure-verification.md   ← 6 类假阳性（端口在听、自环通过、日志打勾…）
→ 回到 protocol-spec.yaml 的 unresolved 逐条排查
→ 需要解密/字段时用 methods.md 的 M3
```

### ⑥ 要交付 / 部署 / 给别人用

```
release-and-ops.md       ← 监听 vs 对外地址、端口族、配置冻结、备份
→ engineering-practices.md（ADR、E2E 证据包）
→ templates/AGENTS.md、templates/status-matrix.md
```

### ⑦ 接手别人（或上一个 AI）的项目

```
closure-verification.md   ←  第一条
→ 对方文档里的结论逐条复核（尤其"唯一卡点是 X"这种）
→ engineering-practices.md（看数据隔离/完成点）
```

---

### ⑧ 想「不起服务端」：单机化 / 离线版

```
inline-server.md              ←  先读这个（先判断该不该走这条路）
→ runtime-object-synthesis.md（响应对象怎么造）
→ platform-sdk-and-admission.md（账号与准入怎么借官方）
→ case-il2cpp-inline.md（完整案例）
```
产出：拦截清单 + 合成响应总表 + 内联版验收完成点。

---

### ⑨ 搞懂原理 / 第一次接触某个客户端

```
primer.md                     ←  先读这个（在反推什么：三要素 / 协议表 / 热更源码）
→ workflow-roadmap.md（四阶段：先做什么、在哪验收）
→ methods.md（选手段）
```

### ⑩ 动手前：先查"别人有没有做过"（抄作业）

```
methods.md 的 M8（已知实现移植法）←  现成实现速查表：同引擎/同厂商/同世代的模拟器、同类 skill
```
有现成 → 抄；只有部分 → 拼装；完全没有 → 纯逆向。**动手前先锁客户端版本。**

---

## 2. 无论什么任务：开读前 / 收工前

### 开读前（30 秒）

```
[ ] 目标是什么？（只分析 / 跑通某里程碑 / 完整服务端 / 改客户端）
[ ] 手上有什么证据？（安装包 / dump / 抓包 / 能运行 / 能注入）
[ ] 有什么约束？（反作弊 / 时间 / 权限 / 平台）
```
→ 记进 `project-profile.yaml` 的 `method` 段。

### 收工前（必须过一遍）

```
[ ] 产出了 project-profile / evidence-inventory / protocol.spec ？
[ ] 结论挂证据档位了吗？（static analysis / runtime observation / Inferred）
[ ] 未解决清单写了吗？
[ ] 三轴状态更新了吗？（实现 / 自动测试 / 客户端验收）
[ ] 回滚命令和基线哈希还在吗？
[ ] 有没有把「端口在听」「自环 OK」「日志打勾」写进成果？
```

---

## 3. 上下文极小时的应急路径

只能读 1~2 个文件时，按这个优先级取：

| 优先级 | 文件 | 能解决什么 |
|---|---|---|
| 1 | `SKILL.md` §0.0~§0.6 | 方法与铁律，避免方向性错误 |
| 2 | **本文件** | 知道该去读哪个文件 |
| 3 | `wire-level-patching.md` | 让"先跑起来"成为可能 |
| 4 | `closure-verification.md` | 避免把假阳性当成功 |
| 5 | `client-address-sources.md` | 避免"改了 URL 还连官方" |

> 剩下的都可以在**需要时**再读。skill 是查询手册，不是必读教材。

---

## 4. 六个反模式（都真实发生过）

1. **线性通读整个 skill 再动手** → 上下文耗尽，写到一半开始猜。
2. **只读 §0.4 工作流就写代码** → 跳过 Spec，字段全靠猜。
3. **跳过 `wire-level-patching.md`** → 陷进"必须先解出全部字段号"的路线。
4. **宣称完成前不读 `closure-verification.md`** → 把"端口在听"写成"已跑通"。
5. **对接客户端前不读 `client-address-sources.md`** → 改了一个 URL，流量还是回官方。
6. **能注入却硬要做外部服务端** → 明明可以在进程内合成响应，却先去还原加密 / 封包（`inline-server.md` §0）。

---

## 5. 一句话

> **先读"决定路线"的那一篇，再读"干活要用"的那几篇，最后读过"防自欺"的那一篇。**
> 其余按需查 —— 不要试图一次读完。