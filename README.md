<p align="center">
  <b>简体中文</b> · <a href="./README.en.md">English</a>
</p>

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://shieldcn.dev/header/grid.svg?title=Game+Client+%E2%86%92+Offline+Localization&subtitle=From+a+client-only+game+to+a+locally+runnable+client&mode=dark&align=center">
    <img alt="Game Client → Offline Localization" src="https://shieldcn.dev/header/grid.svg?title=Game+Client+%E2%86%92+Offline+Localization&subtitle=From+a+client-only+game+to+a+locally+runnable+client&mode=light&align=center">
  </picture>
</p>

<p align="center">
  <a href="https://github.com/ShrugYu/game-client-to-server-reverse"><img alt="GitHub stars" src="https://shieldcn.dev/github/stars/ShrugYu/game-client-to-server-reverse.svg?variant=secondary&v=3"></a>
  <a href="https://github.com/ShrugYu/game-client-to-server-reverse/blob/main/LICENSE"><img alt="License" src="https://shieldcn.dev/github/license/ShrugYu/game-client-to-server-reverse.svg?variant=secondary&v=3"></a>
  <a href="https://github.com/ShrugYu/game-client-to-server-reverse/commits/main"><img alt="Last commit" src="https://shieldcn.dev/github/last-commit/ShrugYu/game-client-to-server-reverse.svg?variant=secondary&v=3"></a>
  <a href="https://github.com/ShrugYu/game-client-to-server-reverse/graphs/contributors"><img alt="Contributors" src="https://shieldcn.dev/github/contributors/ShrugYu/game-client-to-server-reverse.svg?variant=secondary&v=3"></a>
  <a href="https://github.com/ShrugYu/game-client-to-server-reverse/forks"><img alt="Forks" src="https://shieldcn.dev/github/forks/ShrugYu/game-client-to-server-reverse.svg?variant=secondary&v=3"></a>
</p>

# 游戏客户端 → 离线本地化 Skill

> 把「只有客户端」的游戏，还原出「服务端协议 + 可用服务端」，并让**原版客户端成功本地离线运行**。
>
> 说明：本 skill **暂无实战测试**，内容系根据开源的 GitHub 相关项目与现有知识库提炼、结合而成。


