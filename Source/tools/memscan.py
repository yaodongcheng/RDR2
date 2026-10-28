"""RDR2 运行期内存扫描器 —— 为「骨架结构」和「纹理格式」取证。

为什么需要它：
  * **骨架（P2/P3）**：`.yft` 里我们能解出父索引数组 + 骨名池，但卡在
    「FK 约定」和「索引 ↔ 骨名」的对齐。**运行期骨架是活对象**，
    骨名数组 / 父子表 / bind pose 矩阵都是现成的 —— 一次读取就能定性。
  * **纹理（P1a）**：`.ytd` 的块排布疑似 tile/swizzle，纯文件路已排除 6 类假设。
    运行期能看到**真实绑定的纹理对象**（尺寸/格式/数据指针），可一次定案。

⚠️ 前置条件
  1. **RDR2 正在运行**（单人模式；线上模式有反作弊，不要用）；
  2. **以管理员身份**运行本脚本（否则 OpenProcess 会被拒绝）；
  3. 不需要注入、不写内存，**只读**。

用法
  # 0) 环境自检 + 找到进程
  python memscan.py doctor

  # 1) 扫一个已知字符串，拿到它的虚拟地址
  python memscan.py str "SKEL_R_UpperArm"          # 骨架用（ASCII）
  python memscan.py str "SKEL_R_UpperArm" --utf16  # 若 ASCII 没命中
  python memscan.py str "nbx_wall_woodplank"       # 纹理用

  # 2) 谁指向这个地址（从字符串往回找持有者结构）
  python memscan.py ptr 0x1234abcd

  # 3) 看看某地址周围长什么样（hex + 指针解析）
  python memscan.py dump 0x1234abcd 256

  # 4) 一键取证：自动扫骨名 + 纹理名，并给出结构提示
  python memscan.py auto

输出：全部是**只读证据**（地址 / 命中 / 上下文），不修改目标进程。
"""
import argparse
import ctypes
import ctypes.wintypes as wt
import os
import struct
import sys

k32 = ctypes.WinDLL('kernel32', use_last_error=True)
# 关键：这些 API 返回 SIZE_T / HANDLE，不设 restype 会被当成 int32 截断，地址遍历会提前中断
k32.VirtualQueryEx.restype = ctypes.c_size_t
k32.VirtualQueryEx.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t]
k32.OpenProcess.restype = ctypes.c_void_p
k32.OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
k32.ReadProcessMemory.restype = wt.BOOL
k32.ReadProcessMemory.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p]
k32.CloseHandle.argtypes = [ctypes.c_void_p]
PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010
MEM_COMMIT = 0x1000
PAGE_GUARD = 0x100
PAGE_NOACCESS = 0x01
READABLE = (0x02, 0x04, 0x08, 0x20, 0x40, 0x80)  # RO/RW/WRITECOPY/EXEC_R/EXEC_RW/EXEC_WRITECOPY
PAGE_GUARDS = (0x01, 0x100)   # NOACCESS, GUARD


class MEMORY_BASIC_INFORMATION(ctypes.Structure):
    _fields_ = [("BaseAddress", ctypes.c_void_p), ("AllocationBase", ctypes.c_void_p),
                ("AllocationProtect", wt.DWORD), ("RegionSize", ctypes.c_size_t),
                ("State", wt.DWORD), ("Protect", wt.DWORD), ("Type", wt.DWORD)]


def find_pid(name_sub='RDR2.exe', want_pid=None):
    if want_pid:
        return int(want_pid), name_sub
    """枚举进程找 PID（不依赖 psutil）"""
    import subprocess
    try:
        out = subprocess.run(['tasklist', '/FO', 'CSV', '/NH'], capture_output=True,
                             text=True, timeout=30).stdout
    except Exception as e:
        print('tasklist 失败:', e); return None
    for line in out.splitlines():
        cells = [c.strip('"') for c in line.split('","')]
        if cells and name_sub.lower() in cells[0].lower():
            return int(cells[1]), cells[0]
    return None


