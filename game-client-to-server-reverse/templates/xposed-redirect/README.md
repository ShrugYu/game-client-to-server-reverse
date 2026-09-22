# xposed-redirect —— 客户端重定向模块模板（Java / OkHttp 客户端）

> 目的：**把游戏客户端连的服务器，换成我们自建的服务端**（skill「第三步 重定向」）。
> 这是**模板/骨架**，不是成品。按目标客户端改 `TARGET_PKGS` 与 hook 点即可。

## 什么时候用它 / 用哪个

| 客户端网络栈 | 用哪个模板 |
|--------------|-----------|
| Java / OkHttp / HttpURLConnection（原生 Android） | **本模块**（`MainHook.java`） |
| native / il2cpp / Unity（socket 直连） | `templates/frida-redirect.js`（本模块 hook 不到 native） |

> 拿不准就先跑一遍抓包：**能抓到明文 URL** → Java 层；**只有裸字节/连 IP** → native 层。

## 文件

```
xposed-redirect/
├── MainHook.java        核心：读配置 + 改写 URL（okhttp / java.net.URL）
├── AndroidManifest.xml  模块声明（xposedmodule / scope）
├── xposed_init          入口类名（assets/xposed_init）
├── redirect_config.txt  配置模板（adb push 到 /data/local/tmp/）
└── build.gradle         依赖（compileOnly Xposed API）
```

## 用法

1. 改 `MainHook.java`：
   - `TARGET_PKGS` 填目标游戏包名；
   - 需要的话补 hook 点（见下）。
2. 把 `MainHook.java` / `AndroidManifest.xml` / `xposed_init` / `build.gradle` 放进一个 Android 工程编译成模块 APK。
3. 装模块 → 在 **LSPosed** 里**勾选目标游戏** → 重启游戏。
4. 配置重定向：
   ```bash
   adb push redirect_config.txt /data/local/tmp/redirect_config.txt
   # 改完重启游戏生效
   ```
5. 看日志：`adb logcat | grep '\[rdr\]'`（应见 attach + 每条改写）。

## 无 root 也能用

用 **LSPatch** 把模块**修补进**目标 APK（或 `NPatch`），无需 root/框架。

## 常见 hook 点（按需补进 MainHook）

| 客户端用的 | 建议 hook |
|-----------|----------|
| OkHttp | `okhttp3.Request$Builder.url(String)`（已含） |
| HttpURLConnection | `java.net.URL(String)`（已含） |
| 自研 URL 工具 / 配置里的 baseUrl | hook 对应的 `getXxxUrl()` / `setHost()` |
| Unity 的 `UnityWebRequest`（Java 桥） | `com.unity3d.player.UnityPlayer` 相关方法 |
| 服务器地址存在 SharedPreferences | 直接改该 key（见 `client-address-sources.md §3.1`） |
| **native socket** | 换 `frida-redirect.js`（hook `getaddrinfo`/`connect`） |

## 边界与风险

- 这是**换服务端**的正当用途（自研/已授权/离线自测）。
- 注入可能触发客户端保护；被秒退/黑屏时先把注入摘掉定位。
- 端口改写用**正则**只是简化实现，跨端口不一致时请改成按 `URI` 精确重建。
