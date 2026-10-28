"""诊断：只转一根骨，看骨骼的**旋转轴心**是否在正确高度。

用途：走路时"膝盖位置不对"到底是
  (a) 关节轴心一骨段错位（节点放在 tail 而不是 head），还是
  (b) 蒙皮权重错（小腿的顶点被算给大腿）。

做法：导入 glb，把 SKEL_L_Calf 绕世界 X 转 60°（其余骨保持 rest），
侧视渲染；同时打印各关节的世界高度。

用法: blender -b --python tools/diag_knee.py
"""
import bpy
import os
import math
from mathutils import Matrix, Vector

GLB = r'D:/BrainMaker/大镖客2解包分析/export/npc/player/player_zero_walk.glb'
OUT = r'D:/BrainMaker/大镖客2解包分析/work/npc/verify'

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=GLB)
arm = [o for o in bpy.data.objects if o.type == 'ARMATURE'][0]
mesh = [o for o in bpy.data.objects if o.type == 'MESH'][0]

# 清掉动画，进入 rest
arm.animation_data_clear()
arm.data.pose_position = 'POSE'
for pb in arm.pose.bones:
    pb.matrix_basis = Matrix.Identity(4)

print('== rest 关节世界高度（Blender Z-up）==')
for nm in ('SKEL_Pelvis', 'SKEL_L_Thigh', 'SKEL_L_Calf', 'SKEL_L_Foot', 'SKEL_L_Toe0'):
    pb = arm.pose.bones.get(nm)
    if pb:
        print('  %-16s head z=%+.3f' % (nm, (arm.matrix_world @ pb.head).z))

# 只转小腿：绕世界 X（前后方向）转 60°
pb = arm.pose.bones['SKEL_L_Calf']
head = arm.matrix_world @ pb.head
R = Matrix.Translation(head) @ Matrix.Rotation(math.radians(-60), 4, 'X') @ Matrix.Translation(-head)
pb.matrix = arm.matrix_world.inverted() @ R @ (arm.matrix_world @ pb.matrix)
bpy.context.view_layer.update()
print('== 只转小腿 60° 后 ==')
for nm in ('SKEL_L_Thigh', 'SKEL_L_Calf', 'SKEL_L_Foot'):
    p = arm.pose.bones.get(nm)
    if p:
        print('  %-16s head z=%+.3f  tail z=%+.3f' % (nm, (arm.matrix_world @ p.head).z, (arm.matrix_world @ p.tail).z))

# 渲染侧视
mn = Vector((1e9,) * 3)
for o in [mesh]:
    for c in o.bound_box:
        w = o.matrix_world @ Vector(c)
        for i in range(3):
            mn[i] = min(mn[i], w[i])
bpy.ops.mesh.primitive_plane_add(size=12, location=(0, 0, mn.z - 0.002))
g = bpy.context.active_object
gm = bpy.data.materials.new('G')
gm.use_nodes = True
gm.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.24, 0.25, 0.28, 1)
g.data.materials.append(gm)

sc = bpy.context.scene
sc.render.engine = 'CYCLES'
sc.cycles.samples = 16
sc.cycles.device = 'CPU'
sc.render.resolution_x, sc.render.resolution_y = 620, 820
w = bpy.data.worlds.new('W')
sc.world = w
w.use_nodes = True
w.node_tree.nodes['Background'].inputs[0].default_value = (0.09, 0.10, 0.12, 1)
cam_d = bpy.data.cameras.new('C')
cam_d.lens = 55
cam = bpy.data.objects.new('C', cam_d)
bpy.context.collection.objects.link(cam)
sc.camera = cam
cam.location = (3.2, 0.0, 0.0)
cam.rotation_euler = (math.radians(90), 0, math.radians(90))
ld = bpy.data.lights.new('S', 'SUN')
ld.energy = 3.0
lo = bpy.data.objects.new('S', ld)
bpy.context.collection.objects.link(lo)
lo.rotation_euler = (math.radians(60), 0, math.radians(120))
sc.render.filepath = os.path.join(OUT, 'diag_knee_only.png')
bpy.ops.render.render(write_still=True)
print('OUT', sc.render.filepath)
