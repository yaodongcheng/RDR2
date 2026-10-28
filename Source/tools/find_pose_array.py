"""精确定位"活的姿态数组"（RAGE crSkeleton 的 Matrix34 阵列）。

思路：
  1) 全内存两遍 crc32 差分 → 只保留"在变"的 1 MB 块（idle 呼吸也在变）
  2) 在这些块里找 **0x30 步长、连续 ≥40 条严格旋转矩阵**（行正交 + det≈+1）
  3) 输出候选地址

用法: python tools/find_pose_array.py
"""
import ctypes
import ctypes.wintypes as wt
import math
import struct
import subprocess
import sys
import time
import zlib

k32 = ctypes.WinDLL('kernel32', use_last_error=True)
k32.VirtualQueryEx.restype = ctypes.c_size_t
k32.VirtualQueryEx.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t]
k32.OpenProcess.restype = ctypes.c_void_p
k32.OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
k32.ReadProcessMemory.restype = wt.BOOL
k32.ReadProcessMemory.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p]
k32.CloseHandle.argtypes = [ctypes.c_void_p]
READABLE = (0x02, 0x04, 0x08, 0x20, 0x40, 0x80)


class MBI(ctypes.Structure):
    _fields_ = [('BaseAddress', ctypes.c_void_p), ('AllocationBase', ctypes.c_void_p),
                ('AllocationProtect', wt.DWORD), ('RegionSize', ctypes.c_size_t),
                ('State', wt.DWORD), ('Protect', wt.DWORD), ('Type', wt.DWORD)]


def is_rot(f):
    """f = 9 floats（3x3，行优先）：行单位正交 + det≈+1"""
    r0 = f[0:3]; r1 = f[3:6]; r2 = f[6:9]
    def n(v): return math.sqrt(sum(x*x for x in v))
    for r in (r0, r1, r2):
        if abs(n(r) - 1.0) > 0.06:
            return False
    if abs(sum(a*b for a, b in zip(r0, r1))) > 0.06:
        return False
    if abs(sum(a*b for a, b in zip(r0, r2))) > 0.06:
        return False
    if abs(sum(a*b for a, b in zip(r1, r2))) > 0.06:
        return False
    det = (r0[0]*(r1[1]*r2[2]-r1[2]*r2[1])
           - r0[1]*(r1[0]*r2[2]-r1[2]*r2[0])
           + r0[2]*(r1[0]*r2[1]-r1[1]*r2[0]))
    return det > 0.85


def main():
    out = subprocess.run(['tasklist', '/FO', 'CSV', '/NH'], capture_output=True, text=True,
                         encoding='gbk', errors='replace').stdout
    pid = None
    for line in out.splitlines():
        parts = [x.strip('"') for x in line.split('","')]
        if parts and parts[0].lower() == 'rdr2.exe':
            pid = int(parts[1]); break
    if not pid:
        print('没找到 RDR2.exe'); return 1
    h = k32.OpenProcess(0x0400 | 0x0010, False, pid)
    if not h:
        print('OpenProcess 失败（要管理员）'); return 1

    def read(a, n):
        buf = ctypes.create_string_buffer(n)
        got = ctypes.c_size_t(0)
        if not k32.ReadProcessMemory(h, ctypes.c_void_p(a), buf, n, ctypes.byref(got)):
            return None
        return buf.raw[:got.value]

    regions = []
    addr, mbi = 0, MBI()
    while k32.VirtualQueryEx(h, ctypes.c_void_p(addr), ctypes.byref(mbi), ctypes.sizeof(mbi)):
        size = mbi.RegionSize
        if mbi.State == 0x1000 and mbi.Protect in READABLE and not (mbi.Protect & 0x101):
            regions.append((addr, size))
        addr += size or 0x1000
        if addr > 0x7FFFFFFFFFFF:
            break

    CH = 0x100000
    print('区域 %d；第一遍…' % len(regions))
    t0 = time.time()
    first = {}
    for base, size in regions:
        off = 0
        while off < size:
            n = min(CH, size - off)
            b = read(base + off, n)
            if b:
                first[base + off] = (n, zlib.crc32(b))
            off += n
    print('  完成 %.1fs / %d 块' % (time.time() - t0, len(first)))

    print('等 2.5 秒（idle 呼吸）…')
    time.sleep(2.5)

    t0 = time.time()
    changed = []
    for a, (n, crc) in first.items():
        b = read(a, n)
        if b and zlib.crc32(b) != crc:
            changed.append((a, n))
    print('  变化块 %d（%.1fs）' % (len(changed), time.time() - t0))

    print('\n在变化块里找 0x30 步长、≥40 条严格旋转矩阵：')
    hit = []
    for a, n in changed:
        b = read(a, n)
        if not b or len(b) < 0x30 * 40:
            continue
        # 0x30 步长的旋转矩阵（试所有起始相位 + 阈值放到 20）
        for phase in range(0, 0x30, 4):
            run = 0; best = 0; best_start = 0; start = 0
            for off in range(phase, len(b) - 0x30, 0x30):
                if is_rot(struct.unpack_from('<9f', b, off)):
                    if run == 0:
                        start = off
                    run += 1
                    if run > best:
                        best, best_start = run, start
                else:
                    run = 0
            if best >= 20:
                hit.append((a + best_start, best, 'mat34'))
        # 0x10 步长的单位四元数数组
        for phase in range(0, 0x10, 4):
            run = 0; best = 0; best_start = 0; start = 0
            for off in range(phase, len(b) - 0x10, 0x10):
                q = struct.unpack_from('<4f', b, off)
                n = sum(x*x for x in q)
                if abs(n - 1.0) < 0.02:
                    if run == 0:
                        start = off
                    run += 1
                    if run > best:
                        best, best_start = run, start
                else:
                    run = 0
            if best >= 40:
                hit.append((a + best_start, best, 'quat'))
    # 先把"接近 124 条"的挑出来（ped 骨架 124 骨；metaped 400/756）
    near = sorted([h for h in hit if 60 <= h[1] <= 900], key=lambda x: (abs(x[1]-124), -x[1]))
    if near:
        print('')
        print('  接近骨架骨数的候选（按 |n-124| 排）：')
        for a, n, kind in near[:14]:
            print('     @0x%X  %-5s 连续 %d 条' % (a, kind, n))
    hit.sort(key=lambda x: (-x[1]))
    seen = set()
    for a, n, kind in hit[:12]:
        if a in seen:
            continue
        seen.add(a)
        print('  ★ @0x%X  %-5s 连续 %d 条' % (a, kind, n))
    if not hit:
        print('  没找到。可以再跑一次（有时差分窗口正好卡在静止帧）')
    else:
        print('\n下一步：python tools/dump_live_skeleton.py --addr 0x%X --tag walklive --follow 120 --interval 0.25' % hit[0][0])
    return 0


if __name__ == '__main__':
    sys.exit(main())
