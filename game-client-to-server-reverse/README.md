# 游戏客户端 → 服务端反推 Skill

完整支持 **Unity（IL2CPP / Mono / Lua）** 与 **Unreal Engine（UE4 / UE5）**，也覆盖 C#/AS3/Lua/JS/Java 等各类客户端。
从客户端反推协议 → 复现服务端 → 部署 → 让原版客户端成功连上。

> [x] 本包自带的服务端已**实测跑通**：握手 → 登录 → 建角 → 选角 → 进场景 → 移动 → 心跳，
> 并验证 XOR 加密 + zlib 压缩 + GM 控制台 + 充值/邮件发放。
>
>  **2026-09-22 更新（v2.0）** —— 本版主题：原理层 + 四阶段路线 + **换服务端（重定向）**：
> ⓪ **版本升至 2.0**：整合 1.x 全部成果 + 以下 ①~⑪；
> ① **原理层** `references/primer.md`：三要素（配置=数值 / 协议=格式 / 代码=用法）、
>   数据包协议本质、协议号与协议表、**热更新代码是比 dump 更好读的源码**；
> ② **四阶段路线总纲** `references/workflow-roadmap.md`（静态分析 → 建工具+登录链 → 重定向 → 补包循环 → 清单迭代）+ **四层重定向表**；
> ③ 模板：`templates/login-chain.md`（登录链条）、`templates/function-checklist.md`（功能清单）；
> ④ SKILL §0 开头新增**阅读地图（三条主线）**；
> ⑤ **反推对象地图** `references/server-architecture-basics.md`（逆向视角）：你在还原哪几类服、
>   网关留下的隐藏层（合并/加解密/压缩 flag）、从包里认 Protobuf/KCP、同步模型决定"要还原多少逻辑"
>   （来源：平台云架构演进、GameDevAndOps、KCP/protobuf 官方、Skynet/Pomelo/KBEngine/NF）；
> ⑥ **取长补短（折进现有文件）**：`methods.md` M8 补入**现成实现速查（按类型）** + "先查别人做过没" + **先锁版本**；`protocol-spec.md` 补入人类可读协议文档格式；
> ⑦ **SKILL.md 瘦身**：与 references 重复的 §1~§8、§11、§14~§19 压成"要点+指针"（1122 → ~650 行）；§11 常见坑并入 `closure-verification.md §附`；
> ⑧ **跨模型阅读优化（GLM / DeepSeek / Claude）**：SKILL 顶部改为**模型无关的显式阅读协议**（"打开哪个文件"写死）；
>    去掉顶部大段变更历史；给 5 篇 >300 行的 reference 补**章节目录**；`reading-path.md` 顶部声明按它分派；
> ⑨ **去除 emoji**：全库清理（状态标记转 ASCII、装饰 emoji 删除、箭头保留）；
> ⑩ **框架修正 + 资源**：` §0` 改为"**主动改客户端对接自建服务端**"（按重定向四层表、优先跑起来）；
> ⑪ **换服务端手法补全（v2.0 新增）**：`client-address-sources.md §3.0b` 加入 **Xposed / LSPatch 模块重定向**
>    （第三方代理模块实测范例，免 root）；`methods.md` M8 加"**多人/联机复活项目**"检索入口；
> ⑫ **签名绕过**：`repack-rename.md §8` 加入 **LSPatch Signature Bypass（等级 2）机制** / 独立签名破解
>    （`ApkSignatureKiller` / 核心破解） / 真正不改签名的虚拟容器（VirtualXposed / 太极）；§7 落点表述改为"按代价从低到高"；
> ⑬ **配套界面模板**：`templates/register-site/`（注册网站）+ `templates/gm-admin/`（GM 后台），各含 `index.html` + 最小 Flask 后端；
>    接入点：`account.md §6`、`release-and-ops.md §7`、`SKILL §16`；
> ⑭ **GM 后台对齐真实面板**：按实测的"某 Unity IL2CPP 手游"GM 面板（AES-GCM 签名表单 + CDK 激活 + 发货到邮件）
>    重写 `templates/gm-admin/`（选服→账号查角色→角色列表→激活/发货/物品/记录），动作名对齐 `api.php`；知识已记入 `release-and-ops.md §7`；
> ⑮ **邀请码 / 三选一校验**：注册站支持 **邀请码 / QQ群验证 / 白名单** 三选一（`VERIFY_MODE`）；
>    GM 后台新增"**邀请码**"页（任一已注册用户可生成 / 列表 / 撤销），注册站按邀请码核销；两模板共享同一 DB 的 `invite_code` 表；
> ⑯ **GM 后台鉴权改造**：**移除 CDK 激活**；发奖励前须输入**该账号注册时的密码**（服务端校验哈希）；
>    发放支持**货币 / 物品 / 奖励邮件**并写 `gm_send_log` 可查；
> ⑰ **GM 后台补齐通用模块**：新增 **公告广播 / GM 命令台 / 在线列表**；全局操作用**操作员口令**
>    （`GM_ADMIN_TOKEN`）。模块对照开源 GM 后台（gamekeeper 的服务器监控/玩家查询/后台命令等）取长补短；
> ⑱ **GM 后台登录 + 权限 + 安全**：加**操作员登录**（独立账号体系，PBKDF2）与**玩家登录**（游戏账号）；
>    **角色权限分离**（player/viewer/support/admin/super，前后端双重校验）；**全程审计**（`gm_audit` 记操作员/动作/IP）；
>    安全加固（仅绑 127.0.0.1、失败限流、会话 token + `X-GM-Token` 头、常量时间比较、无默认口令）；
> ⑲ **登录页 + Tab 合并**：未登录只显示**独立登录页**；原"公告 + GM命令"合并为**服务器管理**，
>    仅服务器管理员（admin/super）可访问使用；
> ⑳ **操作员管理页（仅 super）**：增删操作员 / 改角色 / 启停 / 重置密码（PBKDF2 重存），
>    权限体系闭环（首个超管由环境变量创建，其余在此维护）；
> ㉑ **收尾**：重写 `templates/README.md`（分类总览 + **快速上手 5 步**）；`release-and-ops.md §7`、`account.md §6` 更新模板指引。
>
>  **2026-09-15 实战沉淀（v1.8 新增）**：
> ⑬ **内联服务端**：不起外部服务端，在客户端**进程内**拦截网络门面合成响应
>   （三类入口 / 回调投递纪律 / 延迟派发 / 双通路 / 内联版验收与假阳性）→ `references/inline-server.md`
> ⑭ **运行时对象合成与字段发现**：用客户端自己的类型系统当 schema，先 dump 再合成 → `references/runtime-object-synthesis.md`
> ⑮ **平台 SDK 登录态复用 + 目录服→区服两段准入** → `references/platform-sdk-and-admission.md`
> ⑯ 真实案例：Unity IL2CPP + 平台 SDK 的内联服务端 → `references/case-il2cpp-inline.md`
>
>  **2026-09-13 实战沉淀（新增）**：
> ② **改包名 / 重打包 / 保留原签名**全清单 → `references/repack-rename.md`
> ④ **闭环验证与 6 类假阳性**（端口在听≠服务可用、自环≠客户端兼容）→ `references/closure-verification.md`
> ⑤ **真实案例：Unity IL2CPP + ECDH 登录服**（帧格式 / SPKI / 已证伪项）→ `references/case-il2cpp-ecdh.md`
> ⑥ SKILL 铁律 3 → 4 条：**不把「能跑」当成「跑通」**
> ⑦ **工程范式**（实机跑通项目的做法：fixture 回放 / 具名完成点 / 证据分档 / ADR）→ `references/engineering-practices.md`
> ⑧ 文档模板：`templates/adr-template.md`、`templates/e2e-evidence-template.md`
> ⑨ **实现层核心**：不依赖 protobuf 运行时的 **wire 级定点改写**（帧 codec + 字段遍历 + splice 替换 + 空子消息必须保留）→ `references/wire-level-patching.md`
> ⑩ **客户端地址来源清查**（六类来源 + 落点优先级 + 重签后果 + 阶段验收）→ `references/client-address-sources.md`
> ⑪ **三轴状态与验收体系**（实现 / 自动测试 / 客户端验收 + 可达性五分类 + 提交门禁）→ `references/verification-and-status.md`
> ⑫ **发布、部署与运营**（监听 vs 对外地址 / 端口族 / 启动期冻结配置 / CDN 版本策略 / 后台 / 备份）→ `references/release-and-ops.md`

