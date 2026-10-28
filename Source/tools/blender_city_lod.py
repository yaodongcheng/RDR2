"""Blender 高模 LOD：把一个据点的真实建筑网格拼起来，用 Decimate(COLLAPSE) 压到目标面数。

为什么必须在 Blender 里做
  自己写的"按面积裁面"会留下薄壳碎条（4 万面的教堂裁到 300 面像一堆木片）。
  Blender 的 Decimate 是二次误差塌陷，能把墙/屋顶简化成连续的面，远处看才是"一栋房"。

用法
  blender -b -P tools/blender_city_lod.py -- --code sdn --target 300000
产物
  deliverable/miniatures/hi/<code>_hi.glb   （材质用真实贴图，多 material）
"""
import bpy
import bmesh
import json
import os
import sys
import struct
import numpy as np
from mathutils import Vector

ROOT = r'D:/BrainMaker/大镖客2解包分析'
HI = os.path.join(ROOT, 'deliverable/miniatures/hi')
MAGIC = b'RMDL1\x00\x00\x00'
SUB = struct.Struct('<I I I I I I I')

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
CODE = 'sdn'
TARGET = 300000
for i, a in enumerate(argv):
    if a == '--code':
        CODE = argv[i + 1]
    if a == '--target':
        TARGET = int(argv[i + 1])

LIB = os.path.join(ROOT, 'assets/lib_native')
src = json.load(open(os.path.join(HI, CODE + '.json'), encoding='utf-8'))


def read_mdl(h):
    hx = hex(h)
    p = os.path.join(LIB, hx[2:4], hx + '.mdl')
    if not os.path.exists(p):
        return None
    d = open(p, 'rb').read()
    if d[:8] != MAGIC:
        return None
    nsub, = struct.unpack_from('<I', d, 8)
    verts, faces, mats, uvs = [], [], [], []
    base = 0
    for i in range(nsub):
        tid, vc, ic, po, no, uo, io = SUB.unpack_from(d, 36 + i * SUB.size)
        if vc == 0 or ic == 0:
            continue
        pos = np.frombuffer(d, dtype=np.float32, count=vc * 3, offset=po).reshape(-1, 3)
        uv = np.frombuffer(d, dtype=np.float32, count=vc * 2, offset=uo).reshape(-1, 2)
        idx = np.frombuffer(d, dtype=np.uint32, count=ic, offset=io).reshape(-1, 3)
        verts.append(pos)
        uvs.append(uv)
        faces.append(idx.astype(np.int64) + base)
        mats.append(np.full(len(idx), tid, np.int64))
        base += vc
    if not verts:
        return None
    return (np.vstack(verts), np.vstack(uvs), np.vstack(faces), np.concatenate(mats))


# ---- 清理场景 ----
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene

mesh_cache = {}
mat_cache = {}
objs = []
total_tris = 0

for it in src['items']:
    h = it['h']
    if h not in mesh_cache:
        mesh_cache[h] = read_mdl(h)
    g = mesh_cache[h]
    if g is None:
        continue
    pos, uv, faces, fmats = g
    if len(faces) == 0:
        continue

    me = bpy.data.meshes.new('m%d' % h)
    me.from_pydata(pos.tolist(), [], faces.tolist())
    me.update()
    uvl = me.uv_layers.new(name='UVMap')
    # 逐 loop 写 uv
    loops = np.zeros(len(me.loops), np.float32)
    vi = np.zeros(len(me.loops), np.int64)
    me.loops.foreach_get('vertex_index', vi)
    uvl.data.foreach_set('uv', uv[vi].reshape(-1))

    # 材质槽
    for tid in np.unique(fmats):
        tid = int(tid)
        if tid not in mat_cache:
            mat = bpy.data.materials.new('t%d' % tid)
            mat.use_nodes = True
            nt = mat.node_tree
            bsdf = nt.nodes['Principled BSDF']
            bsdf.inputs['Roughness'].default_value = 0.9
            bsdf.inputs['Metallic'].default_value = 0.0
            p = os.path.join(LIB, 'tex', '%04d.png' % tid)
            if os.path.exists(p):
                tex = nt.nodes.new('ShaderNodeTexImage')
                tex.image = bpy.data.images.load(p, check_existing=True)
                nt.links.new(tex.outputs['Color'], bsdf.inputs['Base Color'])
            mat_cache[tid] = mat
        me.materials.append(mat_cache[tid])
    slot_of = {m.name: i for i, m in enumerate(me.materials)}
    # 逐面 material_index
    fslot = []
    for tid in fmats:
        fslot.append(slot_of['t%d' % int(tid)])
    me.polygons.foreach_set('material_index', fslot)

    ob = bpy.data.objects.new('o%d' % h, me)
    scene.collection.objects.link(ob)

    # 变换：缩放 → 绕 Z 旋转 → 平移（RDR2 是 Z-up）
    qx, qy, qz, qw = it['qx'], it['qy'], it['qz'], it['qw']
    ob.scale = (it['sx'], it['sy'], it['sz'])
    ob.rotation_mode = 'QUATERNION'
    ob.rotation_quaternion = (qx, qy, qz, qw)
    ob.location = (it['x'], it['y'], it['z'])
    objs.append(ob)
    total_tris += len(faces)

print('objects', len(objs), 'tris', total_tris)

# ---- 合并 ----
bpy.ops.object.select_all(action='DESELECT')
for o in objs:
    o.select_set(True)
bpy.context.view_layer.objects.active = objs[0]
bpy.ops.object.join()
city = bpy.context.view_layer.objects.active
city.name = CODE
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

n_tris = len(city.data.polygons)
ratio = min(1.0, TARGET / max(n_tris, 1))
print('join tris', n_tris, 'ratio', round(ratio, 4))
if ratio < 0.999:
    mod = city.modifiers.new('dec', 'DECIMATE')
    mod.decimate_type = 'COLLAPSE'
    mod.ratio = ratio
    mod.use_collapse_triangulate = True
    bpy.context.view_layer.objects.active = city
    bpy.ops.object.modifier_apply(modifier=mod.name)
print('after decimate', len(city.data.polygons))

# ---- 转到沙盘坐标：X 东、Y 上、Z 南；比例 1/29 ----
S = 1.0 / 29.0
cx, cy = src['cx'], src['cy']
city.scale = (S, S, S)
bpy.ops.object.transform_apply(scale=True)
for v in city.data.vertices:
    x, y, z = v.co
    v.co = (x - cx * S, z - 0.0, -(y - cy * S))
bpy.context.view_layer.update()
# 抬到 y=0
minz = min(v.co.y for v in city.data.vertices)
for v in city.data.vertices:
    v.co.y -= minz

out = os.path.join(HI, f'{CODE}_hi.glb')
bpy.ops.export_scene.gltf(
    filepath=out, export_format='GLB', use_selection=True,
    export_apply=True, export_yup=True,
    export_image_format='JPEG', export_jpeg_quality=82,
)
print('written', out, round(os.path.getsize(out) / 1024 / 1024, 1), 'MB')
