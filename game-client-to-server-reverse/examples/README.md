# 示例索引

这些示例演示**同一个 skill 面对不同项目时如何得出不同方案**。
它们**不是结论，是推演过程**——你的项目不一定和它们一样。

| 示例 | 项目类型 | 关键差异 |
|------|---------|---------|
| [A. Unity + protobuf + TCP](A-unity-il2cpp-protobuf.md) | 手游，IL2CPP，protobuf，TCP 长连接 | 明文 protobuf，`dump.cs` 直接给消息号 |
| [B. UE + KCP + 自定义二进制](B-ue-kcp-custom.md) | 端游，UE5，UDP/KCP，自定义序列化 | 需要 SDK dump，KCP 上再套加密 |
| [C. Unity + Lua + HTTP](C-unity-lua-http.md) | 手游，业务在 Lua，HTTP+轮询 | JSON 明文，鉴权 token，无长连接 |
| [D. 真实 Lua 源码分析](D-real-lua-client.md) | 真实横版动作手游（Unity+xLua） | **1794 个 opCode**、协议模式、无人机协议 |
| [E. Cocos2d-x(JS) + AES HTTP-RPC](E-cocos2dx-http-js.md) | 手游，cocos JSB，AES-256-CBC 自加密 HTTP，多端口 | **进服前 7 节 + §8 进服后 Live 运营实录**（40+ 轮线上迭代） |

> 读法：重点看「证据 → 决策 → Spec 差异 → 代码改动」，而不是记住最终参数。

每个示例的结构：
1. 用户给了什么
2. 证据清单
3. 逐层决策（走了决策树哪条分支）
4. 产出的 Spec 关键片段
5. 参考实现要改哪里
6. 闭环验证路径
7. 坑与回退