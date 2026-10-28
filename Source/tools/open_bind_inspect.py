"""打开 Blender 载入主角（骨骼 + 蒙皮），**不做任何有风险的操作**。

踩坑记录：
  * Blender 5.2 的渲染引擎枚举是 `BLENDER_EEVEE`，**不是** `BLENDER_EEVEE_NEXT`
    （写 NEXE 会抛 TypeError，脚本中断 → Blender 弹报错窗口，看起来像"卡死"）
  * 启动阶段调用 `bpy.ops.object.mode_set` / 视口 op 容易死锁，所以这里一律不做，
    只做：导入 → 删占位球 → 设帧 → 骨架置前 → 选中网格。剩下的用快捷键。
  * glTF 导入器会额外生成一个 42 顶点的 `Icosphere`（骨骼显示占位，半径 1m，
    正好罩住角色）= 用户看到的"一个球"，必须删掉。

用法: "<blender.exe>" --factory-startup --python tools/open_bind_inspect.py
"""
import bpy
import math

GLB = r'D:/BrainMaker/大镖客2解包分析/export/npc/player/player_zero_walk.glb'


def log(*a):
    print('[BIND]', *a)


bpy.ops.import_scene.gltf(filepath=GLB)

# 1) 删掉导入器造的占位球
ms = sorted([o for o in bpy.data.objects if o.type == 'MESH'],
            key=lambda o: -len(o.data.vertices))
mesh = ms[0]
for o in ms[1:]:
    log('删除占位球', o.name, len(o.data.vertices), '顶点')
    bpy.data.objects.remove(o, do_unlink=True)

arm = [o for o in bpy.data.objects if o.type == 'ARMATURE'][0]
log('网格 %s / %d 顶点 / %d 顶点组；骨架 %d 骨'
    % (mesh.name, len(mesh.data.vertices), len(mesh.vertex_groups), len(arm.data.bones)))

# 2) 骨架：穿透显示 + 粗一点的骨型
arm.show_in_front = True
arm.data.display_type = 'OCTAHEDRAL'
arm.data.show_names = False

# 3) 帧：停在一个跨步帧（第 0 帧接近 A-pose，看不出在走）
acts = list(bpy.data.actions)
sc = bpy.context.scene
if acts:
    f0, f1 = (int(round(v)) for v in acts[0].frame_range)
    sc.frame_start, sc.frame_end = f0, f1
    sc.frame_set(f0 + (f1 - f0) // 5)
    log('动作 %s，帧 %d~%d，当前第 %d 帧' % (acts[0].name, f0, f1, sc.frame_current))

# 4) 环境光（只为好看，不影响数据）
try:
    if sc.world is None:
        sc.world = bpy.data.worlds.new('W')
    sc.world.use_nodes = True
    sc.world.node_tree.nodes['Background'].inputs[0].default_value = (0.12, 0.13, 0.16, 1)
    for ang, en in (((55, 0, 30), 3.0), ((50, 0, -115), 1.5)):
        ld = bpy.data.lights.new('S', 'SUN')
        ld.energy = en
        lo = bpy.data.objects.new('S', ld)
        bpy.context.collection.objects.link(lo)
        lo.rotation_euler = tuple(math.radians(a) for a in ang)
except Exception as e:
    log('灯光设置跳过:', e)

# 5) 默认选中左大腿权重 + 选中网格
for i, vg in enumerate(mesh.vertex_groups):
    if vg.name == 'SKEL_L_Thigh':
        mesh.vertex_groups.active_index = i
        log('默认权重组 = SKEL_L_Thigh (#%d)' % i)
        break
bpy.context.view_layer.objects.active = mesh
mesh.select_set(True)
arm.select_set(True)

log('完成。操作：空格=播放 | Numpad0=相机视角 | Numpad.(Del)=聚焦 | '
    'Ctrl+Tab=进入权重绘制 | Z=透视/实体')
