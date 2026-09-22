# 实例 D：真实 Lua 客户端源码分析（横版动作手游）

> 注意: **这只是「一个」真实项目的分析记录，不是通用结论。**
> 目的是演示**方法**：拿到客户端源码后怎么系统性扒出接口清单。
> 换一个游戏，协议模式、opCode 形式、子系统划分**都可能完全不同**。

---

## 1. 项目概况

| 项 | 值 |
|----|----|
| 客户端 | Unity + **xLua**（Lua 承载业务逻辑） |
| 源码规模 | 2429 文件 / 2365 个 `.lua` |
| 协议文件 | `message/Lua_MessageUtil.lua`（**18573 行 / 632KB**） |
| 配置表 | `config/Cfg*`（92+ 张） |
| 反作弊 | ACE / FairGuard / 自研 + 文件校验 |
| 热更 | 遍地 `*Hotfix.lua` + HotfixManager |

---

## 2. 协议模式（本项目特有）

```
msg = GetMessage("LOGIN_INFO")      -- 1) 按 opCode 建信封
msg.request = { ... }               -- 2) 填请求体（字段随 opCode 而变）
SendMessage(msg, callback)          -- 3)
    ├─ protobuf.encode("GameMessage.Message", msg)   -- protobuf 序列化
    └─ NetworkingManager:SendMessage(bytes, msg.opCode, callback)  -- opCode 随帧发送
```

**特征总结**：
- **信封统一**：`GameMessage.Message`
- **opCode 是字符串**（`"LOGIN_INFO"` / `"COMBAT_START"`），不是数字
- **序列化 protobuf**（`pbc/protobuf.lua`）
- 另有 `json` / `msgpack` 库备用

> 对比：其它项目可能是 `数字 opCode + 自定义二进制`、`HTTP 路由 + JSON`、
> `KCP + protobuf`…… **必须自行判定**（见 `decision-tree.md`）。

---

## 3. 反推六步法（可复用）

```
1. 定位协议文件
   grep -rl "protobuf\|opCode\|SendMessage\|Socket" --include=*.lua | head
   → 本项目: message/Lua_MessageUtil.lua

2. 判定协议模式
   grep -n "protobuf.encode\|SendMessage(" 协议文件
   → 信封名 + opCode 形式 + 序列化方式

3. 扒出全部 opCode（接口总表）
   python3 tools/extract_interfaces.py <源码目录> --out interfaces.md
   → 本项目: 1794 个 opCode

4. 按前缀聚类 → 得到子系统划分
   EVENT(207) FAMILY(119) WORKSHOP(102) CHAR(67) PVP(58) TEAM(55) MATCH(44) …

5. 抽取请求字段（payload schema）
   看每个 Send 函数里 msg.request.xxx = 的赋值 → 得到该 opCode 的字段

6. 写进 Spec → 按子系统逐块实现
   protocol.spec.yaml 的 opcodes.table + messages
```

---

## 4. 实测产出

```bash
python3 tools/extract_interfaces.py ./lua_src --out interfaces.md --json interfaces.json
# 扫描文件: 2391
# 合计: opcode_str=1794, route=121, proto_msg=2
```

报告按前缀分组，直接可当**待实现清单**用。

---

## 5. 子系统清单（按 opCode 前缀）