---

## 目录映射（本 skill 的结构）

> 本 skill 遵循 **Agent Skills** 规范：**一个文件夹 = 一个 skill**，且 frontmatter 的 `name`
> 必须与文件夹名一致。本文件夹即 `game-client-to-server-reverse/`；内部目录是对规范约定目录的映射。

| 规范约定 | 本 skill 实际 | 说明 |
|----------|--------------|------|
| `SKILL.md` | `SKILL.md` | 必需：元数据 + 主干（已瘦身到 < 500 行，符合规范建议） |
| `references/` | `references/` | 按需加载的详细文档（正文下沉于此） |
| `assets/` | `templates/`、`schema/`、`server/` | 模板 / 中间产物模板 / 可运行参考实现 |
| `scripts/` | `tools/` | 可执行脚本（`extract_interfaces.py` / `` / `repack_zip.py`） |
| — | `examples/`、`extensions/` | 推演示例 / 可选拓展 |

> 阅读顺序：`SKILL.md`（导航+主干）→ `references/reading-path.md`（按任务分派）→ 按需打开具体文件。

---

##  先读什么（别一次读完整包）

本包有 37 篇参考 + 一份长主文档。**通读完再动手 = 上下文耗尽 + 在半懂的地方开始猜。**

```
1. references/reading-path.md      ← 按任务类型拿到 3~5 个文件的阅读路径
2. SKILL.md §0.0 ~ §0.6            ← 方法选择 + 铁律 + 工作流主干
3. 按路径读完场景层文件 → 动手
收工前：reading-path.md §2 的「收工前检查」
```

