# -*- coding: utf-8 -*-
"""迷你场景：只装「H4 地形小块 + 铁路实例」，秒级出图，用来判断铁路到底在不在、埋没埋。

不打开 continent_v12.blend（7.4 GB / 27k 贴图，加载要十几分钟），
直接用 lib_native 的 `.mdl` + tiles 里的实例表，按与构建**完全相同**的公式摆放：

    世界 = location + R(四元数共轭) * local

    blender -b -P tools/_probe_ann_mini.py -- --x 2884 --y 1348 --w 900 --tag ann
产物：D:/BrainMaker/_test/ann/<tag>_on.png（地形+铁路）/ <tag>_off.png（只有铁路）
"""
import bpy
import os
import sys
import json
import math
import argparse
import numpy as np
from mathutils import Vector

ROOT = r'D:/BrainMaker/大镖客2解包分析'
LIB = os.path.join(ROOT, 'assets/lib_native')
TILES = os.path.join(ROOT, 'export/world/continent/tiles')
H4 = os.path.join(ROOT, 'work/terrain/H4.npy')
NAMES = os.path.join(ROOT, 'tools/rdr2rpf/bin/Release/net9.0/names.txt')
X0, Y0, RES = -7684.0, -8196.0, 4.0

KEYS = ('rails', '_r_c_', '_r_b_sle', '_r_c_steel', 'rrcross', 'railroad')
SKIP = ('_lod', '_decal', '_dec', '_det', '+hi')

MAGIC = b'RMDL1' + bytes(3)
import struct
SUB = struct.Struct('<I I I I I I I')


def joaat(s):
    h = 0
    for c in s.lower().encode('latin1', 'ignore'):
        h = (h + c) & 0xFFFFFFFF
        h = (h + (h << 10)) & 0xFFFFFFFF
        h ^= h >> 6
    h = (h + (h << 3)) & 0xFFFFFFFF
    h ^= h >> 11
    return (h + (h << 15)) & 0xFFFFFFFF


def load_names():
    d = {}
    with open(NAMES, encoding='latin1', errors='ignore') as f:
        for ln in f:
            n = ln.strip()
            if n and not n.startswith('#'):
                d.setdefault(joaat(n), n)
    return d


def mdl_mesh(entry, texmeta, matcache):
    p = os.path.join(LIB, entry['f'].replace('/', os.sep))
    with open(p, 'rb') as f:
        buf = f.read()
    if buf[:8] != MAGIC:
        return None
    nsub = struct.unpack_from('<I', buf, 8)[0]
    off = 36
    subs = [SUB.unpack_from(buf, off + i * SUB.size) for i in range(nsub)]
    V, U, F = [], [], []
    base = 0
    slots = []
    for (tid, vc, ic, po, no, uo, io) in subs:
        if not vc or not ic:
            continue
        pos = np.frombuffer(buf, np.float32, vc * 3, po).reshape(-1, 3)
        uv = np.frombuffer(buf, np.float32, vc * 2, uo).reshape(-1, 2)
        idx = np.frombuffer(buf, np.uint32, ic, io)
        if int(idx.max()) >= vc:
            continue
        V.append(pos)
        U.append(uv)
        F.append(idx[: ic - ic % 3].reshape(-1, 3) + base)
        base += vc
        slots.append(tid)
    if not V:
        return None
    me = bpy.data.meshes.new('m_%s' % entry['f'][-12:])
    vv = np.vstack(V).astype(np.float32)
    ff = np.vstack(F).astype(np.int32)
    uu = np.vstack(U).astype(np.float32)
    me.vertices.add(len(vv))
    me.vertices.foreach_set('co', vv.ravel())
    me.loops.add(len(ff) * 3)
    me.loops.foreach_set('vertex_index', ff.ravel())
    me.polygons.add(len(ff))
    me.polygons.foreach_set('loop_start', np.arange(0, len(ff) * 3, 3, dtype=np.int32))
    me.update()
    uvl = me.uv_layers.new(name='UVMap')
    uvl.data.foreach_set('uv', uu[ff.ravel()].ravel())
    for tid in slots:
        nm = (texmeta[tid].get('n') if 0 <= tid < len(texmeta) else '') or ''
        m = matcache.get(nm)
        if m is None:
            m = bpy.data.materials.new('m_' + (nm or 'none')[:40])
            m.use_nodes = True
            b = [x for x in m.node_tree.nodes if x.type == 'BSDF_PRINCIPLED'][0]
            fp = os.path.join(LIB, texmeta[tid]['f']) if 0 <= tid < len(texmeta) else ''
            if fp and os.path.exists(fp):
                img = bpy.data.images.load(fp, check_existing=True)
                node = m.node_tree.nodes.new('ShaderNodeTexImage')
                node.image = img
                m.node_tree.links.new(node.outputs['Color'], b.inputs['Base Color'])
            else:
                b.inputs['Base Color'].default_value = (0.6, 0.3, 0.3, 1)
            m.diffuse_color = (0.7, 0.4, 0.4, 1)
            matcache[nm] = m
        me.materials.append(m)
    return me


