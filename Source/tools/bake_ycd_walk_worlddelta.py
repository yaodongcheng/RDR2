"""把 `.ycd` 解出来的动作，用**运行期 dump 的真实参考骨架**做世界增量重定向，烘成 glb。

为什么：`.ycd` 的四元数是"相对动画参考骨架 rest 的增量"，而我们之前拿 `meta_base_player.yft`
的 bind 当参考 —— 实测两者逐骨差 60~180°（见 work/npc/live/），所以怎么修都别扭。
现在用运行期 dump 到的 ped 骨架（124 骨、静态 = rest 模板）当源骨架：

    delta_world = W_src_pose ⊗ W_src_rest⁻¹
    W_dst_pose  = delta_world ⊗ W_dst_rest

用法: blender -b --python tools/bake_ycd_walk_worlddelta.py
输出: export/npc/player/player_zero_walk_wd.glb
"""
import bpy
import os
import sys
import glob
import json
import math
from mathutils import Matrix, Vector, Quaternion

PROJ = r'D:/BrainMaker/大镖客2解包分析'
GLB = os.path.join(PROJ, 'export/npc/player/player_zero_walk.glb')
ANIM = os.path.join(PROJ, 'work/npc/anim/walk_int.json')
OUT_GLB = os.path.join(PROJ, 'export/npc/player/player_zero_walk_wd.glb')
OUT_PNG = os.path.join(PROJ, 'work/npc/verify')

# ---- 源骨架：运行期 dump（rest） + 运行期层级
live_tsv = sorted(glob.glob(os.path.join(PROJ, 'work/npc/live/idle_*.tsv')))[-1]
live_q = {}
for l in open(live_tsv, encoding='utf-8').read().splitlines()[1:]:
    c = l.split('\t')
    live_q[c[1]] = tuple(float(x) for x in c[2:6])
par = {}
for l in open(os.path.join(PROJ, 'export/skeleton_runtime/skel_full.tsv'), encoding='utf-8').read().splitlines()[1:]:
    c = l.strip('\r').split('\t')
    if len(c) >= 4:
        par[c[1]] = c[3]
ORD, seen = [], set()
def _go(n):
    if n in seen or n not in live_q:
        return
    pp = par.get(n)
    if pp and pp in live_q:
        _go(pp)
    seen.add(n); ORD.append(n)
for n in live_q:
    _go(n)
print('[WD] 源骨架 %d 骨（rest 来自 %s）' % (len(ORD), os.path.basename(live_tsv)))


def qq(v):
    """tuple → mathutils.Quaternion"""
    return Quaternion((v[3], v[0], v[1], v[2]))


def qmul(a, b):
    return a @ b


def qinv(q):
    return q.inverted()


def qnorm(q):
    q.normalize()
    return q


def q2m(q):
    q = qq(q) if not isinstance(q, Quaternion) else q
    x, y, z, w = q.normalized()
    return Matrix(((1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w)),
                   (2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w)),
                   (2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y))))


def m2q(M):
    return M.to_quaternion()


