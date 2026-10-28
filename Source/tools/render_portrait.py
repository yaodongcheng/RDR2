"""把角色 GLB 渲染成 AVG 用的**半身立绘**（透明底 PNG）。

和 tools/render_glb_views.py 的区别：
  - 只出 1 张（正面 3/4），不是 4 视角
  - 是**半身**：取上半身 0.46 身高，头顶留 6% 余量，腰部切在画面下缘
  - **透明底**（film_transparent），直接叠在 2D 背景上
  - 三点柔光 + 轻微轮廓光，避免立绘糊成一团

用法:
  blender -b --python tools/render_portrait.py -- <in.glb> <out.png> [--samples 16] [--res 760x1000]
"""
import bpy
import sys
import os
import math
from mathutils import Vector

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
glb, out = argv[0], argv[1]
samples = int(argv[argv.index('--samples') + 1]) if '--samples' in argv else 16
res = argv[argv.index('--res') + 1] if '--res' in argv else '760x1000'
W, H = [int(x) for x in res.split('x')]

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=glb)

meshes = [o for o in bpy.data.objects if o.type == 'MESH']
if not meshes:
    print('PORTRAIT_FAIL no mesh')
    sys.exit(1)

mn = Vector((1e9, 1e9, 1e9))
mx = Vector((-1e9, -1e9, -1e9))
for o in meshes:
    for c in o.bound_box:
        w = o.matrix_world @ Vector(c)
        for i in range(3):
            mn[i] = min(mn[i], w[i])
            mx[i] = max(mx[i], w[i])
size = mx - mn
H3 = max(size.z, 1e-4)
cx = (mn.x + mx.x) / 2.0
cy = (mn.y + mx.y) / 2.0

# ---- 取景：头顶往下 0.46 身高（头 + 胸 + 上腹）
top = mx.z + H3 * 0.045
bot = top - H3 * 0.52
mid_z = (top + bot) / 2.0
frame_h = (top - bot) * 1.18          # 留一点上下呼吸

world = bpy.data.worlds.new('W')
bpy.context.scene.world = world
world.use_nodes = True
world.node_tree.nodes['Background'].inputs[1].default_value = 0.0   # 黑底不发光

cam_data = bpy.data.cameras.new('Cam')
cam_data.lens = 85                     # 长焦压扁，立绘更像人像照
cam = bpy.data.objects.new('Cam', cam_data)
bpy.context.collection.objects.link(cam)
bpy.context.scene.camera = cam

# 85mm 在 36mm 幅面下的垂直视角
sensor = 36.0
vfov = 2 * math.atan((sensor * H / max(W, 1)) / (2 * cam_data.lens))
dist = (frame_h / 2.0) / math.tan(vfov / 2.0)

az = math.radians(22.0)                # 正面偏 22° 的 3/4 侧
cam.location = (cx + dist * math.sin(az), cy - dist * math.cos(az), mid_z + frame_h * 0.06)
d = cam.location - Vector((cx, cy, mid_z))
cam.rotation_euler = d.to_track_quat('Z', 'Y').to_euler()

# ---- 三点光
def area(name, loc, energy, size_m, target):
    ld = bpy.data.lights.new(name, 'AREA')
    ld.energy = energy
    ld.size = size_m
    ob = bpy.data.objects.new(name, ld)
    ob.location = loc
    bpy.context.collection.objects.link(ob)
    v = Vector(loc) - Vector(target)
    ob.rotation_euler = v.to_track_quat('Z', 'Y').to_euler()
    return ob

R = max(frame_h, 1.0)
tgt = (cx, cy, mid_z)
area('key',  (cx - R * 0.9, cy - R * 1.5, mid_z + R * 0.7), 900 * R * R, R * 0.8, tgt)
area('fill', (cx + R * 1.4, cy - R * 1.1, mid_z + R * 0.2), 260 * R * R, R * 0.9, tgt)
area('rim',  (cx + R * 0.5, cy + R * 1.6, mid_z + R * 0.9), 520 * R * R, R * 0.7, tgt)

scene = bpy.context.scene
scene.render.resolution_x = W
scene.render.resolution_y = H
scene.render.resolution_percentage = 100
scene.render.film_transparent = True
scene.render.image_settings.file_format = 'PNG'
scene.render.image_settings.color_mode = 'RGBA'
scene.view_settings.view_transform = 'Filmic'
scene.view_settings.look = 'Medium High Contrast'

scene.render.engine = 'CYCLES'
scene.cycles.samples = samples
scene.cycles.use_denoising = True
scene.cycles.device = 'CPU'
scene.cycles.max_bounces = 3
scene.cycles.transparent_max_bounces = 4

os.makedirs(os.path.dirname(out), exist_ok=True)
scene.render.filepath = out
bpy.ops.render.render(write_still=True)
print('PORTRAIT_OUT %s size=%s bbox=%s' % (out, list(size), [round(v, 2) for v in (mn.z, mx.z)]))
