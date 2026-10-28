"""把导出的 glb **重新导回 Blender** 渲染几帧 —— 验证文件真身（不靠绑定会话的内存状态）。

用法: blender -b --python tools/render_exported_glb.py
"""
import bpy
import os
import math
from mathutils import Vector

GLB = os.environ.get('RDR2_GLB', r'D:/BrainMaker/大镖客2解包分析/export/npc/player/player_zero_walk.glb')
OUT = r'D:/BrainMaker/大镖客2解包分析/work/npc/verify'

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=GLB)

meshes = [o for o in bpy.data.objects if o.type == 'MESH']
arms = [o for o in bpy.data.objects if o.type == 'ARMATURE']
print('CHK 网格 %d 个，骨架 %d 个，动作 %s' % (
    len(meshes), len(arms), [a.name for a in bpy.data.actions]))

mn = Vector((1e9,) * 3)
mx = Vector((-1e9,) * 3)
for o in meshes:
    for c in o.bound_box:
        w = o.matrix_world @ Vector(c)
        for i in range(3):
            mn[i] = min(mn[i], w[i])
            mx[i] = max(mx[i], w[i])
print('CHK 包围盒 z[%.3f,%.3f] 高 %.3f m' % (mn.z, mx.z, mx.z - mn.z))

# 地面放到模型脚下
bpy.ops.mesh.primitive_plane_add(size=14, location=(0, 0, mn.z - 0.002))
g = bpy.context.active_object
gm = bpy.data.materials.new('G')
gm.use_nodes = True
gm.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.24, 0.25, 0.28, 1)
g.data.materials.append(gm)

sc = bpy.context.scene
sc.render.engine = 'CYCLES'
sc.cycles.samples = 24
sc.cycles.use_denoising = True
sc.cycles.device = 'CPU'
sc.render.resolution_x, sc.render.resolution_y = 560, 820
w = bpy.data.worlds.new('W')
sc.world = w
w.use_nodes = True
w.node_tree.nodes['Background'].inputs[0].default_value = (0.09, 0.10, 0.12, 1)

H = max(mx.z - mn.z, 1.2)
cz = mn.z + H * 0.52
cam_d = bpy.data.cameras.new('C')
cam_d.lens = 50
cam = bpy.data.objects.new('C', cam_d)
bpy.context.collection.objects.link(cam)
sc.camera = cam
# RDR2_CAM=side 时给正侧机位（看前后摆腿最准）
if os.environ.get('RDR2_CAM') == 'side':
    cam.location = (H * 2.9, 0.0, cz + H * 0.12)
else:
    cam.location = (H * 1.0, -H * 2.6, cz + H * 0.18)
d = cam.location - Vector((0, 0, cz))
cam.rotation_euler = d.to_track_quat('Z', 'Y').to_euler()

for ang, en in (((50, 0, 25), 3.2), ((50, 0, -120), 1.2)):
    ld = bpy.data.lights.new('S', 'SUN')
    ld.energy = en
    lo = bpy.data.objects.new('S', ld)
    bpy.context.collection.objects.link(lo)
    lo.rotation_euler = tuple(math.radians(a) for a in ang)

acts = [a for a in bpy.data.actions]
f0, f1 = (int(round(v)) for v in (acts[0].frame_range if acts else (1, 1)))
print('CHK 帧范围 %d ~ %d' % (f0, f1))
os.makedirs(OUT, exist_ok=True)
frames = [f0, f0 + (f1 - f0) // 6, f0 + (f1 - f0) // 3, f0 + (f1 - f0) // 2]
for i, f in enumerate(frames):
    sc.frame_set(f)
    pre = os.environ.get('RDR2_PNG_PREFIX', 'glb')
    sc.render.filepath = os.path.join(OUT, '%s_%02d_f%03d.png' % (pre, i, f))
    bpy.ops.render.render(write_still=True)
    print('CHK OUT %s' % sc.render.filepath)
print('CHK DONE')
