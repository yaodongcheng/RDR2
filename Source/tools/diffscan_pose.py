"""内存差分扫描：找出"会变化"的那块内存 —— 用来定位**活的姿态数组**。

背景：我们能找到的骨架数组（0x50 步长、带骨名）都是**静态 rest 模板**（连拍零变化）；
真正在动的姿态数组不带骨名，只能靠"它一直在变"这个特征找。
idle 有呼吸 ⇒ 活的姿态数组每次采样都会有微小变化。

做法：把可读内存按 1 MB 分块各算一次 crc32 → 等 2 秒 → 再算一次 → 列出变化的块，
      再在变化的块里找"0x30 步长、连续 3x3 正交矩阵"的候选（RAGE Matrix34 = 48 字节）。

用法: python tools/diffscan_pose.py
"""
import ctypes
import ctypes.wintypes as wt
import struct
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


def main():
    import subprocess
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
    print('区域 %d 个，开始第一遍…' % len(regions))
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
    print('第一遍完成（%.1fs，%d 块）' % (time.time() - t0, len(first)))

    print('等 2 秒（让 idle 呼吸产生变化）…')
    time.sleep(2.0)

    t0 = time.time()
    changed = []
    for a, (n, crc) in first.items():
        b = read(a, n)
        if b and zlib.crc32(b) != crc:
            changed.append((a, n))
    print('第二遍完成（%.1fs），变化块 %d 个' % (time.time() - t0, len(changed)))

    # 在变化的块里找 RAGE Matrix34 阵列：0x30 步长、连续多行的旋转矩阵
    def looks_like_rot(b, off):
        if off + 36 > len(b):
            return False
        f = struct.unpack_from('<9f', b, off)
        if any(abs(x) > 2.0 for x in f):
            return False
        # 每行长度≈1
        for r in range(3):
            ln = f[r*3]**2 + f[r*3+1]**2 + f[r*3+2]**2
            if not (0.8 < ln < 1.25):
                return False
        return True

    print('\n候选（0x30 步长的旋转矩阵阵列）：')
    for a, n in changed:
        b = read(a, n)
        if not b:
            continue
        run = 0; best = 0; best_off = 0
        for off in range(0, len(b) - 0x30 * 4, 0x30):
            if looks_like_rot(b, off):
                run += 1
                if run > best:
                    best, best_off = run, off - (run - 1) * 0x30
            else:
                run = 0
        if best >= 8:
            print('  @0x%X  连续 %d 行 起始偏移 0x%X  块大小 0x%X' % (a, best, best_off, n))
    print('\n提示：把上面地址那块的起始 = 0x地址+偏移 记下来，就能连拍解析。')
    return 0


if __name__ == '__main__':
    sys.exit(main())
