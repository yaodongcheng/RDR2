"""运行期骨架取证：从《荒野大镖客2》进程里 dump 一份**当前姿态**的骨架（局部四元数）。

为什么需要它
------------
`.ycd` 里存的是「相对动画参考骨架 rest 的增量」，但我们手上只有 `meta_base_player.yft` 的 bind，
两者的骨朝向不一致 ⇒ 解出来的动作怎么修都别扭。跑一次运行期 dump 就能拿到**游戏真正在用的
rest/当前姿态**（局部旋转），把它当源骨架做「世界增量重定向」，链路就和已验证过的
UE→RDR2 一样可靠。

布局（由历史 dump `export/skeleton_runtime/skel_full.tsv` 的 raw80 反推）
  bone 记录 = 0x50 字节：
    +0x00 char*  骨名
    +0x20 float4 局部四元数 (x,y,z,w)
    +0x30 float3 位置
    +0x40 float4 scale
  骨记录数组按 0x50 步长连续排列，骨名指针指向名字池里的 "SKEL_xxx" 等字符串。

用法（**需要管理员权限**，游戏要在单人模式运行）
  python tools/dump_live_skeleton.py                 # 自动找进程 + 找骨架 + dump
  python tools/dump_live_skeleton.py --tag idle      # 存成 work/npc/live/idle_<时间>.tsv
输出: work/npc/live/<tag>_<HHMMSS>.tsv
"""
import argparse
import ctypes
import math
import ctypes.wintypes as wt
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
PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010
MEM_COMMIT = 0x1000
PAGE_GUARD = 0x100
PAGE_NOACCESS = 0x01
READABLE = (0x02, 0x04, 0x08, 0x20, 0x40, 0x80)
PAGE_GUARDS = (0x01, 0x100)

PROC_NAMES = ('RDR2.exe', 'rdr2.exe')
PROBE = b'SKEL_L_Thigh'


class MBI(ctypes.Structure):
    _fields_ = [('BaseAddress', ctypes.c_void_p), ('AllocationBase', ctypes.c_void_p),
                ('AllocationProtect', wt.DWORD), ('RegionSize', ctypes.c_size_t),
                ('State', wt.DWORD), ('Protect', wt.DWORD), ('Type', wt.DWORD)]


class Proc:
    def __init__(self, pid):
        self.h = k32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid)
        if not self.h:
            raise RuntimeError('OpenProcess 失败（需要管理员权限）')
        self.regions = self._regions()

    def _regions(self):
        out = []
        addr = 0
        mbi = MBI()
        while k32.VirtualQueryEx(self.h, ctypes.c_void_p(addr), ctypes.byref(mbi), ctypes.sizeof(mbi)):
            size = mbi.RegionSize
            if (mbi.State == MEM_COMMIT and mbi.Protect in READABLE
                    and not (mbi.Protect & 0x101)):
                out.append((addr, size))
            addr += size or 0x1000
            if addr > 0x7FFFFFFFFFFF:
                break
        return out

    def read(self, addr, n):
        buf = ctypes.create_string_buffer(n)
        got = ctypes.c_size_t(0)
        if not k32.ReadProcessMemory(self.h, ctypes.c_void_p(addr), buf, n, ctypes.byref(got)):
            return None
        return buf.raw[:got.value]

    def u64(self, addr):
        b = self.read(addr, 8)
        return struct.unpack('<Q', b)[0] if b and len(b) == 8 else None

    def close(self):
        k32.CloseHandle(self.h)


def find_pid():
    import subprocess
    out = subprocess.run(['tasklist', '/FO', 'CSV', '/NH'], capture_output=True, text=True,
                         encoding='gbk', errors='replace').stdout
    for line in out.splitlines():
        parts = [x.strip('"') for x in line.split('","')]
        if parts and parts[0].lower() in [p.lower() for p in PROC_NAMES]:
            return int(parts[1])
    return None


def scan(p, needle, limit=64):
    hits = []
    for base, size in p.regions:
        if size > 0x8000000:      # 大块分片读
            step = 0x8000000
        else:
            step = size
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


def cstr(p, addr, n=48):
    b = p.read(addr, n)
    if not b:
        return None
    z = b.find(b'\x00')
    if z <= 0:
        return None
    try:
        s = b[:z].decode('ascii')
    except UnicodeDecodeError:
        return None
    return s


