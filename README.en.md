<p align="center">
  <b>English</b> · <a href="./README.md">简体中文</a>
</p>

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://shieldcn.dev/header/grid.svg?title=Game+Client+%E2%86%92+Server+Reverse&subtitle=From+a+client-only+game+to+a+running+self-hosted+server&mode=dark&align=center">
    <img alt="Game Client → Server Reverse" src="https://shieldcn.dev/header/grid.svg?title=Game+Client+%E2%86%92+Server+Reverse&subtitle=From+a+client-only+game+to+a+running+self-hosted+server&mode=light&align=center">
  </picture>
</p>

<p align="center">
  <a href="https://github.com/ShrugYu/game-client-to-server-reverse"><img alt="GitHub stars" src="https://shieldcn.dev/github/stars/ShrugYu/game-client-to-server-reverse.svg?variant=secondary&v=2"></a>
  <a href="https://github.com/ShrugYu/game-client-to-server-reverse/blob/main/LICENSE"><img alt="License" src="https://shieldcn.dev/github/license/ShrugYu/game-client-to-server-reverse.svg?variant=secondary&v=2"></a>
  <a href="https://github.com/ShrugYu/game-client-to-server-reverse/commits/main"><img alt="Last commit" src="https://shieldcn.dev/github/last-commit/ShrugYu/game-client-to-server-reverse.svg?variant=secondary&v=2"></a>
  <a href="https://github.com/ShrugYu/game-client-to-server-reverse/graphs/contributors"><img alt="Contributors" src="https://shieldcn.dev/github/contributors/ShrugYu/game-client-to-server-reverse.svg?variant=secondary&v=2"></a>
  <a href="https://github.com/ShrugYu/game-client-to-server-reverse/forks"><img alt="Forks" src="https://shieldcn.dev/github/forks/ShrugYu/game-client-to-server-reverse.svg?variant=secondary&v=2"></a>
</p>

# Game Client → Server Protocol Reverse Engineering Skill

> Reconstruct the **server protocol** and a **working self-hosted server** from a "client-only" game, and get the **original client to connect successfully**.
>
> An **AI-oriented reverse-engineering playbook**: not a server-development tutorial, but "how to reverse a server out of a client".

