# Wire 级定点改写：不等 schema 齐就能跑通

> **来源**：从**已实机跑通**的成品服务端实现中抽象出的通用技术。
> 适用于任何「protobuf + 长度前缀帧」的长连接游戏协议。
>
>  **这是把「协议 30% 反推完」变成「客户端已经能进游戏」的关键技术。**
> 配套：`engineering-practices.md`（范式层）、`closure-verification.md`（验证层）。
>
> 注意: 文中出现的字段名（`RoleBase` 等）与消息号（25/26/27/28）**只是示例**，
> 换游戏必须按自己的抓包重新确认 —— 别把示例当常量。

---

## 目录

> 0 核心思想 · **1 三层积木** · 2 启动序列打补丁 · **3 空子消息也要保留 注意:** · 4 结构化+原样保存 · 5 幂等(请求体哈希) · 6 HTTP 侧 AES-ECB+JSON · 7 按登录请求选 fixture · 8 落地顺序 · 9 与其它文档关系

---

## 0. 核心思想

```
[x] 常规思路：先反推完整 protobuf schema → 生成代码 → 构造消息 → 发出去
   （字段几百个、嵌套极深 → 永远凑不齐，卡死在某个页面）

[x] 可行思路：把抓包字节【原样保留】，只对【已确认的少数字段】做字节级替换
   （不需要 descriptor、不需要了解 99% 的字段，就能让客户端跑起来）
```

原实现的文件头注释写得很直白：

> “The client uses Google Protobuf, but the repository does not currently carry a
> Python protobuf runtime. This module works at the **wire level** and **preserves
> unknown fields** when patching captured messages.”

代码注释甚至写明：**故意不带 protobuf 运行时**。
——**不引入 pb runtime 是一个决策，不是偷懒。**

---

## 1. 三层积木

### 第一层：帧头（10 字节，大端）

```python
HEADER_SIZE = 10
MAX_BODY_LENGTH = 0xFFFF

# 偏移0: u16 body 长度 / 偏移2: u16 消息号 / 偏移4: i32 序号 / 偏移8: u16 标志
def encode_frame(frame) -> bytes:
    return struct.pack(">HHiH", len(frame.body), frame.msg_id, frame.seq, frame.flag) + frame.body

def decode_frame(data: bytes) -> Frame:
    body_len, msg_id, seq, flag = struct.unpack(">HHiH", data[:HEADER_SIZE])
    assert len(data) == HEADER_SIZE + body_len      # 长度必须自洽
    return Frame(body=data[HEADER_SIZE:], msg_id=msg_id, seq=seq, flag=flag)
```

> 注意 `seq` 是**有符号** i32、`flag` 是 u16 —— 判错类型会在某些帧上炸。

### 第二层：protobuf 字段遍历器（不依赖任何 pb 库）

> 只做四件事：读 tag → 判 wire_type → 取值 → **记住字段在原 buffer 里的 start/end**。

```python
@dataclass(frozen=True)
class Field:
    number: int; wire_type: int; value: int | bytes
    start: int; end: int          #  关键：保留原始字节区间

def iter_fields(data: bytes) -> Iterable[Field]:
    offset = 0
    while offset < len(data):
        start = offset
        tag, offset = _decode_varint(data, offset)
        number, wire_type = tag >> 3, tag & 7
        # wire_type 0=varint 1=fixed64 2=length-delimited 5=fixed32
        ...  # 依次推进 offset
        yield Field(number, wire_type, value, start, offset)
```

读值 API（按字段号取，取不到给默认值 —— **不抛异常**，这是能跑通的前提）：

```python
get_varint(data, number, default=0)
get_string(data, number, default="")
get_bytes(data, number) -> bytes | None
get_bytes_all(data, number) -> list[bytes]      # repeated
get_repeated_varints(data, number) -> list[int] # 兼容 packed
```

### 第三层： 定点替换（splice，不是重新序列化）

```python
def _replace_field(data, number, replacement, *, wire_type=None) -> bytes:
    for field in iter_fields(data):
        if field.number == number and (wire_type is None or field.wire_type == wire_type):
            # 只替换这一段字节，其余（含未知字段）原样保留
            return data[:field.start] + replacement + data[field.end:]
    return data + replacement        # 字段不存在 → 追加（protobuf 允许）
```

对外三个便捷函数 + 一个语义化封装：

```python
patch_varint(data, number, value)
patch_bytes (data, number, value)
patch_string(data, number, value)

def patch_role_base_diamond(role_base: bytes, diamond: int) -> bytes:
    # Confirmed by static analysis: RoleBase.Diamond is field 8.
    if diamond < 0: raise ProtoError("diamond cannot be negative")
    return patch_varint(role_base, 8, diamond)
```

