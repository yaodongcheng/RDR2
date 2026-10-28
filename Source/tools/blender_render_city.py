"""把 sdn.blend 里真实的圣丹尼斯渲成一张"沙盘模型"图（离屏预渲染）。

为什么走预渲染
  沙盘图上每座城只有 10~40 px；用 3D 模型去追这个尺寸，永远到不了参考图的质感。
  GoT 开场的做法本质是"摆拍模型"——我们直接把这套真实场景按固定机位渲成图，
  地图上用 billboard 摆出来，远看就是那个味道，而且 46 城只要几十张图。

用法
  blender -b -P tools/blender_render_city.py -- --blend sdn.blend --out shots/city_sdn.png --res 1200
"""
import bpy
import os
import sys
import math
import time
from mathutils import Vector

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []


def arg(n, d=None):
    return argv[argv.index(n) + 1] if n in argv else d


BLEND = arg('--blend')
OUT = arg('--out')
RES = int(arg('--res', '1200'))
ELEV = float(arg('--elev', '38'))     # 俯角
AZIM = float(arg('--azim', '35'))     # 方位角

t0 = time.time()
bpy.ops.wm.open_mainfile(filepath=BLEND)
print('[render] opened', round(time.time() - t0, 1), flush=True)

# 只取"城"这一片：.blend 里混着周边地形和其它 tile，先用中位中心筛一遍
import statistics
pts = []
for o in bpy.data.objects:
    if o.type == 'MESH':
        pts.append((o.matrix_world.translation.x, o.matrix_world.translation.y))
cx = statistics.median([p[0] for p in pts]) if pts else 0
cy = statistics.median([p[1] for p in pts]) if pts else 0
print('[render] median center', round(cx, 1), round(cy, 1), flush=True)

RADIUS = float(arg('--radius', '700'))
CX = float(arg('--cx', '0'))
CY = float(arg('--cy', '0'))
mins = Vector((1e18, 1e18, 1e18))
maxs = Vector((-1e18, -1e18, -1e18))
used = 0
for o in bpy.data.objects:
    if o.type != 'MESH':
        continue
    # 物件原点常常都在 (0,0)，必须用包围盒中心判断
    cs = [o.matrix_world @ Vector(c) for c in o.bound_box]
    bx = sum(p.x for p in cs) / 8
    by = sum(p.y for p in cs) / 8
    if abs(bx - CX) > RADIUS or abs(by - CY) > RADIUS:
        continue
    used += 1
    for c in o.bound_box:
        w = o.matrix_world @ Vector(c)
        mins = Vector((min(mins[i], w[i]) for i in range(3)))
        maxs = Vector((max(maxs[i], w[i]) for i in range(3)))
print('[render] objects in radius', used, flush=True)
center = (mins + maxs) / 2
size = max((maxs - mins).x, (maxs - mins).y)
print('[render] bbox', tuple(round(v, 1) for v in mins), tuple(round(v, 1) for v in maxs),
      'size', round(size, 1), flush=True)

scene = bpy.context.scene
scene.render.engine = 'BLENDER_EEVEE'
scene.render.resolution_x = RES
scene.render.resolution_y = RES
scene.render.film_transparent = True
scene.render.image_settings.file_format = 'PNG'
try:
    scene.eevee.taa_render_samples = 64
except Exception:
    pass

# 相机：45° 俯视，正交，让整城刚好入画
cam_data = bpy.data.cameras.new('c')
cam_data.type = 'ORTHO'
cam_data.ortho_scale = size * 1.12
cam = bpy.data.objects.new('c', cam_data)
scene.collection.objects.link(cam)
scene.camera = cam

el = math.radians(ELEV)
az = math.radians(AZIM)
d = size * 2
cam.location = center + Vector((math.cos(el) * math.cos(az) * d,
                                math.cos(el) * math.sin(az) * d,
                                math.sin(el) * d))
direction = center - cam.location
cam.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()

# 光：一盏暖主光 + 天空环境
sun = bpy.data.objects.new('sun', bpy.data.lights.new('sun', 'SUN'))
sun.data.energy = 4.0
sun.data.angle = math.radians(3)
sun.rotation_euler = (math.radians(52), math.radians(8), math.radians(35))
scene.collection.objects.link(sun)

world = bpy.data.worlds.new('w') if not scene.world else scene.world
scene.world = world
world.use_nodes = True
bg = world.node_tree.nodes.get('Background')
if bg:
    bg.inputs[0].default_value = (0.55, 0.62, 0.72, 1.0)
    bg.inputs[1].default_value = 0.6

os.makedirs(os.path.dirname(OUT), exist_ok=True)
scene.render.filepath = OUT
bpy.ops.render.render(write_still=True)
print('[render] done', OUT, round(time.time() - t0, 1), 's', flush=True)