A skill package following the [Agent Skills](https://agentskills.io) spec. The core skill is `game-client-to-server-reverse`: a navigation doc `SKILL.md` + 37 `references/` docs + `templates/` + `tools/` + a runnable `server/` reference implementation.

---

## What it is

| Aspect | Description |
|------|------|
| **Purpose** | Reverse the server protocol from a game client and reproduce a server that actually runs (reverse-engineering perspective) |
| **Inputs** | Installers (`.apk` / `.ipa` / `.exe`), `dump.cs`, `*.lua`, `*.usmap`, captures (`.pcap` / mitm exports), existing server samples |
| **Outputs** | `project-profile` → `evidence-inventory` → `protocol.spec.yaml` (single source of truth) → server code + deploy + closure verification |
| **Engines** | Unity (IL2CPP / Mono / Lua), Unreal (UE4 / UE5), Cocos2d-x / Cocos Creator (JS / Lua hot-update) |
| **Languages** | C#, AS3, Lua, JS, Java/Kotlin, C++ |
| **Platforms** | Android (Termux), Windows, Linux servers, Docker |

**Hard rule: produce the spec first, then the code.** Code is derived from `protocol.spec.yaml`; a new game means a new spec, not a pile of rewritten snippets. If an AI dumps code without a spec and an evidence list first, make it start over.

---

## Features

- **Foundations** (`references/primer.md`): the three essentials (config = values / protocol = format / code = usage), the nature of packet protocols, opcodes and opcode tables, and hot-update source as the most readable "source".
- **Four-phase roadmap** (`references/workflow-roadmap.md`): static analysis → build tools + login chain → redirection → packet-filling loop → feature-list iteration, each phase with explicit acceptance.
- **A selector of 11 reverse methods** (`references/methods.md`): white-box source / black-box capture / grey-box hook / auxiliary artifacts / transparent proxy with per-interface replacement / differential probing / replay / port known implementations / self-loop / brute-force / **inline server**, with a selection matrix.
- **Inline-server route** (`references/inline-server.md`): no external server; synthesize responses inside the client process. Transport / framing / crypto layers need not be reconstructed.
- **Wire-level patching** (`references/wire-level-patching.md`): read/write fields at the byte level without a protobuf runtime.
- **Closure verification, 6 false-positive classes** (`references/closure-verification.md`): a listening port ≠ a usable service; a self-loop ≠ client compatibility.
- **Reference implementation** (`server/`): a long-connection binary protocol server (Python), verified end to end: handshake → login → create character → select → enter scene → move → heartbeat.
- **UI templates**: `templates/register-site/` (registration site).

---

## Distribution / Install

### As a Skill (recommended)

```bash
npx skills add ShrugYu/game-client-to-server-reverse
```

Variants:

```bash
npx skills add ShrugYu/game-client-to-server-reverse --global
npx skills add ShrugYu/game-client-to-server-reverse --agent AGENT_NAME
```

### Manual

Copy the whole `game-client-to-server-reverse/` folder into your skills directory
(e.g. Operit: `/storage/emulated/0/Download/Operit/skills/`).
The folder name must match the `name` field in `SKILL.md`'s frontmatter.

### Channels

| Channel | Link |
|------|------|
| **GitHub repo** | https://github.com/ShrugYu/game-client-to-server-reverse |
| **skills CLI** | `npx skills add ShrugYu/game-client-to-server-reverse` |
| **SkillsMP**（auto-indexed） | https://skillsmp.com |
| **skills.sh** | https://skills.sh |

Works with Claude Code, Cursor, Codex, GitHub Copilot, Windsurf, Gemini, Cline, etc.

---

## Usage

Hand the game-related files to an AI and state your goal. A single **installer** is enough to bootstrap:

```
Reverse the server for this game: /path/to/game.apk

Use this APK to reverse the server; get login working first, then deploy locally.

This is a Unity mobile game; produce a protocol-analysis .md first, then write code.
```

The AI responds in this order:

```
1. project-profile.yaml    <- what it read, what's missing
2. evidence-inventory      <- evidence + confidence per conclusion
3. protocol.spec.yaml      <- protocol spec (single source of truth)
4. server code + deploy + verification   <- derived from the spec
```

### Reading order (for the AI)

```
1. references/reading-path.md   <- pick 3-5 files by task type
2. SKILL.md §0.0 - §0.6         <- method selection + iron rules + workflow
3. Read the scenario files per path, then start
Before finishing: reading-path.md §2 "pre-wrap-up checklist"
```

> `SKILL.md` is the map; `references/` is the text. **Do not read the whole package at once** — it exhausts context.

---

## Layout

```
.
├── README.md                        Chinese README
├── README.en.md                     English README (this file)
├── AGENTS.md                        workspace maintenance contract (for skill maintainers)
└── game-client-to-server-reverse/   the skill body (folder name = skill name)
    ├── SKILL.md                     navigation doc (< 500 lines)
    ├── README.md                    detailed skill docs
    ├── TRACKER.md                   progress & interface list
    ├── references/                  37 on-demand docs
    ├── schema/                      project-profile.yaml / protocol.spec.yaml templates
    ├── templates/                   docs & code templates (register site, ADR, e2e evidence, ...)
    ├── tools/                       extract_interfaces.py / make_stub_so.py / repack_zip.py
    ├── examples/                    worked examples for different game types
    ├── extensions/                  optional (server bots / reverse-engineer bots)
    └── server/                      reference: long-connection binary protocol server (Python)
```

---

## Dependencies & Credits

This skill's methodology and toolchain reference / build on the following open-source projects. Thanks to their authors and maintainers (**only projects with a public repository are listed**):

### Decompilation / Reverse engineering

| Project | Purpose | Repository |
|------|------|------|
| Il2CppDumper | Unity IL2CPP metadata extraction | https://github.com/Perfare/Il2CppDumper |
| Il2CppInspector | Unity IL2CPP analysis | https://github.com/djkaty/Il2CppInspector |
| dnSpy | .NET / Unity Mono decompiler & debugger | https://github.com/dnSpyEx/dnSpy |
| ILSpy | .NET decompiler | https://github.com/icsharpcode/ILSpy |
| unluac | Lua bytecode decompiler | https://github.com/HansWessels/unluac |
| luadec | Lua decompiler | https://github.com/viruscamp/luadec |
| Ghidra | Disassembler / decompiler | https://github.com/NationalSecurityAgency/ghidra |
| jadx | Android dex → Java | https://github.com/skylot/jadx |
| Apktool | APK unpack / repack | https://github.com/iBotPeaches/Apktool |
| binwalk | Firmware / container analysis | https://github.com/ReFirmLabs/binwalk |

### Unreal Engine assets / SDK

| Project | Purpose | Repository |
|------|------|------|
| FModel | Browse / export UE assets | https://github.com/4sval/FModel |
| Dumper-7 | UE SDK dump | https://github.com/Encryqed/Dumper-7 |
| UE4SS | UE scripting / SDK | https://github.com/UE4SS-RE/RE-UE4SS |
| UnrealMappingsDumper | Generate .usmap mappings | https://github.com/TheNaeem/UnrealMappingsDumper |
| AESKeyFinder | Locate UE AES keys | https://github.com/GHFear/AESKeyFinder-By-GHFear |

### Dynamic instrumentation / injection / root-free frameworks

| Project | Purpose | Repository |
|------|------|------|
| Frida | Dynamic instrumentation | https://github.com/frida/frida |
| x64dbg | Windows debugger | https://github.com/x64dbg/x64dbg |
| LSPosed | Xposed framework (root) | https://github.com/LSPosed/LSPosed |
| LSPatch | Root-free Xposed (patch-based) | https://github.com/LSPosed/LSPatch |
| NPatch | Root-free Xposed (LSPatch fork) | https://github.com/7723mod/NPatch |
| VirtualXposed | Root-free Xposed (virtual container) | https://github.com/android-hacker/VirtualXposed |
| TaiChi | Root/unlock-free Xposed | https://github.com/taichi-framework |

### Packet capture / protocols

| Project | Purpose | Repository |
|------|------|------|
| mitmproxy | HTTPS capture / MITM | https://github.com/mitmproxy/mitmproxy |
| Wireshark | Network protocol analysis | https://github.com/wireshark/wireshark |
| tcpdump | CLI packet capture | https://github.com/the-tcpdump-group/tcpdump |
| Protocol Buffers (protoc) | protobuf encode/decode | https://github.com/protocolbuffers/protobuf |
| KCP | Reliable UDP transport | https://github.com/skywind3000/kcp |
| zlib | Compression | https://github.com/madler/zlib |

### Server / runtime

| Project | Purpose | Repository |
|------|------|------|
| Flask | Reference server web | https://github.com/pallets/flask |
| PyYAML | Config parsing | https://github.com/yaml/pyyaml |
| aiosqlite | Async SQLite | https://github.com/omnilib/aiosqlite |
| Termux | Linux environment on Android | https://github.com/termux/termux-app |
| proot | Root-free Linux container | https://github.com/proot-me/proot |
| Docker | Containerized deploy | https://github.com/docker |
| systemd | Linux service supervision | https://github.com/systemd/systemd |

### Server architecture references

| Project | Language | Repository |
|------|------|------|
| Skynet | C / Lua | https://github.com/cloudwu/skynet |
| Pomelo | Node.js | https://github.com/NetEase/pomelo |
| KBEngine | C++ | https://github.com/kbengine/kbengine |
| NoahGameFrame | C++ | https://github.com/ketoo/NoahGameFrame |

> Note: the above are open-source projects mentioned/referenced in the methodology; this repository **does not bundle or distribute** them. Follow each project's own license when using them.

---

## Disclaimer

> By using this material you confirm that you have read, understood, and agreed to all clauses below. If you disagree, stop using it immediately.

1. **Scope of use**: This material is for **study, research, and technical exchange**, and for interoperability research and local deployment of **self-developed, authorized, or offline single-player** games. It is a **reverse-engineering methodology document**, not a server-development tutorial, and it targets no specific game.

2. **No illegal use**: Using this material for any **unauthorized** intrusion, attack, destruction, tampering, bypassing of security mechanisms, data theft, or any act that infringes intellectual property or violates a game's terms of service or applicable law is strictly prohibited.

3. **No warranty**: This material is provided "**as-is**", without any express or implied warranty, including but not limited to merchantability, fitness for a particular purpose, and non-infringement. The authors do not guarantee its accuracy, completeness, or usability.

4. **Limitation of liability**: To the maximum extent permitted by law, the authors and contributors **are not liable for any direct, indirect, incidental, special, punitive, or consequential damages** arising from the use of or inability to use this material (including but not limited to data loss, device damage, account bans, and legal disputes).

5. **User responsibility**: Users must **ensure** their use is lawful and compliant (including obtaining necessary authorization), and **bear all legal responsibility and consequences**.

6. **Third-party content**: Third-party projects, code, tools, docs, and services referenced or linked here remain the property of their respective owners; check and comply with their terms. The authors are not responsible for third-party content or its consequences.

7. **Rights claims**: If you are a rights holder and believe this material infringes your rights, contact us via a repository Issue; the authors will **correct or remove** it promptly after verification.

8. **Platform rules**: Rights holders may file a DMCA takedown of this Skill; GitHub may act on violations of its Acceptable Use Policies.

9. **Changes**: This disclaimer may be updated at any time and takes effect upon publication, without further notice.

### On reviving discontinued online games

This material is often used to archive, study, and locally revive **discontinued (shut-down / end-of-online-service)** online games. For such use, the following applies in particular:

- **"Discontinued" does not mean "public domain".** The code, art, trademarks, story, and audio of such games remain the property of the **original rights holders**; shutdown **does not** mean the holder waives its rights, nor does it authorize third-party operation.
- This material supports **non-commercial research, archiving, and continuation for existing player communities or individuals**. Using it to impersonate the official operator, commercialize for profit, run paid services, or harm the rights holder or the original player community is **strictly prohibited**.
- All **legal, financial, and reputational risks** from reviving, private-server deployment, and operation are **borne solely by the user**; the authors do not participate, endorse, or assume any responsibility.
- If the original rights holder or their successor raises objections, the authors will **cooperate in removing** the relevant material promptly.

---

## License

Released under the GNU AGPL-3.0 ([LICENSE](./LICENSE))

---

## Contributors

<p>
  <a href="https://github.com/ShrugYu"><img src="https://github.com/ShrugYu.png?size=120" width="56" height="56" alt="ShrugYu" title="ShrugYu"></a>
  <a href="https://github.com/Qslzy"><img src="https://github.com/Qslzy.png?size=120" width="56" height="56" alt="Qslzy" title="Qslzy"></a>
  <a href="https://github.com/SakuraZuk"><img src="https://github.com/SakuraZuk.png?size=120" width="56" height="56" alt="SakuraZuk" title="SakuraZuk"></a>
</p>

- **ShrugYu** — maintainer
- **Qslzy** — contributor
- **SakuraZuk** — contributor

---

## Changelog

See the top of [`game-client-to-server-reverse/README.md`](./game-client-to-server-reverse/README.md) for the full history.
Current version **v2.0**: foundations + four-phase roadmap + server swap (redirection) + inline-server route.