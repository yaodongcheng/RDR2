# -*- coding: utf-8 -*-
"""不开 Blender 的两层材质体检：`index.json` 里的 `lyr` / `ch` 覆盖得怎么样。

    python tools/audit_two_layers.py
    python tools/audit_two_layers.py --hash 0x3c588f25     # 只看一个模型

打印（判据都在数字里，不需要开 Blender）：
  · 有多少模型/槽位带上了第 1 层、控制图、土
  · 权重来源分布：`ctrl.<通道>` 多少个槽、`l1.alpha` 多少个槽、无来源（退回单层）多少个
  · 池子里缺文件的（`-1` 或文件不存在）有多少
"""
import argparse
import json
import os
import sys
from collections import Counter

ROOT = r'D:/BrainMaker/大镖客2解包分析'
LIB = os.path.join(ROOT, 'assets/lib_native')
INDEX = os.path.join(LIB, 'index.json')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--hash', default='')
    ap.add_argument('--lib', default=LIB)
    a = ap.parse_args()

    idx = json.load(open(os.path.join(a.lib, 'index.json'), encoding='utf-8'))
    models, tex = idx['models'], idx['tex']
    table = {}
    for t in tex:
        table[int(t['id'])] = t

    def exists(tid):
        e = table.get(tid) if tid is not None and tid >= 0 else None
        return bool(e) and os.path.exists(os.path.join(a.lib, e.get('f') or ''))

    hashes = [a.hash] if a.hash else list(models.keys())
    c = Counter()
    chdist = Counter()
    miss = Counter()
    for h in hashes:
        m = models.get(h)
        if not m:
            continue
        ly = m.get('lyr') or []
        if not ly:
            c['models_no_lyr'] += 1
            continue
        c['models_with_lyr'] += 1
        any_usable = False
        for row in ly:
            if not row:
                continue
            l1, ct, dt, n2, m2 = (list(row) + [-1] * 5)[:5]
            c['slots'] += 1
            if l1 >= 0:
                c['slots_l1'] += 1
                if not exists(l1):
                    miss['l1'] += 1
            if ct >= 0:
                c['slots_ctrl'] += 1
                if not exists(ct):
                    miss['ctrl'] += 1
            if dt >= 0:
                c['slots_dirt'] += 1
                if not exists(dt):
                    miss['dirt'] += 1
            if n2 >= 0:
                c['slots_nm2'] += 1
            if m2 >= 0:
                c['slots_ma2'] += 1
            # 权重来源（与 mat_rdr2._layer_weight 同一套判定）
            if l1 < 0 or not exists(l1):
                continue
            if ct >= 0 and exists(ct):
                ch = table[int(ct)].get('ch', -1)
                if ch is not None and ch >= 0:
                    chdist['ctrl.%s' % ('RGBA'[ch])] += 1
                    any_usable = True
                    continue
            ch1 = table[int(l1)].get('ch', -1)
            if ch1 == 3:
                chdist['l1.alpha'] += 1
                any_usable = True
            else:
                chdist['(无权重→单层)'] += 1
        if any_usable:
            c['models_usable'] += 1

    print('[两层] 模型 %d（查询范围内）' % len(hashes))
    for k in ('models_with_lyr', 'models_usable', 'models_no_lyr', 'slots',
              'slots_l1', 'slots_ctrl', 'slots_dirt', 'slots_nm2', 'slots_ma2'):
        if c[k]:
            print('   %-16s %d' % (k, c[k]))
    print('[两层] 权重来源：%s' % dict(chdist))
    if miss:
        print('[两层] ⚠ 池子里缺文件：%s' % dict(miss))
    else:
        print('[两层] 池子文件齐全（引用的 id 都能找到 PNG）')
    if a.hash:
        for row in (models.get(a.hash, {}).get('lyr') or [])[:8]:
            if not row:
                continue
            names = []
            for tid in row:
                e = table.get(int(tid)) if tid is not None and tid >= 0 else None
                names.append((e or {}).get('n', '-'))
            print('   lyr =', names)


if __name__ == '__main__':
    main()
