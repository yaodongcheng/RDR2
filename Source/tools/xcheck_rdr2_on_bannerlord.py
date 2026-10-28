"""方向B：把 RDR2 解出来的走路重定向到骑砍2骨架后，用骑砍2官方小人渲染 —— 看它是不是正常走路。

数据来自 pipeline/run_retarget.py --rig rdr2 --clip rdr2_walk（已产出 output/fbx/rdr2_walk_check.fbx）。
这里：导入官方 human_lod_4.fbx（网格+28骨）→ 把重定向动作挂上去 → 侧视渲染。
"""
import bpy, os, math
from mathutils import Vector

TARGET = r'D:/BrainMaker/骑砍2动画重定向/input/target/bannerlord/human_lod_4.fbx'
ANIM  = r'D:/BrainMaker/骑砍2动画重定向/output/fbx/rdr2_walk_check.fbx'
OUT   = r'D:/BrainMaker/大镖客2解包分析/work/npc/verify'

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.context.scene.render.fps = 30

bpy.ops.import_scene.fbx(filepath=TARGET)
arm = [o for o in bpy.data.objects if o.type == 'ARMATURE'][0]
mesh = [o for o in bpy.data.objects if o.type == 'MESH'][0]

before = set(bpy.data.objects)
bpy.ops.import_scene.fbx(filepath=ANIM)
new_objs = [o for o in bpy.data.objects if o not in before]
acts = [a for a in bpy.data.actions if 'rdr2' in a.name.lower() or 'Scene' in a.name]
act = acts[-1] if acts else bpy.data.actions[-1]
print('用动作', act.name)
if not arm.animation_data:
    arm.animation_data_create()
arm.animation_data.action = act
if hasattr(arm.animation_data, 'action_slot') and getattr(act, 'slots', None):
    try:
        arm.animation_data.action_slot = act.slots[0]
    except Exception:
        pass
for o in new_objs:
    if o.type in ('ARMATURE', 'MESH'):
        o.hide_render = True

fs = [int(round(v)) for v in act.frame_range]
print('帧范围', fs)

sc = bpy.context.scene
sc.render.engine = 'CYCLES'
sc.cycles.samples = 20
sc.cycles.device = 'CPU'
sc.render.resolution_x, sc.render.resolution_y = 620, 820
w = bpy.data.worlds.new('W'); sc.world = w; w.use_nodes = True
w.node_tree.nodes['Background'].inputs[0].default_value = (0.09, 0.10, 0.12, 1)
bpy.ops.mesh.primitive_plane_add(size=14, location=(0, 0, -0.002))
g = bpy.context.active_object
gm = bpy.data.materials.new('G'); gm.use_nodes = True
gm.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.24, 0.25, 0.28, 1)
g.data.materials.append(gm)
cd = bpy.data.cameras.new('C'); cd.lens = 55
cam = bpy.data.objects.new('C', cd); bpy.context.collection.objects.link(cam); sc.camera = cam
cam.location = (3.0, 0.0, 0.9)          # 正侧机位（骑砍2 朝向 +Y ⇒ 侧面在 +X）
cam.rotation_euler = (math.radians(90), 0, math.radians(90))
ld = bpy.data.lights.new('S', 'SUN'); ld.energy = 3.0
lo = bpy.data.objects.new('S', ld); bpy.context.collection.objects.link(lo)
lo.rotation_euler = (math.radians(55), 0, math.radians(120))

frames = [fs[0], fs[0] + (fs[1]-fs[0])//3, fs[0] + 2*(fs[1]-fs[0])//3, fs[1]-1]
for i, f in enumerate(frames):
    sc.frame_set(f)
    sc.render.filepath = os.path.join(OUT, 'bl_rdr2walk_%d.png' % i)
    bpy.ops.render.render(write_still=True)
    print('OUT', sc.render.filepath)
