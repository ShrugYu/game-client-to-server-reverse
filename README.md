<p align="center">
  <b>简体中文</b> · <a href="./README.en.md">English</a>
</p>

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://shieldcn.dev/header/grid.svg?title=Game+Client+%E2%86%92+Server+Reverse&subtitle=From+a+client-only+game+to+a+running+self-hosted+server&mode=dark&align=center">
    <img alt="Game Client → Server Reverse" src="https://shieldcn.dev/header/grid.svg?title=Game+Client+%E2%86%92+Server+Reverse&subtitle=From+a+client-only+game+to+a+running+self-hosted+server&mode=light&align=center">
  </picture>
</p>

<p align="center">
  <a href="https://github.com/ShrugYu/game-client-to-server-reverse"><img alt="GitHub stars" src="https://shieldcn.dev/github/stars/ShrugYu/game-client-to-server-reverse.svg?variant=secondary&v=2"></a>
  <a href="https://github.com/ShrugYu/game-client-to-server-reverse/blob/main/LICENSE"><img alt="License" src="https://shieldcn.dev/github/license/ShrugYu/game-client-to-server-reverse.svg?variant=secondary&v=2"></a>
  <a href="https://github.com/ShrugYu/game-client-to-server-reverse/commits/main"><img alt="Last commit" src="https://shieldcn.dev/github/last-commit/ShrugYu/game-client-to-server-reverse.svg?variant=secondary&v=2"></a>
  <a href="https://github.com/ShrugYu/game-client-to-server-reverse/graphs/contributors"><img alt="Contributors" src="https://shieldcn.dev/github/contributors/ShrugYu/game-client-to-server-reverse.svg?variant=secondary&v=2"></a>
  <a href="https://github.com/ShrugYu/game-client-to-server-reverse/forks"><img alt="Forks" src="https://shieldcn.dev/github/forks/ShrugYu/game-client-to-server-reverse.svg?variant=secondary&v=2"></a>
</p>

# 游戏客户端 → 服务端协议反推 Skill

> 把「只有客户端」的游戏，还原出「服务端协议 + 可用服务端」，并让**原版客户端成功连上自建服务端**。
>
> 一份给 AI 用的**逆向操作手册**：不是服务端开发教程，而是「怎么从客户端反推出服务端」。

