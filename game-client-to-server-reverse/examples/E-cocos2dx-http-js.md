# 示例 E：Cocos2d-x(JS) + 热更 + 多端口 HTTP + AES 自加密

> **注意：这是推演示例，不是通用结论。** 参考实现只提供"套路"，参数按你的项目定。
> 本示例取自一个真实项目（cocos2d-x + JSB JS 脚本 + AES 自加密 HTTP-RPC），关键结论可对照 `references/cocos2d.md`。

## 1. 用户给了什么
- 一个 APK（`libcocos2djs.so` + `libEncryptorP.so` + `assets/` 里的 `index.jsc` / `scripts*.jsc.js`）
- 解出的脚本（JS，几十万行，可 grep）
- 已经能跑起来的客户端 + 一份抓包（HTTP，请求体是 hex 密文）
- 目标：反推出能**正常进服**的服务端，并逐步还原背包/技能/商城/后台

## 2. 证据清单

```
[E01] lib/ 有 libcocos2djs.so + libEncryptorP.so，assets 有 index.jsc         高 → cocos2d-x JSB
[E02] 脚本里 HttpConst.XXX = "User.method"，sendRequest(常量, params, cb)     高 → HTTP-RPC，do 即方法名
[E03] 抓包：请求体 = 长 hex 串，乱码不可读                                    高 → 自加密（非明文 JSON）
[E04] libEncryptorP.so 内字符串含 AES / cbc / pkcs，常量 32B/16B hex           高 → AES-256-CBC + KEY/IV
[E05] 响应外壳 {"errorCode":0,"MsgData":"<hex>"}                             高 → 明文在 MsgData 里
[E06] 解出明文请求 {"mod":"User","do":"LoadGame","p":{...}}                  高 → 明文壳确定
[E07] 三个端口：选服 9898 / 业务 8002 / WS 9002                              高 → 端口族分工
[E08] 客户端脚本里 MessageCenter.on(HttpConst.XXX, cb)，cb 读响应字段         高 → 响应契约来源
[E09] 常量 GET_DUNGEON_INFO = "User.getCopyData\n"（尾部有换行）              高 → 服务端必须 strip
[E10] tables/*.json + lantab_zh.json，item.Name 是语言表 key                  高 → 文本需还原
[E11] project.manifest 存在                                                   中 → 有热更，注意资源来源
```

## 3. 逐层决策

| 层 | 树节点 | 结论 |
|----|--------|------|
| 引擎 | 有 `libcocos2djs.so` + `.jsc` | **cocos2d-x (JSB)** → 见 `cocos2d.md` |
| 传输 | 抓包是 HTTP（80/自定义端口），多端口 | **HTTP-RPC**（非 protobuf 长连接） |
| 封装 | HTTP body 即整个密文 | 无自定义长度头（`opcode_size=0`） |
| 加密 | hex 密文 + `libEncryptorP.so` 的 AES 常量 | **AES-256-CBC + Pkcs7，hex 传输** |
| 序列化 | 解密后是 `{"mod","do","p"}` | **JSON**，`do` 当 RPC 名 |
| 消息号 | `do` 字段 | 路由名（`LoadGame`/`GetMarketList`…） |
| 架构 | 多端口 HTTP + 轮询 + 一个 WS | 网关型，非长连接 |

> 关键判断：**它不是"游戏服务器协议"，而是"HTTP RPC + 整体加密"**。用 Unity/TCP 那套会走偏。

## 4. 产出 Spec 关键片段

