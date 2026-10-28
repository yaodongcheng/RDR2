"""乐高化圣丹尼斯：从 sdn.blend 里只取特征建筑，逐栋 Decimate + 平涂色块。

为什么逐栋减面
  把 1 374 栋 join 成一坨再 Decimate，比例要压到 5%，整城会被撕成碎片（实测 500k 面时就是一堆碎片）。
  逐栋各自 Decimate 到 ~400 面，每栋还是个完整的体块 —— 这才是"乐高化"。

为什么平涂色
  乐高模型的质感是**塑料色块**。保留贴图会有 2 000+ 材质槽 = 2 000+ draw call（实测 2277），
  GLB 293 MB。改成每栋取它贴图的平均色做顶点色，一个材质、十几 MB，远看反而更像积木。

用法
  blender -b -P tools/blender_lego_city.py -- --blend sdn.blend --out sdn_lego.glb --per-object 420
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
PER = int(arg('--per-object', '420'))
SCALE = 1.0 / 29.0

FEATURE_KW = ('church', 'cathedral', 'chapel', 'station', 'train', 'depot',
              'bank', 'hall', 'courthouse', 'theatre', 'hotel', 'mansion', 'man_',
              'plantation', 'jail', 'prison', 'pen', 'factory', 'mill', 'derrick',
              'conv', 'saloon', 'store', 'shop', 'warehouse', 'wrh', 'dock',
              'wharf', 'pier', 'tower', 'school', 'hospital')

WALL = [(0.86, 0.82, 0.72), (0.78, 0.66, 0.50), (0.66, 0.52, 0.40),
        (0.84, 0.84, 0.80), (0.72, 0.64, 0.52), (0.60, 0.42, 0.34)]
ROOF = [(0.52, 0.26, 0.20), (0.30, 0.33, 0.36), (0.44, 0.38, 0.30),
        (0.36, 0.40, 0.34), (0.56, 0.36, 0.26)]

t0 = time.time()


def log(*a):
    print('[lego]', round(time.time() - t0, 1), *a)


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
log('moved', len(objs))

feat = []
for o in objs:
    n = o.name.lower()
    if not any(k in n for k in FEATURE_KW):
        continue
    dim = max(o.dimensions)
    if dim < 2.0 or dim > 150.0:
        continue
    feat.append(o)
log('features', len(feat))

bpy.ops.object.select_all(action='DESELECT')
for o in feat:
    o.select_set(True)
bpy.context.view_layer.objects.active = feat[0]
bpy.ops.object.make_single_user(object=True, obdata=True, material=False, animation=False)
log('single-user')


def avg_color(obj):
    """取对象第一个材质里的贴图平均色（隔点采样，够快）。"""
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
                    c = px.mean(0)
                    return tuple(float(v) for v in np.clip(c, 0, 1))
    except Exception:
        pass
    return (0.72, 0.68, 0.60)


done = 0
for o in feat:
    if o.name not in bpy.data.objects:
        continue
    me = o.data
    n = len(me.polygons)
    if n > PER * 1.4:
        mod = o.modifiers.new('d', 'DECIMATE')
        mod.decimate_type = 'COLLAPSE'
        mod.ratio = max(0.02, PER / n)
        mod.use_collapse_triangulate = True
        bpy.context.view_layer.objects.active = o
        try:
            bpy.ops.object.modifier_apply(modifier=mod.name)
        except Exception:
            o.modifiers.remove(mod)

    # 顶点色：墙色 + 屋顶色（按高度顶部 30% 刷屋顶色）
    c_src = avg_color(o)
    # 把平均色往调色板拉一点，避免脏灰
    k = max(range(len(WALL)), key=lambda i: sum(abs(a - b) for a, b in zip(WALL[i], c_src)))
    wc = WALL[k]
    rc = ROOF[k % len(ROOF)]
    me = o.data
    if not me.color_attributes:
        me.color_attributes.new(name='Col', type='FLOAT_COLOR', domain='POINT')
    ca = me.color_attributes['Col']
    zs = np.array([v.co.z for v in me.vertices], dtype=np.float32)
    if len(zs) == 0:
        continue
    zmin, zmax = float(zs.min()), float(zs.max())
    thr = zmin + (zmax - zmin) * 0.72
    for i, v in enumerate(me.vertices):
        c = rc if v.co.z >= thr else wc
        ca.data[i].color = (c[0], c[1], c[2], 1.0)
    done += 1
    if done % 200 == 0:
        log('processed', done, 'of', len(feat))

log('decimated+colored', done)

# 分块 join
sel = [o for o in feat if o.name in bpy.data.objects]
CHUNK = 250
merged = []
for i in range(0, len(sel), CHUNK):
    part = [o for o in sel[i:i + CHUNK] if o.name in bpy.data.objects]
    if not part:
        continue
    bpy.ops.object.select_all(action='DESELECT')
    for o in part:
        o.select_set(True)
    bpy.context.view_layer.objects.active = part[0]
    bpy.ops.object.join()
    merged.append(bpy.context.view_layer.objects.active)
bpy.ops.object.select_all(action='DESELECT')
for o in merged:
    o.select_set(True)
bpy.context.view_layer.objects.active = merged[0]
bpy.ops.object.join()
city = bpy.context.view_layer.objects.active
city.name = 'city_lego'
log('joined tris', len(city.data.polygons))

# 单一批次材质 + 顶点色
mat = bpy.data.materials.new('lego')
mat.use_nodes = True
nt = mat.node_tree
for n in list(nt.nodes):
    nt.nodes.remove(n)
out_node = nt.nodes.new('ShaderNodeOutputMaterial')
bsdf = nt.nodes.new('ShaderNodeBsdfPrincipled')
attr = nt.nodes.new('ShaderNodeVertexColor')
attr.layer_name = 'Col'
nt.links.new(attr.outputs['Color'], bsdf.inputs['Base Color'])
bsdf.inputs['Roughness'].default_value = 0.85
nt.links.new(bsdf.outputs['BSDF'], out_node.inputs['Surface'])
city.data.materials.clear()
city.data.materials.append(mat)

city.scale = (SCALE, SCALE, SCALE)
bpy.ops.object.transform_apply(scale=True)
minz = min(v.co.z for v in city.data.vertices)
for v in city.data.vertices:
    v.co.z -= minz
# 居中到原点
xs = [v.co.x for v in city.data.vertices]
ys_ = [v.co.y for v in city.data.vertices]
cx = (min(xs) + max(xs)) / 2
cy = (min(ys_) + max(ys_)) / 2
for v in city.data.vertices:
    v.co.x -= cx
    v.co.y -= cy

os.makedirs(os.path.dirname(OUT), exist_ok=True)
bpy.ops.export_scene.gltf(filepath=OUT, export_format='GLB', use_selection=True,
                          export_apply=True, export_yup=True,
                          export_attributes=True,
                          export_vertex_color='MATERIAL')
log('written', round(os.path.getsize(OUT) / 1048576, 1), 'MB')