这是一个遵循 [Agent Skills](https://agentskills.io) 规范的 skill 包。核心 skill 名为 `game-client-to-server-reverse`，
由一份导航主文档 `SKILL.md` + 37 篇 `references/` 正文 + `templates/` 模板 + `tools/` 脚本 + 可运行的 `server/` 参考实现组成。

---

## 这是什么

| 维度 | 说明 |
|------|------|
| **定位** | 根据游戏客户端反推服务端协议，复现出能**本地离线运行**的客户端 |
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
- **配套界面模板**：`templates/register-site/`（注册网站）。

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

### AI 阅读顺序

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
    ├── templates/                   文档与代码模板（注册站、ADR、e2e 证据…）
    ├── tools/                       extract_interfaces.py / repack_zip.py
    ├── examples/                    不同游戏类型的推演示例
    ├── extensions/                  可选拓展（服务端人机 / 反推人机机制）
    └── server/                      参考实现：长连接二进制协议服务端（Python）
```

---

## 依赖与致谢

本 skill 的方法论与工具链参考 / 使用了以下开源项目。感谢各自的作者与维护者（**仅列有公开仓库者**）：


| 项目 | 用途 | 仓库 |
|------|------|------|
| Il2CppDumper | Unity IL2CPP metadata 提取 | https://github.com/Perfare/Il2CppDumper |
| Il2CppInspector | Unity IL2CPP 分析 | https://github.com/djkaty/Il2CppInspector |
| dnSpy | .NET / Unity Mono 反编译调试 | https://github.com/dnSpyEx/dnSpy |
| ILSpy | .NET 反编译 | https://github.com/icsharpcode/ILSpy |
| unluac | Lua 字节码反编译 | https://github.com/HansWessels/unluac |
| luadec | Lua 反编译 | https://github.com/viruscamp/luadec |
| Ghidra | 反汇编 / 反编译 | https://github.com/NationalSecurityAgency/ghidra |
| jadx | Android dex → Java | https://github.com/skylot/jadx |
| Apktool | APK 解包 / 重打包 | https://github.com/iBotPeaches/Apktool |
| binwalk | 固件 / 容器分析 | https://github.com/ReFirmLabs/binwalk |

### 虚幻引擎（UE）资源 / SDK

| 项目 | 用途 | 仓库 |
|------|------|------|
| FModel | UE 资源浏览 / 导出 | https://github.com/4sval/FModel |
| Dumper-7 | UE SDK dump | https://github.com/Encryqed/Dumper-7 |
| UE4SS | UE 脚本 / SDK | https://github.com/UE4SS-RE/RE-UE4SS |
| UnrealMappingsDumper | 生成 .usmap 映射 | https://github.com/TheNaeem/UnrealMappingsDumper |
| AESKeyFinder | 定位 UE AES 密钥 | https://github.com/GHFear/AESKeyFinder-By-GHFear |


| 项目 | 用途 | 仓库 |
|------|------|------|
| Frida | 动态插桩 | https://github.com/frida/frida |
| x64dbg | Windows 调试器 | https://github.com/x64dbg/x64dbg |
| LSPosed | Xposed 框架（root） | https://github.com/LSPosed/LSPosed |
| LSPatch | 免 root 的 Xposed（补丁式） | https://github.com/LSPosed/LSPatch |
| NPatch | 免 root 的 Xposed（复刻 LSPatch） | https://github.com/7723mod/NPatch |
| VirtualXposed | 免 root 的 Xposed（虚拟容器） | https://github.com/android-hacker/VirtualXposed |
| TaiChi（太极） | 免 root / 免解锁的 Xposed | https://github.com/taichi-framework |


| 项目 | 用途 | 仓库 |
|------|------|------|
| mitmproxy | HTTPS 抓包 / 中间人 | https://github.com/mitmproxy/mitmproxy |
| Wireshark | 网络协议分析 | https://github.com/wireshark/wireshark |
| tcpdump | 命令行抓包 | https://github.com/the-tcpdump-group/tcpdump |
| Protocol Buffers（protoc） | protobuf 编解码 | https://github.com/protocolbuffers/protobuf |
| KCP | 可靠 UDP 传输 | https://github.com/skywind3000/kcp |
| zlib | 数据压缩 | https://github.com/madler/zlib |


| 项目 | 用途 | 仓库 |
|------|------|------|
| Flask | 参考服务端 Web | https://github.com/pallets/flask |
| PyYAML | 配置解析 | https://github.com/yaml/pyyaml |
| aiosqlite | 异步 SQLite | https://github.com/omnilib/aiosqlite |
| Termux | Android 上的 Linux 环境 | https://github.com/termux/termux-app |
| proot | 无需 root 的 Linux 容器 | https://github.com/proot-me/proot |
| Docker | 容器化部署 | https://github.com/docker |
| systemd | Linux 服务常驻 | https://github.com/systemd/systemd |


| 项目 | 语言 | 仓库 |
|------|------|------|
| Skynet | C / Lua | https://github.com/cloudwu/skynet |
| Pomelo | Node.js | https://github.com/NetEase/pomelo |
| KBEngine | C++ | https://github.com/kbengine/kbengine |
| NoahGameFrame | C++ | https://github.com/ketoo/NoahGameFrame |

### 服务端参考实现来源

| 项目 | 说明 | 仓库 |
|------|------|------|
| peach-haven | 本地兼容服务端 + 客户端补丁工具链（Python：HTTP SDK + AsyncIO TCP）；本 skill `server/` 的实现参考 | https://github.com/Nanako660/peach-haven |
| BlueRebirth | 已停运手游的本地离线复原工程（C#/.NET 本地服务端 + Mod 环境） | https://github.com/LunarConcerto/BlueRebirth |
| enigma | 卡牌游戏的服务端（Rust） | https://github.com/yoncodes/enigma |
| MikuSB | 本地协议与网络实验的开源 C#/.NET 服务端模拟器 | https://github.com/MikuLeaks/MikuSB |
| kairisei-ma-ch | 某已停服卡牌手游国服的社区保存与本地运行项目（Go：自托管服务端 + 协议适配 + 客户端构建） | https://github.com/kuuhaku1314/kairisei-ma-ch |
| kamihama-server | 卡牌游戏的服务端（Rust） | https://github.com/rayshift/kamihama-server |
| startpoint-cn | 某弹射手游国服的非官方服务端实现（Node.js：API / 联机 / CDN 归档） | https://github.com/DontBeAlarmed/startpoint-cn |

> 说明：以上为方法论中提及 / 参考的开源项目；本仓库**不打包、不分发**它们，使用请遵循各自许可证。

---

## 免责声明

> 使用本资料库skill即表示你已阅读、理解并同意以下全部条款；若不同意，请立即停止使用。

1. **用途限定**：本 skill 资料仅供**学习、研究与技术交流**，以及针对**自研、已获授权或离线单机**游戏的互操作性研究与本地化部署。这是一份**方法论文档**，不针对任何特定特定项目。

2. **禁止非法用途**：严禁将本资料用于任何**未经授权**的入侵、攻击、破坏、篡改、绕过安全机制、窃取数据，或侵犯他人知识产权、违反目标游戏服务条款及所在地法律法规的行为。

3. **无担保**：本资料按"**现状**（as-is）"提供，不附带任何明示或暗示的担保，包括但不限于适销性、特定用途适用性与不侵权担保。作者不保证其准确性、完整性或可用性。

4. **责任限制**：在适用法律允许的最大范围内，作者及贡献者**不对因使用或无法使用本资料而产生的任何直接、间接、附带、特殊、惩戒性或后果性损失承担责任**（包括但不限于数据丢失、设备损坏、ai平台账号封禁及法律纠纷）。

5. **使用者自负其责**：使用者须**自行确保**其使用行为合法合规（含取得必要授权），并**独立承担由此产生的全部法律责任与后果**。

6. **第三方内容**：本资料引用或链接的第三方项目、代码、工具、文档及服务，其版权与许可归各自所有者所有；使用前请自行查阅并遵守其各自条款。作者不对第三方内容及其后果负责。

7. **权利主张**：若你是某作品的权利人，并认为本资料侵犯了你的合法权益，请通过仓库 Issue 联系，作者将在核实后**及时更正或删除**。

8. **平台规则**：权利人可发起 DMCA 下架；GitHub 会因违反可接受使用政策处理本仓库。

9. **AI 平台安全提示与账号责任**：本 skill 涉及逆向 / 协议分析等**可能触发 AI 平台安全规则**的内容。使用本 skill 时，你接入的 AI 服务（如 GPT / Codex / Claude 等）**可能因你的提示词内容性质触发安全提示、限制响应，甚至导致你的 AI 账号被限制或封禁**。**本 skill 作者不对任何 AI 平台对你账号采取的任何措施负责**，包括但不限于警告、降级、限制或封禁。使用前请充分了解你所使用的 AI 平台的服务条款与安全策略，并自行承担相应风险。

10. **条款变更**：本免责声明可能随时更新，更新后自发布之日起生效，恕不另行通知。

### 关于复活已停止运营的网络游戏的说明

本资料常被用于**已停止运营（停服 / 官方终止在线服务）**的网络游戏的存档保存、历史研究与本地化重开。就此类用途，特别声明如下：

- **「已停服」不等于「进入公有领域」**。该类游戏的代码、美术、商标、剧情、音频等知识产权仍归**原权利人**所有；停服**不等于**权利人放弃权利，也不构成对第三方运营的授权。
- 本资料仅支持**面向既有玩家社区或个人的非商业性研究、存档与延续**用途。**严禁**将其用于冒充官方、商业化牟利、发行收费服务，或损害原权利人及原玩家社区利益的行为。
- AI 生成内容所涉及的复活、部署与运营所引发的一切**法律、经济与声誉风险，由使用者自行承担**；作者不参与项目、不提供背书、不承担任何责任。
- 若原权利人或其权利继承方提出异议，作者将**配合删除本仓库**相关资料。

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
当前版本 **v2.0**：原理层 + 四阶段路线 + 重定向 + 内联路线。
