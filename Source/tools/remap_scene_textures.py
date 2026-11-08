# -*- coding: utf-8 -*-
"""把场景 blend 的贴图路径从包外 `assets/lib_native/tex` 重指到交付包内。

映射：
  tex_id → textures/<role>/<name>.png        （导入子集，22,504）
  tex_id → textures_extra/<role>/<name>.png  （额外，824）
  找不到 → 包内贴图池 //../continent/tex/<id>.png（兜底）

用法（Blender 内）：
  blender -b <场景>.blend -P tools/remap_scene_textures.py -- [--dry]
"""
import csv
import io
import os
import sys

import bpy

RDR2 = r'D:/BrainMaker/大镖客2解包分析'
MANIFESTS = os.path.join(RDR2, 'deliverable/manifests')
POOL = os.path.join(RDR2, 'deliverable/blender/continent/tex')
EXTRA = os.path.join(RDR2, 'deliverable/textures_extra')
FALLBACK_CSV = os.path.join(MANIFESTS, 'textures_export_fallback.csv')
TEX_INDEX = os.path.join(RDR2, 'assets/lib_native/index.json')
TEX_NAMES = {}


def load_tex_names():
    try:
        import json
        idx = json.load(io.open(TEX_INDEX, encoding='utf-8'))
        return {int(t['id']): (t.get('n') or '') for t in idx.get('tex', [])}
    except Exception:
        return {}


def role_of(name):
    n = (name or '').lower()
    if n.endswith('_nm'):
        return 'nm'
    if n.endswith(('_ma', '_mb')):
        return 'ma'
    return 'alb'


def add_fallback(tid, blend, dry=False):
    """不在两张导出表里的贴图：从包内池复制到 textures_extra/<role>/<name>.png。"""
    name = TEX_NAMES.get(tid, '')
    if not name:
        return None
    role = role_of(name)
    dst = os.path.join(EXTRA, role, name + '.png')
    src = os.path.join(POOL, '%05d.png' % tid)
    new = '//../../textures_extra/%s/%s.png' % (role, name)
    if dry:
        return new
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if not os.path.exists(dst) and os.path.exists(src):
        import shutil
        shutil.copy2(src, dst)
    # 记录（首次写表头）
    import csv
    new_file = not os.path.exists(FALLBACK_CSV)
    with io.open(FALLBACK_CSV, 'a', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        if new_file:
            w.writerow(['tex_id', 'name', 'role', 'blend', 'dest'])
        w.writerow([tid, name, role, blend, 'textures_extra/%s/%s.png' % (role, name)])
    return new


def load_map():
    m = {}
    for fn, base in (('textures_export.csv', 'textures'),
                     ('textures_export_extra.csv', 'textures_extra')):
        p = os.path.join(MANIFESTS, fn)
        if not os.path.exists(p):
            continue
        for r in csv.DictReader(io.open(p, encoding='utf-8-sig')):
            try:
                m[int(r['tex_id'])] = (base, r['role'], r['name'])
            except Exception:
                pass
    return m


def main():
    global TEX_NAMES
    args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    dry = '--dry' in args
    TEX_NAMES = load_tex_names()
    m = load_map()
    mapped = miss = nonid = orphan = 0
    missing = []
    for im in bpy.data.images:
        stem = os.path.splitext(os.path.basename(im.filepath))[0]
        if not stem.isdigit():
            nonid += 1
            continue
        tid = int(stem)
        rec = m.get(tid)
        if rec:
            base, role, name = rec
            new = '//../../%s/%s/%s.png' % (base, role, name)
        else:
            # 不在两张导出表：仅「被材质/对象引用」的才复制到 textures_extra；
            # 孤儿 image（users=0）只指向包内池，不制造无用文件。
            if getattr(im, 'users', 0) <= 0:
                new = '//../continent/tex/%s.png' % stem
                orphan += 1
            else:
                new = add_fallback(tid, os.path.basename(bpy.data.filepath), dry=dry)
                if not new:
                    new = '//../continent/tex/%s.png' % stem
                miss += 1
                missing.append((tid, im.filepath))
        if not dry:
            im.filepath = new
        mapped += 1
    print('[remap] %s mapped=%d fallback_extra=%d orphan_pool=%d nonid=%d' %
          (os.path.basename(bpy.data.filepath), mapped, miss, orphan, nonid))
    if missing[:5]:
        print('[remap] fallback samples', missing[:5])
    if dry:
        print('[remap] DRY RUN — not saved')
        return
    # 不生成 .blend1 备份（41 GB 会翻倍）
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_mainfile()
    print('[remap] saved')


if __name__ == '__main__':
    main()
