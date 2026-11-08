# -*- coding: utf-8 -*-
"""从**运行中**的 RDR2 进程内存里提取 perschar → ped 模型 绑定表（只读）

为什么要这个工具
----------------
`init_all_sp.c` 里 950 条 `func_34(槽位, joaat("身份名"), 区, 旗标)` **只登记身份**，不含模型；
`perschars.rpf` 里只有牲畜（82 条命中，人类 0 命中）；`metapeds.ymt` 也 0 命中。
模型是运行时由引擎持有的 —— 所以只能从内存里读。

实测结构（RDR2 1491.50，2026-11-02）
-----------------------------------
perschar 记录：**步长 176 字节**，`[+0]` = 身份名哈希，`[+4]` = 模型名哈希（部分记录为空）。
`PERSCHAR::_GET_PERSCHAR_MODEL_NAME(h)` 读的就是 `[+4]`；
`PERSCHAR::_0x8BC555034A5A5E8C(h, modelHash)` 写它（脚本里 864 次，全用于帮派成员表）。

用法（游戏必须是**单人模式**且在运行）
------------------------------------
    python tools/perschar_mem_pairs.py                 # 扫描 + 写 CSV
    python tools/perschar_mem_pairs.py --dry            # 只统计不写文件
    python tools/perschar_mem_pairs.py --window 256     # 采样窗口字节数

输出：`deliverable/manifests/perschar_model_pairs.csv`
    列 = perschar / perschar_zh / model / source / model_kind / model_hash / name_match / confidence
    `confidence=high` = 内存表里的模型名与身份名吻合；`medium` = 只有内存表证据。

注意
----
- 只读（`PROCESS_VM_READ`），不写进程内存、不改游戏状态。
- 覆盖率与"当前加载了哪些区域"有关：本机实测 92 / 950。跑图/换区后再跑一次，数量会变。
- 需要 numpy（系统 Python 3.12 已装）。
"""
import argparse
import csv
import ctypes
import ctypes.wintypes as wt
import os
import re
import subprocess
import sys
import time

import numpy as np

ROOT = r'D:/BrainMaker/大镖客2解包分析'
H = os.path.join(ROOT, 'deliverable/manifests')
NAMES = os.path.join(ROOT, 'tools/rdr2rpf/bin/Release/net9.0/names.txt')
OUT = os.path.join(H, 'perschar_model_pairs.csv')

k32 = ctypes.WinDLL('kernel32', use_last_error=True)
PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010
MEM_COMMIT = 0x1000
PAGE_READABLE = (0x02, 0x04, 0x20, 0x40, 0x80)
PAGE_GUARD = 0x100
STRIDE = 176          # 实测：perschar 记录步长
MODEL_OFF = 1         # 实测：模型哈希在 [+4] = dword 索引 1


class MBI(ctypes.Structure):
    _fields_ = [('BaseAddress', ctypes.c_ulonglong), ('AllocationBase', ctypes.c_ulonglong),
                ('AllocationProtect', wt.DWORD), ('__a1', wt.DWORD),
                ('RegionSize', ctypes.c_ulonglong), ('State', wt.DWORD),
                ('Protect', wt.DWORD), ('Type', wt.DWORD), ('__a2', wt.DWORD)]


def joaat(s):
    h = 0
    for ch in s.lower().encode():
        h = (h + ch) & 0xFFFFFFFF
        h = (h + (h << 10)) & 0xFFFFFFFF
        h ^= h >> 6
    h = (h + (h << 3)) & 0xFFFFFFFF
    h ^= h >> 11
    h = (h + (h << 15)) & 0xFFFFFFFF
    return h


def find_pid(image='RDR2.exe'):
    out = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq %s' % image, '/FO', 'CSV', '/NH'],
                         capture_output=True, text=True, encoding='mbcs', errors='replace')
    for line in out.stdout.splitlines():
        if image.split('.')[0] in line:
            return int([p.strip('"') for p in line.split('","')][1])
    return 0


def load_tables():
    ps, mdl, kind = {}, {}, {}
    for r in csv.DictReader(open(os.path.join(H, 'perschar_roster.csv'), encoding='utf-8-sig')):
        ps[joaat(r['name'])] = (r['name'], r['name_zh'])
    for r in csv.DictReader(open(os.path.join(H, 'ped_model_catalog.csv'), encoding='utf-8-sig')):
        mdl[joaat(r['model'])] = (r['model'], r['package'])
        kind[r['model']] = r['kind']
    byname = {}
    if os.path.exists(NAMES):
        for line in open(NAMES, encoding='utf-8', errors='replace'):
            n = line.strip()
            if n:
                byname[joaat(n)] = n
    return ps, mdl, kind, byname