**上下文极少时**的优先级：
`SKILL §0` → `reading-path.md` → `wire-level-patching.md` → `closure-verification.md` → `client-address-sources.md`

> skill 是**查询手册**，不是必读教材。

---

#  如何使用本 Skill

## 一句话

把游戏（安装包 / 客户端 / 辅助文件）交给 AI，说清「要什么」，
AI 会**自己取证 → 产出协议规格 → 生成并部署服务端 → 让客户端连上**。

## 你最少只需给一样

| 给什么 | 推荐度 | AI 会做什么 |
|--------|--------|------------|
| **一个安装包**（`.apk` / `.ipa` / `.exe`） |  最推荐 | 自己解包、判引擎、跑 dump、抓包（见 `references/from-installer.md`） |
| 客户端目录 / `dump.cs` / `*.lua` / `*.usmap` |  | 直接进静态分析 |
| 抓包 `*.pcap` / mitm 导出 |  | 直接做协议分层 |
| 已有服务端样本 / 协议文档 |  | 对照分析 |
| 只有一个游戏名 | [x] | 没有证据，建议先提供安装包 |

## 提问模板（直接复制改）

```
① 最简
帮我反推这个游戏的服务端：/文件路径/game.apk

② 带目标
用这个 APK 反推服务端，先跑通登录，然后部署到本地。

③ 带约束
这是 Unity 手游，服务端请分析根据当前用户给出客户端来用什么编写（如Go编写），要支持局域网联机链接到我们当前写的服务端上，先做协议分析.md文档再写代码。

④ 指定阶段
先别写代码，只做协议分层，产出 protocol.spec.yaml 和证据清单。
```

## 一个好提问包含 4 个要素

| 要素 | 说明 | 例子 |
|------|------|------|
| **输入** | 你给什么 | `game.apk` / `dump.cs` / `capture.pcap` |
| **目标** | 做到哪一步 | 只分析 / 跑通登录 / 完整服务端+部署 |
| **约束** | 语言/平台/版本 | Go / 安卓局域网 / 客户端 1.8.1 |
| **环境** | 跑在哪 | 本地 / 云服务器 / Termux |

> 缺哪个都行，AI 会用占位符推进；但**输入**最好给一个。

## AI 会按这个顺序回应（重要）

