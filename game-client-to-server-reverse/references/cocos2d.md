# Cocos2d-x / Cocos Creator 分支深潜（JS / Lua 热更 + 自加密 HTTP）

> 适用：`libcocos2d*.so`（cocos2d-x 原生）或 Cocos Creator（`assets/` + `src/`）客户端。
> 特征：**业务逻辑大量在 JS/Lua 脚本层**，且脚本常被**编译/加密**；协议常见 **HTTP-RPC + 自加密**（不是 protobuf 长连接）。
> 本文件解决三件事：**① 脚本怎么解包/读；② 网络与加密怎么定位；③ 用它反推服务端怎么最快。**

---

## A. 判定与形态

```
APK 解压看 lib/ 与 assets/
  libcocos2djs.so + assets/src/*.js 或 index.jsc     → cocos2d-x (JSBinding, JS 业务)
  libcocos2dlua.so + assets/src/*.lua               → cocos2d-x (LuaBinding, Lua 业务)
  libcocos2d.so  + assets/ 下 cocos 资源            → cocos2d-x 老版本
  cocos creator: assets/ + settings + src/ + *.jsc   → Cocos Creator (2.x/3.x)
  另有 libEncryptor*.so / libgame.so                 → 业务/加密在原生层（重点看它）
```

| 线索 | 结论 | 主工具 |
|------|------|--------|
| `libcocos2djs.so` + `index.jsc` | cocos2d-x JSB，脚本编译成 `.jsc` | 解 jsc（见 B） |
| `assets/src/**/*.lua` | cocos2d-x LuaBinding | unluac/luadec |
| `jsb-builtin.js` / `jsb-engine.js` | JSB 运行时绑定层 | 直接读源码定位原生桥 |
| `project.manifest` / `version.manifest` | **热更**存在，资源可能不来自包内 | 见 G |
| `libEncryptorP.so` / `libcocos2djs.so` 内 `AES` 字符串 | 自加密协议 | IDA/Ghidra + 动态 |

> 注意: 关键区分：cocos2d-x 的资源**可能走热更下载**，包里那份只是初始版本。
> "改包后无效" 十有八九是**改的包内旧资源，客户端却加载了热更的新资源**（见 G）。

---

## B. 脚本层解包（这是 cocos 分支的核心）

### B1. JSB 脚本 bundle
- cocos2d-x 把 JS 编成 `.jsc`（本质是 **xxtea 加密 + JSC 编译**），cocos creator 更常见 `index.jsc` + `assets/**/*.jsc`。
- 判定：`.jsc` 头通常是 `XXTEA`（creator 默认）或自定义 magic。
- 解包思路：
```bash
# 1) 在 libcocos2djs.so / libcocos2dlua.so 里找 xxtea key 与解密入口
strings -a libcocos2djs.so | grep -iE 'xxtea|decrypt|jsc|signature'
# 2) 常见 key 来源：硬编码常量 / "xxtea key" / 由包名派生
# 3) 解出后得到可读 JS，再按函数名 grep
```
- **本项目经验**：脚本解出来往往是 `scripts__index.jsc.js` / `scripts2__*.jsc.js` 这种"混编大文件"（几十万行），**能直接 grep**，不必追求还原成模块。

### B2. 建立"函数名 → 文件:行号"索引（最重要的一步）
```bash
# 定位入口与关键回调
grep -n 'LoadGame\|loadGame = function\|updatePlayerData' scripts__index.jsc.js
grep -n 'MessageCenter.on' scripts__index.jsc.js | head
grep -n 'HttpConst\.' scripts__index.jsc.js | head        # 请求常量清单
```
- 把 `LoginMgr.loadGame → scripts__index.jsc.js:66510` 这种映射记进 Spec 的 `client` 段。
- 后面每次排障都靠它。

### B3. 读协议的两种"白给"位置
1. **请求常量表**：`HttpConst.XXX = "User.method"` → **RPC 方法全集**，即你的"待实现接口表"。
2. **回调消费端**：`MessageCenter.on(HttpConst.XXX, function(t,e){...})` → 回调里**读哪些字段、怎么分支**，就是响应契约。

> 注意: 常量可能**带脏字符**：`GET_DUNGEON_INFO = "User.getCopyData\n"`（尾部换行）。
> 服务端入口必须 `do.strip()`，否则该接口**永远匹配不上**（本项目实坑）。

---

## C. 网络层定位

cocos 的网络路径比 Unity 分散，按下面顺序找：

