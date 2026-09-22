/*
 * frida-redirect.js —— 把游戏客户端的网络目标，改到我们自建的服务端
 *
 * 适用：native / il2cpp / Unity 客户端（点这里最通用）。
 *      Java/OkHttp 客户端也可用（getaddrinfo/connect 一样生效），
 *      若要更精细地按 URL 改，用 templates/xposed-redirect/。
 *
 * 用法：
 *   frida -U -f <游戏包名> -l frida-redirect.js
 *   （有 root：frida-server；无 root：LSPatch + Frida gadget）
 *
 * 注意：这是"换服务端"的注入手法之一，属于 skill 的「第三步 重定向」。
 *       注入可能被反作弊检测（见 references/anticheat.md）；自测目标再用。
 */

// ===== 配置：原 host  ->  我们的 host/IP =====
const HOST_MAP = {
  "api.example.com":  "192.168.1.100",
  "game.example.com": "192.168.1.100",
  "login.example.com":"192.168.1.100",
};
// 端口覆盖：原端口 -> 新端口（不需要就留空 {}）
const PORT_MAP = {
  // 8888: 8888,
};
const DEBUG = true;

function log(s){ if (DEBUG) console.log("[rdr] " + s); }
function mapHost(h){ return (h && HOST_MAP[h]) ? HOST_MAP[h] : null; }

/* ---------------------------------------------------------------
 * 1) getaddrinfo —— 域名解析层（覆盖面最广，建议先开这个）
 *    把"原域名"解析成"我们的 IP"，客户端后续 connect 就打到我们这边。
 * ------------------------------------------------------------- */
(function hookGetaddrinfo(){
  const p = Module.findExportByName(null, "getaddrinfo");
  if (!p) { log("getaddrinfo not found"); return; }
  Interceptor.attach(p, {
    onEnter(args){
      this.node = args[0].isNull() ? null : args[0].readCString();
      const to = mapHost(this.node);
      if (to) { args[0] = Memory.allocUtf8String(to); this.to = to; }
    },
    onLeave(ret){
      if (this.to) log("getaddrinfo " + this.node + " -> " + this.to);
    }
  });
})();

/* ---------------------------------------------------------------
 * 2) connect —— 客户端直接连 IP 的情况
 *    仅当"目标端口命中 PORT_MAP"时才改写，避免误伤其它连接。
 * ------------------------------------------------------------- */
(function hookConnect(){
  const p = Module.findExportByName(null, "connect");
  if (!p) { log("connect not found"); return; }
  Interceptor.attach(p, {
    onEnter(args){
      const sa = args[1];
      if (sa.isNull()) return;
      const fam = sa.readU16();
      if (fam === 2) { // AF_INET
        const port = (sa.add(2).readU8() << 8) | sa.add(3).readU8();
        const b = sa.add(4);
        const ip = b.readU8()+"."+b.add(1).readU8()+"."+b.add(2).readU8()+"."+b.add(3).readU8();
        const newPort = PORT_MAP[port];
        if (newPort) {
          sa.add(2).writeU8((newPort >> 8) & 0xff);
          sa.add(3).writeU8(newPort & 0xff);
          log("connect " + ip + ":" + port + " -> :" + newPort + " (需配合 hosts/DNAT 换 IP)");
        }
      }
    }
  });
})();

/* ---------------------------------------------------------------
 * 3) 可选：HTTPS 降级 / 证书校验绕过（当原协议是 TLS 且无本地证书时）
 *    见 templates/frida_bypass_ssl.js；原协议是 TLS 时也可改走本地 CA。
 * ------------------------------------------------------------- */
// require 不对，这里只是提示：
//   frida -U -f <pkg> -l templates/frida_bypass_ssl.js -l frida-redirect.js

log("frida-redirect loaded, host rules = " + JSON.stringify(HOST_MAP));