class Proc:
    def __init__(self, pid):
        self.h = k32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid)
        if not self.h:
            raise OSError(f'OpenProcess 失败 (err={ctypes.get_last_error()}) —— 请以管理员身份运行')
        self.pid = pid

    def regions(self, max_regions=200000):
        mbi = MEMORY_BASIC_INFORMATION()
        addr = 0
        n = 0
        while n < max_regions:
            got = k32.VirtualQueryEx(self.h, ctypes.c_void_p(addr), ctypes.byref(mbi),
                                     ctypes.sizeof(mbi))
            if not got:
                break
            base = mbi.BaseAddress or 0
            size = mbi.RegionSize or 0
            if mbi.State == MEM_COMMIT and not (mbi.Protect & PAGE_GUARD) \
               and (mbi.Protect & 0xFF) in READABLE and size > 0:
                yield base, size, mbi.Protect
            addr = base + size
            n += 1
            if addr <= 0 or addr > 0x7FFFFFFFFFFF:
                break

    def read(self, addr, size):
        buf = ctypes.create_string_buffer(size)
        got = ctypes.c_size_t(0)
        ok = k32.ReadProcessMemory(self.h, ctypes.c_void_p(addr), buf, size, ctypes.byref(got))
        if not ok:
            return None
        return buf.raw[:got.value]

    def close(self):
        try: k32.CloseHandle(self.h)
        except Exception: pass


def scan_bytes(p, needle, limit_hits=40, chunk_mb=8):
    """在可读区域里扫字节串"""
    chunk = chunk_mb * 1024 * 1024
    hits = []
    scanned = 0
    for base, size, prot in p.regions():
        off = 0
        while off < size:
            n = min(chunk, size - off)
            data = p.read(base + off, n)
            if data:
                scanned += len(data)
                i = data.find(needle)
                while i >= 0:
                    hits.append(base + off + i)
                    if len(hits) >= limit_hits:
                        return hits, scanned
                    i = data.find(needle, i + 1)
            off += n
    return hits, scanned


def dump(p, addr, n):
    data = p.read(addr, n)
    if not data:
        print('  读取失败（地址不可读）'); return
    for k in range(0, len(data), 16):
        ch = data[k:k + 16]
        hx = ' '.join('%02x' % b for b in ch)
        asc = ''.join(chr(b) if 32 <= b < 127 else '.' for b in ch)
        labs = []
        for j in (0, 8):
            if k + j + 8 <= len(ch):
                q = struct.unpack_from('<Q', ch, j)[0]
                if 0x10000 <= q <= 0x7FFFFFFFFFFF:
                    labs.append('@+%x:0x%x' % (j, q))
        print(f'  {addr+k:#012x}  {hx:<48} {asc:<16} {" ".join(labs)}')


def cmd_doctor(a):
    r = find_pid(a.name, getattr(a,'pid',None))
    if not r:
        print(f'未找到进程 {a.name} —— 请先启动游戏（单人模式）')
        return 1
    pid, pname = r
    print(f'找到进程: {pname} (PID={pid})')
    try:
        p = Proc(pid)
    except OSError as e:
        print(e); return 1
    n = rgn = 0
    for base, size, prot in p.regions():
        rgn += 1; n += size
    print(f'可读区域 {rgn} 个，共 {n/2**30:.2f} GB')
    print('环境自检通过 ✅（只读，不写内存）')
    p.close()
    return 0


def cmd_str(a):
    r = find_pid(a.name, getattr(a,'pid',None))
    if not r:
        print('进程未运行'); return 1
    pid, _ = r
    p = Proc(pid)
    if a.utf16:
        needle = a.text.encode('utf-16-le')
        enc = 'UTF-16LE'
    else:
        needle = a.text.encode('latin1')
        enc = 'ASCII'
    print(f'扫描 {enc} "{a.text}" ...')
    hits, scanned = scan_bytes(p, needle, a.limit)
    print(f'扫描了 {scanned/2**30:.2f} GB，命中 {len(hits)} 处（上限 {a.limit}）')
    for h in hits:
        print(f'  {h:#014x}  「前16字节」', end=' ')
        pre = p.read(max(0, h - 16), 16)
        if pre:
            print(' '.join('%02x' % b for b in pre), end='  ')
        print()
    if hits and a.dump:
        print('\n第一处命中的上下文：')
        dump(p, max(0, hits[0] - 64), 192)
    p.close()
    return 0


