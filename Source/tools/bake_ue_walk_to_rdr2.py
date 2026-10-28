"""反向验证：把 UE 的走路（002_01）**重定向到 RDR2 骨架**并烘成 glb，方便在查看器里直接看。

方法：rest-aware 世界增量（delta）
    delta      = Q_ue_pose_world ⊗ Q_ue_rest_world⁻¹      # "这根骨相对于自己静止姿势转了多少"
    Q_target   = delta ⊗ Q_rdr2_rest_world                # 套到目标骨的静止朝向上
这样目标保持自己的站姿（A-pose），只吃源动画的"变化量"，不会被源的 T-pose 带偏。

用法: blender -b --python tools/bake_ue_walk_to_rdr2.py
输出: export/npc/player/player_zero_ue_walk.glb（在 export/npc/anim.html 下拉里可选）
"""
import bpy
import os
import sys
import math
from mathutils import Matrix, Vector, Quaternion

UE_FBX = r'D:/BrainMaker/骑砍2动画重定向/input/source/ue_mannequin/clips_slim/002_01.fbx'
RDR2_GLB = r'D:/BrainMaker/大镖客2解包分析/export/npc/player/player_zero_walk.glb'
OUT_GLB = r'D:/BrainMaker/大镖客2解包分析/export/npc/player/player_zero_ue_walk.glb'
OUT_PNG = r'D:/BrainMaker/大镖客2解包分析/work/npc/verify'

# 顺序 = 父 → 子（先设父再设子，世界矩阵才对）
MAP = [
    ('pelvis', 'SKEL_Pelvis'),
    ('spine_01', 'SKEL_Spine0'),
    ('spine_02', 'SKEL_Spine2'),
    ('spine_03', 'SKEL_Spine4'),
    ('neck_01', 'SKEL_Neck1'),
    ('head', 'SKEL_Head'),
    ('clavicle_l', 'SKEL_L_Clavicle'),
    ('upperarm_l', 'SKEL_L_UpperArm'),
    ('lowerarm_l', 'SKEL_L_Forearm'),
    ('hand_l', 'SKEL_L_Hand'),
    ('clavicle_r', 'SKEL_R_Clavicle'),
    ('upperarm_r', 'SKEL_R_UpperArm'),
    ('lowerarm_r', 'SKEL_R_Forearm'),
    ('hand_r', 'SKEL_R_Hand'),
    ('thigh_l', 'SKEL_L_Thigh'),
    ('calf_l', 'SKEL_L_Calf'),
    ('foot_l', 'SKEL_L_Foot'),
    ('thigh_r', 'SKEL_R_Thigh'),
    ('calf_r', 'SKEL_R_Calf'),
    ('foot_r', 'SKEL_R_Foot'),
]


