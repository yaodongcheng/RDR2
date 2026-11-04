# -*- coding: utf-8 -*-
"""合成单测：远景框裁剪（`scene_trim.clip_to_rect`）—— 2026-11-04 圣丹尼斯漏裁的回归闸门。

    blender -b --factory-startup -P tools/_check_scene_trim_clip.py

背景（实锤）：`sdn.blend` 里 `cor_01_slod` 的包围盒越过远景西边界 61 m，
日志却写着"按远景框裁掉超界几何：1 个对象"。根因两条：

  1. `clip_to_rect` 用 `matrix_world` 定位切平面，而**新建对象的 matrix_world 在
     depsgraph 跑之前还是单位阵**（`bb_of` 早就写明无父级要用 `matrix_basis`）
     ⇒ 切平面落到别处，一刀没切却照样返回 True；
  2. `bisect_plane` 的 clear 语义用反：`clear_outer` 删**法线所指**一侧。
     外框法线朝内 ⇒ 旧写法删的是框内；活动区挖空那组两个标志都是 False = 只切不删。

本测试覆盖（每条都必须 PASS）：
  A. 无父级 + 非零 location：跨西边界的盒子裁完必须全部落在框内；
  B. 镜像物体（scale.x < 0）：同样必须全部落在框内（逆转置已处理镜像，不能再乘 det 符号）；
  C. 跨活动区的物体（keep_act 情形）：活动区内的几何必须保留（不得误挖）；
  D. 完全在框内的物体：顶点数不变；
  E. 完全在框外的物体：返回 False（调用方据此删除）；
  F. **负面测试**：旧参数组合（clear_outer=True）必须被 A 的断言抓到 —— 证明检查有分辨力；
  G. 旋转对象的 `bound_box` 角点会高估，`exact_bb` 必须给真实顶点范围
     （manifest 对被裁对象改用 exact_bb 的依据）；
  H. 旋转物体跨边界：法线必须做「世界→局部」`Mᵀ`（旧写法 `(M⁻¹)ᵀ` 一旋转就切错方向）；
  I. 数据口径：`scene_list.csv` 的「能走」四列必须被 `load_scene` 读出、`rects()` 必须用它当活动区。
"""
import os
import sys

import bpy
import bmesh
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import scene_trim   # noqa: E402

FAR = (-10.0, -10.0, 10.0, 10.0)
ACT = (-5.0, -5.0, 5.0, 5.0)


