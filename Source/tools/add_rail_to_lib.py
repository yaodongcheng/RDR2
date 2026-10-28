# -*- coding: utf-8 -*-
"""增量入库：把铁路 / 桥 / 栈桥模型（n_1114_r_*）补进 assets/lib_native。

## 为什么

`blender_continent.py` 是唯一合法管线，但它的模型库 `assets/lib_native`（54,893 个）里
`bridge / _bri / tres / truss / rail` **全部为 0** ⇒ 即使 `--rails` 打开了，跨水桥和栈桥也装不出来，
表现就是「桥在那儿、铁轨断了」。

本脚本把已经解包好的 ydr（`work/sdn/models` 与 `work/rails_extract/*`）**增量**写进库，
不改动已有条目（已存在同名 hash 直接跳过），因此对现有 continent 构建完全向后兼容。

    uv run python tools/add_rail_to_lib.py [--dry]

之后重建：
    blender -b -P tools/blender_continent.py -- --out .../continent.blend --lib assets/lib_native --rails
"""
import os, sys, json, time, glob

ROOT = r'D:/BrainMaker/大镖客2解包分析'
sys.path.insert(0, os.path.join(ROOT, 'tools'))

import dump_model_lib as D

LIB = os.path.join(ROOT, 'assets/lib_native')
INDEX = os.path.join(LIB, 'index.json')


def joaat(s):
    h = 0
    for c in s.lower().encode():
        h = (h + c) & 0xFFFFFFFF
        h = (h + (h << 10)) & 0xFFFFFFFF
        h ^= h >> 6
    h = (h + (h << 3)) & 0xFFFFFFFF
    h ^= h >> 11
    h = (h + (h << 15)) & 0xFFFFFFFF
    return h & 0xFFFFFFFF


def main():
    dry = '--dry' in sys.argv
    idx = json.load(open(INDEX, encoding='utf-8'))
    models = idx['models']
    tex_meta = idx.get('tex', [])
    print('[lib] 现有模型 %d，贴图 %d' % (len(models), len(tex_meta)))

    # 候选 ydr：铁路包 + 模型库里的 n_1114_r_*
    cands = {}
    for d in ('work/rails_extract/c114', 'work/rails_extract/rb_a', 'work/rails_extract/rb_b',
              'work/rails_extract/c1518', 'work/sdn/models'):
        for f in glob.glob(os.path.join(ROOT, d, '*.ydr')):
            n = os.path.splitext(os.path.basename(f))[0]
            if 'n_1114_r_' not in n:
                continue
            cands.setdefault(n, f)
    print('[lib] 候选铁路 ydr %d 个' % len(cands))

    todo = []
    for n, f in cands.items():
        hx = '0x%08x' % joaat(n)
        if hx in models:
            continue
        todo.append((n, f, hx))
    print('[lib] 需入库 %d 个（已存在跳过 %d）' % (len(todo), len(cands) - len(todo)))
    if dry or not todo:
        if todo[:3]:
            print('    示例:', [t[0] for t in todo[:3]])
        print('[lib] dry-run / 无需入库')
        return

    # 贴图管理器：预填已有贴图，避免重复写盘 & 覆盖编号
    tex = D.Tex(LIB, 512)
    for t in tex_meta:
        tex.by_name[t['n'].lower()] = t['id']
        tex.meta.append(t)
    print('[lib] 贴图预填 %d 条' % len(tex.meta))

    t0 = time.time()
    done = skipped = 0
    for i, (n, f, hx) in enumerate(todo):
        try:
            M = D.load_any(f)
        except Exception as e:
            skipped += 1
            continue
        if not M:
            skipped += 1
            continue
        e = D.write_model(M, int(hx, 16), LIB, tex)
        if not e:
            skipped += 1
            continue
        models[hx] = {k: e[k] for k in ('f', 'b', 's')}
        done += 1
        if done % 100 == 0:
            print('  %5d/%d  %.1f 分' % (done, len(todo), (time.time() - t0) / 60))

    json.dump(dict(models=models, tex=tex.meta), open(INDEX, 'w', encoding='utf-8'),
              separators=(',', ':'))
    print('[lib] 入库 %d（跳过 %d），模型总数 %d，贴图 %d，用时 %.1f 分' % (
        done, skipped, len(models), len(tex.meta), (time.time() - t0) / 60))


main()
