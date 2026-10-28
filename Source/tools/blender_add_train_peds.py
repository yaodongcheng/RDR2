"""加入 火车（多节车厢沿线路）+ 行人（带走路动画的 NPC 实例）。"""
import bpy, os, sys, json, math, random, argparse
from mathutils import Vector

ROOT = r'D:/BrainMaker/大镖客2解包分析'

def parse():
    ap = argparse.ArgumentParser()
    ap.add_argument('--blend', default=os.path.join(ROOT,'export/levels/world/blender/sdn.blend'))
    ap.add_argument('--routes', default=os.path.join(ROOT,'work/sdn/ai/routes_all.json'))
    ap.add_argument('--train', default=os.path.join(ROOT,'work/sdn/veh/train.gltf'))
    ap.add_argument('--walker', default=os.path.join(ROOT,'export/npc/player/player_zero_walk.glb'))
    ap.add_argument('--peds', type=int, default=10)
    ap.add_argument('--train-frames', type=int, default=1200)
    return ap.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])

a = parse()

def make_curve(name, pts, cyclic=True):
    cu = bpy.data.curves.new(name, 'CURVE'); cu.dimensions='3D'; cu.resolution_u=2
    sp = cu.splines.new('POLY'); sp.points.add(len(pts)-1)
    for i,(x,y,z) in enumerate(pts): sp.points[i].co=(x,y,z,1.0)
    sp.use_cyclic_u = cyclic
    ob = bpy.data.objects.new(name, cu); bpy.context.scene.collection.objects.link(ob)
    return ob

# ---------------- 火车 ----------------
routes = json.load(open(a.routes, encoding='utf-8'))
key = 'trains_nb1.dat' if 'trains_nb1.dat' in routes else 'trolley1.dat'
pts = routes[key]
train_curve = make_curve('TrainPath', pts, cyclic=True)
print('train curve', key, len(pts))

before=set(bpy.data.objects)
bpy.ops.import_scene.gltf(filepath=a.train)
imp=[o for o in bpy.data.objects if o not in before]
cars=[o for o in imp if o.type=='MESH']
print('train meshes', [c.name for c in cars])
for c in cars:
    mw=c.matrix_world.copy(); c.parent=None; c.matrix_world=mw

order=['ghosttrainsteamer','ghosttraincoalcar','ghosttrainpassenger','ghosttraincaboose']
cars.sort(key=lambda o: order.index(o.name) if o.name in order else 9)
L = sum(math.dist(pts[i],pts[(i+1)%len(pts)]) for i in range(len(pts)))
step = 0.026
sc=bpy.context.scene; sc.frame_start=1; sc.frame_end=max(sc.frame_end, a.train_frames)
for i,c in enumerate(cars):
    rig=bpy.data.objects.new('TrainRig_%d'%i, None); bpy.context.scene.collection.objects.link(rig)
    mw=c.matrix_world.copy(); c.parent=rig; c.matrix_parent_inverse=rig.matrix_world.inverted()
    c.matrix_world=mw
    con=rig.constraints.new('FOLLOW_PATH'); con.target=train_curve
    con.use_curve_follow=True; con.use_fixed_location=True
    con.forward_axis='FORWARD_Y'; con.up_axis='UP_Z'
    base = -i*step % 1.0
    con.offset_factor=base; con.keyframe_insert('offset_factor', frame=1)
    con.offset_factor=(base+1.0)%1.0; con.keyframe_insert('offset_factor', frame=a.train_frames+1)
print('train cars', len(cars), 'route %.0f m' % L)

# ---------------- 行人 ----------------
before=set(bpy.data.objects)
bpy.ops.import_scene.gltf(filepath=a.walker)
imp=[o for o in bpy.data.objects if o not in before]
for o in imp:
    if o.type in ('CAMERA','LIGHT') or o.name.lower() in ('cube','icosphere'):
        bpy.data.objects.remove(o, do_unlink=True)
imp=[o for o in bpy.data.objects if o not in before and o.name in bpy.data.objects]
arm=next((o for o in imp if o.type=='ARMATURE'), None)
mesh=next((o for o in imp if o.type=='MESH'), None)
print('walker', arm.name if arm else None, mesh.name if mesh else None)
if arm and mesh:
    act = bpy.data.actions.get('rdr2_walk') or (arm.animation_data.action if arm.animation_data else None)
    root = bpy.data.objects.new('PedRoot_0', None); bpy.context.scene.collection.objects.link(root)
    arm.parent = root; mesh.parent = arm
    base_loc = Vector((2500.0, -1150.0, 51.0))
    root.location = base_loc
    root.rotation_euler = (0,0,math.radians(-35))
    # 原地走：每 32 帧一个循环（动作长度由 action 决定）
    if act:
        try:
            fs=int(act.frame_range[0]); fe=int(act.frame_range[1])
        except Exception:
            fs, fe = 1, 40
        arm.animation_data_create(); arm.animation_data.action = act
        # 让动作循环
        for fc in []:
            pass
    # 复制出 N 个（linked duplicate：共享网格/骨架数据）
    for i in range(1, a.peds):
        dup_arm = arm.copy(); dup_arm.data = arm.data
        bpy.context.collection.objects.link(dup_arm)
        dup_mesh = mesh.copy(); dup_mesh.data = mesh.data
        bpy.context.collection.objects.link(dup_mesh)
        dup_mesh.parent = dup_arm
        dup_mesh.matrix_parent_inverse = mesh.matrix_parent_inverse.copy()
        r = bpy.data.objects.new('PedRoot_%d'%i, None); bpy.context.collection.objects.link(r)
        dup_arm.parent = r
        # 沿街分布
        off = Vector(((i%5)*3.2-6.4, (i//5)*3.5, 0))
        r.location = base_loc + off
        r.rotation_euler = (0,0,math.radians(-35))
        if act:
            dup_arm.animation_data_create(); dup_arm.animation_data.action = act
    print('peds', a.peds)

bpy.ops.wm.save_as_mainfile(filepath=a.blend)
print('SAVED', a.blend)
