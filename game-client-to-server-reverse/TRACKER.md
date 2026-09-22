# TRACKER —— 进度与接口清单

> **简单维护，别写长。** 每完成/确认一个功能模块，就改对应行的「状态」。
> 目的：一眼看清 **哪些没做 / 没验证 / 游戏本来就没有**。

## 状态图例

| 符号 | 含义 | 要不要做 |
|------|------|---------|
| [x] | 已实现并验证 | 完成 |
| [~] | 部分实现 | 继续 |
| [ ] | 未实现 | 要做 |
| [?] | 已实现但未验证 | 去验证 |
| [-] | **游戏本身就没有** | **不做**

>  **三轴分离（重要）**：`[x]` 只允许表示**一轴**。
> 「服务端实现了」「自动测试覆盖了」「客户端验收了」必须分开记 ——
> 完整规则与模板见 `references/verification-and-status.md` 与 `templates/status-matrix.md`。
>
> 严格档位（推荐用于矩阵）：`Complete / Partial / Stub / Missing`。
> **`Stub`（只返回兼容空响应）必须单独成档**，否则会被误当成已实现。
>
> 写测试或宣称完成前先给场景分类：
> `client-reachable / transport-replay / server-boundary / save-integrity / client-characterization`。

>  **验收判据（来自实机跑通范式，详见 `references/engineering-practices.md`）**：
> 「端口在听 / TCP 连上」**只算 [~]**；必须收到**流程完成点消息**并进入**具名界面**
> （如「启动结束消息 → 主界面」）才允许 [x]。
> 结论行请挂证据档位：`static analysis` / `runtime observation` / `Inferred`。

---

## 接口 / 模块清单

> 每次做完一个大模块，更新这里。

### 账号与登录（见 `references/account.md`）
| 接口 | 状态 | 备注 |
|------|------|------|
| 版本检查 | [-] | TODO |
| 注册 | [ ] | TODO |
| 登录 | [ ] | TODO |
| token 校验 | [ ] | TODO |
| 服务器列表 | [-] | TODO |
| 注册网站html | [ ] | TODO |

> **先跑接口清单**：`python3 tools/extract_interfaces.py <源码目录> --out interfaces.md`
> 把返回的清单按子系统贴到下面各表，再逐条标注状态。

### 游戏
| 模块 | 状态 | 备注 |
|------|------|------|
| 角色列表 / 建角 / 选角 | [ ] | |
| 进场景 / 移动 | [ ] | |
| **房间 / 匹配** | [ ] | 建房/加入/准备/开始（`combat.md`） |
| **战斗** | [ ] | 服务端权威结算（`combat.md`） |
| **掉落 / 物资** | [ ] | 掉落表+掷骰+背包满转邮件（`drops.md`） |
| **抽卡 / 扭蛋** | [ ] | 服务端掷骰+保底落库+重复转换（`gacha.md`） |
| 商店 / 背包 | [ ] | |
| 邮件 | [ ] | |
| 任务 / 活动 | [ ] | |
| 聊天 / 好友 / 公会 | [ ] | [-] 若游戏没有则标 [-] |

### 系统 / 拓展
| 模块 | 状态 | 备注 |
|------|------|------|
| 客户端保护 / 服务端校验 | [ ] | 服务端侧仍要做权威校验 |
| 客户端对接（改包名 / 重打包 / 签名） | [ ] | 见 `references/repack-rename.md`；**优先"不改包 + 端口劫持"** |
| 资源分发 / CDN | [ ] | |
| 人机（假玩家） | [-] |  拓展；游戏没有就不做 |

---

## 实战项目进度：项目A（某 Unity IL2CPP 手游 官服 2.0.109）

> 案例细节见 `references/case-il2cpp-ecdh.md`。规则：**没在真实客户端上确认的，一律不写 [x]**。

