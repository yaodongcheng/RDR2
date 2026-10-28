"""从 deliverable/blender/sdn.blend（参考截图那个整城场景）烘一个"沙盘高模"。

思路（用户定的方向）
  只保留**特征建筑**（教堂 / 车站 / 银行 / 庄园 / 工厂 / 码头 / 仓库 / 旅馆…），
  其余街道杂件全部丢掉；保留下来的真实网格合并后 Decimate 塌陷到沙盘预算，
  贴图沿用原材质 —— 这样形状和材质就是参考图里的那一套，只是面数降下来。

关键坑
  sdn.blend 里 2.3 万个物件大量**共享 mesh**（实例化），直接 join 会报
  "Cannot apply to a multi user"，所以必须先 make_single_user。

用法
  blender -b -P tools/blender_bake_city.py -- --blend sdn.blend --out sdn_hi.glb --target 500000
"""
import bpy
import os
import sys
import time

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []


def arg(name, default=None):
    if name in argv:
        return argv[argv.index(name) + 1]
    return default


BLEND = arg('--blend')
OUT = arg('--out')
TARGET = int(arg('--target', '500000'))
SCALE = 1.0 / 29.0

FEATURE_KW = ('church', 'cathedral', 'chapel', 'station', 'train', 'depot',
              'bank', 'hall', 'courthouse', 'theatre', 'hotel', 'mansion', 'man_',
              'plantation', 'jail', 'prison', 'pen', 'factory', 'mill', 'derrick',
              'conv', 'saloon', 'store', 'shop', 'warehouse', 'wrh', 'dock',
              'wharf', 'pier', 'tower', 'school', 'hospital')

t0 = time.time()


def log(*a):
    print('[bake]', round(time.time() - t0, 1), *a)


bpy.ops.wm.open_mainfile(filepath=BLEND)
log('opened')

objs = [o for o in bpy.data.objects if o.type == 'MESH']

# 场景里有 65 个被隐藏的集合（glTF_not_exported / TILE_* 等），里面的对象选不中、
# 也就 join 不了（会得到"joined tris 2556"这种假结果）。先把要用的对象挪进一个新集合。
BAKE = bpy.data.collections.new('BAKE')
bpy.context.scene.collection.children.link(BAKE)
moved = 0
for o in objs:
    try:
        for c in list(o.users_collection):
            c.objects.unlink(o)
        BAKE.objects.link(o)
        moved += 1
    except Exception:
        pass
log('moved to BAKE', moved)
feat = []
for o in objs:
    n = o.name.lower()
    if not any(k in n for k in FEATURE_KW):
        continue
    dim = max(o.dimensions)
    if dim < 1.0 or dim > 160.0:      # 太碎 / 整块地形都丢掉
        continue
    feat.append(o)
log('features', len(feat), 'of', len(objs))

# 关键：先单用户化，否则 join 会失败（共享 mesh）
bpy.ops.object.select_all(action='DESELECT')
for o in feat:
    o.select_set(True)
bpy.context.view_layer.objects.active = feat[0]
try:
    bpy.ops.object.make_single_user(object=True, obdata=True, material=False, animation=False)
except Exception as e:
    log('make_single_user warn', e)
log('single-user done', sum(1 for o in feat if o.select_get()), 'selected')

# 分块 join（一次 join 上千个对象容易崩）
CHUNK = 120
merged = []
for i in range(0, len(feat), CHUNK):
    part = feat[i:i + CHUNK]
    bpy.ops.object.select_all(action='DESELECT')
    ok = []
    for o in part:
        if o.name in bpy.data.objects:
            o.select_set(True)
            ok.append(o)
    if not ok:
        continue
    bpy.context.view_layer.objects.active = ok[0]
    bpy.ops.object.join()
    merged.append(bpy.context.view_layer.objects.active)
    log('join chunk', i // CHUNK, '->', len(merged))

bpy.ops.object.select_all(action='DESELECT')
for o in merged:
    o.select_set(True)
bpy.context.view_layer.objects.active = merged[0]
bpy.ops.object.join()
city = bpy.context.view_layer.objects.active
city.name = 'city_hi'
n = len(city.data.polygons)
log('joined tris', n)

if n > TARGET:
    mod = city.modifiers.new('dec', 'DECIMATE')
    mod.decimate_type = 'COLLAPSE'
    mod.ratio = TARGET / n
    mod.use_collapse_triangulate = True
    bpy.ops.object.modifier_apply(modifier=mod.name)
    log('decimated ->', len(city.data.polygons))

city.scale = (SCALE, SCALE, SCALE)
bpy.ops.object.transform_apply(scale=True)
minz = min((city.matrix_world @ v.co).z for v in city.data.vertices)
for v in city.data.vertices:
    v.co.z -= minz

os.makedirs(os.path.dirname(OUT), exist_ok=True)
bpy.ops.export_scene.gltf(filepath=OUT, export_format='GLB', use_selection=True,
                          export_apply=True, export_yup=True)
log('written', os.path.getsize(OUT) / 1048576, 'MB')
