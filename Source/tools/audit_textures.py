# -*- coding: utf-8 -*-
"""重绑后的**贴图一致性审计**：`.mdl` 里存的 tid → 名字，是否等于源文件声明的名字？

重绑（`rebind_models_from_sources.py --apply`）把 `.mdl` 的 tid 和 `index.s` 都按源文件重写了，
本工具从**磁盘上的 .mdl** 反着读一遍，和**源 .ydr/.yft** 再对一次 —— 不信任任何中间 JSON。

    python tools/audit_textures.py --sample 300
"""
import os
import sys
import json
import random
import struct
import argparse
from collections import Counter

ROOT = r'D:/BrainMaker/大镖客2解包分析'
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import dump_model_lib as D
import export_sdn_gltf as EX
from rebind_models_from_sources import load_sources, MAGIC, SUB

LIB = os.path.join(ROOT, 'assets/lib_native')
INDEX = os.path.join(LIB, 'index.json')
OUT = os.path.join(ROOT, 'work/audit_textures.json')


def read_mdl_subs(path):
    with open(path, 'rb') as f:
        buf = f.read()
    if buf[:8] != MAGIC:
        return None
    nsub = struct.unpack_from('<I', buf, 8)[0]
    o = 12 + 24
    out = []
    for _ in range(nsub):
        out.append(SUB.unpack_from(buf, o))
        o += SUB.size
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--sample', type=int, default=300)
    a = ap.parse_args()

    d = json.load(open(INDEX, encoding='utf-8'))
    models, tex = d['models'], d['tex']
    tname = {t['id']: t['n'] for t in tex}
    print('[au] 模型 %d / 贴图 %d（epoch %s）' % (len(models), len(tex), d.get('tex_epoch')))

    src = load_sources()
    cand = [hx for hx in models if int(hx, 16) in src]
    random.seed(5)
    sample = random.sample(cand, min(a.sample, len(cand)))

    same = diff = fail = 0
    miss_img = 0
    sub_total = sub_none = 0
    wrong = 0
    missing_img = 0
    bad = []
    for hx in sample:
        e = models[hx]
        subs = read_mdl_subs(os.path.join(LIB, e['f']))
        if subs is None:
            fail += 1
            continue
        try:
            M = D.load_any(src[int(hx, 16)])
        except Exception:
            M = None
        if not M or not M.get('geoms'):
            fail += 1
            continue
        geoms = [g for g in M['geoms'] if g.get('pos') and len(g.get('idx') or [])]
        if len(geoms) != len(subs):
            fail += 1
            continue
        ok = True
        for sub, g in zip(subs, geoms):
            tid = sub[0]
            sub_total += 1
            want = EX.clean_name(g.get('tex') or '').lower()
            got = tname.get(tid if tid != 0xFFFFFFFF else -1, '')
            if tid == 0xFFFFFFFF or tid < 0:
                sub_none += 1
                if want:
                    ok = False
                    missing_img += 1     # 源里有名字、库里没图（区别于"绑错"）
            elif got != want:
                ok = False
                wrong += 1
        if ok:
            same += 1
        else:
            diff += 1
            if len(bad) < 10:
                bad.append(hx)

    print('[au] 抽样 %d：与源一致 %d / 不一致 %d / 无法比对 %d'
          % (len(sample), same, diff, fail))
    print('[au] 子网格 %d 个：绑定正确 %d / 没图 %d / 绑错 %d'
          % (sub_total, sub_total - sub_none - wrong, sub_none, wrong))
    print('[au] 其中"源里有名字但库里没图" %d 个（占子网格 %.2f%%）'
          % (missing_img, 100.0 * missing_img / max(1, sub_total)))
    if bad:
        print('[au] 不一致样例: %s' % bad)
    json.dump({'sample': len(sample), 'same': same, 'diff': diff, 'fail': fail,
               'subs': sub_total, 'subs_no_albedo': sub_none,
               'subs_wrong': wrong, 'subs_missing_image': missing_img},
              open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('[au] 报告 %s' % OUT)


if __name__ == '__main__':
    main()