| 子系统 | 前缀 | 数量 | 关键接口样例 |
|--------|------|------|-------------|
| **活动** | `EVENT_*` | 207 | `EVENT_BAGHERO_*` / `EVENT_BOSSRUSH_*` |
| **家族** | `FAMILY_*` | 119 | 家族 BOSS / 联赛 / 祭坛 |
| **工坊/自制** | `WORKSHOP_*` | 102 | `PUGC` 玩家自制关卡 |
| **角色** | `CHAR_*` | 67 | 培养 / 皮肤 / 天赋 |
| **PVP** | `PVP_*` | 58 | 排位 / 赛季 |
| **队伍** | `TEAM_*` | 55 | `TEAM_MATCH_*` 招募与匹配 |
| **匹配** | `MATCH_*` | 44 | `MATCH_ROOM_INFO` / `MATCH_ROUND_*` / `MATCH_SCORE_*` |
| **Boss** | `BOSS_*` | 36 | `TEAMBOSS_*` / `REWARD_BOSS_*` |
| **好友/组队房** | `FRIENDLY_*` | 25 | `FRIENDLY_3V3_{JOIN,READY,START,KICK,LEAVE,CHANGE_SIDE}` |
| **好友** | `FRIEND_*` | 15 | 好友增删查 |
| **黑名单** | `BLOCK_*` | 3 | `BLOCK_ADD/DELETE/GET` |
| **多人大乱斗** | `MULTICOMBAT_*` / `MULTI_BRAWL_*` | 14+ | 禁卡 / 房间 / 观战 |
| **战斗** | `COMBAT_*` | 13 | `COMBAT_START/FINISH/QUIT/REBORN/RELAY` |
| **充值** | `PAY_*` / `VIP_*` / `REBATE_*` | ~10 | `PAY_PACKAGE_GET_SHOP_LIST` / `PAY_LIMIT_STATISTICS` |
| **邮件** | `MAIL_*` | 3 | `MAIL_GET_LIST` / `MAIL_READ_MSG` / `MAIL_REMOVE_MSG` |
| **背包** | `BAG_*` | 8 | `BAG_GET_ITEM_LIST` / `BAG_OPEN_PACKAGE` / `BAG_ITEM_COMPOSE` |
| **抽卡** | `LOTTERY_*` | 10 | 保底 / 历史 / 选池 / 重复奖励 |
| 抽卡（其他池） | `WEAPON_LOTTERY_*` / `SKIN_LOTTERY` / `RUNELOTTERY` / `GACHAPON_*` / `STEP_GACHA_*` / `NOVICE_DRAW` | ~20 | 武器/皮肤/咒印/扭蛋/阶梯/新手池 |
| 抽卡（活动侧） | `DO_GASHAPON_LOTTERY` / `DO_LOTTERY_EVENT` / `ANNIVERSARY_*_LOTTERY` / `FAMILY_LOTTERY` | ~10 | 活动池、家族抽奖 |
| **掉落/奖励** | `QUEST_DROP` / `COMBAT_LOTTERY_*` / `REWARD_*` | ~29 | 掉落与战令 |
| **任务** | `QUEST_*` | 11 | `QUEST_GET_LIST` / `QUEST_DONE` |
| **防沉迷** | `ANTI_INDULGE_*` | 3 | 实名 / 绑定手机 |
| **反作弊** | `ACE_*` / `FG_SEND_ANTI_DATA` / `COMBAT_CLIENT_CHEAT_LOG` | ~10 | 上报 |
| **热更** | `CLIENT_HOTFIX` | 1 | 客户端热更 |
| **客户端存档** | `CLIENT_SAVE_*` | 4 | 设置类 |
| **心跳** | `NONE` | 1 | 空包保活 |
| **GM/QA** | `QACMD` | 1 | 服务端执行指令 |

---

## 6. 关键发现（对通用 skill 的启示）

### 6.1 注意: 「人机」可能根本没有协议

搜索 `robot|bot|npc|AI|dummy`：

```
GET_NPC_INFO / NPC_VOTE / SEND_NPC_GIFT / UP_NPC_SKIN …（都是社交/投票）
```

**没有任何"人机队友"的 opCode。**
→ 说明该游戏的战斗是 PVE / PVP，**不需要服务端人机**。
→ 印证 `extensions/README.md` 的判断：**人机是拓展，游戏本来没有就不用做**。

> 这是「[-] 游戏本身没有」的教科书案例：**不要凭空造需求**。

### 6.2 充值：客户端只"拉商品列表"，不碰支付

```
PAY_PACKAGE_GET_SHOP_LIST     -- 拉商品
PAY_LIMIT_STATISTICS          -- 限额统计
IOSNEWPAY_* / REBATE_*        -- 渠道与返利
```

真正的支付走 **SDK**，发货在服务端 → 与 `account.md` / §15 的私服支付设计一致。