```
1. project-profile.yaml    ← 我读了什么、还缺什么        （项目档案）
2. evidence-inventory      ← 每条结论的证据 + 置信度     （证据清单）
3. protocol.spec.yaml      ← 协议规格（唯一事实来源）
4. 服务端代码 + 部署 + 验证 ← 由 Spec 派生
```

> 注意: **如果 AI 直接甩给你一堆代码，却没有前 3 样，让它重来。**
> 「先规格，后代码」是本 skill 的硬性要求（见 `references/ai-contract.md`）。

**另有两份"开工/收工"契约**（详见 `references/ai-contract.md`）：

```
AGENTS.md                  ← 工作区边界 + 验证命令 + 收工状态（放在项目根）
docs/status/support-matrix ← 三轴状态：实现 / 自动测试 / 客户端验收
```

## 可以这样追问

- 「先给我证据清单」
- 「先只做协议分层」
- 「为什么判定是 4 字节大端？证据是哪条？」
- 「服务端换成 Go 重写」
- 「把 opcode 表填进去」
- 「客户端连不上，帮我定位是哪一步」
- 「先把账号/登录接口列出来，登记到 TRACKER」

## 常见问题指路

| 问题 | 看哪 |
|------|------|
| 不懂"在反推什么"/第一次做 | `references/primer.md`（原理层） |
| 不知道先做什么、在哪验收 | `references/workflow-roadmap.md`（四阶段路线） |
| 只有安装包怎么办 | `references/from-installer.md` |
| 怎么注册账号 / 替换登录接口 | `references/account.md`（§16） |
| 需要人机（假玩家） | `extensions/`（§18，可选） |
| 不想起服务端 / 想单机化 | `references/inline-server.md`（M11 内联服务端） |
| 进度/接口清单 | `TRACKER.md` |

## 不要这样问

- [x] 只给游戏名就让 AI 凭空写服务端 —— 没有证据 = 必错
- [x] 「直接给我能用的服务端」却不给任何输入

## 边界

- 用于**自研 / 已授权 / 离线**目标的互操作性研究本地化部署和学习
- 使用参考项目/代码前先看其许可证

---

## 目录结构