def enum_regions(h):
    k32.VirtualQueryEx.argtypes = [wt.HANDLE, ctypes.c_ulonglong, ctypes.POINTER(MBI),
                                   ctypes.c_size_t]
    k32.VirtualQueryEx.restype = ctypes.c_size_t
    regions, addr, mbi = [], 0, MBI()
    while addr < 0x7FFFFFFFFFFF:
        if not k32.VirtualQueryEx(h, addr, ctypes.byref(mbi), ctypes.sizeof(mbi)):
            break
        if (mbi.State == MEM_COMMIT and mbi.Protect in PAGE_READABLE
                and not (mbi.Protect & PAGE_GUARD) and mbi.RegionSize >= 0x10000):
            regions.append((mbi.BaseAddress, mbi.RegionSize))
        nxt = mbi.BaseAddress + mbi.RegionSize
        if nxt <= addr:
            break
        addr = nxt
    regions.sort(key=lambda r: -r[1])
    return regions


def scan(ps, window, chunk=64 * 1024 * 1024):
    pid = find_pid()
    if not pid:
        sys.exit('RDR2.exe 没在跑 —— 本工具只能对运行中的进程读内存')
    h = k32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid)
    if not h:
        sys.exit('OpenProcess 失败（err=%d）—— 游戏可能以管理员权限运行，'
                 '用同样权限的终端再试' % ctypes.get_last_error())
    print('[pid] %d  handle=%s' % (pid, bool(h)), flush=True)
    regions = enum_regions(h)
    total = sum(s for _, s in regions)
    print('[mem] %d 块 / %.2f GB 可读' % (len(regions), total / 1024 ** 3), flush=True)

    keys = np.array(sorted(ps), dtype='<u4')
    buf = ctypes.create_string_buffer(chunk)
    wbuf = ctypes.create_string_buffer(window)
    wins = []
    t0 = time.time()
    scanned = 0
    for bi, (base, size) in enumerate(regions):
        off = 0
        while off < size:
            want = min(chunk, size - off)
            n = ctypes.c_size_t(0)
            ok = k32.ReadProcessMemory(h, ctypes.c_void_p(base + off), buf, want, ctypes.byref(n))
            if ok and n.value >= 16:
                arr = np.frombuffer(buf.raw[:n.value - (n.value % 4)], dtype='<u4')
                m = np.isin(arr, keys)
                if m.any():
                    for i in np.nonzero(m)[0]:
                        a = base + off + int(i) * 4
                        nn = ctypes.c_size_t(0)
                        if k32.ReadProcessMemory(h, ctypes.c_void_p(a), wbuf, window,
                                                 ctypes.byref(nn)) and nn.value >= window:
                            wins.append(np.frombuffer(wbuf.raw[:window], dtype='<u4').copy())
            scanned += n.value if ok else 0
            off += want
        if bi % 200 == 0:
            print('  [%5.1fs] %.2f/%.2f GB, 窗口 %d'
                  % (time.time() - t0, scanned / 1024 ** 3, total / 1024 ** 3, len(wins)), flush=True)
    k32.CloseHandle(h)
    print('[done] 扫 %.2f GB / %.0fs / 窗口 %d' % (scanned / 1024 ** 3, time.time() - t0, len(wins)),
          flush=True)
    return wins


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--window', type=int, default=256, help='命中点截取窗口字节数')
    ap.add_argument('--dry', action='store_true', help='只统计，不写 CSV')
    a = ap.parse_args(argv)

    ps, mdl, kind, byname = load_tables()
    print('[keys] perschar %d / 模型 %d / names.txt %d' % (len(ps), len(mdl), len(byname)))
    wins = scan(ps, a.window)
    if not wins:
        sys.exit('没采到窗口')

    W = np.array(wins)
    rows, seen = [], set()
    for i in range(W.shape[0]):
        p = int(W[i, 0])
        m = int(W[i, MODEL_OFF])
        if p not in ps:
            continue
        mname, pkg = mdl.get(m, ('', ''))
        if not mname:
            mname, pkg = byname.get(m, ''), 'names.txt'
            if not mname:
                continue
            if mname in ('arthur', 'john', 'player_zero'):
                continue          # 玩家名字的哈希，噪声
        k = (ps[p][0], mname)
        if k in seen:
            continue
        seen.add(k)
        toks = [t for t in ps[p][0].split('_')[1:] if not t.isdigit() and len(t) > 2]
        mn = re.sub(r'[^a-z0-9]', '', mname.lower())
        conf = 'high(内存表+名字吻合)' if any(re.sub(r'[^a-z0-9]', '', t.lower()) in mn
                                          for t in toks) else 'medium(仅内存表)'
        rows.append((ps[p][0], ps[p][1], mname, pkg, kind.get(mname, ''), '0x%08X' % m, conf))

    print('[pairs] %d 条，涉及 %d 个身份 / %d 个模型'
          % (len(rows), len({r[0] for r in rows}), len({r[2] for r in rows})))
    if a.dry:
        for r in sorted(rows)[:20]:
            print('  %-32s -> %-30s %s' % (r[0], r[2], r[6][:4]))
        return
    with open(OUT, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.writer(f)
        w.writerow(['perschar', 'perschar_zh', 'model', 'source', 'model_kind', 'model_hash',
                    'confidence'])
        for r in sorted(rows):
            w.writerow([r[0], r[1], r[2], r[3], r[4], r[5], r[6]])
    print('[out] %s' % OUT)


if __name__ == '__main__':
    main()
