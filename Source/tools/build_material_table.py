# -*- coding: utf-8 -*-
"""生成「材质 → albedo / normal / ma」对照表（三件套的真实关系）。

为什么需要：
  `textures/alb|nm|ma/` 三个目录是**按贴图角色**去重的产物（10,319 / 6,495 / 5,690 张），
  不是「一张 albedo 对应一张 nm + 一张 ma」。材质槽里三张图是**独立可选**的：
  缺法线、缺高光、只用 albedo 的槽位大量存在；同一张图也会被多个材质共用。
  所以「三件套」的正确视图是**材质表**，不是目测三个目录的数量。

输入：
  assets/lib_native/index.json             模型 → 子网格 texId / st(nm,ma)
  deliverable/manifests/asset_import_models.csv   import=1 的模型

输出：
  deliverable/manifests/material_textures.csv
      material / albedo / normal / ma / models / slots / status
      同名多张时用 `|` 连接；无 albedo 的槽位归到 `no_tex`。

用法：
    python tools/build_material_table.py
"""
import csv
import collections
import io
import json
import os

RDR2 = r'D:/BrainMaker/大镖客2解包分析'
LIB = os.path.join(RDR2, 'assets/lib_native')
MANIFESTS = os.path.join(RDR2, 'deliverable/manifests')
INDEX = os.path.join(LIB, 'index.json')
IMPORT = os.path.join(MANIFESTS, 'asset_import_models.csv')
OUT = os.path.join(MANIFESTS, 'material_textures.csv')


def main():
    idx = json.load(io.open(INDEX, encoding='utf-8'))
    models, tex = idx['models'], idx['tex']
    rows = [r for r in csv.DictReader(io.open(IMPORT, encoding='utf-8-sig'))
            if r.get('import') == '1']

    mats = collections.defaultdict(lambda: {
        'alb': set(), 'nm': set(), 'ma': set(), 'models': set(), 'slots': 0})

    for r in rows:
        h = r.get('model_hash') or ''
        m = models.get(h)
        if not m:
            continue
        st = m.get('st') or []
        for i, sub in enumerate(m.get('s') or []):
            if not sub:
                continue
            tid = sub[0]
            alb = tex[tid]['n'] if isinstance(tid, int) and 0 <= tid < len(tex) else ''
            nt = mt = -1
            if i < len(st) and st[i]:
                nt, mt = st[i][0], st[i][1]
            nm = tex[nt]['n'] if isinstance(nt, int) and 0 <= nt < len(tex) else ''
            ma = tex[mt]['n'] if isinstance(mt, int) and 0 <= mt < len(tex) else ''
            key = alb or 'no_tex'
            e = mats[key]
            e['alb'].add(alb)
            e['nm'].add(nm)
            e['ma'].add(ma)
            e['models'].add(h)
            e['slots'] += 1

    def joined(s):
        return '|'.join(sorted(x for x in s if x))

    out = []
    counts = collections.Counter()
    for name in sorted(mats):
        e = mats[name]
        a, n, m = joined(e['alb']), joined(e['nm']), joined(e['ma'])
        if a and n and m:
            status = 'all3'
        elif a and n:
            status = 'alb+nm'
        elif a and m:
            status = 'alb+ma'
        elif a:
            status = 'alb only'
        else:
            status = 'no alb'
        counts[status] += 1
        out.append([name, a, n, m, len(e['models']), e['slots'], status])

    with io.open(OUT, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f)
        w.writerow(['material', 'albedo', 'normal', 'ma', 'models', 'slots', 'status'])
        w.writerows(out)
    print('materials %d -> %s' % (len(out), OUT))
    print('status:', dict(counts))


if __name__ == '__main__':
    main()