def looks_like_bone_name(s):
    if not s or len(s) < 4 or len(s) > 48:
        return False
    return s.startswith(('SKEL_', 'PH_', 'MH_', 'OH_', 'CH_', 'ES_', 'SC_', 'XH_', 'SM_',
                         'CP_', 'IK_', 'RB_', 'AB_', 'FB_'))


def find_bone_array(p, name_addr):
    """在指向骨名的指针里，找一条"步长 0x50、连续多条 +0x00 都指向骨名"的记录链。"""
    best = None
    ptr = struct.pack('<Q', name_addr)
    hits = scan(p, ptr, limit=200)
    for h in hits:
        # h 可能是 记录+0x00，也可能是别的结构；从 h 开始按 0x50 往后数记录
        ok = 0
        nms = []
        for k in range(200):
            a = h + k * 0x50
            nxt = p.u64(a)
            if not nxt:
                break
            s = cstr(p, nxt)
            if not looks_like_bone_name(s):
                break
            ok += 1
            nms.append(s)
        if ok >= 20 and (best is None or ok > best[1]):
            best = (h, ok, nms)
    return best


def find_animated(p, a):
    """扫描所有"0x50 步长 + 骨名指针"的候选数组，各读两次，挑出会变化的那些。"""
    addrs = scan(p, PROBE, limit=64)
    print('骨名命中 %d 处' % len(addrs))
    cands = []
    for na in addrs:
        ptr = struct.pack('<Q', na)
        for h in scan(p, ptr, limit=200):
            ok = 0
            while ok < 400:
                n = p.u64(h + ok * 0x50)
                if not n or not looks_like_bone_name(cstr(p, n)):
                    break
                ok += 1
            if ok >= 20:
                cands.append((h, ok))
    # 去重（相邻偏移可能指向同一数组内部）
    cands.sort()
    uniq = []
    for arr, n in cands:
        if uniq and arr < uniq[-1][0] + uniq[-1][1] * 0x50:
            if n > uniq[-1][1]:
                uniq[-1] = (arr, n)
            continue
        uniq.append((arr, n))
    print('候选骨架数组 %d 个' % len(uniq))

    def snap(arr, n):
        out = []
        for k in range(n):
            base = arr + k * 0x50
            nm = cstr(p, p.u64(base))
            raw = p.read(base + 0x20, 0x10)
            if not nm or not raw or len(raw) < 0x10:
                out.append(None)
            else:
                out.append(struct.unpack('<4f', raw))
        return out

    A = [(arr, n, snap(arr, n)) for arr, n in uniq]
    time.sleep(1.0)
    best = None
    for arr, n, s0 in A:
        s1 = snap(arr, n)
        moved = 0
        mx = 0.0
        for q0, q1 in zip(s0, s1):
            if not q0 or not q1:
                continue
            d = abs(sum(x*y for x, y in zip(q0, q1)))
            ang = math.degrees(2 * math.acos(min(1.0, d)))
            if ang > 0.5:
                moved += 1
            mx = max(mx, ang)
        if moved:
            print('  0x%X  %d 骨 → %d 根在动，最大 %.1f°' % (arr, n, moved, mx))
            if best is None or mx > best[2]:
                best = (arr, n, mx)
        else:
            print('  0x%X  %d 骨 → 静止（rest 模板）' % (arr, n))
    if best:
        print('★ 会动的骨架 @0x%X（%d 骨，最大 %.1f°）')
        print('   连拍: --addr 0x%X --tag walklive --follow 60 --interval 0.2' % (best[0], best[1], best[2], best[0]))
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--tag', default='live')
    ap.add_argument('--pid', type=int, default=None)
    ap.add_argument('--addr', default=None, help='已知的骨记录数组地址（跳过扫描，秒出）')
    ap.add_argument('--find-animated', action='store_true',
                    help='找出"会动"的骨架数组（静态的只是 rest 模板）')
    ap.add_argument('--follow', type=int, default=0, help='连续采样帧数（配合 --interval）')
    ap.add_argument('--interval', type=float, default=0.05, help='采样间隔秒')
    a = ap.parse_args()

    pid = a.pid or find_pid()
    if not pid:
        print('没找到 RDR2.exe —— 请先启动游戏（单人模式）再跑本脚本')
        return 1
    print('PID =', pid)
    p = Proc(pid)
    print('可读内存块 %d 个' % len(p.regions))

    if a.find_animated:
        return find_animated(p, a)
    if a.addr:
        arr = int(a.addr, 0)
        # 只校验数组还能读
        n0 = p.u64(arr)
        nm0 = cstr(p, n0) if n0 else None
        if not looks_like_bone_name(nm0):
            print('--addr 处的骨记录读不到（可能重启过游戏），改用扫描')
            a.addr = None
    if not a.addr:
        t0 = time.time()
        addrs = scan(p, PROBE, limit=8)
        print('骨名字符串命中 %d 处 (%s)' % (len(addrs), '%.1fs' % (time.time() - t0)))
        if not addrs:
            print('没扫到骨名 —— 可能还在加载，等进到游戏里（能操控角色）再试')
            return 2

    if not a.addr:
        found = None
        for na in addrs:
            r = find_bone_array(p, na)
            if r and (found is None or r[1] > found[2]):
                found = (na, r[0], r[1])
        if not found:
            print('找到了骨名，但没定位到 0x50 步长的骨记录数组')
            return 3
        name_addr, arr, count = found
        # ★ 找到的可能是数组**中间**（实测从 SKEL_L_Thigh 开始，前面还有 ROOT/Spine_Root/Pelvis）
        #   往前扩，直到名字不像骨名为止
        back = 0
        while back < 16:
            n = p.u64(arr - (back + 1) * 0x50)
            if not n or not looks_like_bone_name(cstr(p, n)):
                break
            back += 1
        if back:
            arr -= back * 0x50
            count += back
        # 往后继续数
        k = count
        while k < 400:
            n = p.u64(arr + k * 0x50)
            if not n or not looks_like_bone_name(cstr(p, n)):
                break
            k += 1
        count = k
        print('骨记录数组 @0x%X，共 %d 条（前扩 %d；下次可用 --addr 0x%X 秒读）'
              % (arr, count, back, arr))
    else:
        # 用已知地址，数一下连续多少条
        count = 0
        while count < 400:
            n = p.u64(arr + count * 0x50)
            if not n or not looks_like_bone_name(cstr(p, n)):
                break
            count += 1
        print('沿用 --addr 0x%X，连续 %d 条' % (arr, count))

    outdir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          'work', 'npc', 'live')
    os.makedirs(outdir, exist_ok=True)
    out = os.path.join(outdir, '%s_%s.tsv' % (a.tag, time.strftime('%H%M%S')))

    def grab():
        rr = []
        for k in range(count):
            base = arr + k * 0x50
            np_ = p.u64(base)
            nm = cstr(p, np_)
            if not nm:
                continue
            raw = p.read(base + 0x20, 0x20)
            if not raw or len(raw) < 0x20:
                continue
            q = struct.unpack_from('<4f', raw, 0)
            pos = struct.unpack_from('<3f', raw, 0x10)
            rr.append((k, nm, q, pos))
        return rr

    if a.follow and a.follow > 1:
        # 连续采样：定位后每次只读 ~10 KB（毫秒级），可以跟住移动中的姿态
        rows = ['sample\tindex\tname\tquat_x\tquat_y\tquat_z\tquat_w\tpos_x\tpos_y\tpos_z']
        t0 = time.time()
        for si in range(a.follow):
            for k, nm, q, pos in grab():
                rows.append('%d\t%d\t%s\t%.6f\t%.6f\t%.6f\t%.6f\t%.6f\t%.6f\t%.6f'
                            % (si, k, nm, q[0], q[1], q[2], q[3], pos[0], pos[1], pos[2]))
            time.sleep(a.interval)
        open(out, 'w', encoding='utf-8', newline='\n').write('\n'.join(rows) + '\n')
        print('写出 %s（%d 次采样 × %d 骨，用时 %.1fs）' % (out, a.follow, count, time.time() - t0))
        p.close()
        return 0

    rows = ['index\tname\tquat_x\tquat_y\tquat_z\tquat_w\tpos_x\tpos_y\tpos_z']
    for k, nm, q, pos in grab():
        rows.append('%d\t%s\t%.6f\t%.6f\t%.6f\t%.6f\t%.6f\t%.6f\t%.6f'
                    % (k, nm, q[0], q[1], q[2], q[3], pos[0], pos[1], pos[2]))
    open(out, 'w', encoding='utf-8', newline='\n').write('\n'.join(rows) + '\n')
    print('写出 %s（%d 骨）' % (out, len(rows) - 1))
    p.close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
