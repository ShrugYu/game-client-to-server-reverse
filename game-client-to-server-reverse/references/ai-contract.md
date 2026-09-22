# AI 行为契约（本 skill 的强制产物与硬性规则）

> 本文件是 `SKILL.md §13` 的**完整版**。每次交付前过一遍。

---

## 13. 使用本 Skill 的 AI 行为契约（必读）

### 13.1 强制产物（缺一不可）

AI 处理任何项目，**必须按顺序产出**：
1. `out/project-profile.yaml`（读了什么 / 还缺什么）→ 2. `out/evidence-inventory.md`（证据编号 + 置信度）→ 3. `out/protocol.spec.yaml`（**唯一事实来源**）→ 4. 由 Spec 派生的服务端。

**另需落文件**（模板在 `templates/`）：
`TRACKER.md`（进度/接口清单）· `verify/log.md`（验证 + 回滚）· `docs/decisions/*.md`（ADR：决定了什么 / **当前不做的事** / 何时推进）· `docs/evidence/*.md`（端到端证据：帧序表 / 差异解释 / 重连快照）· `AGENTS.md`（工作区协作契约）· `docs/status/support-matrix.md`（三轴状态：实现 / 测试 / 客户端验收）· `login-chain.md`（登录链条）· `function-checklist.md`（功能清单）。

> ADR / 证据两项来自实机跑通范式：**「为什么先不做」和「怎么证明跑通了」必须落文件**。详见 `engineering-practices.md`。
>
> 结论段一律挂**证据档位**：`Confirmed by static analysis` /
> `Confirmed by packet capture or runtime observation` / `Inferred and still requiring validation`。
> 不确定的写 `Inferred`，不要写「已实现」。

> `TRACKER.md` 用简单状态标记：[x]已实现 / [~]部分 / [ ]未实现 / [?]未验证 / [-]游戏本身没有。
> **保持简短**，不要写长文，省 token。

> 没有 1~3 就写代码 = 违规。**先规格，后代码。**
>
> 另外：`project-profile.yaml` 的 `method` 段必须**在动手前填**（选了什么方法、为什么）。

### 13.2 硬性禁止

1. [x] 把参考实现（`server/`、`templates/`）的**默认协议常量**当作目标游戏的常量。
2. [x] 在没有任何证据时，直接给出"服务端应该长这样"。
3. [x] 忽略 `unresolved` 列表强行推进（要么标注假设，要么索要证据）。
4. [x] 只给口头结论、不落文件。
5. [x] 声称"已生成/已验证"但拿不出产物或路径。

### 13.3 缺信息时的正确做法

- **不追问、不空转**：用占位符推进（`TARGET_HOST`、`PORT`、`OPCODE`、`CHECK_FN`、`TODO_EVIDENCE`）。
- **主动给探测命令**：用户没说清项目类型时，先给出 `find`/`grep` 探测命令让用户跑。
- **把"还需要什么"写进 Spec 的 `unresolved`**，而不是凭空补全。

### 13.4 决策必须可追溯

每个结论都要能回答三问：
1. 这条结论的**证据编号**是什么？
2. 走的决策树**哪条分支**？
3. 置信度是**高/中/低**？低置信的验证计划是什么？

### 13.5 终点定义

**原版客户端连上自建服务端并跑通到某个状态 = 成功。**
跑通后，把 Spec 里对应项置信度回填为 `high`，并更新证据清单。

### 13.6 回滚

所有对客户端的改动，先在副本上做，保留原始哈希与还原命令。

---
