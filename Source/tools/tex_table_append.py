# -*- coding: utf-8 -*-
"""给贴图表**追加**新名字（不重排已有 id），用于 `.ydd` 入库那批模型。

## 为什么需要

贴图表（`id = 名字排序下标`）当初只收 `.ydr/.yft` 源模型引用的 11,515 个名字。
之后从 `.ydd` 补进来的 3,229 个模型里有 57% 的子网格名字不在表里 ——
它们不是"没图"，只是**当时没进表**（抽样 44 个名字：27 个能在 ytd 索引里找到）。

## 做法

**只追加**：新名字按排序追加到 `tex` 末尾，`id` 从现有长度开始 → 已有 id 全部不变，
所以不需要重排、也不需要重写别的模型的 `.mdl`；只要把用到的模型重挂一次即可。

    python tools/tex_table_append.py --names work/needed_ydd_names.json --dry
    python tools/tex_table_append.py --names work/needed_ydd_names.json
"""
import os
import sys
import json
import time
import shutil
import argparse
import struct

ROOT = r'D:/BrainMaker/大镖客2解包分析'
sys.path.insert(0, os.path.join(ROOT, 'tools'))

LIB = os.path.join(ROOT, 'assets/lib_native')
INDEX = os.path.join(LIB, 'index.json')
TEXIDX = os.path.join(ROOT, 'work/tex_name_index.json')
IDS = os.path.join(ROOT, 'work/tex_name_ids.json')
MAXS = 512


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--names', required=True, help='要追加的名字清单 JSON（list 或 {"names": [...]}）')
    ap.add_argument('--dry', action='store_true')
    a = ap.parse_args()

    import rdr2_ytd as T
    from ytd_to_png import decode_one
    from PIL import Image

    d = json.load(open(INDEX, encoding='utf-8'))
    tex = d['tex']
    have = {t['n']: t['id'] for t in tex}
    ytd = json.load(open(TEXIDX, encoding='utf-8'))

    raw = json.load(open(a.names, encoding='utf-8'))
    names = raw['names'] if isinstance(raw, dict) else raw
    names = sorted({str(n).strip().lower() for n in names if str(n).strip()})
    todo = [n for n in names if n not in have]
    in_ytd = [n for n in todo if n in ytd]
    print('[ap] 候选 %d / 已在表 %d / 待追加 %d / 其中 ytd 有图 %d'
          % (len(names), len(names) - len(todo), len(todo), len(in_ytd)))
    if not in_ytd:
        print('[ap] 没有可追加的')
        return
    if a.dry:
        print('[ap] dry-run，未写盘；样例 %s' % in_ytd[:8])
        return

    bak = os.path.join(LIB, 'index_before_append_%s.json' % time.strftime('%Y%m%d_%H%M'))
    if not os.path.exists(bak):
        shutil.copy2(INDEX, bak)
        print('[ap] 备份 %s' % os.path.basename(bak))

    texdir = os.path.join(LIB, 'tex')
    ok = fail = 0
    cache = {}
    for nm in in_ytd:
        e = ytd[nm]
        fp = os.path.join(ROOT, e['f'])
        try:
            if fp not in cache:
                cache[fp] = open(fp, 'rb').read()
            data = cache[fp]
            blob = data[16 + e['sys'] + e['gfx']:]
            blob = blob[:max(4096, e['w'] * e['h'] * 4)]
            im, _fmt = decode_one(blob, e['w'], e['h'], e['fmt'])
        except Exception:
            im = None
        if im is None:
            fail += 1
            continue
        if max(im.size) > MAXS:
            im = im.resize((MAXS, MAXS), Image.LANCZOS)
        if im.mode not in ('RGB', 'RGBA'):
            im = im.convert('RGB')
        tid = len(tex)
        im.save(os.path.join(texdir, '%05d.png' % tid), 'PNG', optimize=False)
        tex.append({'id': tid, 'n': nm, 'f': 'tex/%05d.png' % tid})
        have[nm] = tid
        ok += 1

    d['tex'] = tex
    d['tex_epoch'] = time.strftime('%Y%m%d')
    json.dump(d, open(INDEX, 'w', encoding='utf-8'), separators=(',', ':'))
    ids = {'__epoch__': d['tex_epoch']}
    ids.update(have)
    json.dump(ids, open(IDS, 'w', encoding='utf-8'), separators=(',', ':'))
    print('[ap] 追加 %d 张（失败 %d）→ 贴图表 %d 条' % (ok, fail, len(tex)))


if __name__ == '__main__':
    main()
