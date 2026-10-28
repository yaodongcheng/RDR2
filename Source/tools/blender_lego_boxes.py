"""乐高化（最终版）：从 sdn.blend 直接取特征建筑的真实占地/高度，生成实心积木块。

为什么这么干
  · 直接把真实网格 Decimate 到 400 面 → 薄壳会碎成木片（试过三次，结论稳定）。
  · 乐高模型本来就是"实心块"：每栋楼做成 1~2 层实心块（下宽上窄），
    占地/高度/位置全来自 .blend 里的真实物件，颜色来自它自己的贴图平均色。
  · 结果是 1000 来个实心块、1 万多个面、一个材质 —— 远看就是乐高沙盘。

用法
  blender -b -P tools/blender_lego_boxes.py -- --blend sdn.blend --out sdn_lego.glb
"""
import bpy
import os
import sys
import time

import numpy as np

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []


def arg(name, default=None):
    return argv[argv.index(name) + 1] if name in argv else default


BLEND = arg('--blend')
OUT = arg('--out')
MAX_OBJ = int(arg('--max-objects', '400'))
SCALE = 1.0 / 29.0

FEATURE_KW = ('church', 'cathedral', 'chapel', 'station', 'train', 'depot',
              'bank', 'hall', 'courthouse', 'theatre', 'hotel', 'mansion', 'man_',
              'plantation', 'jail', 'prison', 'pen', 'factory', 'mill', 'derrick',
              'conv', 'saloon', 'store', 'shop', 'warehouse', 'wrh', 'dock',
              'wharf', 'pier', 'tower', 'school', 'hospital')

WALL = [(0.88, 0.84, 0.74), (0.80, 0.68, 0.52), (0.68, 0.54, 0.42),
        (0.86, 0.86, 0.82), (0.74, 0.66, 0.54), (0.58, 0.42, 0.34)]
ROOF = [(0.56, 0.26, 0.20), (0.28, 0.31, 0.34), (0.46, 0.38, 0.28),
        (0.34, 0.38, 0.32), (0.60, 0.36, 0.26)]

t0 = time.time()


def log(*a):
    print('[boxes]', round(time.time() - t0, 1), *a)


bpy.ops.wm.open_mainfile(filepath=BLEND)
log('opened')

objs = [o for o in bpy.data.objects if o.type == 'MESH']
BAKE = bpy.data.collections.new('BAKE')
bpy.context.scene.collection.children.link(BAKE)
for o in objs:
    try:
        for c in list(o.users_collection):
            c.objects.unlink(o)
        BAKE.objects.link(o)
    except Exception:
        pass

feat = []
for o in objs:
    n = o.name.lower()
    if not any(k in n for k in FEATURE_KW):
        continue
    dim = max(o.dimensions)
    if dim < 3.0 or dim > 140.0:
        continue
    feat.append(o)
feat.sort(key=lambda o: -(o.dimensions.x * o.dimensions.y * o.dimensions.z))
feat = feat[:MAX_OBJ]
log('features', len(feat))

verts_all = []   # (x, y, z) 世界米
faces_all = []
cols_all = []
vert_col = []

def avg_color(obj):
    try:
        for slot in obj.material_slots:
            mat = slot.material
            if not mat or not mat.use_nodes:
                continue
            for nd in mat.node_tree.nodes:
                if nd.type == 'TEX_IMAGE' and nd.image is not None:
                    im = nd.image
                    px = np.array(im.pixels[:], dtype=np.float32)
                    if px.size < 12:
                        continue
                    px = px.reshape(-1, 4)[::97, :3]
                    return np.clip(px.mean(0), 0, 1)
    except Exception:
        pass
    return np.array([0.72, 0.68, 0.60], np.float32)


