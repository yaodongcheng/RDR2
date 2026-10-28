"""用 Blender 把 glTF(.glb) 渲染成多视角 PNG —— 用于**交付前的视觉自检**。

为什么必须做：模型是否"像个正常人、贴图对不对、有没有部件丢失/翻转"，
靠读代码判断不出来，必须出图 + 视觉模型核验（见项目 skill
`visual-selfcheck-before-delivery` / `render-visual-self-check`）。

用法:
  "<blender.exe>" -b --python tools/render_glb_views.py -- <in.glb> <out_dir> [name] [--samples 24]
"""
import bpy
import sys
import os
import math
from mathutils import Vector

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
glb = argv[0]
outdir = argv[1]
name = argv[2] if len(argv) > 2 and not argv[2].startswith('--') else os.path.splitext(os.path.basename(glb))[0]
samples = 24
if '--samples' in argv:
    samples = int(argv[argv.index('--samples') + 1])

os.makedirs(outdir, exist_ok=True)

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=glb)

meshes = [o for o in bpy.data.objects if o.type == 'MESH']
if not meshes:
    print('RENDER_FAIL no mesh imported')
    sys.exit(1)

mn = Vector((1e9, 1e9, 1e9))
mx = Vector((-1e9, -1e9, -1e9))
nv = 0
for o in meshes:
    for c in o.bound_box:
        w = o.matrix_world @ Vector(c)
        for i in range(3):
            mn[i] = min(mn[i], w[i])
            mx[i] = max(mx[i], w[i])
    nv += len(o.data.vertices)
center = (mn + mx) / 2.0
size = mx - mn
print('RENDER_INFO meshes=%d verts=%d bbox_min=%s bbox_max=%s size=%s'
      % (len(meshes), nv, list(mn), list(mx), list(size)))

# ---- 世界 / 光照
world = bpy.data.worlds.new('W')
bpy.context.scene.world = world
world.use_nodes = True
bg = world.node_tree.nodes['Background']
bg.inputs[0].default_value = (0.10, 0.11, 0.13, 1.0)
bg.inputs[1].default_value = 1.0

def add_light(kind, loc, energy, size=3.0, rot=None):
    ld = bpy.data.lights.new('L_' + kind, kind)
    ld.energy = energy
    if kind == 'AREA':
        ld.size = size
    ob = bpy.data.objects.new('L_' + kind, ld)
    ob.location = loc
    bpy.context.collection.objects.link(ob)
    d = Vector(loc) - center
    ob.rotation_euler = d.to_track_quat('Z', 'Y').to_euler() if rot is None else rot
    return ob

R = max(size) * 2.0 + 1.0
add_light('SUN', (center.x + R, center.y + R * 0.6, center.z + R), 4.0)
add_light('AREA', (center.x - R * 0.9, center.y + R * 0.9, center.z + R * 0.5), 400.0, 4.0)
add_light('AREA', (center.x, center.y - R, center.z + R * 0.4), 250.0, 4.0)

cam_data = bpy.data.cameras.new('Cam')
cam_data.lens = 60
cam = bpy.data.objects.new('Cam', cam_data)
bpy.context.collection.objects.link(cam)
bpy.context.scene.camera = cam

scene = bpy.context.scene
scene.render.resolution_x = 620
scene.render.resolution_y = 900
scene.render.film_transparent = False

# Cycles CPU 最稳（无 GPU 也能出图）
try:
    scene.render.engine = 'CYCLES'
    scene.cycles.samples = samples
    scene.cycles.use_denoising = True
    scene.cycles.device = 'CPU'
    scene.cycles.max_bounces = 4
except Exception as e:
    print('RENDER_WARN engine cycles failed:', e)

# 贴图正确性：确保材质里 base color 纹理已加载（glTF 导入应已接好）
imgs = [i.name for i in bpy.data.images]
print('RENDER_INFO images=%d %s' % (len(imgs), imgs[:8]))

TARGET_Z = center.z + size.z * 0.05
dist = max(size.z, max(size.x, size.y)) * 2.35

views = [('front', 0.0), ('q34', 40.0), ('side', 90.0), ('back', 180.0)]
for label, az in views:
    a = math.radians(az)
    cam.location = (center.x + dist * math.sin(a),
                    center.y - dist * math.cos(a),
                    center.z + size.z * 0.22)
    d = cam.location - Vector((center.x, center.y, TARGET_Z))
    cam.rotation_euler = d.to_track_quat('Z', 'Y').to_euler()
    fn = os.path.join(outdir, '%s_%s.png' % (name, label))
    scene.render.filepath = fn
    bpy.ops.render.render(write_still=True)
    print('RENDER_OUT', fn)

print('RENDER_DONE')
