"""渲染室内成品视角（取消隐藏墙壳，相机摆在室内）。"""
import bpy, math
from mathutils import Vector

sc = bpy.context.scene
for ob in bpy.data.objects:
    if ob.type == 'MESH':
        ob.hide_render = False
        ob.hide_viewport = False

# 室内补光
for o in list(bpy.data.objects):
    if o.type == 'LIGHT':
        bpy.data.objects.remove(o, do_unlink=True)
for i, (p, e) in enumerate([((0,0,2.6),700),((3,2,1.8),350),((-3,-2,1.8),350),((0,-2.5,1.2),250)]):
    ld = bpy.data.lights.new('LI%d'%i,'POINT'); ld.energy=e; ld.shadow_soft_size=0.8
    lo = bpy.data.objects.new('LI%d'%i,ld); lo.location=p; sc.collection.objects.link(lo)
w = sc.world
if w is None:
    w = bpy.data.worlds.new('W'); sc.world = w
w.use_nodes = True
w.node_tree.nodes['Background'].inputs[0].default_value = (0.25,0.24,0.22,1)
w.node_tree.nodes['Background'].inputs[1].default_value = 0.6

cam = bpy.data.objects.get('Camera')
if cam is None:
    cd = bpy.data.cameras.new('C'); cam = bpy.data.objects.new('Camera',cd); sc.collection.objects.link(cam)
cam.data.lens = 20; cam.data.clip_end = 100
cam.rotation_mode = 'QUATERNION'
sc.camera = cam
sc.render.resolution_x = 1280; sc.render.resolution_y = 720
sc.render.engine = 'BLENDER_EEVEE'

# 用近裁剪面切开外墙（相机在墙外，clip_start 刚好越过墙面）
# shell_main: x -6.55..2.20, y -2.93..2.99
views = [
    ('cut_west',  (-12.0,  0.0, 3.0), (-2.0,  0.0, -0.6), 6.0),
    ('cut_south', ( -2.2, -9.5, 3.0), (-2.0,  0.2, -0.6), 7.0),
    ('cut_top',   ( -9.0, -7.0, 9.0), (-1.5,  0.5, -0.6), 11.0),
    ('cut_ne',    (  8.0,  6.5, 4.0), (-2.0, -0.3, -0.6), 16.0),
]
for name, loc, tgt, cs in views:
    cam.location = loc
    cam.data.clip_start = cs
    cam.rotation_quaternion = (Vector(tgt)-Vector(loc)).to_track_quat('-Z','Y')
    sc.render.filepath = r'D:/BrainMaker/大镖客2解包分析/deliverable/blender/willard/inside_%s.png' % name
    bpy.ops.render.render(write_still=True)
    print('SHOT', name)
print('DONE')