| 模块 | 状态 | 备注 |
|------|------|------|
| 协议分层（u32BE 帧 / 12B 头） | [x] | 真机 tcpdump，切帧 100% |
| opCode 全量提取（1788 条） | [x] | `out/interfaces/` |
| 登录服 ECDH 时序 | [x] | 服务器**先**发 base64 token |
| 56B 挑战派生值算法 | [ ] | 34 种 KDF 候选全败 → 需读 `ProcessHandShakeMessage` |
| 登录**业务响应** | [ ] | `login_server.py` 后续包只做“尝试解密+打日志” |
| 自建服 8 端口监听 | [~] | 端口在听 ≠ 协议正确，进程身份待核 |
| 客户端改包（新包名） | [~] | 能装、启动秒退（自校验）；**未实机跑通** |
| 原版客户端连自建服 | [?] | 未完成 |
| `:8081` TUP/WUP | [-] | **已证伪**，非本游戏（APK 0 命中 + uid 无连接） |

## 实战项目进度：KiHan（平台 Unity IL2CPP 手游，内联服务端路线）

> 案例细节见 `references/case-il2cpp-inline.md`。
> 规则同样：**没在真实客户端上确认的，一律不写 [x]**。

| 模块 | 状态 | 备注 |
|------|------|------|
| 网络门面拦截（两个命名空间） | [x] | SendMessage / SendUnicast / Add / RemoveMessageCallback |
| 合成响应总表 + 主线程投递泵 | [x] | 队列存 gchandle，`thread_local` 重入守卫 |
| 本地登录 / 进入链路 | [x] | 复用客户端原生 `ZoneLogin` 路径 |
| 官方账号桥接连接 | [~] | 连接探测通过；业务取数未验 |
| 官方区服准入 | [-] | **已证伪**：客户端放行 ≠ 服务端准入 |
| wire 级协议规格 | [ ] | 本路线不急 |

---

## 未验证清单（[?]）

> 列出"实现了但没在真实客户端上确认过"的项。

- 自建服务端的自环测试（`client_test.py`）——与 `codec.py` 共用同一份**猜测**字段号，
  `[+] full flow OK` **不构成**对真实协议的验证（见 `closure-verification.md` 假阳性 ②）
- 8 个监听端口的**进程归属**与协议正确性（监听存在 ≠ 服务可用）

---

## 确定不做（[-]）

> 游戏本身就没有，除非用户提出需求。

- （空）

---

## 更新日志（一行一条）