| 路径 | 位置 | 特征 |
|------|------|------|
| JS 层 `XMLHttpRequest` / `fetch` | 脚本内封装的 `NetMgr/HttpMgr` | **HTTP-RPC 型**（本文件主线） |
| JS 层 `WebSocket` / `socket.io` | `NetMgr.http` / `Net.*` | 长连接/聊天 |
| 原生 socket 经 jsb 桥 | `jsb.NET.HttpRequest` / `websocket` | 走 `libcocos2djs.so` |
| 自研 TCP | 原生 `.so` | 少见，按 Unity TCP 那套分析 |

判"HTTP 轮询型"的标志：多端口 + 请求体是**结构化字符串/JSON** + 有 `sendRequest(常量, params, cb)`。
> 本项目：**三个端口分工**（选服 `9898`、登录/业务 `8002`、WS `9002`），典型 HTTP-RPC。

---

## D. 自加密协议（cocos 最常见形态）

### D1. 定位加密
```bash
strings -a libEncryptor*.so libcocos2djs.so | grep -iE 'aes|cbc|pkcs|key|iv|md5|base64'
# 找 encrypt/decrypt 导出函数 → IDA/Ghidra 看参数（key/iv 常量）
```
### D2. 典型结构（HTTP-RPC + AES）
```
请求体 = hex( AES-CBC( "{\"mod\":\"User\",\"do\":\"Method\",\"p\":{...}}" ) )
响应体 = {"errorCode":0,"MsgData":"<hex( AES-CBC( 明文JSON ) )>"}
```
- 参数常见：`AES-256-CBC` + `Pkcs7`，`KEY/IV` 为 16/32 字节 hex 常量。
- 服务端要能**双向**处理：`looks_encrypted()` 判别 → 解密；响应再加密回 hex。
- 明文里 `mod` 常恒为 `"User"`，`do` 是方法名，`p` 是参数对象 —— **把 `do` 当 RPC 名**。

### D3. 加密边界自测（不要靠手抓包）
```python
import server_module as M
body = M.aes_encrypt_hex({'mod':'User','do':'LoadGame','p':{...}}).encode()
# POST → 取回 {"errorCode":0,"MsgData":...} → M.aes_decrypt_body(MsgData) 得明文 dict
```
> 直接 `import` 你的服务端模块造/解包，比反复抓包快一个数量级。

---

## E. 热更与资源来源（cocos 特有的坑）

- `project.manifest` / `version.manifest` 存在 → 客户端启动会**比对版本并可能下载热更资源**。
- 后果：
  1. 你改的**包内资源可能被热更覆盖**；要改就改**热更源**或**屏蔽热更**。
  2. 版本号对不上 → 客户端可能卡在"检查更新"。
- 处置优先级：先**让客户端不更新**（改 manifest 版本/地址/断掉热更域），再谈改包。

---

## F. 改包与重签（确实要改客户端时）

```bash
apktool d app.apk -o out        # 解包
# 改 assets/src/*.jsc.js 里的地址常量 / DevConfig / 服务器 URL
apktool b out -o app-mod.apk    # 回包
# 重签（必须，否则装不上）
keytool -genkey ... ; apksigner sign --ks ks.jks app-mod.apk
```
- **优先"不改包"落点**（见 `client-address-sources.md`）：改客户端读的**配置/热更 manifest** 把地址指向自建服。
- 注意**包名派生密钥**：有的加密 KEY/签名由**包名**派生，改包名会导致解密失败 → 保持原包名最稳。
- cocos 的 `.jsc` 改完若仍是密文形态，需**按原算法重新加密**（key 应与运行时一致）。

---

## G. 配置表与本地化（反推服务端的数据基础）

- cocos 手游普遍**纯客户端算逻辑**，服务端只要提供**存档投影**（属性/背包/技能/任务）。
- 配置表常在 `tables/*.json`（或 csv/xlsx 导出）。**文本字段是语言表 key**：
```python
zh = json.load(open('lantab_zh.json'))     # {key: 文本}
name = zh.get(str(item['Name']))           # item['Name'] 是 key，不是文字
```
- 把 `ID + 名称 + 关键属性` 导出成 CSV，后台发物品/暗号兑换/商店全要用它。

---

## H. Cocos 分支实坑清单（本项目真实踩过）

