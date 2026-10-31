# -*- coding: utf-8 -*-
"""三贴图（漫反射 / 法线 / 高光）覆盖审计 —— 不开 Blender。

读 `assets/lib_native/index.json` 与 43 个地块实例表，给出：
  · 槽位级：`s` 有多少槽有 albedo，`st` 有多少槽有法线/高光
  · 实例加权：场上真正会看到的槽位覆盖
  · 贴图池：按 role 分组计数、文件是否都在磁盘上
  · 缺什么：按原因分桶（无源文件 / 源无该图 / ytd 里没有 / 没绑定）

    python tools/audit_three_maps.py
    python tools/audit_three_maps.py --json out.json
"""
import os
import sys
import json
import glob
import argparse
from collections import Counter

ROOT = r'D:/BrainMaker/大镖客2解包分析'
LIB = os.path.join(ROOT, 'assets/lib_native')
INDEX = os.path.join(LIB, 'index.json')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--json', default='')
    a = ap.parse_args()

    idx = json.load(open(INDEX, encoding='utf-8'))
    models, tex = idx['models'], idx['tex']
    role = {t['id']: (t.get('role') or 'ab') for t in tex}
    texname = {t['id']: (t.get('n') or '') for t in tex}
    texfile = {t['id']: os.path.join(LIB, t['f'].replace('/', os.sep)) for t in tex}

    R = {}
    # --- 池
    c = Counter(role.values())
    R['tex_pool'] = dict(c)
    R['tex_files_missing'] = sum(1 for i, p in texfile.items() if not os.path.exists(p))
    R['tex_png_on_disk'] = len(glob.glob(os.path.join(LIB, 'tex', '*.png')))

    # --- 槽位级
    nsub = sum(len(m.get('s') or []) for m in models.values())
    alb = nrm = orm = both = 0
    with_st = 0
    for m in models.values():
        s = m.get('s') or []
        st = m.get('st') or []
        if len(st) != len(s):
            st = []
        else:
            with_st += 1
        for i, (_t, _v, _i) in enumerate(s):
            tid = _t
            if tid is not None and 0 <= tid < len(tex):
                alb += 1
            if i < len(st):
                p = st[i]
                if p and p[0] >= 0:
                    nrm += 1
                if p and p[1] >= 0:
                    orm += 1
                if p and p[0] >= 0 and p[1] >= 0:
                    both += 1
    R['models'] = len(models)
    R['models_with_st'] = with_st
    R['submeshes'] = nsub
    R['slot_albedo'] = alb
    R['slot_normal'] = nrm
    R['slot_orm'] = orm
    R['slot_both'] = both
    R['pct_albedo'] = round(100.0 * alb / max(1, nsub), 2)
    R['pct_normal'] = round(100.0 * nrm / max(1, nsub), 2)
    R['pct_orm'] = round(100.0 * orm / max(1, nsub), 2)
    R['pct_both'] = round(100.0 * both / max(1, nsub), 2)

    # --- 实例加权
    inst = Counter()
    for tf in sorted(glob.glob(os.path.join(ROOT, 'export/world/continent/tiles/*.json'))):
        for row in json.load(open(tf, encoding='utf-8')):
            inst['0x%08x' % int(row[0])] += 1
    total_slot = 0
    ok_alb = ok_nrm = ok_orm = 0
    obj_no_alb = obj_no_nrm = obj_no_orm = 0
    seen_inst = 0
    for h, k in inst.items():
        m = models.get(h)
        if not m:
            continue
        seen_inst += k
        s = m.get('s') or []
        st = m.get('st') or []
        if len(st) != len(s):
            st = []
        na = nn = no = 0
        for i, (_t, _v, _i) in enumerate(s):
            total_slot += k
            if _t is not None and 0 <= _t < len(tex):
                ok_alb += k
                na += 1
            if i < len(st):
                p = st[i]
                if p and p[0] >= 0:
                    ok_nrm += k
                    nn += 1
                if p and p[1] >= 0:
                    ok_orm += k
                    no += 1
        if s and na == 0:
            obj_no_alb += k
        if s and nn == 0:
            obj_no_nrm += k
        if s and no == 0:
            obj_no_orm += k
    R['instances_with_model'] = seen_inst
    R['inst_slots'] = total_slot
    R['inst_slot_albedo'] = ok_alb
    R['inst_slot_normal'] = ok_nrm
    R['inst_slot_orm'] = ok_orm
    R['inst_pct_albedo'] = round(100.0 * ok_alb / max(1, total_slot), 2)
    R['inst_pct_normal'] = round(100.0 * ok_nrm / max(1, total_slot), 2)
    R['inst_pct_orm'] = round(100.0 * ok_orm / max(1, total_slot), 2)
    R['inst_no_albedo'] = obj_no_alb
    R['inst_no_normal'] = obj_no_nrm
    R['inst_no_orm'] = obj_no_orm

    # --- 失败原因
    for f in ('slot_parse_fail.json', 'slot_tex_fail.json'):
        p = os.path.join(ROOT, 'work', f)
        if os.path.exists(p):
            d = json.load(open(p, encoding='utf-8'))
            if isinstance(d, dict):
                R[f] = dict(Counter(d.values()))
            else:
                R[f] = dict(Counter((x.get('role') or '') + '/' + (x.get('why') or '') for x in d))

    print('=== 贴图池 ===')
    print('  条目 %d：%s；磁盘 PNG %d；表里指不到文件 %d'
          % (len(tex), R['tex_pool'], R['tex_png_on_disk'], R['tex_files_missing']))
    print('=== 槽位级（%d 个模型 / %d 个子网格；%d 个模型有 st） ==='
          % (R['models'], nsub, with_st))
    print('  漫反射 %6d (%.2f%%)   法线 %6d (%.2f%%)   高光 %6d (%.2f%%)   两者都有 %6d (%.2f%%)'
          % (alb, R['pct_albedo'], nrm, R['pct_normal'], orm, R['pct_orm'], both, R['pct_both']))
    print('=== 实例加权（场上 %d 个实例 / %d 个槽位） ===' % (seen_inst, total_slot))
    print('  漫反射 %6d (%.2f%%)   法线 %6d (%.2f%%)   高光 %6d (%.2f%%)'
          % (ok_alb, R['inst_pct_albedo'], ok_nrm, R['inst_pct_normal'], ok_orm, R['inst_pct_orm']))
    print('  整只对象都没有：漫反射 %d / 法线 %d / 高光 %d' % (obj_no_alb, obj_no_nrm, obj_no_orm))
    if R.get('slot_tex_fail.json'):
        print('=== 贴图解不出来的原因 ===')
        for k, v in sorted(R['slot_tex_fail.json'].items(), key=lambda kv: -kv[1]):
            print('  %-24s %d' % (k, v))

    if a.json:
        json.dump(R, open(a.json, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
        print('[audit] → %s' % a.json)
    return R


if __name__ == '__main__':
    main()