```
YYYY-MM-DD  模块  状态变化
```
```
2026-09-12  账号-登录  [ ] → [x]  （示例：跑通真实客户端登录）
2026-09-13  知识库新增  —        references/repack-rename.md（改包名全清单 + 签名 + 重打包）
2026-09-13  知识库新增  —        references/closure-verification.md（闭环 6 类假阳性 + 检查表）
2026-09-13  知识库新增  —        references/case-il2cpp-ecdh.md（项目A 真实案例：帧格式/ECDH/已证伪项）
2026-09-13  方法论升级  —        SKILL.md §0.1 三条铁律 → 四条（新增"不把能跑当跑通"）
2026-09-13  参考项目A（https://github.com/Nanako660/peach-haven）-登录服    [~] → [~]  （修 step2 未定义变量 + 会话清理；派生值与业务响应仍缺）
2026-09-13  知识库新增  —        references/engineering-practices.md（实机跑通范式：fixture 回放/完成点/证据分档）
2026-09-13  模板新增    —        templates/adr-template.md、templates/e2e-evidence-template.md
2026-09-13  方法论升级  —        SKILL §0.6「启动阶段两把钥匙」；§13.1 强制产物 6 → 8 项
2026-09-13  知识库新增  —        references/wire-level-patching.md（实现层核心：帧 codec + pb 字段遍历 + splice 定点改写 + presence 陷阱 + 幂等收据 + fixture 选号）
2026-09-13  知识库新增  —        references/client-address-sources.md（地址六类来源 + 落点优先级 + 重签后果 + 阶段验收）
2026-09-13  知识库新增  —        references/verification-and-status.md（三轴状态 + 可达性五分类 + 测试分组门禁 + fail closed）
2026-09-13  知识库新增  —        references/release-and-ops.md（监听VS对外地址 / 端口族 / 启动期冻结配置 / CDN 版本策略 / 备份 / 变更语义）
2026-09-13  模板新增    —        templates/AGENTS.md（工作区 AI 协作契约）、templates/status-matrix.md（三轴状态矩阵）
2026-09-14  方法论升级  —        SKILL §0.1 四条铁律 → 五条（新增"三件事分开记"）；§13.1 强制产物 8 → 10 项
2026-09-14  知识库新增  —        references/reading-path.md（最小必读路径：按任务类型分派 3~5 个文件；开读前/收工前检查；5 个反模式）
2026-09-14  入口优化    —        SKILL 顶部 + README 顶部 增加"先读这个，不要一次读完"引导块
2026-09-15  知识库新增  —        references/inline-server.md（内联服务端：门面三类入口 / 回调投递纪律 / 延迟派发 / 双通路 / 验收与假阳性）
2026-09-15  知识库新增  —        references/runtime-object-synthesis.md（对象级 schema 自举 + 字段发现循环 + 填值纪律 + 对象级→wire 级切换）
2026-09-15  知识库新增  —        references/platform-sdk-and-admission.md（平台 SDK 登录态复用 + 目录服→区服两段准入 + 卡点定位）
2026-09-15  知识库新增  —        references/case-il2cpp-inline.md（真实案例：Unity IL2CPP + 平台 SDK 内联服务端）
2026-09-15  方法论升级  —        SKILL §0.0 方法表 10 → 11 种（新增 M11 内联服务端法）、§0.4 主干加分叉、§0.5 参考表 +4、铁律 4 增内联判据
2026-09-15  方法论升级  —        methods.md 10 → 11 种、decision-tree 顶部增加「外部 vs 内联」路径分叉、reading-path 增加任务类型 ⑧
2026-09-15  版本        —        1.7 → 1.8
2026-09-22  版本        —        1.8 → 1.9 → 2.0
2026-09-22  知识库新增  —        references/primer.md（原理层：三要素 / 数据包协议 / 协议表 / 热更源码 / 双证据链）
2026-09-22  知识库新增  —        references/workflow-roadmap.md（四阶段路线总纲 + 四层重定向表）
2026-09-22  知识库新增  —        references/server-architecture-basics.md（反推对象地图：还原哪几类服 / 网关隐藏层 / 同步模型）
2026-09-22  知识库新增  —        references/phases-detail.md（§1~§10 反推主流程详细版：命令/工具/判断/坑）
2026-09-22  知识库新增  —        references/ai-contract.md（AI 行为契约完整版：强制产物/禁止/终点/回滚）
2026-09-22  模板新增    —        templates/login-chain.md、templates/function-checklist.md
2026-09-22  模板新增    —        templates/register-site/
2026-09-22  模板新增    —        templates/frida-redirect.js、templates/xposed-redirect/（客户端重定向：native / Java）
2026-09-22  方法论升级  —        methods.md M8 增「现成实现速查 + 复活 / 本地离线项目合集」；protocol-spec.md 增「人类可读协议文档格式」
2026-09-22  结构合规    —        skill 目录重命名为 game-client-to-server-reverse（frontmatter name == 父目录名）
2026-09-22  元数据合规  —        frontmatter：version/platforms 移入 metadata；补 license / compatibility
2026-09-22  体量优化    —        SKILL.md 656 → 467 行（§1~§10、§13 下沉到 references，标题/编号保留 + 指针）
2026-09-22  入口优化    —        全库去 emoji；新增跨模型阅读协议；README 加「目录映射」表；篇数同步
2026-09-22  维护契约    —        工作区根 AGENTS.md（契约 + 守则合并：完善内容放哪 / 如何接入 / 硬约束 / 自检脚本）
```
