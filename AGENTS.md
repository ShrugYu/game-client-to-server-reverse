# AGENTS.md —— 维护本 skill 的契约与守则

> 本文件是**给 AI 的单一契约**：在**本工作区**里「更新 skill」时——**该放哪、怎么接入、各客户端怎么装、
> 必须/禁止做什么**。（契约与守则**合并于此**，不再拆成两份文件。）
>
> **注意**：这**不是** `game-client-to-server-reverse/templates/AGENTS.md` ——
> 那个是**放进"被反推的游戏项目"**里的协作契约（给逆向作业用），用途不同，别混淆。
>
> **权威来源**（冲突以官方为准，见 §12 完整清单）。

---

## 1. 你的角色与范围

- 你在**维护一个 Agent Skill（`game-client-to-server-reverse/`）**，**不是**在给某个游戏写服务端。
- **一个文件夹 = 一个 skill**：skill 本体就是 `game-client-to-server-reverse/`。
- 产出 = 对它的**内容增改**；改完必须**仍然符合 Agent Skills 标准（agentskills.io）**。

## 2. 工作区边界

```
[可改] 服务端反推skill_2.0/game-client-to-server-reverse/**     （skill 本体）
[可改] 服务端反推skill_2.0/AGENTS.md                            （本契约；维护用）
[不动] 工作区外的任何目录（含 ../服务端反推skill_1.8、1.9），除非用户点名
[禁止] 在工作区/仓库根新增第二份 SKILL.md 或第二份 AGENTS.md
```

---

## 3. 完善内容放在哪 · 如何接入（核心）

> 规范约定目录为 `scripts/` `references/` `assets/`；本 skill 的**映射**见 skill `README.md`"目录映射"：
> `tools/ → scripts/`；`templates/` + `schema/` + `server/ → assets/`。
>
> **总原则：能改现有文件就不新增；新增必须"可发现（被引用）+ 写明何时读/怎么用"，否则等于不存在。**

| 你要加的东西 | 放哪个文件夹 | 如何"接入"（让 agent 找得到） |
|--------------|--------------|-------------------------------|
| 原理 / 方法论 / 流程 / 参考文档 | `references/` | 在 `SKILL.md §0.5 参考表` **和** `references/reading-path.md` 各加一行，**写清"何时读"** |
| 可执行脚本 / 工具 | `tools/` | 在 SKILL `§12 工具速查` 或对应 reference 引用；脚本内写清**依赖与用法** |
| 成品界面 / 模板 / 资产 | `templates/` | 该目录内加 `README.md` 写**用法**；再从相关 reference 加指针 |
| 中间产物模板（Spec / 档案） | `schema/` | 在 `protocol-spec.md` / `adaptation.md` 里引用 |
| 参考实现代码 | `server/` | 在 SKILL `§7` 或 `codegen.md` 里引用 |
| 端到端示例 | `examples/` | 在 `examples/README.md` + SKILL `§18` 引用 |
| 可选 / 外围拓展 | `extensions/` | 在 `extensions/README.md` + SKILL `§19` 引用 |

**接入三问**（新增前自问）：①**它被谁引用？** ②**"何时读/怎么用"写清了吗？** ③**会不会让 `SKILL.md` 超 500 行？**（会 → 先下沉到 `references/` 再留「标题 + 指针」）

---

## 4. 跨平台适配（各客户端怎么"装"这个 skill）

> 一个 skill 要**到处能用**，就**只依赖标准字段**；用客户端扩展字段会**降低可移植性**（要用就把影响写清）。

