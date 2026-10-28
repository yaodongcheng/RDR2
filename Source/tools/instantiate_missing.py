# -*- coding: utf-8 -*-
"""把「库里新增、但场景里还没有实例」的模型补进 blend。

配合 tools/add_missing_models.py 使用：
  1) add_missing_models.py 把 raw 里已有的 .ydr 转成 .mdl 塞进 lib_native
  2) 本脚本在 Blender 里按 tiles 的实体变换把它们实例化，并按名字归到对应分类

用法：
    blender -b <blend> -P tools/instantiate_missing.py -- [--out <out.blend>] [--limit N]
"""
import bpy
import os
import sys
import json
import glob
import argparse
import collections

ROOT = r'D:/BrainMaker/大镖客2解包分析'
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import blender_continent as BC
import blender_tour as tour
import classify_entities as CE

NAMES = os.path.join(ROOT, 'tools/rdr2rpf/bin/Release/net9.0/names.txt')


def argv():
    a = sys.argv
    return a[a.index('--') + 1:] if '--' in a else []


def _mat_for(tid, texmeta, matcache, libdir):
    if tid in matcache:
        return matcache[tid]
    mat = bpy.data.materials.new('m_%d' % tid)
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = next((n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED'), None)
    if bsdf is None:
        return mat
    if 0 <= tid < len(texmeta):
        p = os.path.join(libdir, texmeta[tid]['f'])
        img = bpy.data.images.load(p, check_existing=True)
        img.colorspace_settings.name = 'sRGB'
        node = nt.nodes.new('ShaderNodeTexImage')
        node.image = img
        nt.links.new(node.outputs['Color'], bsdf.inputs['Base Color'])
        bsdf.inputs['Roughness'].default_value = 0.85
    else:
        bsdf.inputs['Base Color'].default_value = (0.34, 0.32, 0.29, 1.0)
        bsdf.inputs['Roughness'].default_value = 0.95
    matcache[tid] = mat
    return mat


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default='')
    ap.add_argument('--limit', type=int, default=0)
    a = ap.parse_args(argv())

    libdir = os.path.join(ROOT, 'assets/lib_native')
    idx = json.load(open(os.path.join(libdir, 'index.json'), encoding='utf-8'))
    models, texmeta = idx['models'], idx['tex']

    # 场景里已有的 hash
    present = set()
    ent = bpy.data.collections['ENTITIES']
    for c in ent.children:
        for sub in c.children:
            for o in sub.all_objects:
                try:
                    present.add(int(o.name[2:].split('.')[0], 16))
                except Exception:
                    pass
    print('[inst] 场景已有 hash %d / 库 %d' % (len(present), len(models)))

    BC._mat_for = _mat_for

    import re as _re
    TERRAIN_CELL = _re.compile(r'(_r_c_\d+|_rc_\d+|_ground\d*$|_terrain)', _re.I)
    LODNAME = _re.compile(r'slod|_lod|_strm|_proxy|_vfx', _re.I)
    RAILISH = _re.compile(r'rails|_r_c_|_r_b_|rrcross', _re.I)
    names = CE.load_names()
    cats = {k: c for k, zh, c in tour.cats()}

    # 找出「库里有、场景没有」的实体
    todo = collections.defaultdict(list)
    for p in glob.glob(os.path.join(ROOT, 'export/world/continent/tiles/*.json')):
        if p.endswith('.bak'):
            continue
        for e in json.load(open(p, encoding='utf-8')):
            if e[0] in present:
                continue
            if hex(e[0]) not in models:
                continue
            nm = names.get(e[0], '')
            b = nm.split('/')[-1]
            if nm and TERRAIN_CELL.search(b):
                continue
            if LODNAME.search(b):
                continue
            if CE.classify(nm) == 'veg':      # 用户已决定不复原植被
                continue
            bb = models[hex(e[0])].get('b')
            if bb and len(bb) >= 6:
                dx, dy, dz = bb[3] - bb[0], bb[4] - bb[1], bb[5] - bb[2]
                if (abs(dx - 64) < 2 and abs(dy - 64) < 2) or (abs(dx - 128) < 2 and abs(dy - 128) < 2):
                    continue
                if not RAILISH.search(b):
                    # 原来「max(dx,dy)>45 一律剔」会误杀桥段/高架（如 new_pie_train_es_2 66x55x13）
                    # 现在只在「确实扁平」(dz < 4 m) 或「超大且薄」时才剔
                    if dz < 2.0 and max(dx, dy) >= 16:
                        continue
                    if max(dx, dy) > 45 and dz < 4.0:
                        continue
                    if max(dx, dy) > 120 and dz < 8.0:
                        continue
            todo[e[0]].append(e)
    total = sum(len(v) for v in todo.values())
    print('[inst] 可补的实体: %d 种 / %d 个实例' % (len(todo), total))
    if a.limit:
        keys = list(todo)[:a.limit]
        todo = {k: todo[k] for k in keys}
        total = sum(len(v) for v in todo.values())

    matcache, meshcache = {}, {}
    made = 0
    bycat = collections.Counter()
    for h, ents in todo.items():
        n = names.get(h, '')
        key = CE.classify(n)
        cat = cats.get(key) or cats.get('unknown')
        if cat is None:
            continue
        tile_cols = {sub.get('tile'): sub for sub in cat.children}
        for e in ents:
            try:
                me = BC.load_model_mesh(libdir, models[hex(h)], texmeta, matcache, meshcache)
            except Exception as ex:
                print('[inst] load fail %s: %s' % (hex(h), ex))
                continue
            if not me:
                print('[inst] empty mesh %s' % hex(h))
                continue
            ob = bpy.data.objects.new('e_%s' % hex(h)[2:], me)   # 与其它实体同名规则，便于按 hash 反查
            ob.location = (e[1], e[2], e[3])
            ob.rotation_mode = 'QUATERNION'
            ob.rotation_quaternion = (e[7], -e[4], -e[5], -e[6])   # 共轭（与全图一致）
            ob.scale = (e[8], e[8], e[9])
            sub = tile_cols.get(tour._tile_of(e[1], e[2]))
            if sub is None:
                sub = bpy.data.collections.new('%s|%s' % (key, tour._tile_of(e[1], e[2])))
                sub['tile'] = tour._tile_of(e[1], e[2])
                sub['cat'] = key
                cat.children.link(sub)
                tile_cols[sub['tile']] = sub
            sub.objects.link(ob)
            made += 1
            bycat[key] += 1
    print('[inst] 已实例化 %d 个对象；分类分布: %s' % (made, dict(bycat)))

    out = a.out or bpy.data.filepath
    bpy.ops.wm.save_as_mainfile(filepath=out)
    print('[inst] saved %s (%.2f GB)' % (out, os.path.getsize(out) / 1e9))


if __name__ == '__main__':
    main()