```yaml
transport: {type: http, ports: {select: 9898, biz: 8002, ws: 9002}, tls: false, confidence: high, evidence: [E06,E07]}
frame: {mode: "http_body", opcode_size: 0, confidence: high}          # do 字段即 opcode
crypto:
  enabled: true
  algo: AES-256-CBC
  padding: pkcs7
  key: "<32B hex>"
  iv:  "<16B hex>"
  wire: hex
  response_wrapper: {errorCode: 0, payload_field: MsgData}
  evidence: [E03,E04,E05]
serialize: {format: json, plaintext_shape: {mod: User, do: <name>, p: {...}}, confidence: high, evidence: [E06]}
opcodes:
  source: client_js            # 从 HttpConst.XXX 抓
  note: "客户端常量可能含尾部 \\n，服务端入口必须 strip()"
  confidence: high
  evidence: [E02,E09]
state_machine:                 # 登录链（用"下一条请求"夹逼）
  - {state: SELECT_SERVER, on: [ChooseServer], next: LOGIN}
  - {state: LOGIN,         on: [quicklogin],   next: LOAD}
  - {state: LOAD,          on: [LoadGame],     next: IN_GAME}   # 失败则退回重试
  - {state: IN_GAME,       on: [GetChatAddress], next: IN_SCENE}
client:
  index:                       # 函数名 -> 文件:行号（排障全靠它）
    - {fn: LoginMgr.loadGame,        loc: "scripts__index.jsc.js:66510"}
    - {fn: SaveDataMgr.updatePlayerData, loc: "scripts__index.jsc.js:106692"}
    - {fn: InventoryModel.parseEqData,   loc: "scripts__index.jsc.js:61238"}
data:
  tables: "tables/*.json"
  l10n:   "lantab_zh.json"     # item.Name / Description 是 key
```

## 5. 参考实现要改哪里

| 位置 | 改动 |
|------|------|
| `net/server.py` | **不用 TCP 长连接** → 起 **HTTP 服务**（aiohttp/Flask），按端口族起多个 listener |
| `net/codec.py` | 换成 **AES-CBC 加解密 + hex**；响应包成 `{"errorCode":0,"MsgData":...}` |
| `net/dispatcher.py` | 用 `do`（**先 strip**）当路由名分派；`mod` 通常恒 `"User"` |
| `proto/opcodes.py` | 换成 **路由表**：`{"loadgame": handler, "getmarketlist": handler, ...}` |
| `logic/handlers/` | 每个 `do` 一个 handler，**只喂客户端回调会读的字段**，默认 `eRet:1` |
| 存档 | 按 `userAccount` **分桶**（物品/技能/装备），避免串号 |
| `server/` 参考实现 | 会话/战斗/广播/心跳基本用不上，**只借它的分层思路** |

**技术栈建议**：Python **aiohttp** 或 **FastAPI**；自测直接 `import` 服务端模块造/解包。

## 6. 闭环验证路径

```
部署 HTTP-RPC 服务端（先回最小 eRet:1）
→ 服务端日志记录客户端发的每个 do
→ 逐 do：找到它的回调 → 补回调要读的字段
→ 真机跑：登录 → 选服 → 进服
    验收标准 = 客户端发出【下一条请求】（如 LoadGame 后出现 GetChatAddress），不是"服务端返回 200"
→ 进服后再补：背包/技能/商城/后台
→ 强制停止 + 重启 + 重连，确认状态仍在
```

**真机 vs 自测必须分开看**：
```
grep 'Dalvik' server.log            # 真机
grep 'Python-urllib' server.log     # 自测（只证明服务端没崩）
```

## 7. 坑与回退

| 坑 | 现象 | 回退/处置 |
|----|------|-----------|
| `do` 带 `\n` | 某接口永不匹配 | 入口 `strip()` |
| **自测全绿、真机进不去** | 自测过了但进服转圈 | 自测≠真机；以"下一条请求"为验收 |
| **一次改太多** | 崩了无法定位，只能整体回滚 | **最小增量、一次一变量**；保留"最后一次可进服"基线 |
| 字段类型错 | 回调 `.indexOf/.length/.split` 抛异常 | 回回调里核对期望类型（`equipLocks` 要数组不是对象） |
| 回滚不彻底 | 删了几个 key 仍崩 | **整文件对齐基线**，而不是只删字段 |
| 配置表是数字 | 名称显示为数字 | `lantab_zh` 还原 |
| 角色串号 | 技能/物品跨角色 | 按账号分桶 |
| 大文件拖死会话/打包 | 复制/压缩卡住 | 排除 100M+ 的 `.so`、APK |
| WS 心跳 ID 猜错 | 聊天 30~80s 必断重连 | 从 APK 解 `protoidmap` 逐号实证（本项目 5288=Pong，非 5279） |
| 登录回包带事件 | 进服即崩、无报错循环 | LoadGame 只放数据；事件（eco 等）放战斗结算 |
| 伪物品入背包 | 后台发经验后进不去 | 4001/4002/4003 按属性路由，LoadGame 过滤 itemObj |
| 穿戴契约猜错 | 装备穿上打怪空手、重登被脱 | 从 REQ 日志反推真实字段（EquipmentType+itemID） |

