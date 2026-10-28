"""双向对拍：用 UE 的 002_01 走路验证 RDR2 骨架（并把 RDR2 走路反套到 UE 骨架上）。

方向 A：UE 002_01（clips_slim/002_01.fbx，72 帧）→ 按【世界旋转拷贝】套到 RDR2 骨架上，
        用 RDR2 的网格渲染 —— 若这条"已知正常"的走路在 RDR2 骨架上正常，说明骨架/蒙皮没问题。
方向 B：我们的 rdr2_walk（walk_interior 解出来的）→ 同一套世界旋转拷贝套到 UE 骨架上，
        渲染 UE 自带的网格（若 fbx 内有）—— 若它也僵，说明是我们的数据问题，不是骨架。

用法:
  blender -b --python tools/xcheck_ue_rdr2.py -- --mode a     # UE 走路 → RDR2
  blender -b --python tools/xcheck_ue_rdr2.py -- --mode b     # RDR2 走路 → UE
"""
import bpy
import os
import sys
import math
from mathutils import Matrix, Vector

UE_FBX = r'D:/BrainMaker/骑砍2动画重定向/input/source/ue_mannequin/clips_slim/002_01.fbx'
RDR2_GLB = r'D:/BrainMaker/大镖客2解包分析/export/npc/player/player_zero_walk.glb'
OUT = r'D:/BrainMaker/大镖客2解包分析/work/npc/verify'

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
MODE = 'a'
if '--mode' in argv:
    MODE = argv[argv.index('--mode') + 1]

# UE mannequin → RDR2
MAP = {
    'pelvis': 'SKEL_Pelvis',
    'spine_01': 'SKEL_Spine0',
    'spine_02': 'SKEL_Spine2',
    'spine_03': 'SKEL_Spine4',
    'neck_01': 'SKEL_Neck0',
    'head': 'SKEL_Head',
    'clavicle_l': 'SKEL_L_Clavicle', 'upperarm_l': 'SKEL_L_UpperArm',
    'lowerarm_l': 'SKEL_L_Forearm', 'hand_l': 'SKEL_L_Hand',
    'thigh_l': 'SKEL_L_Thigh', 'calf_l': 'SKEL_L_Calf', 'foot_l': 'SKEL_L_Foot',
    'clavicle_r': 'SKEL_R_Clavicle', 'upperarm_r': 'SKEL_R_UpperArm',
    'lowerarm_r': 'SKEL_R_Forearm', 'hand_r': 'SKEL_R_Hand',
    'thigh_r': 'SKEL_R_Thigh', 'calf_r': 'SKEL_R_Calf', 'foot_r': 'SKEL_R_Foot',
}


def clear_pose(arm):
    for pb in arm.pose.bones:
        pb.matrix_basis = Matrix.Identity(4)
    bpy.context.view_layer.update()


def load_rdr2():
    bpy.ops.import_scene.gltf(filepath=RDR2_GLB)
    objs = [o for o in bpy.data.objects]
    arm = [o for o in objs if o.type == 'ARMATURE'][0]
    mesh = max([o for o in objs if o.type == 'MESH'], key=lambda o: len(o.data.vertices))
    return arm, mesh


def load_ue():
    objs_before = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath=UE_FBX)
    objs = [o for o in bpy.data.objects if o not in objs_before]
    arm = [o for o in objs if o.type == 'ARMATURE'][0]
    meshes = [o for o in objs if o.type == 'MESH']
    # ⚠️ bpy.data.actions[0] 可能是 glb 导入时带的动作（rdr2_walk）；这里只认 fbx 的动作
    cand = [a for a in bpy.data.actions
            if ('Unreal' in a.name or 'Take' in a.name or 'Base Layer' in a.name)]
    if not cand:
        cand = [a for a in bpy.data.actions if 'rdr2' not in a.name.lower()]
    act = max(cand, key=lambda a: a.frame_range[1] - a.frame_range[0]) if cand else None
    return arm, meshes, act


def copy_world_rotations(src_arm, dst_arm, act, frames):
    """逐帧把 src 每根骨的**世界旋转**写到 dst 同名映射骨上（位置保持 dst 自身骨架）。"""
    # 让 dst 绑定动作（新建一个 action）
    if not dst_arm.animation_data:
        dst_arm.animation_data_create()
    new_act = bpy.data.actions.new('xcheck')
    dst_arm.animation_data.action = new_act
    if hasattr(dst_arm.animation_data, 'action_slot') and getattr(new_act, 'slots', None):
        try:
            dst_arm.animation_data.action_slot = new_act.slots[0]
        except Exception:
            pass

    for f in frames:
        bpy.context.scene.frame_set(f)
        bpy.context.view_layer.update()
        src_world = {}
        for ue_name, rd_name in MAP.items():
            pb_s = src_arm.pose.bones.get(ue_name)
            pb_d = dst_arm.pose.bones.get(rd_name)
            if not pb_s or not pb_d:
                continue
            M = src_arm.matrix_world @ pb_s.matrix      # 源骨世界矩阵
            # ★ 两个 armature 的 object 朝向可能不同（fbx 导入常带 −90°X）：
            #   先把源姿态换回"源 armature 自身空间"，再换到目标 armature 空间
            Qa_s = src_arm.matrix_world.to_quaternion()
            Qa_d = dst_arm.matrix_world.to_quaternion()
            R = Qa_d @ (Qa_s.inverted() @ M.to_quaternion())
            # 目标：保持自身平移，只换旋转
            cur = dst_arm.matrix_world @ pb_d.matrix
            loc = cur.to_translation()
            newM = Matrix.Translation(loc) @ R.to_matrix().to_4x4()
            pb_d.matrix = dst_arm.matrix_world.inverted() @ newM
            bpy.context.view_layer.update()
        for ue_name, rd_name in MAP.items():
            pb_d = dst_arm.pose.bones.get(rd_name)
            if pb_d:
                pb_d.keyframe_insert('rotation_quaternion', frame=f)
                pb_d.keyframe_insert('location', frame=f)
    return new_act


