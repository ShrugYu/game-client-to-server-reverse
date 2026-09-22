#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
make_stub_so.py —— 从一个真实 .so 生成「空壳 so」（反作弊剥离用）

为什么需要它：
    保护库（libtprt.so / libtersafe2.so …）经常被别的库 DT_NEEDED 依赖，
    直接删会 `JNI FatalError: Unable to load library: ...libunity.so` → SIGABRT。
    所以只能「换空壳」：文件在、soname 对、符号全，但函数全是空实现。

它做什么：
    1. readelf 读出原库的**全部导出符号**（FUNC / NOTYPE / OBJECT）
    2. FUNC/NOTYPE → 生成返回 0 的空函数
    3. OBJECT（尤其函数指针表）→ 按**原始字节大小**复刻数组，并**填上有效函数指针**
       （填 0 会导致调用方 `blr x0` 跳空指针 → SIGSEGV）
    4. JNI_OnLoad → 返回 JNI_VERSION_1_6（0x00010006），不做任何注册
    5. gcc 编译成 aarch64 .so，SONAME 与原库一致

用法：
    python3 make_stub_so.py <原lib.so> <输出.so> [--extra-jni 名字...]

额外 JNI 函数（如 AceApplication.initialize 这种按名字查找的）：
    --extra-jni Java_com_ace_gshell_AceApplication_initialize
    （会自动生成 `int <名字>(void*,void*,void*,void*,void*,void*,void*) { return 0; }`）
"""
import re
import subprocess
import sys
import os

JNI_ONLOAD_RET = 0x00010006


def dyn_syms(so_path):
    out = subprocess.run(['readelf', '--dyn-syms', '--wide', so_path],
                         capture_output=True, text=True).stdout
    syms = []
    for line in out.splitlines():
        p = line.split()
        if len(p) < 8 or not p[0].endswith(':'):
            continue
        try:
            int(p[0][:-1])
        except ValueError:
            continue
        # 注意：readelf --dyn-syms 的 Size 列是【十进制】（Value 列才是十六进制）
        size = int(p[2], 10) if p[2].isdigit() else 0
        typ, ndx, name = p[3], p[6], p[7].split('@')[0]
        if ndx == 'UND':
            continue
        syms.append({'type': typ, 'size': size, 'name': name})
    return syms


def orig_soname(so_path):
    """读原库的 SONAME（DT_NEEDED 靠它匹配，必须保持一致）。"""
    out = subprocess.run(['readelf', '-d', so_path], capture_output=True, text=True).stdout
    m = re.search(r'SONAME\).*?\[(.+?)\]', out)
    return m.group(1) if m else None


def gen(so_path, out_so, extra_jni):
    syms = dyn_syms(so_path)
    funcs = [s['name'] for s in syms if s['type'] in ('FUNC', 'NOTYPE') and s['name'] != 'JNI_OnLoad']
    objs = [s for s in syms if s['type'] == 'OBJECT']
    print('[i] 原库导出: FUNC/NOTYPE=%d  OBJECT=%d' % (len(funcs), len(objs)))
    for o in objs:
        print('    OBJECT %-28s size=%d  -> %d 项指针表' % (o['name'], o['size'], o['size'] // 8))
    L = ['#include <stdint.h>', 'typedef void* p;',
         'static long noop_fn(void){ return 0; }']
    for o in objs:
        n = o['size'] // 8
        n = max(n, 1)
        L.append('void* %s[%d] = { %s };' % (o['name'], n, ','.join(['(void*)noop_fn'] * n)))
    for f in funcs:
        L.append('p %s(void){ return 0; }' % f)
    for j in extra_jni:
        L.append('long %s(void* a,void* b,void* c,void* d,void* e,void* f,void* g){ return 0; }' % j)
    L.append('int JNI_OnLoad(void* vm, void* res){ return 0x%08X; }' % JNI_ONLOAD_RET)
    c_path = out_so + '.c'
    open(c_path, 'w').write('\n'.join(L) + '\n')
    soname = orig_soname(so_path) or os.path.basename(out_so)
    if os.path.basename(out_so) != soname:
        print('[!] 提示：输出文件名建议就叫 %s（DT_NEEDED 靠 soname 匹配，装进 APK 时路径也要一致）'
              % soname)
    cmd = ['gcc', '-shared', '-fPIC', '-O2', '-o', out_so, c_path, '-Wl,-soname,' + soname]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print('[!] gcc 失败:\n' + r.stderr[:800])
        return 1
    print('[+] 生成 %s (%d bytes)，源码在 %s' % (out_so, os.path.getsize(out_so), c_path))
    chk = subprocess.run(['readelf', '--dyn-syms', '--wide', out_so],
                         capture_output=True, text=True).stdout
    got = set(re.findall(r'\b(Java_\w+|JNI_OnLoad)\b', chk))
    print('[i] 导出检查: 函数 %d 个, JNI 前缀符号 %d 个' %
          (len([l for l in chk.splitlines() if 'FUNC' in l]), len(got)))
    return 0


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    extra = []
    if '--extra-jni' in sys.argv:
        i = sys.argv.index('--extra-jni')
        extra = sys.argv[i + 1:]
    sys.exit(gen(sys.argv[1], sys.argv[2], extra))