# 端游环境：Windows 运行服务端

> 场景：Windows 上跑游戏服务端，同机客户端连 `127.0.0.1`，或局域网/公网客户端连。

## A. 快速启动（开发）

```bat
:: 1. 装 Python 3.10+（勾选 Add to PATH）
:: 2. 进目录
cd /d D:\服务端反推\server

:: 3. 建虚拟环境
python -m venv venv
venv\Scripts\pip install -r requirements.txt

:: 4. 启动
venv\Scripts\python -m app.main -c config\config.yaml
```

配套脚本：`server/deploy/start_windows.bat`

## B. 后台常驻（生产级）

### 方式一：NSSM（推荐，最稳）
```bat
:: 下载 nssm.exe 放到 PATH 或当前目录
nssm install gsrv "D:\服务端反推\server\venv\Scripts\python.exe" "-m app.main -c D:\服务端反推\server\config\config.yaml"
nssm set gsrv AppDirectory "D:\服务端反推\server"
nssm set gsrv AppStdout "D:\服务端反推\server\logs\stdout.log"
nssm set gsrv AppStderr "D:\服务端反推\server\logs\stderr.log"
nssm set gsrv AppExit Default Restart
nssm set gsrv Start SERVICE_AUTO_START
nssm start gsrv
:: 管理
nssm status gsrv
nssm stop gsrv
nssm remove gsrv confirm
```

### 方式二：WinSW（XML 配置）
```xml
<!-- gsrv.xml -->
<service>
  <id>gsrv</id>
  <name>Game Mock Server</name>
  <executable>D:\服务端反推\server\venv\Scripts\python.exe</executable>
  <arguments>-m app.main -c D:\服务端反推\server\config\config.yaml</arguments>
  <workingdirectory>D:\服务端反推\server</workingdirectory>
  <logmode>roll</logmode>
  <onfailure action="restart" delay="5 sec"/>
</service>
```
```bat
winsw install gsrv.xml
winsw start gsrv
```

### 方式三：任务计划程序（无需第三方）
```
taskschd.msc → 创建任务
  触发器：系统启动时
  操作：启动程序 venv\Scripts\pythonw.exe
       参数 -m app.main -c config\config.yaml
       起始于 D:\服务端反推\server
  勾选"不管用户是否登录都要运行"
```

## C. 防火墙与端口

```powershell
# 放行游戏端口（管理员 PowerShell）
New-NetFirewallRule -DisplayName "GameMockServer" -Direction Inbound `
  -Protocol TCP -LocalPort 8888 -Action Allow
# 若用 UDP/KCP
New-NetFirewallRule -DisplayName "GameMockServerUDP" -Direction Inbound `
  -Protocol UDP -LocalPort 8888 -Action Allow
# GM 端口(9900) 只允许本机，不要对外开放
```

## D. 公网访问
- 路由器端口转发：外部端口 → 内网主机 IP:8888
- 或内网穿透：`cloudflared` / `frp` / `ngrok`
- 有云服务器：直接把 `server/` 拷到云主机，用 Linux 的 `deploy.sh`

## E. 客户端对接到 Windows 服务端

| 场景 | 做法 |
|------|------|
| 同机客户端 | 改 `C:\Windows\System32\drivers\etc\hosts`，把游戏域名→127.0.0.1 |
| 局域网客户端 | hosts → 服务端局域网 IP |
| 需重定向 | `netsh interface portproxy` 或抓包工具做 DNS 映射 |
| 证书固定 | 自签 CA 装进系统信任库；或 Frida 绕过（自测） |

改 hosts 示例（管理员编辑）：
```
127.0.0.1  game.example.com
127.0.0.1  login.example.com
```

## F. 可被 agent 驱动的 Windows 工具

