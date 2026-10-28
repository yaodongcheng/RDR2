"""给 Blender GUI 用的启动脚本：导入主角 glb，摆好相机/灯光/当前帧，直接能看走路。

用法（GUI 启动，不是后台）:
  "<blender.exe>" --python tools/open_walk_in_blender.py
"""
import bpy
import math
from mathutils import Vector

GLB = r'D:/BrainMaker/大镖客2解包分析/export/npc/player/player_zero_walk.glb'

# 清空默认场景
bpy.ops.wm.read_factory_settings(use_empty=True)

# 导入
bpy.ops.import_scene.gltf(filepath=GLB)
# ★ 导入器会给骨架造一个 42 顶点的 Icosphere 占位球（半径 1m，罩在原点），必须删掉
ms = sorted([o for o in bpy.data.objects if o.type == 'MESH'], key=lambda o: -len(o.data.vertices))
meshes = ms[:1]
for o in ms[1:]:
    print('删除导入器占位球:', o.name, len(o.data.vertices), '顶点')
    bpy.data.objects.remove(o, do_unlink=True)
arms = [o for o in bpy.data.objects if o.type == 'ARMATURE']
print('打开: 网格 %d / 骨架 %d / 动作 %s' % (
    len(meshes), len(arms), [a.name for a in bpy.data.actions]))

# 包围盒
mn = Vector((1e9,) * 3)
mx = Vector((-1e9,) * 3)
for o in meshes:
    for c in o.bound_box:
        w = o.matrix_world @ Vector(c)
        for i in range(3):
            mn[i] = min(mn[i], w[i])
            mx[i] = max(mx[i], w[i])
H = max(mx.z - mn.z, 1.2)
cz = (mn.z + mx.z) / 2

# 地面
bpy.ops.mesh.primitive_plane_add(size=12, location=(0, 0, mn.z - 0.002))
g = bpy.context.active_object
g.name = 'Ground'
gm = bpy.data.materials.new('GroundMat')
gm.use_nodes = True
gm.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.32, 0.33, 0.36, 1)
g.data.materials.append(gm)

# 相机
cam_d = bpy.data.cameras.new('Cam')
cam_d.lens = 55
cam = bpy.data.objects.new('Cam', cam_d)
bpy.context.collection.objects.link(cam)
cam.location = (H * 0.75, -H * 2.3, cz + H * 0.15)
cam.rotation_euler = (cam.location - Vector((0, 0, cz))).to_track_quat('Z', 'Y').to_euler()
bpy.context.scene.camera = cam

# 灯
for ang, en in (((52, 0, 30), 3.0), ((52, 0, -110), 1.4), ((12, 0, 180), 1.2)):
    ld = bpy.data.lights.new('S', 'SUN')
    ld.energy = en
    lo = bpy.data.objects.new('S', ld)
    bpy.context.collection.objects.link(lo)
    lo.rotation_euler = tuple(math.radians(a) for a in ang)

# 世界底色
w = bpy.data.worlds.new('W')
bpy.context.scene.world = w
w.use_nodes = True
w.node_tree.nodes['Background'].inputs[0].default_value = (0.08, 0.09, 0.11, 1)

# 帧范围 + 停在一个迈步帧（不要停在第 0 帧，看起来像 A-pose）
acts = list(bpy.data.actions)
sc = bpy.context.scene
if acts:
    f0, f1 = (int(round(v)) for v in acts[0].frame_range)
    sc.frame_start, sc.frame_end = f0, f1
    sc.frame_set(f0 + (f1 - f0) // 5)
    print('动作 %s 帧 %d~%d，当前停在第 %d 帧' % (acts[0].name, f0, f1, sc.frame_current))
sc.render.engine = 'BLENDER_EEVEE_NEXT'
sc.render.fps = 30

# 视口切成"相机视角"，模型居中
def _post():
    try:
        for area in bpy.context.screen.areas:
            if area.type == 'VIEW_3D':
                region = [r for r in area.regions if r.type == 'WINDOW'][0]
                with bpy.context.temp_override(area=area, region=region):
                    bpy.ops.view3d.view_camera()
                    for sp in area.spaces:
                        if sp.type == 'VIEW_3D':
                            sp.shading.type = 'MATERIAL'
                            sp.overlay.show_floor = False
    except Exception as e:
        print('视口切换失败（手动按 Numpad 0 即可）:', e)
    return None

bpy.app.timers.register(_post, first_interval=1.2)
print('提示：空格 = 播放/暂停，拖动时间轴看任意帧')