def main():
    argv = sys.argv
    args = argv[argv.index('--') + 1:] if '--' in argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument('--x', type=float, default=2884.0)
    ap.add_argument('--y', type=float, default=1348.0)
    ap.add_argument('--w', type=float, default=900.0)
    ap.add_argument('--tag', default='ann')
    ap.add_argument('--out', default=r'D:/BrainMaker/_test/ann')
    ap.add_argument('--res', type=int, default=1400)
    a = ap.parse_args(args)
    os.makedirs(a.out, exist_ok=True)

    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene

    names = load_names()
    idx = json.load(open(os.path.join(LIB, 'index.json'), encoding='utf-8'))
    models, texmeta = idx['models'], idx['tex']

    # ---- 地形小块（与构建同一份 H4、同一个采样公式）
    h4 = np.load(H4)
    half = a.w / 2.0
    r0 = int(round((a.y - half - Y0) / RES)); r1 = int(round((a.y + half - Y0) / RES))
    c0 = int(round((a.x - half - X0) / RES)); c1 = int(round((a.x + half - X0) / RES))
    sub = h4[r0:r1 + 1, c0:c1 + 1].astype(np.float32)
    ny, nx = sub.shape
    X = X0 + (np.arange(c0, c1 + 1) * RES)
    Y = Y0 + (np.arange(r0, r1 + 1) * RES)
    XX, YY = np.meshgrid(X, Y, indexing='xy')
    co = np.stack([XX.ravel(), YY.ravel(), sub.ravel()], 1).astype(np.float32)
    ii = np.arange(ny * nx, dtype=np.int32).reshape(ny, nx)
    quads = np.stack([ii[:-1, :-1].ravel(), ii[:-1, 1:].ravel(),
                      ii[1:, 1:].ravel(), ii[1:, :-1].ravel()], 1)
    me = bpy.data.meshes.new('terrain_patch')
    me.vertices.add(len(co))
    me.vertices.foreach_set('co', co.ravel())
    me.loops.add(quads.size)
    me.loops.foreach_set('vertex_index', quads.ravel())
    me.polygons.add(len(quads))
    me.polygons.foreach_set('loop_start', np.arange(0, len(quads) * 4, 4, dtype=np.int32))
    me.update()
    tm = bpy.data.materials.new('terrain')
    tm.use_nodes = True
    tm.diffuse_color = (0.35, 0.33, 0.30, 1)
    me.materials.append(tm)
    ter = bpy.data.objects.new('TerrainPatch', me)
    sc.collection.objects.link(ter)
    print('[mini] 地形块 %dx%d' % (nx, ny))

    # ---- 铁路实例
    rail_h = set()
    for ln in open(NAMES, encoding='latin1', errors='ignore'):
        n = ln.strip()
        if not n or n.startswith('#'):
            continue
        l = n.lower()
        if any(k in l for k in KEYS) and not any(k in l for k in SKIP):
            rail_h.add(joaat(n))

    matcache = {}
    made = 0
    names_of = {}
    r2 = half * half
    for tf in sorted(os.listdir(TILES)):
        if not tf.endswith('.json'):
            continue
        for e in json.load(open(os.path.join(TILES, tf), encoding='utf-8')):
            if (e[1] - a.x) ** 2 + (e[2] - a.y) ** 2 > r2:
                continue
            hx = '0x%08x' % (int(e[0]) & 0xFFFFFFFF)
            ent = models.get(hx)
            if not ent:
                continue
            nm = names.get(int(e[0]) & 0xFFFFFFFF, '')
            low = nm.lower()
            is_rail = (int(e[0]) & 0xFFFFFFFF) in rail_h
            is_dec = 'rail_decal' in low or 'rails_decal' in low
            if not (is_rail or is_dec):
                continue
            mesh = mdl_mesh(ent, texmeta, matcache)
            if not mesh:
                continue
            ob = bpy.data.objects.new(nm or hx, mesh)
            ob.location = (e[1], e[2], e[3])
            ob.rotation_mode = 'QUATERNION'
            q = e[4:8]
            ob.rotation_quaternion = (q[3], -q[0], -q[1], -q[2])   # 共轭，与构建一致
            sc.collection.objects.link(ob)
            names_of[ob.name] = is_dec
            made += 1
    print('[mini] 装进铁路/道砟贴花 %d 个（其中 rail_decal %d）' %
          (made, sum(1 for v in names_of.values() if v)))

    # ---- 相机
    cam_d = bpy.data.cameras.new('c')
    cam_d.type = 'ORTHO'
    cam_d.ortho_scale = a.w
    cam_d.clip_start = 0.1
    cam_d.clip_end = 20000.0
    cam = bpy.data.objects.new('c', cam_d)
    sc.collection.objects.link(cam)
    sc.camera = cam
    cam.location = (a.x, a.y, 2000.0)
    cam.rotation_euler = (0, 0, 0)

    sc.render.engine = 'BLENDER_WORKBENCH'
    sh = sc.display.shading
    sh.light = 'STUDIO'
    sh.color_type = 'TEXTURE'
    sh.show_cavity = True
    sc.view_settings.view_transform = 'Standard'
    sc.render.resolution_x = sc.render.resolution_y = a.res
    sc.render.image_settings.file_format = 'PNG'

    sc.render.filepath = os.path.join(a.out, '%s_on.png' % a.tag)
    bpy.ops.render.render(write_still=True)
    print('[mini] 写入 %s' % sc.render.filepath)

    ter.hide_render = True
    sc.render.filepath = os.path.join(a.out, '%s_off.png' % a.tag)
    bpy.ops.render.render(write_still=True)
    print('[mini] 写入 %s' % sc.render.filepath)


if __name__ == '__main__':
    main()