**为什么 splice 合法**：protobuf 是顺序自描述流，字段只靠 tag 定位。
长度变化会让后续字节位移，但**解析器跟着走，语义不变**。

---

## 2. 启动序列：静态模板 + 按状态打补丁

### 模板怎么来的（离线一次性）

```
原版客户端 ↔ 原版服务器 的抓包 records（c2s/s2c + msg_id + body）
                    +
本地 fixture（已结构化的 25/26/27/28）
         ↓  merge
startup_template.json   ← 运行时不再需要原始抓包文件
```

合并规则（`build_startup_template`，值得照抄）：

```python
1. 找到 s2c 的 SCLoginAck(4)，只从它【之后】开始取
2. 遇到 c2s 就停（启动序列是纯下行段）
3. 丢掉 {7, 4}（握手/登录应答由服务端实时生成）
4. {25, 26, 27, 28} → 用【fixture 里对应的帧】替换（顺序消费，支持同一消息号多片）
5. 其余帧 → 原样保留
```

### 模板要过校验（缺一个就直接报错，别等客户端崩）

```python
def load_startup_template(path):
    for frame in frames:
        if frame.msg_id in {3, 4, 7}:
            raise ProtoError("startup template must only contain frames after SCLoginAck")
    if not any(f.msg_id == 25 for f in frames): raise ProtoError("... missing SCStartupInfoNtf(25)")
    if not any(f.msg_id == 26 for f in frames): raise ProtoError("... missing (26)")
    if not any(f.msg_id == 27 for f in frames): raise ProtoError("... missing (27)")
    if not any(f.msg_id == 28 for f in frames): raise ProtoError("... missing (28)")
    if not any(f.msg_id == 25 and get_bytes(f.body, 6) is not None for f in frames):
        raise ProtoError("... missing RoleRiskBattle (field 6)")
```

>  **把「客户端会崩的缺失」在启动时校验掉**，而不是等客户端黑屏。
> 这是把调试成本从「猜」变成「读报错」的关键。

### 发送时按本地状态打补丁（`_send_startup`）

```python
for frame in startup_frames:
    body = frame.body
    if frame.msg_id == 25 and get_bytes(body, 4) is not None:     # RoleBase
        body = patch_bytes(body, 4, patch_role_base_from_state(role_base, state))
    if frame.msg_id == 25 and role_bag and get_bytes(body, 5) is not None:   # RoleBag
        ...
    if frame.msg_id == 25 and get_bytes(body, 6) is not None:     # RoleRiskBattle
        ...
    if frame.msg_id == 27:                                        # 英雄/编队
        body = encode_startup_hero_ntf(...)
    await self._send(writer, Frame(body=body, msg_id=frame.msg_id, seq=frame.seq, flag=frame.flag))
```

**原则**：**每片 25 只改它自己带的那部分**（这片的 field 4 就改 4，field 5 就改 5），
不认识的部分一个字节都不动。

---

## 3. 注意: 最值钱的一条经验：空子消息也要保留

`encode_role_risk_battle` 的注释（原文）：

> “The original startup carries an **empty-but-present** RoleRiskBattle
> (`Tower` and `StarReward` as empty sub-messages). Keeping those sub-messages
> **present** is important because the client's 149 settlement handler
> **dereferences** UserDataComponent.RoleRiskBattle **without a null check**.”

```python
# Preserve the original empty sub-messages so the client sees a non-null object
result += encode_bytes_field(6, b"")
result += encode_bytes_field(7, b"")
```

**教训**：
> 你重建对象时把「空但存在」的字段省掉，客户端就会拿到 `null` → 空指针崩溃 / 卡死。
> **字段的存在性（presence）和字段的值一样重要。**
> 重建任何嵌套消息时，先照着原抓包**把字段骨架抄全**，再填值。

---

## 4. 状态模型：结构化已确认 + 原样保存未确认

```python
state = {
  "schema_version": 1,
  "role_base": {...},          # 已确认字段 → 结构化，可读可改
  "role_bag": {                #  双轨制
      "items": {...},
      "wire_b64": "<原始字节 base64>",   # 未确认部分原样留底
      "wire_dirty": False,             # 是否被本地改过（决定用重建还是回放原字节）
  },
  "heroes": {}, "lineups": {...}, "risk_battle": {...},
  "strength_state": {...}, "tasks": {...}, "story": {...},
  "gacha": {...}, "social": {...},
  "operations": {"battle": {}, "gacha": {}, "payment": {}},   # 幂等收据
}
```

**合并规则**（`merge_role_state`）：按 key 走**字段级**分支，而不是整段覆盖。