def add_box(x0, x1, y0, y1, z0, z1, wc, rc):
    base = len(verts_all)
    v = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
         (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
    verts_all.extend(v)
    # 底面+四壁用墙色，顶面用屋顶色
    wall_faces = [(0, 1, 2), (0, 2, 3), (0, 4, 5), (0, 5, 1),
                  (1, 5, 6), (1, 6, 2), (2, 6, 7), (2, 7, 3), (3, 7, 4), (3, 4, 0)]
    roof_faces = [(4, 6, 5), (4, 7, 6)]
    for (a, b, c) in wall_faces:
        faces_all.append((base + a, base + b, base + c))
        vert_col.append(wc)
    for (a, b, c) in roof_faces:
        faces_all.append((base + a, base + b, base + c))
        vert_col.append(rc)


boxes = []
for o in feat:
    try:
        me = o.data
        if len(me.vertices) == 0:
            continue
        mw = o.matrix_world
        co = np.array([(mw @ v.co)[:] for v in me.vertices], np.float32)
        x0, x1 = float(co[:, 0].min()), float(co[:, 0].max())
        y0, y1 = float(co[:, 1].min()), float(co[:, 1].max())
        z0, z1 = float(co[:, 2].min()), float(co[:, 2].max())
        if (x1 - x0) < 1.0 or (y1 - y0) < 1.0 or (z1 - z0) < 1.0:
            continue
        c = avg_color(o)
        k = max(range(len(WALL)),
                key=lambda i: -sum(abs(a - b) for a, b in zip(WALL[i], c)))
        wc = WALL[k]
        rc = ROOF[k % len(ROOF)]

        boxes.append((x0, x1, y0, y1, z0, z1, wc, rc))
    except Exception:
        continue

# 只保留城区（取中位数中心 ±450 m），.blend 里混着整块大陆的其它 tile
if boxes:
    cxs = sorted([(b[0] + b[1]) / 2 for b in boxes])
    cys = sorted([(b[2] + b[3]) / 2 for b in boxes])
    mx = cxs[len(cxs) // 2]
    my = cys[len(cys) // 2]
    boxes = [b for b in boxes
             if abs((b[0] + b[1]) / 2 - mx) < 450 and abs((b[2] + b[3]) / 2 - my) < 450]

for (x0, x1, y0, y1, z0, z1, wc, rc) in boxes:
    try:
        h = z1 - z0
        if h > 9.0:
            zm = z0 + h * 0.62
            add_box(x0, x1, y0, y1, z0, zm, wc, wc)
            ix = (x1 - x0) * 0.14
            iy = (y1 - y0) * 0.14
            add_box(x0 + ix, x1 - ix, y0 + iy, y1 - iy, zm, z1, wc, rc)
        else:
            add_box(x0, x1, y0, y1, z0, z1, wc, rc)
    except Exception:
        continue

log('boxes built, verts', len(verts_all), 'faces', len(faces_all))

# 建 mesh
me = bpy.data.meshes.new('lego')
me.from_pydata(verts_all, [], faces_all)
me.update()
ca = me.color_attributes.new(name='Col', type='FLOAT_COLOR', domain='CORNER')
li = 0
for f_i, poly in enumerate(me.polygons):
    col = vert_col[f_i]
    for _ in poly.loop_indices:
        ca.data[li].color = (col[0], col[1], col[2], 1.0)
        li += 1

obj = bpy.data.objects.new('lego_city', me)
bpy.context.scene.collection.objects.link(obj)

mat = bpy.data.materials.new('lego')
mat.use_nodes = True
nt = mat.node_tree
for nd in list(nt.nodes):
    nt.nodes.remove(nd)
outn = nt.nodes.new('ShaderNodeOutputMaterial')
bsdf = nt.nodes.new('ShaderNodeBsdfPrincipled')
vc = nt.nodes.new('ShaderNodeVertexColor')
vc.layer_name = 'Col'
nt.links.new(vc.outputs['Color'], bsdf.inputs['Base Color'])
bsdf.inputs['Roughness'].default_value = 0.82
nt.links.new(bsdf.outputs['BSDF'], outn.inputs['Surface'])
me.materials.append(mat)

# 不删原物件：导出只导选区，删两万个对象反而要十几分钟
bpy.ops.object.select_all(action='DESELECT')

obj.scale = (SCALE, SCALE, SCALE)
bpy.context.view_layer.objects.active = obj
obj.select_set(True)
bpy.ops.object.transform_apply(scale=True)
minz = min(v.co.z for v in obj.data.vertices)
xs = [v.co.x for v in obj.data.vertices]
ys = [v.co.y for v in obj.data.vertices]
cx = (min(xs) + max(xs)) / 2
cy = (min(ys) + max(ys)) / 2
for v in obj.data.vertices:
    v.co.x -= cx
    v.co.y -= cy
    v.co.z -= minz

os.makedirs(os.path.dirname(OUT), exist_ok=True)
bpy.ops.export_scene.gltf(filepath=OUT, export_format='GLB', use_selection=True,
                          export_apply=True, export_yup=True)
log('written', round(os.path.getsize(OUT) / 1048576, 2), 'MB')