| 客户端 | 放置目录 | 识别 / 调用 | 备注 |
|--------|----------|-------------|------|
| **通用标准**（可移植核心） | 任意含 `SKILL.md` 的文件夹 | 读 `name` + `description` 决定是否加载 | **只靠标准字段 → 到处可用**；本 skill 即按此维护 |
| **Claude Code** | `.claude/skills/<name>/SKILL.md`（或 `.claude/commands/<name>.md`） | `/name` 调用；可被自动加载 | 支持扩展字段（调用控制 / 子代理 / 动态注入）；**扩展字段非标准** |
| **Codex CLI** | `.agents/skills/<name>/SKILL.md` | 客户端扫描加载 | 与 Claude Code 目录约定不同，**别混放** |
| **Operit** | `/sdcard/Download/Operit/skills/<name>/SKILL.md`（`skill.md` 也认） | 包管理 > Skills；**列表读 `name`/`description`**；有"可见性开关" | 支持**仓库 / ZIP / 商店**导入；**无 frontmatter 时**也会读文件头 `name:`/`description:` |

**打包与命名（通用）**：
- **ZIP 内必须能找到 `SKILL.md`**（允许在子目录）；**同名 skill 会被拒绝导入** → **改名 = 必须同步 frontmatter `name`**。
- 目录名建议**直接等于 `name`**（slug），避免各客户端识别不一致。

---

## 5. 硬约束（违反 = 不合规，禁止交付）

| # | 约束 |
|---|------|
| 1 | frontmatter `name` **== 父目录名**；仅小写字母/数字/连字符，1–64 字符 |
| 2 | `description` **≤1024 字符**，必须同时说清「做什么」和「何时用」 |
| 3 | 顶层字段**只允许** `name / description / license / compatibility / metadata / allowed-tools`（`version`/`platforms` 一律放进 `metadata:`） |
| 4 | `SKILL.md` **< 500 行**（超了先下沉到 `references/`，再留「标题 + 指针」，**保留标题与编号**） |
| 5 | 引用**一层深**；`references/` 单文件 **> 300 行需加 ToC** |
| 6 | **无 emoji**；**保持逆向视角**（写"反推、让游戏跑起来"，**不是**"服务端开发教程"） |
| 7 | **只用标准 frontmatter 字段**；确需扩展字段（如 Claude Code 的调用控制）→ 在 README 注明"非标准、影响可移植性" |

---

## 6. 写作规范

**来自 Agent Skills Best practices（Anthropic）**
- **简洁优先**：`SKILL.md` 与对话历史抢上下文。每段自问"**没有它，agent 会做错吗？**"不会就删。
  （正面例子：直接给 `pip` 命令；反面例子：先解释"PDF 是什么"。）
- **自由度校准**：**脆弱/需一致**的操作 → **写死命令**（低自由度）；**多路径皆可** → 讲清"为什么"让模型判断（高自由度）。
- **在多模型上测试**：一个 skill 会在不同模型上跑（Claude Haiku/Sonnet/Opus、GLM、DeepSeek…）。**要在你打算用的所有模型上都验证**（写成模型无关、显式、少歧义）。
- **按需加载写清"何时读"**；**description 用祈使句**、可略"pushy"。

**来自 Claude Code / SkillsMP**
- Skills 与 **MCP** 分工不同：**Skill=知识/流程；MCP=外部功能**。别把"接外部服务"塞进 skill。
- 何时用 skill：**重复任务 / 需一致流程 / 公司或项目专属规范**；一次性小事**不必**写 skill。

## 7. 本项目额外约定

- **全库不用 emoji**（标题/正文/注释都一样）。
- **保持逆向视角**；中文为主，命令/代码/字段名可英文。
- **术语一致**：沿用现有用词（Spec / opcode / wire-level / 闭环 / 补包循环 / 重定向四层表…），不另造同义词。

---

## 8. 更新流程（照做）

```
1) 读：本 AGENTS.md + references/reading-path.md + SKILL.md §0
2) 定性：本次改【内容】还是【结构】还是【元数据】
3) 定位：按 §3 选好"放哪 + 如何接入"；按 §4 确认跨平台可用性；优先改【已有文件】
4) 若 SKILL.md 将 > 500 行 → 先下沉到 references/ 再加指针（保留标题/编号）
5) 同步：改了清单/结构 → 同步 README 目录树、篇数、变更记录（TRACKER.md）
6) 跑 §9 自检；全过再交付
```

## 9. 提交前自检（必须全过）

