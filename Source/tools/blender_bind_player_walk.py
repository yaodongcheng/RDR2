"""用 Blender 把「RDR2 主角网格」绑到「RDR2 原生骨架」上，并套上原生 walk 动画。

为什么不用 Sollumz：Sollumz-RDR 只吃 CodeWalker XML、且要求 Blender 4.0；
而我们两端（网格 glb / 骨架+动画 gltf）都是标准 glTF，Blender 自带导入导出就够，
蒙皮用 Blender 的 Automatic Weights（Bone Heat）。

输入：
  MESH  export/npc/player/player_zero/player_zero.glb          （网格，bind pose，脚在 y=0）
  SKEL  骑砍2动画重定向/input/source/rdr2/rdr2_walk.gltf        （763 joints + move 动画）
输出：
  OUT    export/npc/player/player_zero_walk.glb                 （网格 + 蒙皮 + 动画）
  PNG    work/npc/verify/blender_<frame>.png                    （验收渲染）

用法: blender -b --python tools/blender_bind_player_walk.py
"""
import bpy
import os
import math
from mathutils import Vector

PROJ = r'D:/BrainMaker/大镖客2解包分析'
MESH = os.path.join(PROJ, 'export/npc/player/player_zero/player_zero.glb')
# 可用环境变量覆盖（便于 A/B 试不同动画源，不改脚本）
# ★ 2026-10-17：改用「move 片段」（= biped_q7@biped@0_0，121 帧，见 RDR2_ycd动画解码.md §7.3）
SKEL = os.environ.get('RDR2_SKEL',
                      r'D:/BrainMaker/骑砍2动画重定向/input/source/rdr2/rdr2_walk.gltf')
OUTG = os.environ.get('RDR2_OUTG', os.path.join(PROJ, 'export/npc/player/player_zero_walk.glb'))
PNGPREFIX = os.environ.get('RDR2_PNG_PREFIX', 'bind')
PNGD = os.path.join(PROJ, 'work/npc/verify')


