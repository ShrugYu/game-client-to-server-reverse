#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
repack_zip.py —— APK/ZIP「原样复制」重打包（秒级，2GB 包也不慢）

为什么不用 apktool：
    apktool 会全解全 build，把所有条目重新压缩一遍 → 偏移全变、原签名彻底作废，
    对 2GB 的包还非常慢。
    本脚本只做「搬运 + 定点替换」：除被替换/删除的条目外，其余**压缩数据原样拷贝**。

支持：
    --replace <zip内路径>=<本地文件>     替换（不存在则新增）
    --delete  <zip内路径>                删除条目
    --add-from <另一个apk> <zip内路径>   从别的包拷贝条目（例：原包的 META-INF 签名文件）

注意：
    · 会清掉 data-descriptor 位（flg & ~0x8），长度/CRC 写在 local header 里
    · **不会**写 APK Signing Block（v2/v3）→ 需要签名请最后用 apksigner 签
    · 条目数需 < 65535、单条目 < 4GB（普通 APK 都满足）

用法示例：
    python3 repack_zip.py game.apk game_stub.apk \\

    # 塞回原包签名、顺手删掉自己的签名
    python3 repack_zip.py mod.apk mod_origsig.apk \\
        --delete META-INF/ANDROID.RSA --delete META-INF/ANDROID.SF --delete META-INF/MANIFEST.MF \\
        --add-from orig.apk META-INF/APP.RSA \\
        --add-from orig.apk META-INF/APP.SF \\
        --add-from orig.apk META-INF/MANIFEST.MF
"""
import os
import struct
import sys
import zipfile
import zlib

LOCAL_SIG = 0x04034B50
CD_SIG = 0x02014B50
EOCD_SIG = 0x06054B50


def raw_entries(src):
    """按 central directory 顺序产出 (name, local_header_offset)。"""
    z = zipfile.ZipFile(src)
    out = []
    for info in z.infolist():
        out.append((info.filename, info.header_offset))
    return out


def main(argv):
    if len(argv) < 3:
        print(__doc__)
        return 1
    src, dst = argv[1], argv[2]
    replace, delete, addfrom = {}, set(), []
    i = 3
    while i < len(argv):
        a = argv[i]
        if a == '--replace':
            path, f = argv[i + 1].split('=', 1)
            replace[path] = open(f, 'rb').read()
            i += 2
        elif a == '--delete':
            delete.add(argv[i + 1])
            i += 2
        elif a == '--add-from':
            addfrom.append((argv[i + 1], argv[i + 2]))
            i += 3
        else:
            print('未知参数: ' + a)
            return 1

    src_f = open(src, 'rb')
    out = open(dst, 'wb')
    cd = []
    copied = 0
    for name, hoff in raw_entries(src):
        if name in delete or name in replace:
            continue
        src_f.seek(hoff)
        hdr = src_f.read(30)
        sig, ver, flg, meth, mt, md, crc, cs, us, fnl, xl = struct.unpack('<IHHHHHIIIHH', hdr)
        assert sig == LOCAL_SIG, 'bad local header @%d' % hoff
        src_f.seek(hoff + 30)
        fn = src_f.read(fnl)
        ex = src_f.read(xl)
        src_f.seek(hoff + 30 + fnl + xl)
        data = src_f.read(cs)
        flg &= ~0x8
        off = out.tell()
        out.write(struct.pack('<IHHHHHIIIHH', LOCAL_SIG, ver, flg, meth, mt, md, crc, cs, us, fnl, len(ex)))
        out.write(fn)
        out.write(ex)
        out.write(data)
        cd.append((fn, ver, flg, meth, mt, md, crc, cs, us, ex, off))
        copied += 1
    print('[i] 原样搬运 %d 个条目' % copied)

    def add(name, data, meth=8):
        crc = zlib.crc32(data) & 0xffffffff
        if meth == 8:
            co = zlib.compressobj(9, zlib.DEFLATED, -15)
            blob = co.compress(data) + co.flush()
        else:
            blob = data
        if not blob:
            blob, meth = data, 0
        fn = name.encode()
        off = out.tell()
        out.write(struct.pack('<IHHHHHIIIHH', LOCAL_SIG, 20, 0, meth, 0, 0,
                              crc, len(blob), len(data), len(fn), 0))
        out.write(fn)
        out.write(blob)
        cd.append((fn, 20, 0, meth, 0, 0, crc, len(blob), len(data), b'', off))
        print('    [+/~] %s (%d B)' % (name, len(data)))

    for path, data in replace.items():
        add(path, data)
    for apk, path in addfrom:
        data = zipfile.ZipFile(apk).read(path)
        add(path, data)

    cd_off = out.tell()
    for (fn, ver, flg, meth, mt, md, crc, cs, us, ex, off) in cd:
        out.write(struct.pack('<IHHHHHHIIIHHHHHII', CD_SIG, 20, 20, flg, meth, mt, md,
                              crc, cs, us, len(fn), len(ex), 0, 0, 0, 0, off))
        out.write(fn)
        out.write(ex)
    cd_size = out.tell() - cd_off
    out.write(struct.pack('<IHHHHIIH', EOCD_SIG, 0, 0, len(cd), len(cd), cd_size, cd_off, 0))
    out.close()
    src_f.close()
    print('[+] 写出 %s (%d bytes)，条目 %d' % (dst, os.path.getsize(dst), len(cd)))
    bad = zipfile.ZipFile(dst).testzip()
    print('[i] testzip = %s (None 即 CRC 全对)' % bad)
    with open(dst, 'rb') as f:
        head = f.read()
    print('[i] 含 APK Signing Block: %s' % (b'APK Sig Block 42' in head))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))