```
[ ] name == 父目录名；只含小写字母/数字/连字符
[ ] description ≤ 1024 字符，且含"何时用"
[ ] 顶层字段只有：name / description / license / compatibility / metadata / allowed-tools
[ ] SKILL.md < 500 行
[ ] 引用的每个 references/*.md 都真实存在（无死链）
[ ] 新增内容已"接入"（被 SKILL / reading-path 引用，并写明何时读/怎么用）
[ ] > 300 行的 ref 有 ToC
[ ] 无 emoji；术语一致
[ ] 只用标准字段（若用扩展字段已在 README 注明）
[ ] 工作区/仓库根没有第二份 SKILL.md / AGENTS.md
```

自检脚本（在 skill 文件夹内跑）：

```bash
cd game-client-to-server-reverse
python3 - <<'PY'
import re, os
t = open("SKILL.md", encoding="utf-8").read()
fm = re.match(r"---\n(.*?)\n---", t, re.S).group(1)
name = re.search(r"^name:\s*(\S+)", fm, re.M).group(1)
desc = re.search(r"^description:\s*(.*)$", fm, re.M).group(1)
dirn = os.path.basename(os.getcwd())
print("name =", name, "| 目录 =", dirn)
print("name 合法 =", bool(re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", name)), "| == 目录 =", name == dirn)
print("description 长度 =", len(desc), "(<=1024)")
print("SKILL.md 行数 =", len(t.split(chr(10))), "(目标 <500)")
print("顶层字段 =", [l.split(":")[0] for l in fm.split("\n") if l and not l.startswith(" ")])
miss = [m for m in set(re.findall(r"references/[A-Za-z0-9_.\-]+\.md", t)) if not os.path.exists(m)]
print("死链 =", miss or "无")
PY
```

---

## 10. 禁止事项

- 不确认就**大规模重构**（改目录名、删/合并大量文件、重写主干）。
- 把**参考实现（server/、templates/）的默认值**当成目标游戏的答案写进 skill。
- 引入 **emoji / corporate 空话 / 与现有术语冲突的新词**。
- **删除被引用的文件**（删前必须先改掉所有引用）。
- 交付**没跑自检**的改动。
- 让 `SKILL.md` **超过 500 行**、或让 `name` 与目录名**不一致**。
- 在工作区/仓库根**留下第二份 SKILL.md / AGENTS.md**（会让加载器 / 契约识别出错）。

## 11. 失败 / 不确定时

```
- 拿不准 → 只改【最小必要范围】，把疑问写进交付说明，请用户拍板。
- 自检不过 → 改到过；改不动 → 回滚到改动前的版本（保留备份）。
- 涉及工作区外文件 / 无法判断影响面 → 先问，不要擅自动手。
```

## 12. 权威来源（写/改 skill 时以这些为准）

| 来源 | 讲什么 |
|------|--------|
| https://agentskills.io/specification | 格式规范（frontmatter / 目录 / 渐进式披露） |
| https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices | Anthropic 官方《Skill authoring best practices》 |
| https://code.claude.com/docs/en/skills | Claude Code 的 skill 目录 / 调用 / 扩展字段 |
| developers.openai.com/codex/skills（Codex CLI） | Codex 的 `.agents/skills/<name>/SKILL.md` 约定 |
| https://github.com/AAswordman/OperitWeb/.../skill.md | **Operit** 的 skill 放置路径与导入方式 |
| https://skillsmp.com/docs | Skills vs MCP、跨工具（Claude Code / Codex / ChatGPT）对照 |
| https://github.com/agentskills/agentskills | 规范的 GitHub 仓库（可提 issue/PR） |
| https://github.com/anthropics/skills · skills/skill-creator | 官方模板与"写→测→改"流程 |

---

## 13. 一句话

> 你是这个 skill 的**维护者**：**按 §3 放对位置并"接入"、按 §4 保证跨平台可用 → 能改现有就不新增 →
> 每次改动都合规（§5）+ 自检（§9）+ 同步清单**；
> 目标是让 skill **始终符合 Agent Skills 标准**，且内容始终**聚焦"从客户端反推服务端"。**