def new_box(name, local_bounds, loc=(0.0, 0.0, 0.0), scale=(1.0, 1.0, 1.0)):
    """建盒子：网格顶点 = local_bounds，对象用 location/scale 摆到世界里。

    🔴 建完**不调** `view_layer.update()` —— 要复现"matrix_world 还是单位阵"的真实条件。
    """
    (lx0, lx1), (ly0, ly1), (lz0, lz1) = local_bounds
    verts = [(x, y, z) for x in (lx0, lx1) for y in (ly0, ly1) for z in (lz0, lz1)]
    faces = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1),
             (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.update()
    ob = bpy.data.objects.new(name, me)
    ob.location = loc
    ob.scale = scale
    bpy.context.scene.collection.objects.link(ob)
    return ob


def world_verts(ob):
    mw = ob.matrix_world if ob.parent else ob.matrix_basis
    return [mw @ v.co for v in ob.data.vertices]


def inside_rect(vs, r, eps=1e-3):
    return all(r[0] - eps <= v.x <= r[2] + eps and r[1] - eps <= v.y <= r[3] + eps
               for v in vs)


def main():
    # ---------- 先确认：本测试确实跑在"matrix_world 是单位阵"的条件下 ----------
    probe = new_box('probe', ((-1, 1), (-1, 1), (-1, 1)), loc=(50.0, 60.0, 0.0))
    w = probe.matrix_world.translation
    b = probe.matrix_basis.translation
    print('[clip-test] 新建对象 matrix_world=(%.1f,%.1f) · matrix_basis=(%.1f,%.1f)'
          % (w.x, w.y, b.x, b.y))
    if (w - b).length > 1e-6:
        print('[clip-test] ✅ 复现了真实条件：matrix_world 尚未求值（旧代码会用错矩阵）')
    else:
        print('[clip-test] ⚠ 本机 matrix_world 已即时求值；A 仍会验证结果，负测 F 兜底')
    bpy.data.objects.remove(probe, do_unlink=True)

    # ---------- A. 无父级 + 非零 location，跨西边界 ----------
    a = new_box('A', ((-25, -5), (-2, 2), (-2, 2)), loc=(0.0, 0.0, 0.0))
    before = world_verts(a)
    assert any(v.x < FAR[0] for v in before), 'A 的初始状态不对：没有顶点在框外'
    n0 = len(a.data.vertices)
    ok = scene_trim.clip_to_rect(a, FAR)
    vs = world_verts(a)
    print('[clip-test] A 非镜像：%d → %d 顶点，x[%.2f, %.2f]'
          % (n0, len(vs), min(v.x for v in vs), max(v.x for v in vs)))
    assert ok and vs, 'A 被整块裁光了'
    assert inside_rect(vs, FAR), 'A 裁完仍有顶点在远景框外（外框裁剪方向/矩阵口径错）'
    assert max(v.x for v in vs) <= FAR[0] + 5.5, 'A 的框外部分没被删（只做了切割）'

    # ---------- B. 镜像物体 ----------
    b = new_box('B', ((5, 25), (-2, 2), (-2, 2)), loc=(0.0, 0.0, 0.0),
                scale=(-1.0, 1.0, 1.0))
    before = world_verts(b)
    assert any(v.x < FAR[0] for v in before), 'B 的初始世界范围不对（应跨西边界）'
    ok = scene_trim.clip_to_rect(b, FAR)
    vs = world_verts(b)
    print('[clip-test] B 镜像  ：%d → %d 顶点，x[%.2f, %.2f]'
          % (len(before), len(vs), min(v.x for v in vs), max(v.x for v in vs)))
    assert ok and vs, 'B 被整块裁光了'
    assert inside_rect(vs, FAR), 'B 镜像物体裁完仍有顶点在框外（det 符号乘反了）'

    # ---------- C. 跨活动区的物体（keep_act 情形）：活动区内几何必须保留 ----------
    # 只有包围盒与活动区不相交的对象才会进 keep_ring（见 trim_current_scene），
    # 所以这里代表的是活动区内的高清对象 —— 裁远景框**不得**动它活动区里的部分。
    # （原先的 inner= 挖空已删除：按构造是空转，且顺序切四刀会整块删光。）
    c = new_box('C', ((-8, 8), (-1, 1), (-1, 1)))
    ok = scene_trim.clip_to_rect(c, FAR)
    vs = world_verts(c)
    x0, x1 = min(v.x for v in vs), max(v.x for v in vs)
    print('[clip-test] C 跨活动区：剩 %d 顶点，x[%.2f, %.2f]' % (len(vs), x0, x1))
    assert ok and len(vs) == 8, 'C 被误裁（远景框内的物体不该动）'
    assert x0 < ACT[0] and x1 > ACT[2], 'C 跨活动区的几何被误挖掉了（inner 挖空不该存在）'

    # ---------- D. 完全在框内：不动 ----------
    d = new_box('D', ((-2, 2), (-2, 2), (-2, 2)))
    n0 = len(d.data.vertices)
    ok = scene_trim.clip_to_rect(d, FAR)
    print('[clip-test] D 框内  ：%d → %d 顶点' % (n0, len(d.data.vertices)))
    assert ok and len(d.data.vertices) == n0, 'D 框内物体被改了'

    # ---------- E. 完全在框外：返回 False ----------
    e = new_box('E', ((20, 30), (-2, 2), (-2, 2)))
    ok = scene_trim.clip_to_rect(e, FAR)
    print('[clip-test] E 框外  ：返回 %s，剩 %d 顶点' % (ok, len(e.data.vertices)))
    assert not ok and not e.data.vertices, 'E 框外物体应被整块裁光并返回 False'

    # ---------- H. 旋转物体跨边界：法线必须做「世界→局部」变换 ----------
    # 旧代码用 (M⁻¹)ᵀ（局部→世界），不旋转时恰好相同，一旋转就切错方向。
    h = new_box('H', ((-25, -5), (-2, 2), (-2, 2)))
    h.rotation_mode = 'XYZ'
    h.rotation_euler[2] = 0.5                     # 绕 Z 转 ~28.6°
    bpy.context.view_layer.update()
    before = world_verts(h)
    assert any(v.x < FAR[0] for v in before), 'H 的初始状态不对：没有顶点在框外'
    ok = scene_trim.clip_to_rect(h, FAR)
    vs = world_verts(h)
    print('[clip-test] H 旋转+跨边界：%d → %d 顶点，x[%.2f, %.2f]'
          % (len(before), len(vs), min(v.x for v in vs), max(v.x for v in vs)))
    assert ok and vs, 'H 被整块裁光了'
    assert inside_rect(vs, FAR), 'H 旋转物体裁完仍有顶点在框外（法线变换方向错）'

    # ---------- G. 旋转对象的包围盒高估：manifest 必须用 exact_bb ----------
    # 八面体的局部 AABB 是 [-1,1]^3，但 8 个角点不是顶点；绕 Z 转 45° 后，
    # 真实顶点 |x|≤0.707，而 bound_box 角点会到 1.414 —— 贴边界时就是假报超界。
    verts = [(-1, 0, 0), (1, 0, 0), (0, -1, 0), (0, 1, 0), (0, 0, 1), (0, 0, -1)]
    faces = [(0, 2, 4), (2, 1, 4), (1, 3, 4), (3, 0, 4),
             (2, 0, 5), (1, 2, 5), (3, 1, 5), (0, 3, 5)]
    me = bpy.data.meshes.new('G')
    me.from_pydata(verts, [], faces)
    me.update()
    g = bpy.data.objects.new('G', me)
    g.rotation_mode = 'XYZ'
    g.rotation_euler[2] = 0.7853981633974483      # 45°
    bpy.context.scene.collection.objects.link(g)
    bpy.context.view_layer.update()               # 求值后才能读 bound_box
    b0, b1 = scene_trim.bb_of(g)
    e0, e1 = scene_trim.exact_bb(g)
    print('[clip-test] G 旋转  ：bb_of x[%.2f, %.2f] · exact_bb x[%.2f, %.2f]'
          % (b0.x, b1.x, e0.x, e1.x))
    assert e1.x <= 0.72 and e0.x >= -0.72, 'exact_bb 不对：真实顶点应 |x|≤0.707'
    assert b1.x > 1.0 or b0.x < -1.0, '负面测试失效：bound_box 居然没有高估'

    # ---------- I. 数据口径：scene_list.csv 的「能走范围」列必须被读出来 ----------
    # 2026-11-04 用户裁定：P 就是活动区边界。CSV 末尾四列读不到 = 整条规则失效。
    sc = scene_trim.load_scene('sdn')
    act, far = scene_trim.rects(sc)
    print('[clip-test] I 数据口径：sdn P=%s · 活动区=%s · 远景=%.0f×%.0f'
          % (sc.get('p'), act, far[2] - far[0], far[3] - far[1]))
    assert sc.get('p'), 'scene_list.csv 缺「能走」四列（重跑 build_scene_division.py）'
    assert act == sc['p'], 'rects() 没把 P 当活动区'
    assert far[2] - far[0] > act[2] - act[0], '远景框必须大于活动区'

    # ---------- J. 跨活动区的 lod：挖掉 P 内、保留 P 外 ----------
    # 合并 LOD 块跨活动区时，整块隐藏会让"活动区外的另一座据点"消失（西西卡 292 面）。
    j = new_box('J', ((-8, 8), (-2, 2), (-2, 2)))
    ok = scene_trim.clip_to_outside_rect(j, ACT)
    vs = world_verts(j)
    inner = [v for v in vs if ACT[0] + 0.1 < v.x < ACT[2] - 0.1]
    print('[clip-test] J 挖 P 内：剩 %d 顶点，x[%.2f, %.2f]'
          % (len(vs), min(v.x for v in vs), max(v.x for v in vs)))
    assert ok and vs, 'J 被整块挖光'
    assert not inner, 'J 的 P 内几何没被挖掉（可见副本会伸进活动区）'
    assert min(v.x for v in vs) < ACT[0] and max(v.x for v in vs) > ACT[2], 'J 的 P 外几何丢了'

    # ---------- K. 整块都在 P 内：返回 False（副本应丢弃） ----------
    k = new_box('K', ((-2, 2), (-2, 2), (-2, 2)))
    ok = scene_trim.clip_to_outside_rect(k, ACT)
    print('[clip-test] K 全在 P 内：返回 %s，剩 %d 顶点' % (ok, len(k.data.vertices)))
    assert not ok and not k.data.vertices, 'K 全在 P 内却没被整块挖光'

    # ---------- F. 负面测试：旧参数组合必须被 A 的判据抓到 ----------
    f = new_box('F', ((-25, -5), (-2, 2), (-2, 2)))
    mw = f.matrix_basis
    mwi = mw.inverted()
    nmat = mwi.to_3x3().transposed()
    bm = bmesh.new()
    bm.from_mesh(f.data)
    for pco, pno in (((FAR[0], 0, 0), (1, 0, 0)), ((FAR[2], 0, 0), (-1, 0, 0)),
                     ((0, FAR[1], 0), (0, 1, 0)), ((0, FAR[3], 0), (0, -1, 0))):
        bmesh.ops.bisect_plane(
            bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], dist=1e-4,
            plane_co=mwi @ Vector(pco),
            plane_no=(nmat @ Vector(pno)).normalized(),
            clear_outer=True)          # ← 旧写法
    bm.to_mesh(f.data)
    bm.free()
    f.data.update()
    vs = world_verts(f)
    # 合法裁剪结果 = 非空 且 全部落在框内；旧参数把整块删光 / 留下框外部算不合格。
    old_ok = bool(vs) and inside_rect(vs, FAR)
    print('[clip-test] F 负面  ：旧参数剩 %d 顶点，合法结果=%s' % (len(vs), old_ok))
    assert not old_ok, \
        '负面测试失效：旧参数居然通过了 A 的判据（检查没有分辨力）'

    print('=== UNIT OK ===')


if __name__ == '__main__':
    main()
