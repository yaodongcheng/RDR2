"""把有轨电车接进 sdn.blend：曲线路径 + Follow Path 动画 + 车体模型。"""
import bpy, os, sys, json, argparse, math
from mathutils import Vector
ROOT = r'D:/BrainMaker/大镖客2解包分析'

def parse():
    ap = argparse.ArgumentParser()
    ap.add_argument('--blend', default=os.path.join(ROOT,'export/levels/world/blender/sdn.blend'))
    ap.add_argument('--routes', default=os.path.join(ROOT,'work/sdn/ai/routes_all.json'))
    ap.add_argument('--trolley', default=os.path.join(ROOT,'work/sdn/veh/trolley.gltf'))
    ap.add_argument('--frames', type=int, default=1800, help='一圈的帧数（24fps）')
    ap.add_argument('--shots', default=os.path.join(ROOT,'export/levels/world/blender/shots'))
    ap.add_argument('--render', default='')
    return ap.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])

a = parse()
routes = json.load(open(a.routes, encoding='utf-8'))
pts = routes['trolley1.dat']
print('trolley1 节点', len(pts))

# 1) 曲线
cu = bpy.data.curves.new('TrolleyPath', 'CURVE')
cu.dimensions = '3D'
cu.resolution_u = 2
sp = cu.splines.new('POLY')
sp.points.add(len(pts)-1)
for i,(x,y,z) in enumerate(pts):
    sp.points[i].co = (x, y, z, 1.0)
sp.use_cyclic_u = True
curve = bpy.data.objects.new('TrolleyPath', cu)
bpy.context.scene.collection.objects.link(curve)
print('curve created, cyclic, len', len(pts))

# 2) 车体
before = set(bpy.data.objects)
bpy.ops.import_scene.gltf(filepath=a.trolley)
imported = [o for o in bpy.data.objects if o not in before]
roots = [o for o in imported if o.parent is None]
print('imported', len(imported), 'roots', [o.name for o in roots][:3])

# 3) 挂到 Empty 上，由 Empty 沿曲线跑
emp = bpy.data.objects.new('TrolleyRig', None)
bpy.context.scene.collection.objects.link(emp)
emp.location = (0,0,0)
for r in roots:
    r.parent = emp
    r.matrix_parent_inverse = emp.matrix_world.inverted()

con = emp.constraints.new('FOLLOW_PATH')
con.target = curve
con.use_curve_follow = True
con.use_fixed_location = True
con.forward_axis = 'FORWARD_Y'
con.up_axis = 'UP_Z'

# 4) 动画：offset_factor 0 → 1
sc = bpy.context.scene
sc.frame_start = 1
sc.frame_end = a.frames
try:
    bpy.context.preferences.edit.keyframe_new_interpolation_type = 'LINEAR'
except Exception:
    pass
con.offset_factor = 0.0
con.keyframe_insert(data_path='offset_factor', frame=1)
con.offset_factor = 1.0
con.keyframe_insert(data_path='offset_factor', frame=a.frames)
# 线性插值（Blender 5 的 Action 结构变了，失败就跳过——默认 Bezier 也能看）
try:
    act = emp.animation_data.action
    fcs = []
    if hasattr(act, 'fcurves'):
        fcs = list(act.fcurves)
    else:
        for lay in getattr(act, 'layers', []):
            for strip in getattr(lay, 'strips', []):
                for cbag in getattr(strip, 'channelbags', []):
                    fcs += list(cbag.fcurves)
    for fc in fcs:
        for kp in fc.keyframe_points:
            kp.interpolation = 'LINEAR'
    print('fcurves set linear:', len(fcs))
except Exception as e:
    print('interp skip', e)
print('animated 1..%d' % a.frames)

bpy.ops.wm.save_as_mainfile(filepath=a.blend)
print('SAVED', a.blend)

if a.render:
    os.makedirs(a.shots, exist_ok=True)
    sc.render.engine='BLENDER_EEVEE'
    sc.render.resolution_x, sc.render.resolution_y = 1600, 900
    cam = bpy.data.cameras.new('c_tram'); cam.lens=35; cam.clip_start=0.5; cam.clip_end=20000
    co = bpy.data.objects.new('c_tram', cam); bpy.context.collection.objects.link(co)
    look = Vector((2650,-1250,50))
    co.location = look + Vector((120,-160,70))
    co.rotation_euler = (look-co.location).to_track_quat('-Z','Y').to_euler()
    sc.camera = co
    for fr in [int(x) for x in a.render.split(',')]:
        sc.frame_set(fr)
        sc.render.filepath = os.path.join(a.shots, f'trolley_f{fr}.png')
        bpy.ops.render.render(write_still=True)
        print('SHOT', sc.render.filepath)
