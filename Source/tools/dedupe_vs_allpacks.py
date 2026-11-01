# -*- coding: utf-8 -*-
"""去重：把某个目录下**已经在 `raw/all_packs` 里有逐字节副本**的文件删掉。

判据（两段式，避免误删）：
    1. 文件名 + 字节数 完全相同 → 候选
    2. 对候选做 MD5，真相同才进删除清单

默认只打印清单，不动盘；`--apply` 才真删。删完写 `work/dedupe_<目录名>.json` 作为凭据。

用法：
    python tools/dedupe_vs_allpacks.py raw/towns                 # 只看
    python tools/dedupe_vs_allpacks.py raw/towns --apply         # 真删
    python tools/dedupe_vs_allpacks.py raw/npc --exts ytd --ref raw/lib_gtxd/txd_game
    python tools/dedupe_vs_allpacks.py raw/ann --apply

`--ref` 默认是 `raw/all_packs`；清理「与非 levels 包重复」的目录时改成对应池（如 `txd_game`）。

安全：`raw/all_packs` 本身、以及任何包含它的目录都不能作为 `--target`。
"""
import os
import sys
import json
import time
import hashlib
import argparse
from collections import defaultdict

ROOT = r'D:/BrainMaker/大镖客2解包分析'
PACKS = os.path.join(ROOT, 'raw/all_packs')
WORK = os.path.join(ROOT, 'work')


_CACHE = {}


def md5(path, buf=1 << 20):
    """带缓存：同一批候选会被多个目标重复比对，不缓存会退化成 O(n²)。"""
    d = _CACHE.get(path)
    if d is not None:
        return d
    h = hashlib.md5()
    with open(path, 'rb') as fh:
        for chunk in iter(lambda: fh.read(buf), b''):
            h.update(chunk)
    _CACHE[path] = h.digest()
    return _CACHE[path]


def build_index(ref):
    idx = defaultdict(list)
    n = 0
    for dp, _, fs in os.walk(ref):
        for f in fs:
            p = os.path.join(dp, f)
            try:
                idx[(f.lower(), os.path.getsize(p))].append(p)
                n += 1
            except OSError:
                pass
    print('[dedupe] 参照树 %s：%d 个文件 / %d 组' % (ref, n, len(idx)))
    return idx


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('target', help='要清理的目录（相对项目根或绝对路径）')
    ap.add_argument('--ref', default=PACKS, help='参照树，默认 raw/all_packs')
    ap.add_argument('--exts', nargs='*', default=None, help='只处理这些扩展名，如 ytd ydr')
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--json', default='')
    a = ap.parse_args()

    target = a.target if os.path.isabs(a.target) else os.path.join(ROOT, a.target)
    target = os.path.abspath(target)
    if os.path.abspath(PACKS).startswith(target.rstrip('\\/') + os.sep) or target == os.path.abspath(PACKS):
        print('[dedupe] 拒绝对 all_packs 本身或其父目录操作')
        return 2
    if not os.path.isdir(target):
        print('[dedupe] 目录不存在：%s' % target)
        return 2

    ref = a.ref if os.path.isabs(a.ref) else os.path.join(ROOT, a.ref)
    exts = [('.' + e.lower().lstrip('.')) for e in a.exts] if a.exts else None
    idx = build_index(ref)

    todo, bytes_, tested, skipped = [], 0, 0, 0
    t0 = time.time()
    for dp, _, fs in os.walk(target):
        for f in fs:
            p = os.path.join(dp, f)
            if exts and not any(f.lower().endswith(e) for e in exts):
                continue
            try:
                size = os.path.getsize(p)
            except OSError:
                continue
            cand = idx.get((f.lower(), size))
            if not cand:
                continue
            tested += 1
            if tested % 2000 == 0:
                print('[..] 已比对 %d，可删 %d（%.1f GB），%.0f 秒'
                      % (tested, len(todo), bytes_ / 2**30, time.time() - t0))
            try:
                d = md5(p)
                if not any(md5(c) == d for c in cand if c != p):
                    continue
            except OSError:
                skipped += 1
                continue
            todo.append(p)
            bytes_ += size

    print('[dedupe] %s：扫描候选 %d，可删 %d 个 / %.2f GB（%.0f 秒）'
          % (target, tested, len(todo), bytes_ / 2**30, time.time() - t0))
    for p in todo[:10]:
        print('    ', p[len(ROOT) + 1:])
    if len(todo) > 10:
        print('     …… 另外 %d 个' % (len(todo) - 10))

    report = dict(target=target, files=len(todo), bytes=bytes_,
                  exts=exts, applied=bool(a.apply), list=todo)
    out = a.json or os.path.join(WORK, 'dedupe_%s.json' % os.path.basename(target.rstrip('\\/')))
    if a.apply:
        freed = 0
        for p in todo:
            try:
                sz = os.path.getsize(p)
                os.remove(p)
                freed += sz
            except OSError as e:
                print('    删除失败 %s: %s' % (p, e))
        print('[dedupe] 已删 %d 个 / %.2f GB' % (len(todo), freed / 2**30))
    else:
        print('[dedupe] 未删除（加 --apply 才真删）')
    json.dump(report, open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('[dedupe] 清单写入 %s' % out)
    return 0


if __name__ == '__main__':
    sys.exit(main())