def bbox(objs):
    mn = Vector((1e9,) * 3)
    mx = Vector((-1e9,) * 3)
    for o in objs:
        for c in o.bound_box:
            w = o.matrix_world @ Vector(c)
            for i in range(3):
                mn[i] = min(mn[i], w[i])
                mx[i] = max(mx[i], w[i])
    return mn, mx


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    # ★ 30fps：.ycd 的时间轴是 30fps（帧号/30 = 秒）。Blender 默认 24fps 会把 glTF 里
    #   按秒写入的关键帧重新按 24fps 解释 ⇒ 动作整体慢 25%。这里显式对齐。
    bpy.context.scene.render.fps = 30

    # 1) 骨架 + 动画
    bpy.ops.import_scene.gltf(filepath=SKEL)
    arms = [o for o in bpy.data.objects if o.type == 'ARMATURE']
    if not arms:
        print('BIND_FAIL 没有导入到骨架')
        return
    arm = arms[0]
    bpy.ops.object.select_all(action='DESELECT')
    arm.select_set(True)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    print('BIND_INFO 骨架变换已烘焙（避免 glTF 导出 bind 矩阵错位）')
    acts = list(bpy.data.actions)
    print('BIND_INFO 骨架=%s 骨=%d 动作=%s' % (arm.name, len(arm.data.bones),
                                              [a.name for a in acts]))

    # 2) 网格
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=MESH)
    meshes = [o for o in bpy.data.objects if o.type == 'MESH' and o not in before]
    # 删掉骨架 gltf 自带的 3 顶点桩
    for o in list(bpy.data.objects):
        if o.type == 'MESH' and o not in meshes:
            bpy.data.objects.remove(o, do_unlink=True)
    if not meshes:
        print('BIND_FAIL 没有导入到网格')
        return
    mesh = meshes[0]
    bpy.ops.object.select_all(action='DESELECT')
    mesh.select_set(True)
    bpy.context.view_layer.objects.active = mesh
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    print('BIND_INFO 网格=%s 顶点=%d（变换已烘焙）' % (mesh.name, len(mesh.data.vertices)))

    # 3) 对齐：Blender 里向上是 Z。只用 SKEL_* 骨算范围（围巾/背带那些辅助骨
    #    的 rest 位移能到 2.7 m，会把包围盒撑爆）
    def skel_z_range():
        zs = []
        for b in arm.data.bones:
            if not b.name.startswith('SKEL_'):
                continue
            zs.append((arm.matrix_world @ b.head_local).z)
            zs.append((arm.matrix_world @ b.tail_local).z)
        return min(zs), max(zs)

    z0, z1 = skel_z_range()
    mmn, mmx = bbox([mesh])
    dz = z0 - mmn.z          # 网格往下移，去贴骨架的脚底
    print('BIND_INFO 骨架(SKEL_) z[%.3f,%.3f]  网格 z[%.3f,%.3f]  → 上移 %+.3f'
          % (z0, z1, mmn.z, mmx.z, dz))
    mesh.location.z += dz
    bpy.context.view_layer.update()
    bpy.ops.object.select_all(action='DESELECT')
    mesh.select_set(True)
    bpy.context.view_layer.objects.active = mesh
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    print('BIND_INFO 网格已下移 %+.3f 并烘焙' % dz)

    # 4) 蒙皮。骨热在这套"多壳、非流形"的游戏网格上必然失败（实测 total weight=0），
    #    所以用**自算权重**：最近骨 → 候选=它自己+父+子 → 反距离²混合；
    #    并把三根趾骨(Toe0/Toe10/Toe20)的权重并回 *_Foot，避免靴子被撕成三块。
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode='EDIT')
    kill = [x for x in arm.data.edit_bones if not x.name.startswith('SKEL_')]
    for x in kill:
        arm.data.edit_bones.remove(x)
    bpy.ops.object.mode_set(mode='OBJECT')
    print('BIND_INFO 删除辅助骨 %d 根，剩 %d 根 SKEL_' % (len(kill), len(arm.data.bones)))

    arm.data.pose_position = 'REST'
    bpy.context.view_layer.update()

    bmap = {bb.name: bb for bb in arm.data.bones}

    # ★ 关键：glTF 里没有"骨长"，Blender 导入后合成的 tail 是错的（实测 Calf 的
    #   head/tail 的 z 完全相同 = 水平骨）。用 tail 算"最近骨段"会把小腿顶点判给大腿。
    #   正确做法：骨段 = 该骨的 head → 它的（第一个）子骨的 head；叶子骨沿父方向延伸。
    # ★★ 重要：RDR2 的 bind 里，每根骨记录的 "pos" 是**骨头的末端(tail)**，
    #    不是起点。所以一根骨的实际范围 = 父骨的位置 → 本骨的位置。
    #    实测：Pelvis -0.038(髋) → Thigh -0.481(膝) → Calf -0.902(踝) → Foot -0.963。
    # ★ 2026-10-17 修正：关节已经放到"骨头的 head"上了（见 export_gltf_source.py），
    #   所以一根骨的范围 = **本骨 head → 子骨 head**。
    #   旧写法是 (父骨 head → 本骨 head) —— 那是修复前"关节放在 tail"时的对应关系，
    #   在修正后会整体错一格（大腿的权重被算给骨盆、小腿的被算给大腿）。
    segs = []
    for nm, bb in bmap.items():
        start = arm.matrix_world @ bb.head_local
        kids = [c for c in bb.children if c.name in bmap]
        if kids:
            end = arm.matrix_world @ kids[0].head_local
        else:
            end = start - Vector((0, 0, 0.08))
        if (end - start).length < 3e-3:
            end = start - Vector((0, 0, 0.08))
        segs.append((nm, start, end))
    print('BIND_INFO 骨段: %d 根（用 骨->子骨，不是 Blender 合成的 tail）' % len(segs))
    segd = {nm: (h, t) for nm, h, t in segs}
    cand = {}
    for nm, bb in bmap.items():
        c = {nm}
        if bb.parent and bb.parent.name in bmap:
            c.add(bb.parent.name)
        for ch in bb.children:
            if ch.name in bmap:
                c.add(ch.name)
        cand[nm] = c

    toe2foot = {}
    for nm in bmap:
        if '_Toe' in nm:
            k = nm.split('_Toe')[0] + '_Foot'
            if k in bmap:
                toe2foot[nm] = k
    print('BIND_INFO 趾骨并回脚掌: %d 根' % len(toe2foot))

    def dist_seg(p, x, y):
        ab = y - x
        L2 = ab.length_squared
        if L2 < 1e-12:
            return (p - x).length
        u = max(0.0, min(1.0, (p - x).dot(ab) / L2))
        return (p - (x + ab * u)).length

    for nm in bmap:
        if nm not in mesh.vertex_groups:
            mesh.vertex_groups.new(name=nm)

    mw = mesh.matrix_world
    verts = mesh.data.vertices
    for vi, v in enumerate(verts):
        p = mw @ v.co
        dmin, nmin = 1e9, None
        for nm, x, y in segs:
            d = dist_seg(p, x, y)
            if d < dmin:
                dmin, nmin = d, nm
        ws = []
        for nm in cand[nmin]:
            x, y = segd[nm]
            d = dist_seg(p, x, y)
            if d > dmin * 4 + 0.05:
                continue
            ws.append((1.0 / (d + 1e-3) ** 2, nm))
        if not ws:
            ws = [(1.0, nmin)]
        ws.sort(reverse=True)
        merged = {}
        for w, nm in ws[:3]:
            nm2 = toe2foot.get(nm, nm)
            merged[nm2] = merged.get(nm2, 0.0) + w
        tot = sum(merged.values())
        for nm, w in merged.items():
            mesh.vertex_groups[nm].add([vi], w / tot, 'REPLACE')

    # ★ 权重平滑：最近骨分配会让一小块网格被几根骨各拽一份（靴子会自己叠成一团），
    #   沿网格边做几轮拉普拉斯平滑，让同一片区域的权重一致。
    bpy.ops.object.select_all(action='DESELECT')
    mesh.select_set(True)
    bpy.context.view_layer.objects.active = mesh
    try:
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.object.vertex_group_smooth(group_select_mode='ALL', factor=0.5, repeat=12)
        bpy.ops.object.mode_set(mode='OBJECT')
        print('BIND_OK 权重平滑完成（12 轮）')
    except Exception as e:
        try:
            bpy.ops.object.mode_set(mode='OBJECT')
        except Exception:
            pass
        print('BIND_WARN 权重平滑失败: %s' % e)

    # ★ 原来这里有一段"脚踝以下 100% 硬绑到 *_Foot"的 hack —— 已删除。
    #   骨段修对（父骨位置→本骨位置）之后，靴筒自然落到 Calf、脚掌落到 Foot，
    #   平滑过渡由 vertex_group_smooth 负责；再硬绑反而会在脚踝处折断、马刺被整体拽飞。

    mod = mesh.modifiers.new('Armature', 'ARMATURE')
    mod.object = arm
    mesh.parent = arm
    mesh.matrix_parent_inverse = arm.matrix_world.inverted()   # 骨架此时为单位变换
    mesh.matrix_world = mesh.matrix_world
    arm.data.pose_position = 'POSE'
    bpy.context.view_layer.update()
    print('BIND_OK 自算权重完成（%d 顶点 / %d 骨）' % (len(verts), len(bmap)))

    # 5) 动画：**不要重新赋 action**（Blender 4.4+/5.x 有 action slot，
    #    重新赋值会把 importer 已经绑好的 slot 清掉 → 动画不生效）
    ad = arm.animation_data
    if ad and ad.action:
        act = ad.action
        # 5.x：槽位没选上时动画同样不生效，补一次
        if hasattr(ad, 'action_slot') and getattr(act, 'slots', None):
            if ad.action_slot is None:
                ad.action_slot = act.slots[0]
        fs = [int(round(v)) for v in act.frame_range]
        bpy.context.scene.frame_start, bpy.context.scene.frame_end = fs
        print('BIND_INFO 动画=%s 帧范围=%s slot=%s'
              % (act.name, fs, getattr(ad, 'action_slot', None)))
    else:
        fs = [0, 1]
        print('BIND_WARN 没有导入到动画')

    # 5b) ★ 落地：.ycd 的**位移轨**没导（我们只导旋转），所以姿势里脚的绝对高度会漂。
    #     按帧求"双脚最低点"，把根骨按帧下沉/抬起到地面 —— 相当于补一个占位的 root motion。
    try:
        ground_z = z0 - 0.002
        root = arm.pose.bones.get('SKEL_ROOT')
        f0_, f1_ = (fs if acts else (0, 0))
        base_loc = root.location.copy() if root else None
        offsets = {}
        for f in range(f0_, f1_ + 1):
            bpy.context.scene.frame_set(f)
            bpy.context.view_layer.update()
            minz = 1e9
            for bn in ('SKEL_L_Foot', 'SKEL_R_Foot', 'SKEL_L_Toe0', 'SKEL_R_Toe0'):
                pb = arm.pose.bones.get(bn)
                if pb:
                    minz = min(minz, (arm.matrix_world @ pb.head).z,
                               (arm.matrix_world @ pb.tail).z)
            if minz > 1e8:
                continue
            offsets[f] = ground_z - minz
        if offsets and root is not None:
            for f, dz in offsets.items():
                bpy.context.scene.frame_set(f)
                # 根骨局部坐标下，世界 +Z 对应哪个轴：用根骨矩阵反解
                Rw = (arm.matrix_world @ root.matrix).to_3x3()
                dloc = Rw.inverted() @ Vector((0.0, 0.0, dz))
                root.location = base_loc + dloc
                root.keyframe_insert('location', frame=f)
            print('BIND_INFO 逐帧落地：%d 帧，幅度 %+.3f ~ %+.3f m'
                  % (len(offsets), min(offsets.values()), max(offsets.values())))
    except Exception as e:
        print('BIND_WARN 落地修正失败: %s' % e)

    # 6) 灯光/相机 + 渲染几帧验收
    scene = bpy.context.scene
    scene.render.engine = 'CYCLES'
    scene.cycles.samples = 16
    scene.cycles.use_denoising = True
    scene.cycles.device = 'CPU'
    scene.render.resolution_x, scene.render.resolution_y = 560, 820
    world = bpy.data.worlds.new('W')
    scene.world = world
    world.use_nodes = True
    world.node_tree.nodes['Background'].inputs[0].default_value = (0.10, 0.11, 0.13, 1)
    bpy.ops.mesh.primitive_plane_add(size=12, location=(0, 0, z0 - 0.002))
    ground = bpy.context.active_object
    gm = bpy.data.materials.new('G')
    gm.use_nodes = True
    gm.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.22, 0.23, 0.26, 1)
    ground.data.materials.append(gm)
    c = ((mmn + mmx) / 2).copy()
    c.z = (z0 + z1) / 2
    h = max(mmx.x - mmn.x, mmx.y - mmn.y, mmx.z - mmn.z)
    cam_d = bpy.data.cameras.new('C')
    cam_d.lens = 55
    cam = bpy.data.objects.new('C', cam_d)
    bpy.context.collection.objects.link(cam)
    scene.camera = cam
    cam.location = (c.x + h * 0.75, -h * 2.6, c.z + h * 0.9)
    d = cam.location - Vector((c.x, 0, c.z))
    cam.rotation_euler = d.to_track_quat('Z', 'Y').to_euler()
    for loc, en in (((c.x + h, c.x + h, h * 2.2), 3.0),):
        ld = bpy.data.lights.new('S', 'SUN')
        ld.energy = en
        lo = bpy.data.objects.new('S', ld)
        bpy.context.collection.objects.link(lo)
        lo.rotation_euler = (math.radians(55), 0, math.radians(35))
    os.makedirs(PNGD, exist_ok=True)
    frames = []
    if acts:
        f0, f1 = fs
        span = (f1 - f0) // 2
        frames = [f0, f0 + span // 4, f0 + span // 2, f0 + 3 * span // 4]
    for i, f in enumerate(frames or [1]):
        scene.frame_set(f)
        scene.render.filepath = os.path.join(PNGD, '%s_f%03d.png' % (PNGPREFIX, i))
        bpy.ops.render.render(write_still=True)
        print('BIND_OUT %s (frame %d)' % (scene.render.filepath, f))

    # 6b) 验证：同一批顶点在不同帧的世界坐标是否变化
    if acts:
        dg = bpy.context.evaluated_depsgraph_get()
        samples = {}
        for f in (fs[0], fs[0] + (fs[1] - fs[0]) // 2):
            bpy.context.scene.frame_set(f)
            bpy.context.view_layer.update()
            ev = mesh.evaluated_get(bpy.context.evaluated_depsgraph_get())
            mw = ev.matrix_world
            samples[f] = [(mw @ ev.data.vertices[i].co).copy() for i in range(0, len(ev.data.vertices), 997)]
        a, b = list(samples.values())
        dmax = max((x - y).length for x, y in zip(a, b))
        dmean = sum((x - y).length for x, y in zip(a, b)) / len(a)
        print('BIND_CHECK 顶点位移: 最大 %.4f m  平均 %.4f m  %s'
              % (dmax, dmean, '✅ 网格在动' if dmean > 0.005 else '❌ 网格没动'))

    # 7) 导出 glb（含蒙皮 + 动画）
    #    ★ 只导骨架 + 网格：之前 use_selection=True + 全选，把渲染用的地面平面也导进去了，
    #      导致外部查看器里包围盒被 14 m 的地面撑爆、地面还把腿挡住。
    for o in list(bpy.data.objects):
        if o.type == 'MESH' and o is not mesh:
            bpy.data.objects.remove(o, do_unlink=True)
    bpy.ops.object.select_all(action='DESELECT')
    arm.select_set(True)
    mesh.select_set(True)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.export_scene.gltf(filepath=OUTG, export_format='GLB',
                              export_animations=True, export_skins=True,
                              export_apply=False, use_selection=True)
    print('BIND_EXPORT %s (%.1f MB)' % (OUTG, os.path.getsize(OUTG) / 1e6))


main()