def src_world(qs):
    """源骨架世界旋转（只算旋转，位置用不上）"""
    W = {}
    I = Matrix.Identity(3)
    for n in ORD:
        P = W.get(par.get(n), I)
        W[n] = P @ q2m(qs.get(n, live_q[n]))
    return W


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.scene.render.fps = 30
    bpy.ops.import_scene.gltf(filepath=GLB)
    objs = list(bpy.data.objects)
    arm = [o for o in objs if o.type == 'ARMATURE'][0]
    mesh = max([o for o in objs if o.type == 'MESH'], key=lambda o: len(o.data.vertices))
    for o in objs:
        if o.type == 'MESH' and o is not mesh:
            bpy.data.objects.remove(o, do_unlink=True)
    if arm.animation_data:
        arm.animation_data_clear()

    # 目标 rest 世界旋转
    Wt_rest = {}
    for b in arm.data.bones:
        Wt_rest[b.name] = (arm.matrix_world @ b.matrix_local).to_quaternion()
    # 目标骨架的骨骼名（去掉非 SKEL_ 的也没关系，按名字对齐）

    # 动画：tag → 骨名（用 yft 的 tag 表）
    skel = json.load(open(os.path.join(PROJ, 'export/skeleton_runtime/yft_skel.json'), encoding='utf-8'))
    tag2name = {}
    for b in skel['bones']:
        tag2name.setdefault(b['tag'], b['name'])
    A = json.load(open(ANIM, encoding='utf-8'))
    anim = A['animations'][0]
    tr = {}
    for b in anim['bones']:
        nm = tag2name.get(b['boneId'])
        if nm and nm in live_q:
            tr[nm] = [qq(x).normalized() for x in b['quats']]
    frames = anim['frames']
    print('[WD] 动画轨 %d 条 / %d 帧' % (len(tr), frames))

    Wsrc_rest = src_world({})
    Wsrc_rest = {n: m2q(M) for n, M in Wsrc_rest.items()}

    # 逐帧
    if not arm.animation_data:
        arm.animation_data_create()
    act = bpy.data.actions.new('ycd_walk_wd')
    arm.animation_data.action = act
    if hasattr(arm.animation_data, 'action_slot') and getattr(act, 'slots', None):
        try:
            arm.animation_data.action_slot = act.slots[0]
        except Exception:
            pass

    # 目标骨的父链顺序（父先子后）
    order = []
    seen2 = set()
    bones_by_name = {b.name: b for b in arm.data.bones}
    def go(nm):
        if nm in seen2 or nm not in bones_by_name:
            return
        pp = bones_by_name[nm].parent
        if pp:
            go(pp.name)
        seen2.add(nm); order.append(nm)
    for nm in bones_by_name:
        go(nm)

    for f in range(frames):
        qs = {n: v[min(f, len(v)-1)] for n, v in tr.items()}
        pose_loc = {n: qmul(qq(live_q[n]), qq(qs[n])) if n in qs else qq(live_q[n]) for n in live_q}
        Wp = {n: m2q(M) for n, M in src_world(pose_loc).items()}
        delta = {n: qmul(Wp[n], qinv(Wsrc_rest[n])) for n in Wp}
        Wt = {}
        for nm in order:
            if nm in delta:
                Wt[nm] = delta[nm] @ Wt_rest[nm]
            else:
                Wt[nm] = Wt_rest[nm]
        for nm in order:
            pb = arm.pose.bones.get(nm)
            if not pb:
                continue
            cur = (arm.matrix_world @ pb.matrix).to_translation()
            M = Matrix.Translation(cur) @ Wt[nm].to_matrix().to_4x4()
            pb.matrix = arm.matrix_world.inverted() @ M
            bpy.context.view_layer.update()
        for nm in order:
            pb = arm.pose.bones.get(nm)
            if pb:
                pb.keyframe_insert('rotation_quaternion', frame=f)
        if f % 100 == 0:
            print('  帧', f)

    # 落地
    bpy.context.scene.frame_start, bpy.context.scene.frame_end = 0, frames - 1
    # 导出
    for a in list(bpy.data.actions):
        if a is not act:
            try:
                bpy.data.actions.remove(a)
            except Exception:
                pass
    bpy.ops.object.select_all(action='DESELECT')
    arm.select_set(True); mesh.select_set(True)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.export_scene.gltf(filepath=OUT_GLB, export_format='GLB',
                              export_animations=True, export_skins=True,
                              export_apply=False, use_selection=True)
    print('[WD] 导出 %s (%.1f MB)' % (OUT_GLB, os.path.getsize(OUT_GLB) / 1e6))

    # 侧视渲染
    mn = Vector((1e9,)*3)
    for c in mesh.bound_box:
        w = mesh.matrix_world @ Vector(c)
        for i in range(3):
            mn[i] = min(mn[i], w[i])
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'; sc.cycles.samples = 18; sc.cycles.device = 'CPU'
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
    cam.location = (3.2, 0, 0.05); cam.rotation_euler = (math.radians(90), 0, math.radians(90))
    ld = bpy.data.lights.new('S', 'SUN'); ld.energy = 3.0
    lo = bpy.data.objects.new('S', ld); bpy.context.collection.objects.link(lo)
    lo.rotation_euler = (math.radians(55), 0, math.radians(120))
    for i, f in enumerate([0, frames//3, 2*frames//3, frames-2]):
        sc.frame_set(f)
        sc.render.filepath = os.path.join(OUT_PNG, 'wd_%d.png' % i)
        bpy.ops.render.render(write_still=True)
        print('OUT', sc.render.filepath)


main()
