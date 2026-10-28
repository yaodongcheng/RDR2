# -*- coding: utf-8 -*-
"""把一个导出好的角色 .glb 装进 Blender，配好灯光/相机，存成可双击打开的 .blend。

用法：
  blender -b -P tools/make_character_blend.py -- <glb> <out.blend> [角色名]

做出来的场景：
  · 角色（glb 原样导入，贴图内嵌）
  · 三点光 + 环境光
  · 一台对准**头部特写**的相机（想拉远就把相机往后推）
  · 世界背景深灰（方便看黑发/黑衣服）
"""
import bpy
import sys
import os
import math
from mathutils import Vector

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
glb, out_blend = argv[0], argv[1]
name = argv[2] if len(argv) > 2 else os.path.splitext(os.path.basename(glb))[0]

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=glb)

meshes = [o for o in bpy.data.objects if o.type == 'MESH']
if not meshes:
    raise SystemExit('no mesh in ' + glb)

# 统一到一个空物体下，方便整体移动
root = bpy.data.objects.new('CHARACTER', None)
bpy.context.scene.collection.objects.link(root)
for m in meshes:
    if m.parent is None:
        m.parent = root

# 计算包围盒
mn = Vector((1e9, 1e9, 1e9))
mx = Vector((-1e9, -1e9, -1e9))
for m in meshes:
    for c in m.bound_box:
        w = m.matrix_world @ Vector(c)
        mn = Vector((min(mn.x, w.x), min(mn.y, w.y), min(mn.z, w.z)))
        mx = Vector((max(mx.x, w.x), max(mx.y, w.y), max(mx.z, w.z)))
h = mx.z - mn.z if mx.z > mn.z else 1.8
eye_z = mn.z + h * 0.90          # 眼睛大致在总高 90% 处

# 世界
world = bpy.data.worlds.new('W')
bpy.context.scene.world = world
world.use_nodes = True
nt = world.node_tree
for n in list(nt.nodes):
    nt.nodes.remove(n)
out = nt.nodes.new('ShaderNodeOutputWorld')
bg = nt.nodes.new('ShaderNodeBackground')
bg.inputs[0].default_value = (0.09, 0.10, 0.12, 1)
bg.inputs[1].default_value = 0.6
nt.links.new(bg.outputs[0], out.inputs['Surface'])

# 灯光
def add_light(name, kind, loc, energy, size=3.0, rot=(0, 0, 0)):
    d = bpy.data.lights.new(name, kind)
    d.energy = energy
    if kind == 'AREA':
        d.size = size
    o = bpy.data.objects.new(name, d)
    o.location = loc
    o.rotation_euler = rot
    bpy.context.scene.collection.objects.link(o)
    return o

def aim(obj, target):
    d = Vector(target) - obj.location
    obj.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()

k = add_light('Key', 'AREA', (1.4, -1.6, eye_z + 0.55), 320, 2.0)
aim(k, (0, 0, eye_z))
f = add_light('Fill', 'AREA', (-1.8, -1.2, eye_z + 0.15), 140, 2.5)
aim(f, (0, 0, eye_z))
r = add_light('Rim', 'AREA', (0.3, 1.8, eye_z + 0.45), 180, 2.0)
aim(r, (0, 0, eye_z))

# 相机：头部特写
cam_d = bpy.data.cameras.new('Camera')
cam = bpy.data.objects.new('Camera', cam_d)
bpy.context.scene.collection.objects.link(cam)
cam_d.lens = 85
cam.location = (0.02, -0.62, eye_z + 0.02)
aim(cam, (0, 0, eye_z - 0.01))
bpy.context.scene.camera = cam

# 另一台相机：全身
cam2_d = bpy.data.cameras.new('Camera_Full')
cam2 = bpy.data.objects.new('Camera_Full', cam2_d)
bpy.context.scene.collection.objects.link(cam2)
cam2_d.lens = 50
cam2.location = (0.9, -2.6, mn.z + h * 0.55)
aim(cam2, (0, 0, mn.z + h * 0.5))

sc = bpy.context.scene
sc.render.engine = 'BLENDER_EEVEE'
sc.render.resolution_x = 1280
sc.render.resolution_y = 900
sc.render.film_transparent = False
sc.view_settings.view_transform = 'Standard'

os.makedirs(os.path.dirname(out_blend), exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=out_blend)
print('SAVED', out_blend, 'height %.2f m' % h)
