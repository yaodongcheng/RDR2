# -*- coding: utf-8 -*-
"""把 `.ydd` 那批新模型的贴图名收集出来，并用当前贴图表回写它们的 s / .mdl tid。

用途：`tex_table_append.py` 追加完新名字后，跑这个把新模型的 tid 指到新 id 上。

    python tools/fix_ydd_textures.py --collect      # 产出 work/needed_ydd_names.json
    python tools/fix_ydd_textures.py --apply        # 回写 s 与 .mdl
"""
import os
import sys
import json
import struct
import argparse

ROOT = r'D:/BrainMaker/大镖客2解包分析'
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import rdr2_ydr as Y
import export_sdn_gltf as EX
from ingest_ydd_models import load_drawable_at

MAGIC = b'RMDL1' + bytes(3)
SUB = struct.Struct('<7I')     # tid, vc, ic, po, no, uo, io

LIB = os.path.join(ROOT, 'assets/lib_native')
INDEX = os.path.join(LIB, 'index.json')
YDDIDX = os.path.join(ROOT, 'work/ydd_index.json')
OLD = os.path.join(LIB, 'index_before_ydd_20261029_0623.json')
OUT = os.path.join(ROOT, 'work/needed_ydd_names.json')


def new_hashes(cur):
    old = json.load(open(OLD, encoding='utf-8'))['models'] if os.path.exists(OLD) else {}
    return [hx for hx in cur['models'] if hx not in old]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--collect', action='store_true')
    ap.add_argument('--apply', action='store_true')
    a = ap.parse_args()

    cur = json.load(open(INDEX, encoding='utf-8'))
    ydd = json.load(open(YDDIDX, encoding='utf-8'))
    new = new_hashes(cur)
    print('[fx] .ydd 入库的新模型 %d' % len(new))

    plan = {}
    names = set()
    for hx in new:
        if hx not in ydd:
            continue
        rel, off = ydd[hx]
        try:
            res = Y.Res(open(os.path.join(ROOT, rel), 'rb').read())
            geoms = [g for g in load_drawable_at(res, off)
                     if g.get('pos') and len(g.get('idx') or [])]
        except Exception:
            continue
        subs = []
        for g in geoms:
            nm = EX.clean_name(g.get('tex') or '').lower()
            subs.append((nm, len(g['pos']), len(g['idx'])))
            if nm:
                names.add(nm)
        plan[hx] = subs

    print('[fx] 解析 %d 个模型，贴图名 %d 个' % (len(plan), len(names)))
    json.dump(sorted(names), open(OUT, 'w', encoding='utf-8'), ensure_ascii=False)
    print('[fx] 名字清单 %s' % OUT)
    if not a.apply:
        return

    ids = json.load(open(os.path.join(ROOT, 'work/tex_name_ids.json'), encoding='utf-8'))
    ids = {k: v for k, v in ids.items() if not k.startswith('__')}
    patched = subs_n = 0
    for hx, subs in plan.items():
        e = cur['models'][hx]
        if len(subs) != len(e.get('s') or []):
            continue
        s = [[ids.get(nm, -1) if nm else -1, nv, ni] for nm, nv, ni in subs]
        e['s'] = s
        p = os.path.join(LIB, e['f'])
        try:
            with open(p, 'r+b') as f:
                head = f.read(36)
                if head[:8] != MAGIC:
                    continue
                n = struct.unpack_from('<I', head, 8)[0]
                if n != len(s):
                    continue
                for i, sub in enumerate(s):
                    f.seek(12 + 24 + i * SUB.size)
                    tid = sub[0]
                    f.write(struct.pack('<I', tid if tid >= 0 else 0xFFFFFFFF))
                patched += 1
                subs_n += n
        except Exception as ex:
            print('[fx] 失败 %s: %s' % (e['f'], ex))
    json.dump(cur, open(INDEX, 'w', encoding='utf-8'), separators=(',', ':'))
    print('[fx] 回写 %d 个模型 / %d 个子网格' % (patched, subs_n))


if __name__ == '__main__':
    main()
