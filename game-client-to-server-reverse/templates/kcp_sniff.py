#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KCP / 自定义 UDP 流量还原骨架
- 从 pcap 里按 (src_ip, src_port, dst_ip, dst_port) 重组流
- 按 KCP 头结构剥离，输出每段载荷

用法: python3 kcp_sniff.py capture.pcap out/flows/
"""
import sys, os, struct
from collections import defaultdict

try:
    from scapy.all import rdpcap, IP, UDP
except ImportError:
    print("请先 pip install scapy")
    sys.exit(1)

# KCP 头: conv(4) cmd(1) frg(1) wnd(2) ts(4) sn(4) una(4) len(4)
KCP_HDR = ">IBB HIIII".replace(" ", "")
KCP_HDR_SIZE = 24


def parse_kcp(payload: bytes):
    if len(payload) < KCP_HDR_SIZE:
        return None
    conv, cmd, frg, wnd, ts, sn, una, length = struct.unpack(KCP_HDR, payload[:KCP_HDR_SIZE])
    data = payload[KCP_HDR_SIZE:KCP_HDR_SIZE + length]
    return dict(conv=conv, cmd=cmd, frg=frg, wnd=wnd, ts=ts, sn=sn, una=una, data=data)


def main(pcap_path, outdir):
    os.makedirs(outdir, exist_ok=True)
    pkts = rdpcap(pcap_path)
    flows = defaultdict(list)
    for p in pkts:
        if IP in p and UDP in p:
            key = (p[IP].src, p[UDP].sport, p[IP].dst, p[UDP].dport)
            flows[key].append(bytes(p[UDP].payload))

    for i, (key, segs) in enumerate(flows.items()):
        name = f"{key[0]}_{key[1]}-{key[2]}_{key[3]}"
        path = os.path.join(outdir, name + ".bin")
        with open(path, "wb") as f:
            for s in segs:
                k = parse_kcp(s)
                if k and k["data"]:
                    f.write(k["data"])
                else:
                    f.write(s)  # 非 KCP，原样落盘
        print(f"[+] {name}: {len(segs)} packets -> {path}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    main(sys.argv[1], sys.argv[2])