### 6.2b 抽卡：客户端只有"概率展示"，没有掷骰 

**抽卡在本项目共 62 个接口，分散在多个族**：

```
LOTTERY_*                     主抽卡：SELECT_ROLE / SELECT_POOL_TYPE /
                              GUARANTEE_CHOOSE / HISTORY / GET_REPLICA_AWARD
WEAPON_LOTTERY_* / SKIN_LOTTERY / RUNELOTTERY / GACHAPON_*
STEP_GACHA_* / NOVICE_DRAW
DO_GASHAPON_LOTTERY / DO_LOTTERY_EVENT / ANNIVERSARY_*_LOTTERY / FAMILY_LOTTERY
COMBAT_LOTTERY_*              （战斗内的抽取玩法）
```

**关键验证**：在 `UI/Draw/` 里搜随机：

```bash
grep -rnE 'math.random|Mathf.Random|概率|probability' UI/Draw/
# 只命中：_getProbabilityColor / "SSR概率提升10%"  → 全是展示逻辑
```

→ **客户端没有任何掷骰**，抽卡**完全在服务端**。
→ 与 `references/gacha.md` 的「第一铁律」完全吻合。

**额外发现**：
- 有**多池类型**（`SELECT_POOL_TYPE`）
- 有**保底自选**（`GUARANTEE_CHOOSE` / `_CANCEL`）
- 有**重复转换**（`GET_REPLICA_AWARD`，重复角色换奖励）
- 有**抽卡历史**（`HISTORY` / `HISTORY_TOKEN`）

### 6.3 房间/匹配是「一族」接口

```
TEAMBOSS_NEW_ROOM / JOIN_ROOM / LEAVE_ROOM / READY / START / KICK / ROOM_INFO
FRIENDLY_3V3_JOIN / READY / START / KICK / LEAVE / CHANGE_SIDE
MATCH_ROOM_INFO / MATCH_ROUND_* / MATCH_SCORE_*
```
→ 与 §17「房间」设计的规则（槽位/准备/开始/踢人/房主）**完全吻合**，可互相印证。

### 6.4 反作弊是「独立上报通道」

```
COMBAT_CLIENT_CHEAT_LOG / ACE_SEND_ANTI_DATA / FG_SEND_ANTI_DATA
```
→ 客户端上报，**服务端裁决**。反推服务端时：
- 这些接口**可以接受上报但不裁决**（我们自己的服务端）
- 或**直接忽略**（私服不需要）

### 6.5 热更后门

遍地 `*Hotfix.lua` = 官方线上补丁机制。
→ 但**我们做的是服务端**，客户端的 Hotfix 与我们无关（除非要 patch 客户端）。

---

## 7. 对「反推服务端」的启示

| 发现 | 对服务端的行动 |
|------|---------------|
| 1794 个 opCode | 不可能一次做完全部；**按子系统分批**，先做能跑通主流程的 |
| 字符串 opCode | 服务端需建 `opCode → handler` 映射表（不是数字 switch） |
| protobuf 信封 | 需要 `.proto` 定义或按 `msg.request.xxx` 还原字段 |
| 有 `NONE` 心跳 | 必须先实现心跳应答，否则上线秒掉 |
| 有 `QACMD` | 服务端可保留但**不实现**（或只做调试用） |
| 有反作弊上报 | 可接收但**不裁决** |
| 无人机协议 | **不做人机**（游戏本身没有） |

---

## 8. 通用方法总结（这才是要带走的东西）

1. **先找协议文件**（一次 grep 就能定位）
2. **判协议模式**（信封 / opCode 形式 / 序列化）
3. **用工具扒接口总表**（`tools/extract_interfaces.py`）
4. **按前缀聚类 = 子系统划分**
5. **看请求字段 = payload schema**
6. **按子系统分批实现**，先主流程后周边
7. **不存在的东西不要造**（如本项目无人机协议）

> 换一个游戏：先跑第 1~4 步，你会得到**完全不同的**一份接口清单。
> 方法不变，结论必变。