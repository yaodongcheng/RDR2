"""采集约翰走路时的运行期骨架姿态（给 .ycd 解码做 ground truth）。

流程（全自动，不需要用户卡时间）：
  1. 找到 RDR2 进程 → 定位静态骨架（0x50 步长的骨记录数组）
  2. 从"指向该数组的引用"附近收集候选指针（姿态数组通常就在骨架对象里）
  3. **一直轮询候选地址，直到发现某个地址的内容开始变化**（= 你开始动了）
  4. 一旦检测到运动，立刻开始 20Hz 高频录制
  5. 录 20 秒或你关掉窗口即结束，落盘 raw 二进制 + meta json（离线再解析）

用法（一般由「采集约翰走路.bat」调用）：
  python tools/capture_john_walk.py [--seconds 20]
"""
import argparse
import ctypes
import ctypes.wintypes as wt
import json
import os
import struct
import sys
import time

k32 = ctypes.WinDLL('kernel32', use_last_error=True)
k32.VirtualQueryEx.restype = ctypes.c_size_t
k32.VirtualQueryEx.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t]
k32.OpenProcess.restype = ctypes.c_void_p
k32.OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
k32.ReadProcessMemory.restype = wt.BOOL
k32.ReadProcessMemory.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p]
k32.CloseHandle.argtypes = [ctypes.c_void_p]

PROC_NAMES = ('rdr2.exe',)
PROBE = b'SKEL_L_Thigh'
READABLE = (0x02, 0x04, 0x08, 0x20, 0x40, 0x80)
MEM_COMMIT = 0x1000


class MBI(ctypes.Structure):
    _fields_ = [('BaseAddress', ctypes.c_void_p), ('AllocationBase', ctypes.c_void_p),
                ('AllocationProtect', wt.DWORD), ('RegionSize', ctypes.c_size_t),
                ('State', wt.DWORD), ('Protect', wt.DWORD), ('Type', wt.DWORD)]


class Proc:
    def __init__(self, pid):
        self.h = k32.OpenProcess(0x0400 | 0x0010, False, pid)
        if not self.h:
            raise RuntimeError('OpenProcess 失败：请用管理员身份运行')
        self.regions = []
        addr, mbi = 0, MBI()
        while k32.VirtualQueryEx(self.h, ctypes.c_void_p(addr), ctypes.byref(mbi), ctypes.sizeof(mbi)):
            size = mbi.RegionSize
            if (mbi.State == MEM_COMMIT and mbi.Protect in READABLE and not (mbi.Protect & 0x101)):
                self.regions.append((addr, size))
            addr += size or 0x1000
            if addr > 0x7FFFFFFFFFFF:
                break

    def read(self, a, n):
        buf = ctypes.create_string_buffer(n)
        got = ctypes.c_size_t(0)
        if not k32.ReadProcessMemory(self.h, ctypes.c_void_p(a), buf, n, ctypes.byref(got)):
            return None
        return buf.raw[:got.value]

    def u64(self, a):
        b = self.read(a, 8)
        return struct.unpack('<Q', b)[0] if b and len(b) == 8 else None

    def close(self):
        k32.CloseHandle(self.h)


def find_pid():
    import subprocess
    out = subprocess.run(['tasklist', '/FO', 'CSV', '/NH'], capture_output=True, text=True,
                         encoding='gbk', errors='replace').stdout
    for line in out.splitlines():
        parts = [x.strip('"') for x in line.split('","')]
        if parts and parts[0].lower() in PROC_NAMES:
            try:
                return int(parts[1])
            except ValueError:
                pass
    return None


def scan(p, needle, limit=64):
    hits = []
    for base, size in p.regions:
        step = min(size, 0x4000000)
        off = 0
        while off < size:
            n = min(step, size - off)
            buf = p.read(base + off, n)
            if buf:
                i = buf.find(needle)
                while i >= 0:
                    hits.append(base + off + i)
                    if len(hits) >= limit:
                        return hits
                    i = buf.find(needle, i + 1)
            off += n
    return hits


