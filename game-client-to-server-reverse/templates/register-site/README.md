# 注册网站模板（通用 · 响应式）

成品页面：`index.html`（自包含，无 CDN）。后端：`server.py`（最小 Flask）。

## 特点
- **注册 / 登录**切换、密码强度、显示/隐藏密码、深/浅色主题、表单校验。
- **响应式**：桌面左右分栏；手机隐藏左栏、表单铺满（含安全区）。
- 借用了成熟注册页的通用做法：**注册引导区**、**账号前缀**（如 `svr_`）、
  **第三方校验字段**、成功后**醒目标出账号 + 复制**、底部**注意事项**。

## 注册校验：三选一（`CFG.verifyMode` / 环境变量 `VERIFY_MODE`）
| 模式 | 前端字段 | 服务端校验 |
|------|---------|-----------|
| `invite`（默认） | 邀请码 | 命中 `invite_code` 表：未过期、`used<quota`；成功后 `used+1` |
| `group` | QQ 号 | 命中 `group_members` 表（可批量导入群成员） |
| `whitelist` | 账号 | 命中 `whitelist` 表 |
| `none` | 无 | 不校验 |

> 新玩家用该码注册。奖励闭环：`注册 → 得码 → 邀请 → 新人注册 → 码 used+1`。

## 可配置项（页面 `CFG` 一处改完）
| 键 | 作用 |
|----|------|
| `appName/title/sub/hero*` | 品牌与文案 |
| `prefix` | 账号前缀；留空 `""` 即无前缀 |
| `userLabel/userHint/userPattern` | 账号标签/提示/正则 |
| `guide/guideTitle` | 注册引导（空数组隐藏） |
| **`verifyMode` + `verify{}`** | **三选一校验**（label/placeholder/pattern/hint/key） |
| `notes` | 注意事项 |
| `apiRegister/apiLogin` | 后端地址 |

## 运行
```bash
pip install flask
# 邀请码模式：
GAME_DB=../server/data/game.db PWD_SALT=你的盐 VERIFY_MODE=invite ACCOUNT_PREFIX=svr_ python3 server.py
# QQ群模式：VERIFY_MODE=group   白名单模式：VERIFY_MODE=whitelist
# 新用户自动带一个邀请码：AUTO_GRANT_INVITE=1
```
浏览器打开 `http://127.0.0.1:8080/`。

## 接口契约（可换 FastAPI/Express）
```
POST /api/register {username,password,confirm?,verify_mode?,invite?,qq?} -> {ok:true,username:"svr_xxx"} / 4xx {ok:false,msg}
POST /api/login    {username,password}                                    -> {ok:true} / 401 {ok:false,msg}
```

## 表（与游戏服同一 DB）
```
account(username, password_hash)
group_members(qq PK, note)                                              # QQ群名单
whitelist(username PK)                                                  # 白名单
```

> 注意：若客户端发包前先处理密码（如 `MD5(pwd+salt)`），注册站必须用**同一套哈希**，否则注册的密码登不上（`references/account.md §16.2`）。