```
服务端反推/
├── SKILL.md                主流程（18 节，核心方法论）
├── README.md               本文件
├── TRACKER.md               进度与接口清单（每模块更新，从简）
├── schema/                  中间产物模板（AI 填这些）
│   ├── project-profile.yaml   项目档案
│   └── protocol.spec.yaml     协议规格（唯一事实来源）
├── references/
│   ├── adaptation.md        自适应方法论：项目→证据→决策→Spec
│   ├── reading-path.md      最小必读路径（按任务类型分派）
│   ├── primer.md            原理层：三要素/数据包协议/协议表/热更源码/双证据链
│   ├── workflow-roadmap.md  四阶段路线总纲（静态分析→建工具+登录链→重定向→补包循环→清单迭代）
│   ├── phases-detail.md     §1~§10 反推主流程详细版（命令/工具/判断/坑）
│   ├── ai-contract.md       AI 行为契约（强制产物/禁止/终点/回滚）
│   ├── server-architecture-basics.md  反推对象地图（逆向视角：你在还原哪几类服/网关隐藏层/同步模型）
│   ├── methods.md           10 种反推方法 + 选择矩阵（动手前先看）
│   ├── closure-verification.md  闭环验证 6 类假阳性（宣布成功前必看）
│   ├── engineering-practices.md  实机跑通范式：fixture 回放 + 完成点 + 证据分档 + ADR
│   ├── wire-level-patching.md  实现层核心：不依赖 pb runtime 的 wire 级定点改写
│   ├── client-address-sources.md  客户端地址来源清查 + 落点策略
│   ├── verification-and-status.md  三轴状态 + 可达性分类 + 测试门禁
│   ├── release-and-ops.md   发布 / 部署 / 运营 / CDN / 后台 / 备份
│   ├── case-il2cpp-ecdh.md  真实案例：IL2CPP + ECDH 登录服 + 卡点复核
│   ├── inline-server.md     内联服务端：进程内合成响应（与外部服务端并列的第二条路）
│   ├── runtime-object-synthesis.md  运行时对象合成与字段发现（对象级 schema 自举）
│   ├── platform-sdk-and-admission.md  平台 SDK 登录态复用 + 目录服→区服两段准入
│   ├── case-il2cpp-inline.md  真实案例：IL2CPP + 平台 SDK 的内联服务端
│   ├── account.md           账号体系与接口还原（登录/注册/接口替换）
│   ├── combat.md            房间与战斗（局内、同步模型、服务端权威）
│   ├── drops.md             掉落与物资（掉落表、掷骰、背包满转邮件）
│   ├── gacha.md             抽卡/扭蛋（服务端掷骰、保底、重复转换）
│   ├── decision-tree.md     逐层决策树（引擎/传输/封装/加密/序列化/架构）
│   ├── protocol-spec.md     协议规格规范 + codegen 映射
│   ├── codegen.md           由 Spec 生成/改造服务端（多语言）
│   ├── client-languages.md  客户端语言分支（C#/AS3/Lua/JS/Java/C++）
│   ├── from-installer.md    零输入自举：只有安装包怎么自产证据
│   ├── cases.md             两个真实成功项目案例（Go / Node）
│   ├── unity.md            Unity(IL2CPP/Mono/Lua) 深潜
│   ├── unreal.md           Unreal(UE4/UE5) 深潜
│   ├── windows.md          端游：Windows 运行服务端
│   ├── termux.md           手游：Android/Termux 运行服务端
│   └── repack-rename.md     改包名/重打包/签名/包名派生密钥
├── examples/                推演示例（同 skill，不同项目→不同方案）
│   ├── A-unity-il2cpp-protobuf.md
│   ├── B-ue-kcp-custom.md
│   ├── C-unity-lua-http.md
│   └── D-real-lua-client.md     真实 Lua 源码分析（1794 个 opCode）
├── tools/
│   └── extract_interfaces.py    接口清单提取器（扒 opCode/路由）
├── templates/              参考代码与文档模板
│   ├── mock_server.py      极简桩
│   ├── frida_bypass_ssl.js / kcp_sniff.py
│   ├── frida-redirect.js   客户端重定向：hook getaddrinfo/connect（native/il2cpp）
│   ├── xposed-redirect/    LSPosed 模块骨架：改写 URL（Java/OkHttp 客户端）
│   ├── register-site/      注册网站（index.html + 最小 Flask 后端）
│   ├── gm-admin/           GM 后台（index.html + 最小 Flask 后端）
│   ├── AGENTS.md            工作区 AI 协作契约（放在项目根）
│   ├── adr-template.md      架构决策记录（含「当前不做的事情」+ 回滚）
│   ├── e2e-evidence-template.md  实机端到端证据（帧序表 + 差异解释 + 重连快照）
│   ├── status-matrix.md     三轴状态矩阵（实现 / 测试 / 客户端验收）
│   ├── login-chain.md       登录链条文档（启动到主场景每一步）
│   └── function-checklist.md  功能清单（按子系统登记实通/未通）
├── extensions/              后续拓展（可选，不影响核心运行）
│   ├── README.md           拓展说明与判断标准
│   ├── bots.md             服务端人机（假玩家）
│   └── bot-reverse.md      反推人机机制再复刻
└── server/                 参考实现：长连接二进制协议服务端（Python）
```

## 端游 / 手游怎么跑

| 平台 | 启动 | 常驻 | 客户端对接 |
|------|------|------|-----------|
| Windows(端游) | `deploy/start_windows.bat` | NSSM 服务 | 改 hosts → 127.0.0.1 |
| Android(手游) | `bash start_termux.sh` | wake-lock + tmux | hosts / DNS 重定向 |
| Linux 服务器 | `deploy/deploy.sh` | systemd | 域名解析 / 端口转发 |
| Docker | `docker compose up -d` | 容器策略 | 同上 |

## 客户端语言不只有 Unity/UE