def cstr(p, a, n=48):
    b = p.read(a, n)
    if not b:
        return None
    z = b.find(b'\x00')
    if z <= 0:
        return None
    try:
        s = b[:z].decode('ascii')
    except UnicodeDecodeError:
        return None
    return s if 4 <= len(s) <= 48 and s.startswith(('SKEL_', 'PH_', 'MH_', 'OH_', 'CH_', 'ES_', 'SC_', 'XH_', 'SM_', 'CP_', 'IK_')) else None


def chain_len(p, h, maxn=400):
    """一次性读整段，按 0x50 步长数"指针链"长度。骨名指针可能分散在不同拷贝里，
    所以不做地址集中度检查，只抽查名字。"""
    buf = p.read(h, maxn * 0x50)
    if not buf or len(buf) < 0x50 * 5:
        return 0
    ptrs = []
    k = 0
    while (k + 1) * 0x50 <= len(buf):
        v = struct.unpack_from('<Q', buf, k * 0x50)[0]
        if not v or v < 0x10000:
            break
        ptrs.append(v)
        k += 1
    if len(ptrs) < 5:
        return 0
    # 抽查首/中/尾三个名字
    for idx in (0, len(ptrs)//2, len(ptrs)-1):
        if not cstr(p, ptrs[idx]):
            return 0
    return len(ptrs)


def scan_ptrs_to(p, targets, limit=4096):
    """单趟扫全内存，找出「值 ∈ targets」的 8 字节槽位（numpy 向量化，快）"""
    import numpy as np
    out = []
    tset = np.array(sorted(targets), dtype=np.uint64)
    for base, size in p.regions:
        step = min(size, 0x4000000)
        off = 0
        while off < size:
            n = min(step, size - off)
            buf = p.read(base + off, n)
            if buf and len(buf) >= 8:
                arr = np.frombuffer(buf[:len(buf) // 8 * 8], dtype='<u8')
                m = np.isin(arr, tset)
                if m.any():
                    for i in np.nonzero(m)[0]:
                        out.append(base + off + int(i) * 8)
                        if len(out) >= limit:
                            return out
            off += n
    return out


def find_bone_array(p, name_addr):
    best = None
    for h in scan(p, struct.pack('<Q', name_addr), limit=120):
        n = chain_len(p, h)
        if n >= 20 and (best is None or n > best[1]):
            best = (h, n)
    return best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--seconds', type=float, default=20.0, help='检测到运动后录多久')
    ap.add_argument('--hz', type=float, default=20.0)
    a = ap.parse_args()

    print('=' * 62)
    print(' RDR2 走路姿态采集')
    print(' 1) 现在站在空地上别动  2) 看到"检测到运动"后开始走')
    print('=' * 62)

    pid = find_pid()
    if not pid:
        print('[x] 没找到 RDR2.exe —— 先启动游戏（单人模式）再来')
        return 1
    print('[1] 进程 PID =', pid)
    p = Proc(pid)

    cache = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         'work', 'npc', 'live', 'bone_addr.txt')
    arr = count = None
    if os.path.isfile(cache):
        try:
            c = int(open(cache).read().strip(), 0)
            n = chain_len(p, c, maxn=400)
            if n >= 20:
                arr, count = c, n
                print('[2] 用缓存地址 @0x%X（%d 骨）' % (arr, count))
        except Exception:
            pass

    if arr is None:
        t0 = time.time()
        hits = scan(p, PROBE, limit=48)
        if not hits:
            print('[x] 扫不到骨名 —— 可能还在加载，等能操控角色再试')
            return 2
        print('[2] 骨名串命中 %d 处（%.1fs），找引用…' % (len(hits), time.time() - t0))
        slots = scan_ptrs_to(p, hits)
        print('    引用槽 %d 个（%.1fs），验证骨记录链…' % (len(slots), time.time() - t0))
        found = None
        for sl in slots[:256]:
            n = chain_len(p, sl)
            if n >= 20 and (found is None or n > found[1]):
                found = (sl, n)
        if not found:
            print('[x] 没定位到骨记录数组')
            return 3
        arr, count = found
        os.makedirs(os.path.dirname(cache), exist_ok=True)
        open(cache, 'w').write(hex(arr))
    # 往前扩到数组真起点
    back = 0
    while back < 16:
        n = p.u64(arr - (back + 1) * 0x50)
        if not n or not cstr(p, n):
            break
        back += 1
    arr -= back * 0x50
    count += back
    open(cache, 'w').write(hex(arr))
    print('[2] 静态骨架 @0x%X，%d 骨' % (arr, count))

    # ---- 候选：指向该数组的引用附近的所有指针
    cands = set()
    for x in scan(p, struct.pack('<Q', arr), limit=32):
        base = x - 0x200
        buf = p.read(base, 0x400)
        if not buf:
            continue
        for off in range(0, len(buf) - 8, 8):
            v = struct.unpack_from('<Q', buf, off)[0]
            if v and abs(v - arr) > 0x2000 and 0x10000 < v < 0x7FFFFFFFFFFF:
                cands.add(v)
    cands = sorted(cands)
    print('[3] 候选指针 %d 个，开始轮询等运动…' % len(cands))

    def snap(addr, n=0x2000):
        return p.read(addr, n)

    # 基线
    prev = {c: snap(c) for c in cands}

    # ---- 等运动
    hit = None
    t_wait = time.time()
    while time.time() - t_wait < 300:
        time.sleep(0.2)
        for c in cands:
            if hit and c != hit:
                continue
            cur = snap(c)
            old = prev.get(c)
            if cur and old and cur != old:
                # 变化足够多才算（排除计数器之类）
                diff = sum(1 for i in range(0, min(len(cur), len(old)), 4) if cur[i:i+4] != old[i:i+4])
                if diff >= 8:
                    hit = c
                    print('[4] ★ 检测到运动 @0x%X（%d 个 dword 变化）—— 现在开始走！' % (c, diff))
                    break
        if hit:
            break
        prev = {c: snap(c) for c in cands}
        if int(time.time() - t_wait) % 10 == 0:
            sys.stdout.write('.')
            sys.stdout.flush()

    if not hit:
        print('\n[x] 5 分钟内没检测到运动。请确认角色真的在走动（不是站桩/菜单）')
        return 4

    # ---- 录制
    outdir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          'work', 'npc', 'live')
    os.makedirs(outdir, exist_ok=True)
    ts = time.strftime('%H%M%S')
    binpath = os.path.join(outdir, 'johnwalk_%s.bin' % ts)
    metapath = os.path.join(outdir, 'johnwalk_%s.json' % ts)
    N = 0x2000
    interval = 1.0 / a.hz
    samples = []
    t_end = time.time() + a.seconds
    print('[5] 录制 %.0f 秒 @ %.0f Hz（走起来，别停）…' % (a.seconds, a.hz))
    with open(binpath, 'wb') as f:
        while time.time() < t_end:
            b = snap(hit, N)
            if b:
                f.write(b)
                samples.append(len(b))
            time.sleep(interval)
    meta = dict(pid=pid, pose_addr=hit, bone_array=arr, bone_count=count,
                bytes_per_sample=N, samples=len(samples), hz=a.hz,
                static_bone_record=0x50, note='pose array 每帧快照，离线按 0x30/0x40 stride 试解析')
    open(metapath, 'w', encoding='utf-8').write(json.dumps(meta, ensure_ascii=False, indent=2))
    print('[6] 完成：%s（%d 帧）' % (binpath, len(samples)))
    print('    meta: %s' % metapath)
    p.close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