| 工具 | 用途 |
|------|------|
| PowerShell / CMD | 启动/停止服务、看日志、改配置 |
| `nssm` / `winsw` | 注册为系统服务、崩溃自重启 |
| 任务计划程序 (`schtasks`) | 开机自启 |
| WSL2 | 需要 Linux 工具链时（抓包/逆向工具） |
| `sc.exe` | 原生服务控制 |
| AutoHotkey / WinAppDriver | 需要 UI 自动化（点启动器、模拟登录） |
| PsExec | 远程/提权执行命令 |

> 若 Windows 上装了 OpenSSH Server，则可让 Linux 侧 agent 通过 SSH 直接操作 Windows。

## G. WSL2 注意
- WSL2 默认 NAT，Windows 端口不会自动暴露到局域网：
  - 用 `netsh interface portproxy add v4tov4 ...` 做端口转发
  - 或在 `.wslconfig` 里确保 `localhostForwarding=true`（仅本机可用）
- WSL2 里跑服务端，客户端在 WSL 外访问需用 Windows 主机 IP。

## H. 常见坑

- Python 没加 PATH → `python` 找不到。
- 用了 Store 版 python 别名 → 建议关掉"应用执行别名"，用官方安装版。
- NSSM 服务起不来 → 看 `AppStderr` 日志，多半是工作目录/路径含中文空格（用引号包住）。
- 防火墙没放行 → 局域网客户端连不上。
- GM 端口暴露公网 → 安全风险，务必只绑 `127.0.0.1`。
---

## I.  逆向工具链在 Windows/Git Bash 的坑（实测）

> 在 Windows 上跑 adb/radare2/Ghidra 做协议反推时的特有问题，Linux 上不存在。

### I.1 MSYS/Git Bash 的路径转换（最高频）

Git Bash 会把 `/xxx` 开头的参数当路径转换成 Windows 路径，破坏一切类 Unix 命令：

| 现象 | 原因 | 解法 |
|---|---|---|
| `adb pull /data/local/tmp/x.pcap` 报 `D:/Git/data/... does not exist` | `/data/...` 被转成 `D:\Git\data\...` | 命令前加 `MSYS_NO_PATHCONV=1` |
| radare2 的 `/r 0x1234`（xref 搜索）报 `Invalid command 'D:/Git/r ...'` | `/r` 被当路径吃掉 | 同上；或用 `-c` 时双保险 |
| heredoc/脚本换行符 | Windows 写出的脚本是 CRLF | 写入时 `open(f,'w',newline='\n')`；或 `tr -d '\r'` |

> 推论：设备端 shell 脚本要么 PC 生成（控制换行符）后 push，
> 要么纯单行命令。CRLF 脚本在 mksh 里会静默失败（连目录都建不出）。

### I.2 Ghidra headless（无 GUI 批量反编译的正确姿势）

Ghidra 11+ 需要 **JDK 21**；**JRE 不行**（校验 javac）——直接下 JDK zip 解压版
（Temurin `.../jdk/.../eclipse` 接口给 zip），**不要用 MSI**（静默安装会被提权问题卡死）。

```bat
@echo off
set JAVA_HOME=E:\tools\jdk-21.x.x+x
set PATH=%JAVA_HOME%;%PATH%
:: 首次: -import 分析(20MB so 约10-30分钟); 之后: -process 复用(秒开)
call ghidra\support\analyzeHeadless.bat <proj_dir> <proj_name> ^
  -process libmmo.so -noanalysis ^
  -scriptPath <scripts_dir> -postScript DecompFuncs.py
```

