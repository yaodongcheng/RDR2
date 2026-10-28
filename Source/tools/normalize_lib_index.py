# -*- coding: utf-8 -*-
"""把 `assets/lib_native/index.json` 规范化：key 一律 `0x` + 8 位小写 hex，`f` 指向磁盘真实文件。

## 为什么

`dump_model_lib.write_model()` 以前用 `hex(h)` 生成路径 —— `hex()` **不补零**：
`0x04ac59bc` 写成 `0x4ac59bc.mdl`。于是 index 里出现两种 key：

    0x4ac59bc   （旧，不补零）
    0x04ac59bc  （新，补零）

两者指向同一文件，多数 hash 只是"重复一条"；但 **367 个 hash 只有不补零的那个 key**，
构建时按 `'0x%08x' % h` 查表查不到 → 明明有模型却被算成"缺模型"。
这正是最高原则 §6.4「禁丢可读信息」那个坑的复发。

## 做法（以**磁盘**为准，不信任旧 index 的记录）

1. 扫 `<lib>/<xx>/*.mdl`，从文件头（`RMDL1` + nsub + bbox + subs）重建每条记录；
2. key 用 `'0x%08x'`；`f` 用磁盘上的真实相对路径（保留旧的不补零文件名，不改文件）；
3. 贴图表 `tex` 原样保留（贴图 id 顺序不能动，动了就串号）；
4. 先备份 `index_before_normalize_<时间>.json`（已存在则不覆盖）。

    uv run python tools/normalize_lib_index.py --dry
    python tools/normalize_lib_index.py            # 需要 numpy 之外的库 → 用 python 即可
"""
import os
import re
import json
import glob
import time
import shutil
import struct
import argparse

ROOT = r'D:/BrainMaker/大镖客2解包分析'
LIB = os.path.join(ROOT, 'assets/lib_native')
INDEX = os.path.join(LIB, 'index.json')
MAGIC = b'RMDL1\x00\x00\x00'
SUB = struct.Struct('<I I I I I I I')


def read_mdl(path):
    """→ dict(b=bbox6, s=[[tid,v,n],...]) 或 None"""
    try:
        with open(path, 'rb') as f:
            head = f.read(12 + 24)
            if head[:8] != MAGIC:
                return None
            nsub = struct.unpack_from('<I', head, 8)[0]
            bb = struct.unpack_from('<6f', head, 12)
            subs = []
            if nsub:
                raw = f.read(nsub * SUB.size)
                for i in range(nsub):
                    tid, v, n = struct.unpack_from('<III', raw, i * SUB.size)
                    subs.append([tid, v, n])
    except Exception:
        return None
    return dict(b=[round(x, 3) for x in bb], s=subs)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry', action='store_true')
    a = ap.parse_args()

    old = json.load(open(INDEX, encoding='utf-8'))
    tex = old.get('tex', [])
    oldm = old['models']
    print('[norm] 旧 index：模型记录 %d，贴图 %d' % (len(oldm), len(tex)))

    byhash = {}
    for p in glob.glob(os.path.join(LIB, '*', '*.mdl')):
        name = os.path.splitext(os.path.basename(p))[0]
        if not name.lower().startswith('0x'):
            continue
        try:
            h = int(name[2:], 16)
        except ValueError:
            continue
        rec = read_mdl(p)
        if rec is None:
            continue
        rec['f'] = '%s/%s.mdl' % (os.path.basename(os.path.dirname(p)), name)
        byhash[h] = rec
    print('[norm] 磁盘可读 .mdl：%d 个唯一 hash' % len(byhash))

    before_padded = {k for k in oldm if re.fullmatch(r'0x[0-9a-f]{8}', k)}
    new = {'0x%08x' % h: rec for h, rec in byhash.items()}
    recovered = sorted(set(new) - before_padded)
    print('[norm] 旧 index 里补零 key %d；规范化后 %d；**找回 %d 个此前查不到的模型**'
          % (len(before_padded), len(new), len(recovered)))
    if recovered:
        for k in recovered[:8]:
            print('         + %s  %s' % (k, new[k]['f']))

    if a.dry:
        print('[norm] dry-run，未写盘')
        return

    bak = os.path.join(LIB, 'index_before_normalize_%s.json' % time.strftime('%Y%m%d_%H%M'))
    if not os.path.exists(bak):
        shutil.copy2(INDEX, bak)
        print('[norm] 已备份 %s' % os.path.basename(bak))
    json.dump(dict(models=new, tex=tex), open(INDEX, 'w', encoding='utf-8'),
              separators=(',', ':'))
    print('[norm] 写入 %s（%.1f MB）：模型 %d / 贴图 %d'
          % (INDEX, os.path.getsize(INDEX) / 1e6, len(new), len(tex)))


if __name__ == '__main__':
    main()
