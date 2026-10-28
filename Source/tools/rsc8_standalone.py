"""
解**独立的游戏原始格式 RSC8 文件**（磁盘上的 `.yft/.ydd/.ydr/...`，不是从 .rpf 里抽出来的）。
==============================================================================
为什么需要：项目此前只能通过 `rdr2rpf extract` 从 `.rpf` 里取资源；拿到**单文件**（mod 替换件、
手工拷贝的资源）时无法解析 —— 因为游戏体是 **Deflate/Oodle 压缩**的，直接 `find_skeleton` 会失败
（熵 ≈ 7.97 bits/byte，且没有任何明文骨名）。

破解（2026-10-16，来自 `Ultimate Player Skeleton` mod 的 `meta_base_player.yft`）：

    RSC8 头 16 字节 = magic(4) + val1(4) + val2(8)
    val1 的 bit8-12 = 压缩方式（**0x1f → 不压缩；否则 +1** = Compressorid 枚举值）
        Compressorid: 0=None 1=Deflate 2=Oodle
    val2 的低 32 位 = **解压后的资源体大小 + 11**（与项目自己抽出的 vanilla 产物差 11，两边一致）
    压缩体 = 文件 [16:]，用 raw deflate（`zlib.decompressobj(-15)`）解

校验：`Ultimate Player Skeleton` 的 `meta_base_player.yft`（160,594 B, val1=0xBA）
      → val1 压缩位=0 → +1 = **1(Deflate)**；val2 低32位 = 393,227 → 解出 **393,216 B**（= 393,227−11）✅
      解出后 `find_skeleton` = (0x52e40, **1063 骨**)；881 个明文骨名 ✅

⚠️ 注意：mod/CodeX 重写过的 `.yft` **内部布局可能与 vanilla 不同**
   （实测该 mod：名字指针在骨结构 `+0x40` 直接指向串、tag 在 `+0x0a`、骨表基址也偏）
   ⇒ `yft_bind.py` 里 `bp+0x40 / +0x1a` 那套常量只对 vanilla 家族成立。

用法：
  python tools/rsc8_standalone.py <input.yft> <out.bin>
"""
import struct
import sys
import zlib
import os
import re

COMP = {0: 'None', 1: 'Deflate', 2: 'Oodle'}


def parse_header(data):
    magic, val1, val2 = struct.unpack_from('<IIQ', data, 0)
    if magic != 0x38435352:
        raise ValueError('not RSC8: %#x' % magic)
    cbits = (val1 >> 8) & 0x1F
    comp = 0 if cbits == 0x1F else cbits + 1
    return dict(magic=magic, val1=val1, val2=val2,
                resource_id=val1 & 0xFF, comp_id=comp,
                comp=COMP.get(comp, '?'),
                sys_flags=val2 & 0xFFFFFFFF, gfx_flags=(val2 >> 32) & 0xFFFFFFFF,
                stated_size=(val2 & 0xFFFFFFFF) - 11)


def decompress_file(path, out_path=None):
    """返回解压后的资源体 bytes。"""
    data = open(path, 'rb').read()
    h = parse_header(data)
    body = data[16:]
    if h['comp_id'] == 1:
        out = zlib.decompressobj(-15).decompress(body)
    elif h['comp_id'] == 2:
        raise RuntimeError('Oodle 压缩：本脚本未实现（项目里可走 tools/rdr2rpf 的 Compression.cs）')
    else:
        out = body
    if out_path:
        os.makedirs(os.path.dirname(out_path) or '.', exist_ok=True)
        open(out_path, 'wb').write(out)
    return out, h


if __name__ == '__main__':
    src = sys.argv[1]
    dst = sys.argv[2] if len(sys.argv) > 2 else None
    out, h = decompress_file(src, dst)
    print('magic=%#x resource_id=%d comp=%s(%d)' % (h['magic'], h['resource_id'], h['comp'], h['comp_id']))
    print('val2 低32=%d（约=原始大小 %d）  sysFlags=%#x gfxFlags=%#x' %
          (h['sys_flags'], h['stated_size'], h['sys_flags'], h['gfx_flags']))
    print('解出 %d 字节%s' % (len(out), (' → ' + dst) if dst else ''))
    names = re.findall(rb'[A-Za-z_][A-Za-z0-9_]{5,}', out)
    print('明文串 %d 个；样例 %s' % (len(names), [n.decode('latin1')[:20] for n in names[:5]]))