这是一个遵循 [Agent Skills](https://agentskills.io) 规范的 skill 包。核心 skill 名为 `game-client-to-server-reverse`，
由一份导航主文档 `SKILL.md` + 37 篇 `references/` 正文 + `templates/` 模板 + `tools/` 脚本 + 可运行的 `server/` 参考实现组成。

---

## 这是什么

| 维度 | 说明 |
|------|------|
| **定位** | 根据游戏客户端反推服务端协议，复现出一个能真正跑起来的服务端（逆向视角） |
| **输入** | 安装包（`.apk` / `.ipa` / `.exe`）、`dump.cs`、`*.lua`、`*.usmap`、抓包（`.pcap` / mitm 导出）、已有服务端样本 |
| **输出** | `project-profile` → `evidence-inventory` → `protocol.spec.yaml`（唯一事实来源）→ 服务端代码 + 部署 + 闭环验证 |
| **引擎覆盖** | Unity（IL2CPP / Mono / Lua）、Unreal（UE4 / UE5）、Cocos2d-x / Cocos Creator（JS / Lua 热更） |
| **语言覆盖** | C#、AS3、Lua、JS、Java/Kotlin、C++ |
| **平台覆盖** | Android（Termux）、Windows（端游）、Linux 服务器、Docker |

**硬性要求：先产出规格，再产出代码。** 代码由 `protocol.spec.yaml` 派生，换游戏 = 换规格，而不是重写一堆散代码。
如果 AI 直接甩给你一堆代码却没有规格与证据清单，让它重来。

---

## 核心特性

- **原理层**（`references/primer.md`）：三要素（配置=数值 / 协议=格式 / 代码=用法）、数据包协议本质、协议号与协议表、热更源码。
- **四阶段路线**（`references/workflow-roadmap.md`）：静态分析 → 建工具+登录链 → 重定向 → 补包循环 → 功能清单迭代，每阶段有明确验收。
- **11 种反推方法选择器**（`references/methods.md`）：白盒源码 / 黑盒抓包 / 灰盒 Hook / 辅助 Artifact / 代理透传逐接口替换 / 差分探测 / 回放 / 已实现移植 / 自环 / 穷举 / **内联服务端**，附选择矩阵。
- **内联服务端路线**（`references/inline-server.md`）：不起外部服务端，在客户端进程内合成响应；传输 / 封装 / 加密层不必还原。
- **wire 级定点改写**（`references/wire-level-patching.md`）：不依赖 protobuf 运行时，直接在字节层读写字段。
- **闭环验证 6 类假阳性**（`references/closure-verification.md`）：端口在听 ≠ 服务可用，自环 ≠ 客户端兼容。
- **参考实现**（`server/`）：长连接二进制协议服务端（Python），实测跑通握手 → 登录 → 建角 → 选角 → 进场景 → 移动 → 心跳。
- **配套界面模板**：`templates/register-site/`（注册网站）、`templates/gm-admin/`（GM 后台，含权限 / 审计 / 邀请码）。

---

## 分发 / 安装

### 作为 Skill 安装（推荐）

```bash
npx skills add ShrugYu/game-client-to-server-reverse
```

安装到当前项目、全局、或指定 agent：

```bash
npx skills add ShrugYu/game-client-to-server-reverse --global
npx skills add ShrugYu/game-client-to-server-reverse --agent AGENT_NAME
```

### 手动安装

把 `game-client-to-server-reverse/` 整个文件夹复制到你的 skill 目录即可
（例如 Operit：`/storage/emulated/0/Download/Operit/skills/`）。
文件夹名必须与 `SKILL.md` frontmatter 里的 `name` 保持一致。

### 分发渠道

| 渠道 | 链接 |
|------|------|
| **GitHub 仓库** | https://github.com/ShrugYu/game-client-to-server-reverse |
| **skills CLI** | `npx skills add ShrugYu/game-client-to-server-reverse` |
| **SkillsMP**（自动索引） | https://skillsmp.com |
| **skills.sh** | https://skills.sh |

支持 Claude Code / Cursor / Codex / GitHub Copilot / Windsurf / Gemini / Cline 等 agent。

---

## 怎么用

把游戏相关文件交给 AI，说清「要什么」。它最少只需要**一个安装包**就能自举：

```
帮我反推这个游戏的服务端：/文件路径/game.apk

用这个 APK 反推服务端，先跑通登录，然后部署到本地。

这是 Unity 手游，先做协议分析产出 .md 文档，再写代码。
```

AI 会按这个顺序回应：

```
1. project-profile.yaml    ← 读了什么、还缺什么
2. evidence-inventory      ← 每条结论的证据 + 置信度
3. protocol.spec.yaml      ← 协议规格（唯一事实来源）
4. 服务端代码 + 部署 + 验证 ← 由 Spec 派生
```

### 阅读顺序（给 AI）

```
1. references/reading-path.md   ← 按任务类型拿到 3~5 个文件的阅读路径
2. SKILL.md §0.0 ~ §0.6         ← 方法选择 + 铁律 + 工作流主干
3. 按路径读完场景层文件 → 动手
收工前：reading-path.md §2 的「收工前检查」
```

> `SKILL.md` 是导航，`references/` 是正文。**不要一次读完整包**——会耗尽上下文。

---

## 目录结构

```
.
├── README.md                        本文件（简体中文）
├── README.en.md                     English README
├── AGENTS.md                        工作区维护契约（skill 维护者用）
└── game-client-to-server-reverse/    skill 本体（文件夹名 = skill name）
    ├── SKILL.md                     导航主文档（< 500 行）
    ├── README.md                    skill 自身的详细说明
    ├── TRACKER.md                   进度与接口清单
    ├── references/                  37 篇按需加载的正文
    ├── schema/                      project-profile.yaml / protocol.spec.yaml 模板
    ├── templates/                   文档与代码模板（注册站、GM 后台、ADR、e2e 证据…）
    ├── tools/                       extract_interfaces.py / make_stub_so.py / repack_zip.py
    ├── examples/                    不同游戏类型的推演示例
    ├── extensions/                  可选拓展（服务端人机 / 反推人机机制）
    └── server/                      参考实现：长连接二进制协议服务端（Python）
```

---

## 免责声明

> 使用本资料即表示你已阅读、理解并同意以下全部条款；若不同意，请立即停止使用。

1. **用途限定**：本资料仅供**学习、研究与技术交流**，以及针对**自研、已获授权或离线单机**游戏的互操作性研究与本地化部署。它是一份**逆向方法论文档**，不是服务端开发教程，也不针对任何特定游戏。

2. **禁止非法用途**：严禁将本资料用于任何**未经授权**的入侵、攻击、破坏、篡改、绕过安全机制、窃取数据，或侵犯他人知识产权、违反目标游戏服务条款及所在地法律法规的行为。

3. **无担保**：本资料按"**现状**（as-is）"提供，不附带任何明示或暗示的担保，包括但不限于适销性、特定用途适用性与不侵权担保。作者不保证其准确性、完整性或可用性。

4. **责任限制**：在适用法律允许的最大范围内，作者及贡献者**不对因使用或无法使用本资料而产生的任何直接、间接、附带、特殊、惩戒性或后果性损失承担责任**（包括但不限于数据丢失、设备损坏、账号封禁及法律纠纷）。

5. **使用者自负其责**：使用者须**自行确保**其使用行为合法合规（含取得必要授权），并**独立承担由此产生的全部法律责任与后果**。

6. **第三方内容**：本资料引用或链接的第三方项目、代码、工具、文档及服务，其版权与许可归各自所有者所有；使用前请自行查阅并遵守其各自条款。作者不对第三方内容及其后果负责。

7. **权利主张**：若你是某作品的权利人，并认为本资料侵犯了你的合法权益，请通过仓库 Issue 联系，作者将在核实后**及时更正或删除**。

8. **条款变更**：本免责声明可能随时更新，更新后自发布之日起生效，恕不另行通知。

### 关于复活已停止运营的网络游戏

本资料常被用于**已停止运营（停服 / 官方终止在线服务）**的网络游戏的存档保存、历史研究与本地化重开。就此类用途，特别声明如下：

- **「已停服」不等于「进入公有领域」**。该类游戏的代码、美术、商标、剧情、音频等知识产权仍归**原权利人**所有；停服**不等于**权利人放弃权利，也不构成对第三方运营的授权。
- 本资料仅支持**面向既有玩家社区或个人的非商业性研究、存档与延续**用途。**严禁**将其用于冒充官方、商业化牟利、发行收费服务，或损害原权利人及原玩家社区利益的行为。
- 复活、私服部署与运营所引发的一切**法律、经济与声誉风险，由使用者自行承担**；作者不参与具体项目、不提供背书、不承担任何责任。
- 若原权利人或其权利继承方提出异议，作者将**配合及时删除**相关资料。

---

## 法律风险提示（重要）

本仓库仅提供**通用的逆向方法论**，**不包含**任何具体游戏的服务端实现、破解工具或技术保护绕过方案。使用前请务必了解：

1. **私服 / 未授权运营**：未经著作权人许可，复制、架设并运营网络游戏服务端，可能构成**侵犯著作权罪**（《刑法》第二百一十七条；达到司法解释的违法所得 / 非法经营数额即入罪），且**刑民并行**（刑事 + 民事双重追责）。
2. **提供工具 / 技术支持**：为他人实施上述行为提供程序、工具或技术支持，可能构成**帮助信息网络犯罪活动罪**（《刑法》第二百八十七条之二）或**提供侵入、非法控制计算机信息系统程序、工具罪**（《刑法》第二百八十五条）。
3. **反规避技术措施**：绕过或提供绕过版权技术保护措施的方法，在**美国 DMCA §1201** 下可能被认定为违法，并导致仓库被 **DMCA 下架**（GitHub 对「规避」主张设有专门审查流程）。
4. **平台规则**：权利人可发起 DMCA 下架；GitHub 也可能因违反可接受使用政策处理本仓库。

**因此，本仓库明确禁止**：将本资料用于任何**未经授权**的游戏服务端架设 / 运营 / 牟利，制作或分发破解工具，或绕过、破坏他人的技术保护措施 / 完整性校验。违反者的一切后果自负。

---

## 开源协议

本项目以 GNU AGPL-3.0 发布（[LICENSE](./LICENSE)）

---

## 贡献者

<p>
  <a href="https://github.com/ShrugYu"><img src="https://github.com/ShrugYu.png?size=120" width="56" height="56" alt="ShrugYu" title="ShrugYu"></a>
  <a href="https://github.com/Qslzy"><img src="https://github.com/Qslzy.png?size=120" width="56" height="56" alt="Qslzy" title="Qslzy"></a>
  <a href="https://github.com/SakuraZuk"><img src="https://github.com/SakuraZuk.png?size=120" width="56" height="56" alt="SakuraZuk" title="SakuraZuk"></a>
</p>

- **ShrugYu** — 维护者
- **Qslzy** — 贡献者
- **SakuraZuk** — 贡献者

---

## 更新日志

完整变更历史见 [`game-client-to-server-reverse/README.md`](./game-client-to-server-reverse/README.md) 顶部。
当前版本 **v2.0**：原理层 + 四阶段路线 + 换服务端（重定向）+ 内联服务端路线。