# -*- coding: utf-8 -*-
"""按 index.json 里的 tex 列表，从贴图池重新导出 png（恢复被覆盖的旧贴图）。

为什么：dump_model_lib 会把 tex 从 0000.png 重新编号写盘，覆盖旧文件；
旧 index 的 tid 仍指向那些编号，于是模型贴图全部错配。本脚本按「名字→图」重建，
保证 tid = id 的映射与 index 完全一致。

    uv run --with numpy --with pillow python tools/regen_tex_from_index.py [--limit N]
"""
import os, sys, json
ROOT = r'D:/BrainMaker/大镖客2解包分析'
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import export_sdn_gltf as EX
from PIL import Image

LIB = os.path.join(ROOT, 'assets/lib_native')
IDX = os.path.join(LIB, 'index.json')


def main():
    d = json.load(open(IDX, encoding='utf-8'))
    tex = d['tex']
    print('[regen] tex 条目 %d' % len(tex))
    lib = EX.TexLib([os.path.join(ROOT, 'work/lib_gtxd/txd'),
                     os.path.join(ROOT, 'work/sdn/gtxd/txd'),
                     os.path.join(ROOT, 'work/sdn/gtxd/txd_int')], maxs=512)
    print('[regen] 池内贴图名 %d' % len(lib.idx))
    outdir = os.path.join(LIB, 'tex')
    os.makedirs(outdir, exist_ok=True)
    ok = miss = 0
    for t in tex:
        name = t['n']
        tid = t['id']
        fn = os.path.join(outdir, '%04d.png' % tid)
        ent = lib.idx.get(name.lower())
        if ent is None:
            miss += 1
            continue
        try:
            im, fmt = lib._decode(*ent)
        except Exception:
            miss += 1
            continue
        if im is None:
            miss += 1
            continue
        if max(im.size) > 512:
            im = im.resize((512, 512), Image.LANCZOS)
        if im.mode not in ('RGB', 'RGBA'):
            im = im.convert('RGB')
        im.save(fn, 'PNG', optimize=True)
        ok += 1
        if ok % 500 == 0:
            print('  %d/%d' % (ok, len(tex)))
    print('[regen] 重写 %d 张，缺 %d 张' % (ok, miss))


main()