Jython 后处理脚本模板（批量反编译指定地址到文件）：
```python
# DecompFuncs.py —— 记得: Ghidra 地址 = ELF vaddr + image_base!
from ghidra.app.decompiler import DecompInterface
from ghidra.util.task import ConsoleTaskMonitor
di = DecompInterface(); di.openProgram(currentProgram)
fm = currentProgram.getFunctionManager()
af = currentProgram.getAddressFactory().getDefaultAddressSpace()
out = []
for label, av in [('fn1', 0x28c358), ('fn2', 0x293964)]:   # 填 Ghidra 地址
    fn = fm.getFunctionContaining(af.getAddress(av))
    if fn:
        r = di.decompileFunction(fn, 180, ConsoleTaskMonitor())
        if r.decompileCompleted():
            out.append('==== %s ====\n%s\n' % (label, r.getDecompiledFunction().getC()))
open(r'E:\work\decomp.c','w').write(''.join(out))
```

**两个必踩的坑**：
1. **image base 偏移**：PIE so 导入后 Ghidra 地址 = ELF vaddr + image_base
   （如 +0x100000）。用 `currentProgram.getImageBase()` 先探测。不换算 → 全部
   `NO FUNCTION`，白跑一轮。
2. `-process` 复用项目时目标必须叫 `/libmmo.so`（导入名），
   目录不存在会报 `Directory not found`——先 `mkdir`。

### I.3 Android so 静态分析的 relocation 陷阱

**so 文件里的 vtable 指针字段全是 0**（Android RELA/packed relocs：运行时才填）。
静态读文件找 vtable → 全空 → 误判"没有类信息"。三个出路：

1. **Ghidra**（自动应用 relocation）——首选；
2. **手工链 .rela.dyn**：解析 `SHT_RELA` 的 `R_AARCH64_RELATIVE`(1027) 重定位，
   `addend → 目标字符串地址` 反查 typeinfo 名，`typeinfo ← vtable` 建指针链
   （pyelftools 30 行搞定，适合只要一两个类的场合）；
3. 运行时 dump（设备上读进程内存）。

> 另注意区分：so 可能用标准 `DT_RELA`，也可能是 **packed relocs（Android 专有
> SHT_ANDROID_RELA）**——pyelftools 不解后者，静态手工链会失败，只能走 Ghidra。

### I.4 找自研加密/压缩函数的特征扫描（不用 Ghidra 全量分析）

| 目标 | 扫描特征 | 说明 |
|---|---|---|
| 加密/哈希热点 | **EOR 指令密集簇**（每 4B 指令窗内 EOR 聚集） | 但 MD5 也是 EOR 密集——**再用 T 常量识别**：`0xFFFA3942/0x8771F681/0x6D9D6122…` → 是 MD5（多半用于 HTTP 签名，不是会话加密） |
| TEA/XXTEA | delta `0x9E3779B9` 的 movz/movk 指令编码（扫 `movk #0x9e37, lsl#16`） | 3 处以内，逐个看调用者 |
| zlib | 直接搜字符串/导入：`inflateInit2_`、`"need dictionary"`、`0x1f8b` 常量、CRC32 表 | **能命中 → 大概率传输层是压缩不是加密（见 decision-tree §4.0）** |
| OpenSSL 全家桶 | 导出符号一堆 EVP/AES/RSA | 注意: **链了 ≠ 用了**：全量统计 BL 调用点到这些 PLT stub，0 调用 = 死代码（实测常见：RSA 只用于 HTTP 登录，会话层根本不用 OpenSSL） |

### I.5 进程内存 dump（设备端，root）

```sh
adb root && adb shell
PID=$(pidof <包名>)
kill -STOP $PID                      # 冻结, 防缓冲被覆盖
# 遍历 /proc/$PID/maps 的 rw-p 匿名段
dd if=/proc/$PID/mem bs=4096 skip=$((VA/4096)) count=$((SZ/4096)) of=/data/local/tmp/m_xxx.bin
kill -CONT $PID
```
**坑**：mksh 的 `$(( ))` 对 64 位地址（0x7xxxxxxxxx）**算术溢出** → dump 全是空文件。
必须 **PC 端预计算好十进制偏移**生成脚本再 push 执行。
**验证 dump 有效**：先搜一个已知明文（角色名/域名/协议字符串）——搜不到说明 dump 是空的。