def setup_render(ground_z, center, h):
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'
    sc.cycles.samples = 20
    sc.cycles.device = 'CPU'
    sc.render.resolution_x, sc.render.resolution_y = 620, 820
    w = bpy.data.worlds.new('W')
    sc.world = w
    w.use_nodes = True
    w.node_tree.nodes['Background'].inputs[0].default_value = (0.09, 0.10, 0.12, 1)
    bpy.ops.mesh.primitive_plane_add(size=14, location=(0, 0, ground_z - 0.002))
    g = bpy.context.active_object
    gm = bpy.data.materials.new('G')
    gm.use_nodes = True
    gm.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.24, 0.25, 0.28, 1)
    g.data.materials.append(gm)
    cam_d = bpy.data.cameras.new('C')
    cam_d.lens = 55
    cam = bpy.data.objects.new('C', cam_d)
    bpy.context.collection.objects.link(cam)
    sc.camera = cam
    cam.location = (h * 1.0, -h * 2.6, center.z + h * 0.18)
    d = cam.location - Vector((center.x, 0, center.z))
    cam.rotation_euler = d.to_track_quat('Z', 'Y').to_euler()
    ld = bpy.data.lights.new('S', 'SUN')
    ld.energy = 3.0
    lo = bpy.data.objects.new('S', ld)
    bpy.context.collection.objects.link(lo)
    lo.rotation_euler = (math.radians(55), 0, math.radians(35))


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.scene.render.fps = 30

    if MODE == 'a':
        r_arm, r_mesh = load_rdr2()
        ue_arm, ue_meshes, ue_act = load_ue()
        # UE 的 fbx 可能自带网格，先隐藏，只用它提供动作
        for m in ue_meshes:
            m.hide_render = True
        f0, f1 = (int(round(v)) for v in ue_act.frame_range) if ue_act else (1, 72)
        frames = list(range(f0, f1 + 1, 2))
        print('XCHK 方向A：UE %s 帧 %d~%d → RDR2 骨架' % (ue_act.name if ue_act else '?', f0, f1))
        # UE 动作要先绑到 UE 骨架
        if not ue_arm.animation_data:
            ue_arm.animation_data_create()
        ue_arm.animation_data.action = ue_act
        if hasattr(ue_arm.animation_data, 'action_slot') and getattr(ue_act, 'slots', None):
            try:
                ue_arm.animation_data.action_slot = ue_act.slots[0]
            except Exception:
                pass
        copy_world_rotations(ue_arm, r_arm, ue_act, frames)
        mesh = r_mesh
        tag = 'ue_walk_on_rdr2'
    else:
        r_arm, r_mesh = load_rdr2()
        ue_arm, ue_meshes, ue_act = load_ue()
        # RDR2 的动作在 r_arm 上；把它套到 UE 骨架
        f0, f1 = 0, 120
        if r_arm.animation_data and r_arm.animation_data.action:
            fr = r_arm.animation_data.action.frame_range
            f0, f1 = int(round(fr[0])), int(round(fr[1]))
        frames = list(range(f0, f1 + 1, 4))
        print('XCHK 方向B：RDR2 walk 帧 %d~%d → UE 骨架' % (f0, f1))
        r_mesh.hide_render = True
        copy_world_rotations(r_arm, ue_arm, None, frames)
        mesh = ue_meshes[0] if ue_meshes else r_mesh
        tag = 'rdr2_walk_on_ue'

    # 取包围盒做取景
    mn = Vector((1e9,) * 3)
    mx = Vector((-1e9,) * 3)
    for o in [mesh]:
        for c in o.bound_box:
            w = o.matrix_world @ Vector(c)
            for i in range(3):
                mn[i] = min(mn[i], w[i])
                mx[i] = max(mx[i], w[i])
    center = (mn + mx) / 2
    h = max(mx.x - mn.x, mx.y - mn.y, mx.z - mn.z)
    setup_render(mn.z, center, h)
    sc = bpy.context.scene
    sc.frame_start, sc.frame_end = frames[0], frames[-1]
    sc.render.fps = 24
    outs = []
    for i, f in enumerate([frames[0], frames[len(frames)//3], frames[2*len(frames)//3], frames[-1]]):
        sc.frame_set(f)
        sc.render.filepath = os.path.join(OUT, '%s_%d.png' % (tag, i))
        bpy.ops.render.render(write_still=True)
        outs.append(sc.render.filepath)
        print('XCHK OUT', sc.render.filepath)


main()
