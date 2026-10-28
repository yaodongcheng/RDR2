"""渲染"蒙皮/绑骨诊断图"：网格、网格+骨骼、按主导骨着色的权重图。

用法: blender -b --python tools/blender_diag_bind.py
输出: work/npc/verify/diag_A_mesh.png / diag_B_bones.png / diag_C_weights.png
"""
import bpy
import math
from mathutils import Vector

GLB = r'D:/BrainMaker/大镖客2解包分析/export/npc/player/player_zero_walk.glb'
OUT = r'D:/BrainMaker/大镖客2解包分析/work/npc/verify/'
FRAME = 80

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=GLB)
# ★ Blender 的 glTF 导入器会给骨架造一个 42 顶点的 Icosphere（骨骼显示占位），
#   半径 1m 罩在原点，看/渲染都会被它挡住 → 只取顶点最多的那个网格，其余删掉。
ms = sorted([o for o in bpy.data.objects if o.type == 'MESH'],
            key=lambda o: -len(o.data.vertices))
mesh = ms[0]
for o in ms[1:]:
    print('DIAG 删除多余网格: %s (%d 顶点)' % (o.name, len(o.data.vertices)))
    bpy.data.objects.remove(o, do_unlink=True)
arm = [o for o in bpy.data.objects if o.type == 'ARMATURE'][0]
sc = bpy.context.scene
sc.frame_set(FRAME)
bpy.context.view_layer.update()
print('DIAG 网格=%s 顶点=%d 骨=%d 顶点组=%d' % (mesh.name, len(mesh.data.vertices),
      len(arm.data.bones), len(mesh.vertex_groups)))

mn = Vector((1e9,) * 3)
mx = Vector((-1e9,) * 3)
for c in mesh.bound_box:
    w = mesh.matrix_world @ Vector(c)
    for i in range(3):
        mn[i] = min(mn[i], w[i])
        mx[i] = max(mx[i], w[i])
H = max(mx.z - mn.z, 1.2)
cz = (mn.z + mx.z) / 2

# --- 场景基础
bpy.ops.mesh.primitive_plane_add(size=12, location=(0, 0, mn.z - 0.002))
g = bpy.context.active_object
gm = bpy.data.materials.new('G')
gm.use_nodes = True
gm.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.30, 0.31, 0.34, 1)
g.data.materials.append(gm)

cam_d = bpy.data.cameras.new('C')
cam_d.lens = 55
cam = bpy.data.objects.new('C', cam_d)
bpy.context.collection.objects.link(cam)
cam.location = (H * 0.85, -H * 2.5, cz + H * 0.10)
cam.rotation_euler = (cam.location - Vector((0, 0, cz))).to_track_quat('Z', 'Y').to_euler()
sc.camera = cam

for ang, en in (((55, 0, 28), 3.2), ((50, 0, -115), 1.5), ((15, 0, 175), 1.2)):
    ld = bpy.data.lights.new('S', 'SUN')
    ld.energy = en
    lo = bpy.data.objects.new('S', ld)
    bpy.context.collection.objects.link(lo)
    lo.rotation_euler = tuple(math.radians(a) for a in ang)

w = bpy.data.worlds.new('W')
sc.world = w
w.use_nodes = True
w.node_tree.nodes['Background'].inputs[0].default_value = (0.07, 0.08, 0.10, 1)

sc.render.engine = 'CYCLES'
sc.cycles.samples = 20
sc.cycles.use_denoising = True
sc.cycles.device = 'CPU'
sc.render.resolution_x, sc.render.resolution_y = 520, 760
sc.render.film_transparent = False


def render(name):
    sc.render.filepath = OUT + name
    bpy.ops.render.render(write_still=True)
    print('DIAG OUT', name)


# ============ A 网格 ============
render('diag_A_mesh.png')

# ============ B 网格 + 骨骼（把每根骨画成橙色圆柱）============
bone_mat = bpy.data.materials.new('BoneMat')
bone_mat.use_nodes = True
bsdf = bone_mat.node_tree.nodes['Principled BSDF']
bsdf.inputs['Base Color'].default_value = (1.0, 0.45, 0.05, 1)
bsdf.inputs['Emission Color'].default_value = (1.0, 0.5, 0.05, 1)
bsdf.inputs['Emission Strength'].default_value = 3.0

# 网格半透明，方便看里面的骨
for slot in mesh.material_slots:
    m = slot.material
    if not m or not m.use_nodes:
        continue
    for n in m.node_tree.nodes:
        if n.type == 'BSDF_PRINCIPLED':
            n.inputs['Alpha'].default_value = 0.22
    m.blend_method = 'BLEND'

nb = 0
for b in arm.pose.bones:
    h = arm.matrix_world @ b.head
    t = arm.matrix_world @ b.tail
    v = t - h
    L = v.length
    if L < 1e-4:
        continue
    bpy.ops.mesh.primitive_cylinder_add(radius=max(0.008, L * 0.06), depth=L,
                                        location=(h + t) / 2)
    c = bpy.context.active_object
    c.rotation_euler = v.to_track_quat('Z', 'Y').to_euler()
    c.data.materials.append(bone_mat)
    nb += 1
print('DIAG 画出骨骼 %d 根' % nb)
render('diag_B_bones.png')

# ============ C 权重着色（按主导骨上色）============
for o in list(bpy.data.objects):
    if o.type == 'MESH' and o is not mesh and o.name != 'Ground':
        bpy.data.objects.remove(o, do_unlink=True)
for slot in mesh.material_slots:
    if slot.material:
        slot.material.blend_method = 'OPAQUE'
        for n in slot.material.node_tree.nodes:
            if n.type == 'BSDF_PRINCIPLED':
                n.inputs['Alpha'].default_value = 1.0

gname = {vg.index: vg.name for vg in mesh.vertex_groups}
bone_names = [b.name for b in arm.data.bones]


def hue_by_bone(nm):
    i = bone_names.index(nm) if nm in bone_names else 0
    return (i * 0.61803398875) % 1.0


def hsv2rgb(h, s=0.85, v=0.95):
    i = int(h * 6) % 6
    f = h * 6 - int(h * 6)
    p = v * (1 - s)
    q = v * (1 - f * s)
    t = v * (1 - (1 - f) * s)
    return [(v, t, p), (q, v, p), (p, v, t), (p, q, v), (t, p, v), (v, p, q)][i]


col = mesh.data.color_attributes.new('WCol', 'FLOAT_COLOR', 'POINT') \
    if hasattr(mesh.data, 'color_attributes') else None
for vi, v in enumerate(mesh.data.vertices):
    best, bw = None, -1
    for gg in v.groups:
        if gg.weight > bw:
            bw, best = gg.weight, gname.get(gg.group)
    rgb = hsv2rgb(hue_by_bone(best or ''))
    if col:
        col.data[vi].color = (rgb[0], rgb[1], rgb[2], 1.0)

wm = bpy.data.materials.new('WMat')
wm.use_nodes = True
nt = wm.node_tree
for n in list(nt.nodes):
    nt.nodes.remove(n)
out = nt.nodes.new('ShaderNodeOutputMaterial')
attr = nt.nodes.new('ShaderNodeVertexColor')
attr.layer_name = 'WCol'
em = nt.nodes.new('ShaderNodeEmission')
em.inputs['Strength'].default_value = 1.0
nt.links.new(attr.outputs['Color'], em.inputs['Color'])
nt.links.new(em.outputs['Emission'], out.inputs['Surface'])
mesh.data.materials.clear()
mesh.data.materials.append(wm)
render('diag_C_weights.png')

print('DIAG DONE')