| # | 现象 | 根因 | 处置 |
|---|------|------|------|
| 1 | 某接口永远匹配不上 | `do` 常量带 `\n` | 入口 `strip()` |
| 2 | **自测全绿，真机进不去** | 只验证了 HTTP 通，没跑客户端脚本 | 真机 UA vs `Python-urllib` **分开看日志**；以"下一条请求"为准 |
| 3 | 进服转圈后退出 | LoadGame 回包字段让客户端回调抛异常 | 用"后续请求是否发出"夹逼；**回包大小对账** |
| 4 | 一次改多字段=不可定位 | 同时上线 5+ 新字段 | **最小增量 + 一次一变量**，保"最后一次可进服"基线 |
| 5 | 字段类型错就崩 | 回调无保护 `.length/.indexOf/.split`；`equipLocks` 客户端要数组却收到对象 | 每个字段**回回调里核对期望类型** |
| 6 | 配置表全是数字 | 文本是语言表 key | `lantab_zh` 还原 |
| 7 | 角色数据串号 | 物品/技能存成扁平结构 | 按账户分桶 |
| 8 | WS 心跳应答后仍 30~80s 断线循环 | **protobuf 消息号是猜的**（5279 当 Pong） | 从 APK 解 `protoidmap` 表核对：本项目 5288=Pong、5279=TeamBattleRoomChatMessageRes；消息号表必须**逐号实证**，不能按语义猜 |
| 9 | 改完功能玩家仍报"没用" | 玩家在线时改的服务端/发的物品，**客户端不重登不刷新** | 存档型变更（装备/物品/称号）一律提示重登；在线推送只对带 note 事件的响应生效 |
| 10 | 登录后立刻崩、反复重试无报错 | **登录阶段派发 eco 事件**（角色实体未初始化，空引用） | LoadGame 回包**只放数据不放事件**；经验/货币同步放战斗结算（客户端已就绪的时机） |
| 11 | 后台发"经验/铜钱"玩家进不去 | 这些是**伪物品**（ID 4001/4002/4003），进了 itemObj 客户端做 `+=` 累加爆掉 | 后台发放接口按 ID 路由到对应属性桶；LoadGame 永久过滤伪物品出 itemObj |
| 12 | 装备穿上打怪空手、重登被脱 | 客户端穿戴契约是 `{EquipmentType:槽位, itemID:实例ID}`，服务端等的是别的字段名 | **从 REQ 日志反推真实请求体**，不靠猜；穿戴/卸下(itemID=0)都持久化 |
| 13 | 玩家反馈 A 实际发生 B（买A到账B） | 商店族多接口共用处理器，参数语义不同（商城发商品ID vs 杂货铺发物品ID） | 每个购买接口**独立实现**并核对客户端 `reqBuy` 的字段含义 |
| 14 | 主线卡死在"找XX对话" | 送物型任务需要背包有剧情物品（SpRequire），接取时没发 | 接任务发放 + 交任务收回 + **LoadGame 自愈**（每次登录对账补齐）三层兜底 |
| 15 | 改了 A 功能 B 功能坏了 | 存档读-改-写竞态：中途另一处 `_save_store(旧快照)` 回滚了新写入 | 同一请求内**改完立即落库**，或统一"重读→合并→写"；禁止持旧引用跨函数写 |
| 16 | 崩溃无 JS 报错、无法定位 | 多个新字段同时上线，崩在加载早期（错误上报都未初始化） | **二分排除法**：撤下全部新增字段→能进→逐个加回；每次只验证一个 |
| 17 | 提取的 JS 行号与崩溃栈对不上 | 解出的脚本与设备实际运行的 **APK 版本有偏差** | 行号只做参考；**函数名 + grep 内容**定位；拿设备同版 APK 复核 |
| 18 | 服务器表和客户端表互相怀疑 | 双方各持一份配置表 | 用 APK 解包比对（`zipfile` + uuid 解码定位 `startres/import/**.json`；`.mbin`=msgpack、语言表=lz-string）；本项目实测 35/6310/106768 条**零差异**，据此排除"表不一致"假设 |
| 19 | 金条商城"弹窗对物品不对" | 客户端本地表自加货 + 服务端按自己表再发一份(note绝对值覆盖) — **双表版本差异** | 服务端只扣钱, 货物客户端自加(读回调确认谁加货); 详见 live-ops.md §3 |
| 20 | 接口落保底桶 eRet=0 | 注册键名拼写错(getalchemytdata 多了个t) | 自定义键与接口清单**逐字符核对** |
| 21 | 回血永远到不了真实上限 | 客户端发的 maxhpLimit 是本地缓存旧值, 服务端拿它当上限还覆盖存档 | 上限以存档(战斗hpmax同步值)为准; 自愈只清精确作弊值 |

> 与 Unity/UE 最大的不同在 **②**：cocos 脚本层信息量大但**客户端更脆**，
> 且"服务端返回 200"与"客户端能消费"之间落差更大，**验证必须更严**（见 `closure-verification.md`）。

---

## H2. 进服之后的 Live 运营经验（本项目 v28~v33 实践）