| 客户端语言 | 反编译工具 | 能拿到源码？ | 客户端补丁方式 |
|-----------|-----------|------------|--------------|
| C#（Unity Mono / .NET） | dnSpy / ILSpy | [x] 近源码 | 配置 / 重编译 / hook |
| C#（Unity IL2CPP） | Il2CppDumper + IDA | [x] 仅签名 | Frida hook |
| ActionScript3 / Flash | JPEXS FFDec | [x] 反编译 | 改源码重编译 |
| Lua 热更 | unluac / luadec | [x] | 改 lua |
| Java/Kotlin | jadx | [x] | smali patch / hook |
| JS / H5 | beautify / sourcemap | [x] | 改 js |
| C++ / UE | SDK dump | 注意: 结构 | hook / patch |

详见 `references/client-languages.md`。
真实项目案例（Go 服务端 + C# 启动器；Node/TS 服务端 + AS3 客户端）见 `references/cases.md`。

## 服务端语言也不固定

Python 只是本仓库的参考实现。真实案例里：**Go**（某 Unity 手游）、**Node/TS**（某 Cocos 手游）。
选型见 `references/codegen.md`，由 Spec 决定，不是照抄。

## 充值 / 发放（私服支付）
- `game.pay_grant_mode`: `direct`（直接进背包）/ `mail`（发邮件领取）
- `game.pay_auto_success: true` → 点击购买直接成功
- 商品表 `PAY_PRODUCTS` 键 = 客户端真实 `product_id`
- GM 直发：`give` / `mail` / `pay`

##  后续拓展（可选，不影响核心运行）

> **判断标准**：去掉它，游戏还能不能正常玩？**能 → 就是拓展。**
>
> 注意: **内联服务端不是拓展**：它是与「外部服务端」并列的**核心路线**（M11，见 `references/inline-server.md`），
> 不适用本判断标准。

| 拓展 | 文件 | 一句话 |
|------|------|--------|
| 服务端人机（假玩家） | `extensions/bots.md` | 多人游戏凑不齐人时用 AI 补位 |
| 反推人机机制 | `extensions/bot-reverse.md` | 无参考项时，从客户端反推它的人机实现 |

**人机为什么是拓展**：单人也能玩的游戏完全不需要；多人游戏缺人只是**体验受损，
服务端本身能跑**，不影响「连上/登录/进游戏」。

- 参考骨架：`server/app/logic/bots.py`（**只是骨架**，默认 `auto_fill: 0` 不生成假玩家）
- 调试：GM 命令 `bots spawn / bots clear / bots difficulty`
- 联调：`python server/test_bots.py`

> 注意: 拓展**不参与**核心验收。没做拓展 ≠ 交付不完整。

## 两种服务端模板怎么选

| | templates/mock_server.py | server/ |
|---|---|---|
| 用途 | 抓包后快速验证协议结论 | 真正部署、长期运营 |
| 规模 | 单文件 | 分层工程 |
| 能力 | 帧收发 + opcode 桩 | 数据库/状态机/客户端保护/GM/部署 |
| 何时用 | 逆向中期试探 | 逆向完成、要跑起来 |

## 最快上手

```bash
# 1. 起服务端
cd server && chmod +x start.sh && ./start.sh

# 2. 联调自测（另开一个终端）
./venv/bin/python client_test.py --host 127.0.0.1 --port 8888 \
    --user alice --password 123456 --name Hero01
# 期望输出结尾：[+] full flow OK

# 3. 部署到服务器
sudo bash server/deploy/deploy.sh
```

## 工作流

```
[只有安装包？] 解包 → 判引擎/语言 → 自产 dump/lua/资源 → 抓包 → 动态dump
        ↓
侦察引擎 → 协议分层 → 客户端静态定位 → 字段推断
        → 服务端建模 → 部署 → 客户端对接 → 闭环验证
```

> 只有 `.apk`/`.ipa`/`.exe` 也能开始 —— 见 `references/from-installer.md`。

## 给 AI 的使用方式

1. 把辅助文件（`dump.cs` / `*.lua` / `*.usmap` / SDK `.h`）丢进来。
2. AI 按 `SKILL.md §1` 分类，自动进入 Unity 或 UE 分支。
3. 逆向结论落到 `server/app/proto/`（消息号 + 结构）与 `config.yaml`（协议参数）。
4. 起点验证用 `templates/mock_server.py`，终点交付用 `server/`。