def cmd_ptr(a):
    """找指向 [target-span, target] 的 8 字节指针（回溯持有者结构）"""
    r = find_pid(a.name, getattr(a, 'pid', None))
    if not r:
        print('进程未运行'); return 1
    pid, _ = r
    p = Proc(pid)
    targets = {a.addr - k: k for k in range(0, a.span, 8)}
    print(f'查找指向 {a.addr:#x} 附近（-0..-{a.span}，步进 8）的指针 ...')
    chunk = 8 * 1024 * 1024
    found = []
    _scanned = 0
    _rgn = 0
    for base, size, prot in p.regions():
        _rgn += 1
        off = 0
        while off < size:
            n = min(chunk, size - off)
            data = p.read(base + off, n)
            if data:
                n8 = (len(data) // 8) * 8
                import numpy as _np
                if n8:
                    arr = _np.frombuffer(data[:n8], dtype='<u8')
                    for tv, delta in targets.items():
                        idx = _np.nonzero(arr == tv)[0]
                        for ix in idx[:20]:
                            found.append((base + off + int(ix) * 8, delta))
                            if len(found) > 300: break
                        if len(found) > 300: break
            _scanned += len(data) if data else 0
            off += n
        if len(found) > 300: break
    print(f'扫描 {_rgn} 个区域 / {_scanned/2**30:.2f} GB，命中 {len(found)} 处')
    for fa, d in found[:40]:
        print(f'  {fa:#014x}  -> 指向 target-{d}')
    if found:
        print('--- 第一个持有者的上下文 ---')
        dump(p, max(0, found[0][0] - 64), 192)
    p.close()
    return 0


def cmd_dump(a):
    r = find_pid(a.name, getattr(a,'pid',None))
    if not r:
        print('进程未运行'); return 1
    pid, _ = r
    p = Proc(pid)
    dump(p, a.addr, a.size)
    p.close()
    return 0


BONES = ['SKEL_R_UpperArm', 'SKEL_L_UpperArm', 'SKEL_R_Calf', 'SKEL_Spine3', 'SKEL_Head']
TEXS = ['nbx_wall_woodplank', 'val_sn_ext_22', 'nbx_wall_woodpaintedoverlap']


def cmd_auto(a):
    r = find_pid(a.name, getattr(a,'pid',None))
    if not r:
        print('进程未运行 —— 请先启动游戏（单人模式），再以管理员身份运行本脚本')
        return 1
    pid, pname = r
    print(f'=== auto 取证：{pname} (PID={pid}) ===')
    p = Proc(pid)
    print('\n[1] 骨架骨名（ASCII）')
    for b in BONES:
        hits, _ = scan_bytes(p, b.encode('latin1'), 8)
        print(f'  {b:20s} 命中 {len(hits)} 处' + (f'  首个 @{hits[0]:#x}' if hits else ''))
        if hits and a.dump:
            dump(p, max(0, hits[0] - 48), 160)
    if not any(scan_bytes(p, b.encode('latin1'), 1)[0] for b in BONES[:1]):
        print('  （ASCII 没命中，试试 --utf16）')
    print('\n[2] 纹理名字符串')
    for t in TEXS:
        hits, _ = scan_bytes(p, t.encode('latin1'), 8)
        print(f'  {t:28s} 命中 {len(hits)} 处' + (f'  首个 @{hits[0]:#x}' if hits else ''))
    print('\n[3] 下一步（把结果贴回来，我来判读）')
    print('  * 骨架：对「首个骨名地址」做 ptr 回溯，找到持有点名的结构（通常是 BoneName 数组）')
    print('  * 骨架：在骨名数组附近找 u16 索引数组 / float4x4 bind pose 数组')
    print('  * 纹理：对纹理名做 ptr 回溯，找到 texture 对象 → 读它的 width/height/format/mip/dataPtr')
    p.close()
    return 0


def main():
    ap = argparse.ArgumentParser(description='RDR2 运行期内存扫描（只读）')
    ap.add_argument('--name', default='RDR2.exe', help='进程名（默认 RDR2.exe）')
    ap.add_argument('--pid', type=int, default=None, help='直接指定 PID（优先于 --name）')
    sub = ap.add_subparsers(dest='cmd', required=True)
    d = sub.add_parser('doctor'); d.set_defaults(f=cmd_doctor)
    s = sub.add_parser('str'); s.add_argument('text'); s.add_argument('--utf16', action='store_true')
    s.add_argument('--limit', type=int, default=40); s.add_argument('--dump', action='store_true', default=True)
    s.set_defaults(f=cmd_str)
    q = sub.add_parser('ptr'); q.add_argument('addr', type=lambda x: int(x, 0))
    q.add_argument('--span', type=int, default=256); q.set_defaults(f=cmd_ptr)
    m = sub.add_parser('dump'); m.add_argument('addr', type=lambda x: int(x, 0))
    m.add_argument('size', type=int, nargs='?', default=256); m.set_defaults(f=cmd_dump)
    au = sub.add_parser('auto'); au.add_argument('--dump', action='store_true', default=True)
    au.set_defaults(f=cmd_auto)
    a = ap.parse_args()
    sys.exit(a.f(a))


if __name__ == '__main__':
    main()
