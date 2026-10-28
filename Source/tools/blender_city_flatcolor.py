"""从 sdn.blend 抽真实建筑：平面消融(Planar Dissolve)减面 + 顶点色，保留真实形状。

为什么这次能成
  · 之前用 COLLAPSE 减面：按误差塌陷，薄墙会被撕成木片（试过三次，全是碎片）。
  · 建筑是**平面构成**的：墙是一整块平板、屋顶是一块斜板。Blender 的
    Decimate → DISSOLVE(planar) 正好是"把同一平面上的三角面合成一个多边形"，
    形状一点不变，面数能掉一个数量级。
  · 颜色：每栋楼把自己贴图的平均色烘到顶点色，一个材质、不要贴图，
    远看就是"上色的模型"，近看也不会碎。

用法
  blender -b -P tools/blender_city_flatcolor.py -- --blend sdn.blend --out sdn_hero.glb
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
ANGLE = float(arg('--angle', '6.0'))
COLLAPSE_MAX = int(arg('--max-tris', '1400000'))
SCALE = 1.0 / 29.0

FEATURE_KW = ('church', 'cathedral', 'chapel', 'station', 'train', 'depot',
              'bank', 'hall', 'courthouse', 'theatre', 'hotel', 'mansion', 'man_',
              'plantation', 'jail', 'prison', 'pen', 'factory', 'mill', 'derrick',
              'conv', 'saloon', 'store', 'shop', 'warehouse', 'wrh', 'dock',
              'wharf', 'pier', 'tower', 'school', 'hospital', 'com_', 'gar_',
              'pie_', 'slm_', 'wrh_')

t0 = time.time()


def log(*a):
    print('[hero]', round(time.time() - t0, 1), *a, flush=True)


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
    if dim < 1.5 or dim > 150.0:
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
    try:
        for slot in obj.material_slots:
            mat = slot.material
            if not mat or not mat.use_nodes:
                continue
            for nd in mat.node_tree.nodes:
                if nd.type == 'TEX_IMAGE' and nd.image is not None:
                    px = np.array(nd.image.pixels[:], dtype=np.float32)
                    if px.size < 12:
                        continue
                    px = px.reshape(-1, 4)[::37, :3]
                    # 用中位数而不是均值：墙贴图里常有大片天空/白边，均值会把颜色冲淡
                    c = np.median(px, axis=0)
                    # 稍微提饱和，避免整座城一片灰白
                    c = 0.5 + (c - 0.5) * 1.35
                    return np.clip(c, 0, 1)
    except Exception:
        pass
    return np.array([0.70, 0.66, 0.58], np.float32)


# 每栋先把自己贴图的平均色烘到顶点色
n = 0
for o in feat:
    if o.name not in bpy.data.objects:
        continue
    me = o.data
    if len(me.vertices) == 0:
        continue
    c = avg_color(o)
    # 屋顶类物件（面法线大多朝上）压暗，做出"墙亮顶暗"的体积感；
    # 不压的话整城是一片白的（大部分浅色屋顶会吃掉所有层次）
    try:
        arr = np.zeros(len(me.polygons) * 3, np.float32)
        me.polygons.foreach_get('normal', arr)
        nz = arr.reshape(-1, 3)[:, 2].mean()
        if nz > 0.45:
            c = c * 0.62
    except Exception:
        pass
    if not me.color_attributes:
        me.color_attributes.new(name='Col', type='FLOAT_COLOR', domain='POINT')
    ca = me.color_attributes['Col']
    for i in range(len(me.vertices)):
        ca.data[i].color = (float(c[0]), float(c[1]), float(c[2]), 1.0)
    n += 1
    if n % 300 == 0:
        log('colored', n)
log('colored done', n)

# 分块 join（join 上千对象要分批）
CHUNK = 200
merged = []
for i in range(0, len(feat), CHUNK):
    part = [o for o in feat[i:i + CHUNK] if o.name in bpy.data.objects]
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
city.name = 'city_hero'
log('joined tris', len(city.data.polygons))

# 平面消融：共面三角面合成多边形，形状不变、面数大降
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.mesh.dissolve_limited(angle_limit=np.deg2rad(ANGLE), use_dissolve_boundaries=False)
bpy.ops.object.mode_set(mode='OBJECT')
log('dissolved faces', len(city.data.polygons))

# 仍然太多的话再做一次温和的 collapse
if len(city.data.polygons) > COLLAPSE_MAX:
    mod = city.modifiers.new('dec', 'DECIMATE')
    mod.decimate_type = 'COLLAPSE'
    mod.ratio = COLLAPSE_MAX / len(city.data.polygons)
    mod.use_collapse_triangulate = True
    bpy.context.view_layer.objects.active = city
    bpy.ops.object.modifier_apply(modifier=mod.name)
    log('collapsed ->', len(city.data.polygons))

# 三角化（GLB 只吃三角面）
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.mesh.quads_convert_to_tris(quad_method='BEAUTY', ngon_method='BEAUTY')
bpy.ops.object.mode_set(mode='OBJECT')
log('triangulated', len(city.data.polygons))

# 保留原始材质（不合并）：各自带自己的贴图，GLB 里会是多个 material + texture
log('materials kept', len(city.data.materials))

# 缩到沙盘尺度、落地、居中
city.scale = (SCALE, SCALE, SCALE)
bpy.ops.object.transform_apply(scale=True)
xs = [v.co.x for v in city.data.vertices]
ys = [v.co.y for v in city.data.vertices]
zs = [v.co.z for v in city.data.vertices]
cx, cy, z0 = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2, min(zs)
for v in city.data.vertices:
    v.co.x -= cx
    v.co.y -= cy
    v.co.z -= z0

os.makedirs(os.path.dirname(OUT), exist_ok=True)
bpy.ops.export_scene.gltf(filepath=OUT, export_format='GLB', use_selection=True,
                          export_apply=True, export_yup=True,
                          export_image_format='JPEG')
log('written', round(os.path.getsize(OUT) / 1048576, 1), 'MB')
