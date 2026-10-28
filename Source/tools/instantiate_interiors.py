# -*- coding: utf-8 -*-
"""把「几何验证通过」的室内包按 MLO 实例变换摆进大陆，并单列一个「室内」分类。

前置：
  1) raw/_interiors/<pkg>/ 已解包（146 个包）
  2) export/world/interior_placement_audit.json 里 inside=True（包裹住宿主建筑）

用法：
    blender -b <continent.blend> -P tools/instantiate_interiors.py -- [--out <out.blend>] [--only-ok]
"""
import bpy
import os
import sys
import json
import glob
import math
import argparse
import numpy as np
from mathutils import Vector, Quaternion

ROOT = r'D:/BrainMaker/大镖客2解包分析'
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import blender_continent as BC
import blender_tour as tour
import parse_interior_mlo as PM

TILES = os.path.join(ROOT, 'export/world/continent/tiles')
LIB = os.path.join(ROOT, 'assets/lib_native')
AUDIT = os.path.join(ROOT, 'export/world/interior_placement_audit.json')


def argv():
    a = sys.argv
    return a[a.index('--') + 1:] if '--' in a else []


def _mat_for(tid, texmeta, matcache, libdir):
    if tid in matcache:
        return matcache[tid]
    mat = bpy.data.materials.new('m_%d' % tid)
    mat.use_nodes = True
    bsdf = next((n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
    if bsdf is None:
        return mat
    if 0 <= tid < len(texmeta):
        p = os.path.join(libdir, texmeta[tid]['f'])
        img = bpy.data.images.load(p, check_existing=True)
        img.colorspace_settings.name = 'sRGB'
        node = mat.node_tree.nodes.new('ShaderNodeTexImage')
        node.image = img
        mat.node_tree.links.new(node.outputs['Color'], bsdf.inputs['Base Color'])
        bsdf.inputs['Roughness'].default_value = 0.85
    else:
        bsdf.inputs['Base Color'].default_value = (0.34, 0.32, 0.29, 1.0)
        bsdf.inputs['Roughness'].default_value = 0.95
    matcache[tid] = mat
    return mat


def load_mlo(pkg, names):
    want = [pkg, pkg + '_lod', pkg + '_main']
    for p in glob.glob(os.path.join(TILES, '*.json')):
        if p.endswith('.bak'):
            continue
        for e in json.load(open(p, encoding='utf-8')):
            n = names.get(e[0])
            if n and n.split('/')[-1] in want:
                return e
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default='')
    ap.add_argument('--only-ok', action='store_true', default=True)
    a = ap.parse_args(argv())

    BC._mat_for = _mat_for
    idx = json.load(open(os.path.join(LIB, 'index.json'), encoding='utf-8'))
    models, texmeta = idx['models'], idx['tex']

    audit = json.load(open(AUDIT, encoding='utf-8'))
    ok = [x['pkg'] for x in audit if x['inside']]
    print('[int] 审计通过包: %d / %d' % (len(ok), len(audit)))

    names = {}
    for l in open(os.path.join(ROOT, 'tools/rdr2rpf/bin/Release/net9.0/names.txt'),
                  encoding='latin1', errors='ignore'):
        n = l.strip()
        if n:
            names.setdefault(PM.joaat(n), n.lower())

    ent = bpy.data.collections['ENTITIES']
    col = ent.children.get('C_int_室内')
    if col is None:
        col = bpy.data.collections.new('C_int_室内')
        col['sz'] = 9
        ent.children.link(col)

    matcache, meshcache = {}, {}
    made = placed = 0
    for pkg in ok:
        yp = os.path.join(ROOT, 'raw/_interiors', pkg, pkg + '.ytyp')
        if not os.path.exists(yp):
            cand = glob.glob(os.path.join(ROOT, 'raw/_interiors', pkg, '*.ytyp'))
            if not cand:
                continue
            yp = cand[0]
        inst = load_mlo(pkg, names)
        if not inst:
            continue
        P = Vector((inst[1], inst[2], inst[3]))
        q = Quaternion((inst[7], -inst[4], -inst[5], -inst[6]))   # 共轭
        try:
            lay = PM.parse_ytyp(yp)
        except Exception:
            continue
        ents = lay['entities'] if isinstance(lay, dict) else lay
        n_pkg = 0
        for e in ents:
            hx = hex(e['h'])
            m = models.get(hx)
            if not m:
                continue
            try:
                me = BC.load_model_mesh(LIB, m, texmeta, matcache, meshcache)
            except Exception:
                continue
            if not me:
                continue
            ob = bpy.data.objects.new('i_%s' % hx[2:], me)
            local = Vector(e['p'])
            ob.location = P + (q @ local)
            ob.rotation_mode = 'QUATERNION'
            lq = Quaternion((e['q'][3], -e['q'][0], -e['q'][1], -e['q'][2]))
            ob.rotation_quaternion = q @ lq
            tid = tour._tile_of(ob.location.x, ob.location.y)
            sub = next((s for s in col.children if s.get('tile') == tid), None)
            if sub is None:
                sub = bpy.data.collections.new('int|%s' % tid)
                sub['tile'] = tid
                sub['cat'] = 'int'
                col.children.link(sub)
            sub.objects.link(ob)
            made += 1
            n_pkg += 1
        if n_pkg:
            placed += 1
    print('[int] 已摆放 %d 个包 / %d 个对象' % (placed, made))

    out = a.out or bpy.data.filepath
    bpy.ops.wm.save_as_mainfile(filepath=out)
    print('[int] saved %s (%.2f GB)' % (out, os.path.getsize(out) / 1e9))


if __name__ == '__main__':
    main()
