# -*- coding: utf-8 -*-
"""探针：场景 blend 里「街面/地面贴花」到底有没有埋进地形。

判据（可分辨）：
  · 已贴地对象（有 snap_ground 属性）→ 埋深顶点占比应接近 0；
  · 对照：地面类但**没**贴地的对象（抬高栈桥/垂直件/离地 >2 m）→ 允许有埋深；
    若两组数字一样，说明判据没有分辨力，不能拿来验收。

逐顶点：世界坐标 → 对地形网格 BVH 从上向下打射线 → 命中高度 > 顶点高度 + 0.05 m 记埋深。

    blender -b <scene.blend> -P tools/_unbuffer.py -P tools/_probe_street_snap.py
"""
import bpy
import sys
from mathutils import Vector
from mathutils.bvhtree import BVHTree

ARGS = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []


def show_all():
    """隐藏集合里的 matrix_world 是陈旧的（AGENTS §6.x），先全开再 update。"""
    def walk(lc):
        lc.exclude = False
        lc.hide_viewport = False
        lc.collection.hide_viewport = False
        lc.collection.hide_render = False
        for c in lc.children:
            walk(c)
    walk(bpy.context.view_layer.layer_collection)
    for ob in bpy.data.objects:
        ob.hide_viewport = False
        try:
            ob.hide_set(False)
        except Exception:
            pass
    bpy.context.view_layer.update()


show_all()
dg = bpy.context.evaluated_depsgraph_get()

# ---- 地形：把所有 Terrain 网格（主片区 + 四条远景带）合成一个 BVH ----
terrs = [o for o in bpy.data.objects
         if o.type == 'MESH' and ('terrain' in o.name.lower())]
if not terrs:
    big = sorted(((len(o.data.vertices), o) for o in bpy.data.objects
                  if o.type == 'MESH'), reverse=True)[:6]
    print('[probe] 未找到 Terrain，最大网格：' +
          ', '.join('%s(%d)' % (o.name, n) for n, o in big))
    sys.exit(2)
print('[probe] 地形对象 %d 个：%s'
      % (len(terrs), ', '.join('%s(%d)' % (o.name, len(o.data.vertices))
                               for o in terrs)))

verts, faces = [], []
for t in terrs:
    mw = t.matrix_world
    bm = bpy.data.meshes.new_from_object(t.evaluated_get(dg))
    base = len(verts)
    verts.extend([mw @ v.co for v in bm.vertices])
    faces.extend([tuple(i + base for i in p.vertices) for p in bm.polygons])
    bpy.data.meshes.remove(bm)
bvh = BVHTree.FromPolygons(verts, faces)
print('[probe] 地形 BVH 就绪（%d 顶点 / %d 面）' % (len(verts), len(faces)))


def buried_ratio(ob):
    m = ob.matrix_world
    verts = ob.data.vertices
    if not verts:
        return 0, 0, 0.0
    bad = 0
    deepest = 0.0
    for v in verts:
        w = m @ v.co
        loc, nrm, idx, dist = bvh.ray_cast(Vector((w.x, w.y, w.z + 2000.0)),
                                           Vector((0, 0, -1)))
        if loc is None:
            continue
        if loc.z > w.z + 0.05:
            bad += 1
            deepest = max(deepest, loc.z - w.z)
    return bad, len(verts), deepest


GROUND = ('road', 'decal', 'track_decal', 'rail_decal')


def cls_of(ob):
    for c in ob.users_collection:
        n = c.name
        if n.startswith('C_') and '_' in n:
            return n[2:].split('_')[0]
    return ''


groups = {'snap': [], 'control': []}
for ob in bpy.data.objects:
    if ob.type != 'MESH':
        continue
    if ob.get('snap_ground'):
        groups['snap'].append(ob)
    elif cls_of(ob) in GROUND:
        groups['control'].append(ob)

for key, label in (('snap', '已贴地（snap_ground=1）'),
                   ('control', '对照：地面类未贴地')):
    obs = groups[key]
    tb = tv = 0
    worst = (0.0, '')
    for ob in obs:
        b, n, d = buried_ratio(ob)
        tb += b
        tv += n
        if d > worst[0]:
            worst = (d, ob.name)
    pct = (100.0 * tb / tv) if tv else 0.0
    print('[probe] %-22s 对象 %5d · 顶点 %7d · 埋深顶点 %6d（%5.2f%%）· 最深 %.3f m %s'
          % (label, len(obs), tv, tb, pct, worst[0], worst[1]))

print('[probe] === DONE ===')