```python
if key == "role_base":        _merge_dict(...)      # 浅合并
elif key == "role_bag":       _merge_keyed(items)   # 满合并 + wire_dirty = True
elif key in {"heroes","operations"}: _merge_keyed(...)   # 值 None/False = 删除
else:
    # 未知状态 retains under extensions，不静默替换已知分区
    result.setdefault("extensions", {})[key] = _copy(value)
```

> 「未知的进 `extensions`，**绝不覆盖已知分区**」—— 这条能防止后续补 schema 时数据互相污染。

**未确认阶段的处理**：`normalize_role_state` 在迁移老数据时
`if equipment_body and not state["equipment"].get("wire_b64"):` 才写入 → **不覆盖已有的 wire 快照**。

---

## 5. 幂等：用请求体哈希当收据 key

```python
def operation_key(namespace: str, body: bytes) -> str:
    return f"{namespace}:{hashlib.sha256(body).hexdigest()}"

record_operation(state, "battle", key, result)   # 存下上次的结算结果
if (cached := get_operation(state, "battle", key)): return cached   # 重放同一请求 → 返回原结果
MAX_OPERATION_RECEIPTS = 256     # 环形淘汰，防无限增长
```

**优点**：不需要客户端配合传订单号；同一个请求体 = 同一次操作。
（代价：客户端真重复点击时也会被当成重放 —— 需按业务判断是否可接受。）

> 另注：`role_version` 这类**单调递增版本号**要单独维护，
> 别让它因为幂等缓存而停在旧值（客户端可能用它判断数据新旧）。

---

## 6. HTTP 侧：AES-ECB + JSON 信封（实战要点）

```python
KEY = b"<16 字节硬编码密钥>"      # 例：从 APK 的 OkHttp interceptor / smali 里抠出来
BLOCK_SIZE = 16                  # AES-128-ECB + PKCS5/7 padding

def decode_request(ciphertext):
    value = decode_json(ciphertext)            # AES-ECB 解密 → JSON
    return {"token": ..., "deviceId": ..., "data": value.get("data", {})}
```

**要点**：
- **密钥硬编码是常见的**（从 APK 的 OkHttp interceptor / smali 里就能抠出来），不要一上来假设是协商密钥。
- 信封结构固定：`{token, deviceId, data}` → 认证信息在**外层**，业务在 `data`。
- JSON 序列化要跟客户端对齐：`separators=(",", ":")`、`ensure_ascii=False`
  （差一个空格就可能被客户端的签名/校验拒绝）。

---

## 7. 按登录请求选 fixture（防串号）

```python
def _fixture_for_login(self, request):
    # 用 login 请求里的 open_id / account / user_id 去匹配 fixture 身份
    ...
```

**必须显式映射**，禁止「按账号名猜角色」，否则会把别人的角色数据发给你。

配套的**去泄漏**手法（`_patch_nested_uid`）：模板里嵌套着原账号的 UID，
要按 `(outer_field, inner_field)` 路径**逐层挖出来替换成当前账号的 game_uid**。

```python
def _patch_nested_uid(body, outer_field, inner_field, game_uid) -> bytes:
    # 进入 outer_field 子消息 → 替换 inner_field 的 uid → 装回去
```

**上线前扫描**：对所有回放模板做一遍 UID / open_id / 订单号 / 资源数扫描。

---

## 8. 落地顺序（可直接照跑）

```
① 抓一次原版完整启动序列（pcap）→ 重组帧 → 存 records(json)
② 写帧 codec（10B 头）+ protobuf 字段遍历器 + patch_* 三件套
③ 用【已确认字段号】把 fixture 结构化（先只要 RoleBase/RoleBag/RoleRiskBattle/英雄）
④ 生成 startup_template.json（fixture ∪ capture，规则见 §2）+ 启动校验
⑤ 服务端：实时生成 7/4 → 回放 template（按片打补丁）→ 跑起来看能到哪一步
⑥ 卡住时看客户端**下一个请求的消息号**，按同样手法给它加一条【回放模板 + 定点改写】
⑦ 每加一条业务，就把结构化字段从 wire_b64 迁到 state 的正式分区
```

**第 ⑤ 步的判定**：能走到「收到启动结束消息 → 主界面」就算这一阶段成功；
之后每个模块都是重复 ⑥⑦，**不需要一次反推完**。

---

## 9. 与其它文档的关系

| 文档 | 层次 |
|------|------|
| 本文 | **实现层**：怎么写代码让它跑起来 |
| `engineering-practices.md` | 范式层：怎么组织工作、怎么验收、怎么写文档 |
| `closure-verification.md` | 验证层：怎么证明真的通了 |
| `protocol-spec.md` | 规格层：确认下来的字段要落进 Spec |
| `case-ninja3-ecdh.md` | 反例参照：卡在「必须先把算法解出来」的思路里 |