# 这几根用"绝对朝向"（否则躯干会把源的弯曲和自身 rest 叠加，显得更驼）
# 绝对朝向会让"目标自身的 rest 弯曲"被源覆盖/反之叠加，实测反而更驼 ⇒ 保持纯增量。
# （想试绝对：把要绝对朝向的骨名放进来，例如 {'SKEL_Pelvis','SKEL_Spine0'}）
ABSOLUTE_BONES = set()
Q_FRAME = Quaternion((1, 0, 0, 0))   # 运行期按两侧 armature 朝向重算（见 main）


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.fps = 30

    # 1) RDR2（网格 + 骨架 + 自带 walk，我们只借它的骨架和网格）
    bpy.ops.import_scene.gltf(filepath=RDR2_GLB)
    objs = list(bpy.data.objects)
    r_arm = [o for o in objs if o.type == 'ARMATURE'][0]
    r_mesh = max([o for o in objs if o.type == 'MESH'], key=lambda o: len(o.data.vertices))
    for o in objs:
        if o.type == 'MESH' and o is not r_mesh:
            bpy.data.objects.remove(o, do_unlink=True)
    if r_arm.animation_data:
        r_arm.animation_data_clear()          # 丢掉 rdr2 自己的走路

    # 2) UE 源
    before = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath=UE_FBX)
    new = [o for o in bpy.data.objects if o not in before]
    ue_arm = [o for o in new if o.type == 'ARMATURE'][0]
    ue_meshes = [o for o in new if o.type == 'MESH']
    for m in ue_meshes:
        m.hide_render = True
    cand = [a for a in bpy.data.actions if 'Unreal' in a.name or 'Take' in a.name]
    ue_act = max(cand, key=lambda a: a.frame_range[1] - a.frame_range[0])
    if not ue_arm.animation_data:
        ue_arm.animation_data_create()
    ue_arm.animation_data.action = ue_act
    if hasattr(ue_arm.animation_data, 'action_slot') and getattr(ue_act, 'slots', None):
        try:
            ue_arm.animation_data.action_slot = ue_act.slots[0]
        except Exception:
            pass
    fs = [int(round(v)) for v in ue_act.frame_range]
    print('[UE→RDR2] 源动作 %s 帧 %s' % (ue_act.name, fs))

    # 3) 两边的 rest 世界旋转
    def rest_world_q(arm):
        out = {}
        for b in arm.data.bones:
            out[b.name] = (arm.matrix_world @ b.matrix_local).to_quaternion()
        return out

    ue_rest = rest_world_q(ue_arm)
    r_rest = rest_world_q(r_arm)
    # 源/目标 armature 的"对象朝向"可能不同（fbx 常带 −90°X）。增量法里它会自然抵消，
    # 但"绝对朝向"必须显式换帧，否则整条躯干会被转 90°。
    Q_FRAME = r_arm.matrix_world.to_quaternion() @ ue_arm.matrix_world.to_quaternion().inverted()

    # 4) 逐帧烘
    if not r_arm.animation_data:
        r_arm.animation_data_create()
    act = bpy.data.actions.new('ue_walk_on_rdr2')
    r_arm.animation_data.action = act
    if hasattr(r_arm.animation_data, 'action_slot') and getattr(act, 'slots', None):
        try:
            r_arm.animation_data.action_slot = act.slots[0]
        except Exception:
            pass

    miss = [(u, r) for u, r in MAP if u not in ue_rest or r not in r_rest]
    if miss:
        print('[UE→RDR2] 缺骨，跳过：', miss)

    for f in range(fs[0], fs[1] + 1):
        sc.frame_set(f)
        bpy.context.view_layer.update()
        for ue_name, rd_name in MAP:
            if ue_name not in ue_rest or rd_name not in r_rest:
                continue
            pb_s = ue_arm.pose.bones.get(ue_name)
            pb_d = r_arm.pose.bones.get(rd_name)
            if not pb_s or not pb_d:
                continue
            q_src = (ue_arm.matrix_world @ pb_s.matrix).to_quaternion()
            if rd_name in ABSOLUTE_BONES:
                # 躯干/头：直接取源的**绝对世界朝向**（保证和源同一个前倾角）
                q_new = q_src @ Q_FRAME
            else:
                # 四肢：rest-aware 增量（保留我们自己 A-pose 的站姿）
                delta = q_src @ ue_rest[ue_name].inverted()
                q_new = delta @ r_rest[rd_name]
            cur = (r_arm.matrix_world @ pb_d.matrix).to_translation()
            M = Matrix.Translation(cur) @ q_new.to_matrix().to_4x4()
            pb_d.matrix = r_arm.matrix_world.inverted() @ M
            bpy.context.view_layer.update()
        for ue_name, rd_name in MAP:
            pb_d = r_arm.pose.bones.get(rd_name)
            if pb_d:
                pb_d.keyframe_insert('rotation_quaternion', frame=f)

    # 4b) 骨盆上下起伏：UE 的 pelvis 世界 z 在 0.855→0.902 之间起伏（原地走的重心波动）
    ue_pelvis_rest = None
    bobs = {}
    for f in range(fs[0], fs[1] + 1):
        sc.frame_set(f)
        bpy.context.view_layer.update()
        pb = ue_arm.pose.bones.get('pelvis')
        if pb:
            z = (ue_arm.matrix_world @ pb.matrix).to_translation().z
            if ue_pelvis_rest is None:
                ue_pelvis_rest = z
            bobs[f] = z - ue_pelvis_rest
    root = r_arm.pose.bones.get('SKEL_ROOT')
    if root is not None and bobs:
        for f, dz in bobs.items():
            sc.frame_set(f)
            Rw = (r_arm.matrix_world @ root.matrix).to_3x3()
            root.location = Rw.inverted() @ Vector((0, 0, dz))
            root.keyframe_insert('location', frame=f)
        print('[UE→RDR2] 骨盆起伏 %+.3f ~ %+.3f m' % (min(bobs.values()), max(bobs.values())))

    # 5) 逐帧落地
    ground = None
    minz = 1e9
    for f in range(fs[0], fs[1] + 1):
        sc.frame_set(f)
        bpy.context.view_layer.update()
        for bn in ('SKEL_L_Foot', 'SKEL_R_Foot', 'SKEL_L_Toe0', 'SKEL_R_Toe0'):
            pb = r_arm.pose.bones.get(bn)
            if pb:
                minz = min(minz, (r_arm.matrix_world @ pb.head).z)
    dz = -1.0 - minz
    root = r_arm.pose.bones.get('SKEL_ROOT')
    if root is not None:
        for f in range(fs[0], fs[1] + 1):
            sc.frame_set(f)
            Rw = (r_arm.matrix_world @ root.matrix).to_3x3()
            base = root.location.copy()
            root.location = base + Rw.inverted() @ Vector((0, 0, dz))
            root.keyframe_insert('location', frame=f)
        print('[UE→RDR2] 整体抬升 %.3f m' % dz)

    sc.frame_start, sc.frame_end = fs[0], fs[1]

    # 5c) 只留我们烘的这一条动作（导入残留的 action 会被一起导出，查看器里就会出现 3 条）
    for a in list(bpy.data.actions):
        if a is not act:
            try:
                bpy.data.actions.remove(a)
            except Exception:
                pass
    print('[UE→RDR2] 剩余动作:', [a.name for a in bpy.data.actions])

    # 6) 导出 glb（只导骨架 + 网格）
    for o in list(bpy.data.objects):
        if o.type == 'MESH' and o is not r_mesh:
            bpy.data.objects.remove(o, do_unlink=True)
    bpy.ops.object.select_all(action='DESELECT')
    r_arm.select_set(True)
    r_mesh.select_set(True)
    bpy.context.view_layer.objects.active = r_arm
    bpy.ops.export_scene.gltf(filepath=OUT_GLB, export_format='GLB',
                              export_animations=True, export_skins=True,
                              export_apply=False, use_selection=True)
    print('[UE→RDR2] 导出 %s (%.1f MB)' % (OUT_GLB, os.path.getsize(OUT_GLB) / 1e6))

    # 7) 侧视渲染 4 帧验收
    mn = Vector((1e9,) * 3)
    for c in r_mesh.bound_box:
        w = r_mesh.matrix_world @ Vector(c)
        for i in range(3):
            mn[i] = min(mn[i], w[i])
    sc.render.engine = 'CYCLES'
    sc.cycles.samples = 18
    sc.cycles.device = 'CPU'
    sc.render.resolution_x, sc.render.resolution_y = 620, 820
    w = bpy.data.worlds.new('W'); sc.world = w; w.use_nodes = True
    w.node_tree.nodes['Background'].inputs[0].default_value = (0.09, 0.10, 0.12, 1)
    bpy.ops.mesh.primitive_plane_add(size=14, location=(0, 0, mn.z - 0.002))
    g = bpy.context.active_object
    gm = bpy.data.materials.new('G'); gm.use_nodes = True
    gm.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.24, 0.25, 0.28, 1)
    g.data.materials.append(gm)
    cd = bpy.data.cameras.new('C'); cd.lens = 55
    cam = bpy.data.objects.new('C', cd); bpy.context.collection.objects.link(cam); sc.camera = cam
    cam.location = (3.2, 0.0, 0.05)
    cam.rotation_euler = (math.radians(90), 0, math.radians(90))
    ld = bpy.data.lights.new('S', 'SUN'); ld.energy = 3.0
    lo = bpy.data.objects.new('S', ld); bpy.context.collection.objects.link(lo)
    lo.rotation_euler = (math.radians(55), 0, math.radians(120))
    for i, f in enumerate([fs[0], fs[0] + (fs[1]-fs[0])//3, fs[0] + 2*(fs[1]-fs[0])//3, fs[1]-1]):
        sc.frame_set(f)
        sc.render.filepath = os.path.join(OUT_PNG, 'ue2rdr2_%d.png' % i)
        bpy.ops.render.render(write_still=True)
        print('OUT', sc.render.filepath)


main()