> 引擎无关的完整方法论已抽出为 `live-ops.md`（子系统次序/契约反推法/双表版本差异/
> 客户端本地状态/事件时机/自愈/后台工具）。本节保留 cocos 专属细节。

> 进服只是开始。以下是把"能进游戏"做成"能长期玩"的关键机制，全部来自本项目线上实跑。

### H2.1 note 变更通知协议（cocos RPC 的"推送"）

客户端对**带 note 的响应**要求**双层包裹**，否则 note 子事件永远不派发：

```json
{"p": "User.UseItem", "User.UseItem": {"eRet":1, "note": {"ivch": {...}}}}
```

- note 键 → 客户端事件：`ivch`(物品, **绝对数量**) / `eqch`(装备实例) / `skch`(技能 [lv,pgr,brlv]) / `eco`(货币, 绝对值) / `attrch`(血蓝/修为/饥饿)
- 值是**绝对值不是增量**——发增量会导致客户端显示翻倍
- 没有双层包裹 = 客户端收到数据但不刷新 UI（表现是"接口没生效"）

### H2.2 客户端本地存档与服务端历史的合并

cocos 客户端把任务完成史存在 localStorage（key 如 `<roleID>$#&A`）。
LoadGame 回包若带 `finishTaskObj`（哪怕是**空数组**）会**整体覆盖**本地历史。
客户端会在请求里上报本地数量（`finishTaskFlag` / `taskFlag`）——
**服务端只在自己更全时才下发该字段，否则省略键**。省略键 ≠ 发空值。

### H2.3 位置数组编码（baseValueAy 类）

角色属性是**按位置编码的数组**（不是字典）。字段序号即语义：
本项目 `[27]=hp [28]=hpLimit [29]=mp [30]=mpLimit [31]=饥饿 [34]=潜能 [35]=铜钱 [37..40]=四维 [42]=年龄 [47]=出师门派列表`。
**坑**：个别位置要求特定类型（[47] 必须是数组，填 0 → 客户端 `.indexOf` 崩）。
给位置数组补默认值时，逐位核对客户端解析代码的类型期望。

### H2.4 后台即排障工具

给管理后台做这些能力，线上问题分钟级闭环（都按账号分桶）：
- 角色全量数据查看（roledata API：背包/装备/穿戴/任务/货币/技能）
- 物品/装备/技能/称号发放（**装备走实例、伪物品走属性路由**）
- **强制完成任务**（卡任务救援：标记完成+收回剧情物品+发奖励）
- 货币与经验直设
- 兑换码（暗号）系统
经验类数值**不能在登录回包推送**（见坑 10），通过"打一场战斗→结算同步"到账。

### H2.5 部署纪律

- 部署脚本向 `/tmp` 追加式传文件 → **先 `rm -f` 再传**（本项目曾因拼接出"双模块缝合"服务端，编译通过但行为怪异）
- 传完 **md5 对账** 本地与远端
- 服务起不来时部署脚本会中断 → 准备 **SFTP 直传 + 手动 start** 的应急路径
- 改动前保留"最后一次可进服"版本的副本与回包大小记录（回包大小突变=报警）

### H2.6 多账号隔离的兜底自查

任何"按账号分桶"的存储，上线前跑一遍双账号用例：
A 穿装备/学技能/做任务 ≠ 影响 B 的对应数据；
新注册号走建角流程（quicklogin 回 `userName:''` 触发客户端建角，**绝不回退 default 存档**——
本项目曾因新号回退 default 拿到别人角色导致跳过建角）。

---

## I. 工具与命令速查

```bash
# 判引擎
unzip -l app.apk | grep -E 'libcocos|\.jsc|\.lua|manifest'
# 找地址/域名/端口
grep -aoE '(https?|wss?)://[^"'\'' ]+|[0-9]{1,3}(\.[0-9]{1,3}){3}:[0-9]+' libcocos2djs.so | sort -u
# 脚本定位
grep -n 'HttpConst\.\|MessageCenter.on\|loadGame' assets/src/scripts*.jsc.js | head
# 配置表还原
python3 -c "import json;zh=json.load(open('lantab_zh.json'));print(zh.get('506'))"  # → 金条
```

---

## J. 一张图：cocos 分支的最快路线

```
解 APK → 判 libcocos2djs/2dlua → 解脚本(.jsc/.lua)
→ grep HttpConst.* 拿 RPC 全集
→ 找 AES(key/iv) + 明文壳(mod/do/p + MsgData)
→ 起 HTTP-RPC 服务端(逐 do 回 eRet:1 + 回调要的字段)
→ 真机进服(以"下一条请求"为验收) → 再逐功能补数据
```