> 回退锚点：**"最后一次真实可进服"的服务端版本**（连同它的**回包大小**一起记）。
> 本项目基线 ≈ 2200B；加了一堆新字段后到 2944B → 真机崩。大小变化本身就是报警信号。

## 8. 进服之后：Live 运营阶段（本项目 v28~v33 实录）

> 进服 ≈ 项目完成 30%。下面是"能进"到"能长期玩"的实跑经验，机制细节见 `cocos2d.md §H2`。

### 8.1 子系统补全的优先级（按玩家投诉频率排序）

```
1. 任务系统(主线卡死=玩家流失) → 2. 装备穿戴一致性 → 3. 商店购买(多套契约!)
→ 4. 武学修炼闭环(饥饿→练功→结算) → 5. 好友/查看玩家 → 6. 排行榜
→ 7. 副本 → 8. 打坐/治疗 → 9. 坐骑 → 10. 称号
```

### 8.2 本项目踩出的三条通用规律

1. **每个"没效果"的接口，一半概率是字段名/契约错**，不是逻辑没写。
   例：穿戴等 `equipments` 字典（客户端从不发）→ 实际发 `{EquipmentType, itemID}`；
   打坐回包缺 `beginTime` → 客户端计时器不启动。
   **第一动作永远是 grep 客户端发送端代码，而不是改服务端逻辑。**

2. **note 双层包裹 + 绝对值**是 UI 刷新的开关（见 cocos2d.md §H2.1）。
   服务端数据对了但客户端"看不见变化"，九成是缺包裹或发了增量。

3. **客户端本地有状态**（localStorage 的任务史/聊天记录），
   服务端下发"空"或"部分"都会**覆盖**它——要么更全才发，要么省略键。
   客户端请求里的 count 型 flag（taskFlag/finishTaskFlag）就是它告诉你"我有多少"。

### 8.3 长线运营的自愈设计

- **LoadGame 自愈**：每次登录对账（任务物品缺→补、幽灵装备→剔、毒化血量→修、伪物品→滤），
  任何历史脏数据在玩家下次登录时自动修复，无需人工
- **接发收闭环**：剧情物品接任务发、交任务收、登录对账补——三层兜底后该类工单归零
- **后台=运维工具**：强推完成任务/直设货币经验/装备走实例，线上问题分钟级闭环

### 8.4 验收口径的变化

进服后的验收不再是"下一条请求"，而是**玩家可感知的正确性**：
穿剑→战斗实体带剑系武功；买A→背包到账A且扣款对；练功结束→等级+1 且 UI 即刷。
配合双账号用例（A 的操作不影响 B）+ 重登一致性（重登后状态不变）。

### 8.5 后续迭代补充（v34 实录 → 已抽象进 live-ops.md）

- **金条商城双发冲突**（"弹窗对物品不对"的终局根因）：客户端 onPaySuccess 用本地 mall 表自加货，
  服务端又按自己表发一份并用 note 绝对值覆盖 → 两表版本不同即表现为买A到B。
  修复=服务端只扣钱，货物客户端自加（读回调确认加货方是关键一步）。
- **回血卡旧上限**：客户端 useItem 上报的 maxhpLimit 是本地缓存(510)，服务端当权威值用
  → 高属性号(真实上限10224)永远回不满还把存档上限打回去。修复=上限以存档为准。
- **键名拼写**：注册 getalchemytdata(多t) vs 真名 getAlchemyData → 整个接口落保底桶。
- **化妆镜/时装持久化**：BeginTitivate{itemObj} → makeup 桶；LoadGame 下发 titivateObj。
