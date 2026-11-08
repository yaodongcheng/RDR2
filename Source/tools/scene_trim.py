# -*- coding: utf-8 -*-
"""场景两层裁剪 —— 把「刚装好的场景」按玩家活动区 / 远景范围裁一遍。

两种用法：

1) 由 `blender_continent.py --scene <id>` 在装配 + 分类之后**同进程**调用（推荐，不用二次加载）。
2) 单独对已经装好的 blend 重跑一遍：

    blender -b <scene.blend> -P tools/scene_trim.py -- \
        --scene sdn --out <scene.blend> [--report ...] [--manifest ...] \
        [--keep-terrain] [--keep-water] [--no-recenter]

规则（2026-11-03 两层口径，与 scene_list.csv 一致）：

* 世界包围盒与**远景范围**不相交 → 删；
* 与**玩家活动区**相交 → 留（高清）；
* 只在远景那一圈 → **只留 `cls_key == 'lod'`**（远景碎片），其余删；
* 留下的远景碎片打 `ring=1` 并额外挂到集合 `活动区外远景`（导出时据此关碰撞 / 寻路 / 投影）；
* 默认把场景中心平移到原点。

产物：`manifest_<id>.jsonl`（平移前的世界包围盒，方便和 v23 / region 对账）+ 报告 JSON。
"""

import bpy
import collections
import csv
import json
import os
import time
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.dirname(HERE)
DEFAULT_CSV = os.path.join(SRC, "docs", "世界与地编", "scene_list.csv")
RING_COLLECTION = "C_lod_out_远景碎片·区外"
SPECIAL = ("Terrain", "Water")
# 跨远景框时**直接丢、不做裁剪**的隐藏类：它们是整类默认隐藏的冗余地形片
# （场景有自己按 H4 建的 Terrain 网格）。而且 `bisect_plane` 遇到大片共面三角形会
# 卡死 —— 实测 rat 的 outg_a_03_hd_02（5,473 顶点）卡了 40 分钟，把整批拖超时。
HIDDEN_TERRAIN = ("terrain_cell", "terrain_lod")


# ------------------------------------------------------------------ 场景数据
def load_scene(sid, csv_path=DEFAULT_CSV):
    with open(csv_path, encoding="utf-8-sig", newline="") as fp:
        for r in csv.DictReader(fp):
            if r.get("id") == sid or r.get("code") == sid:
                n = lambda k: float((r.get(k) or "0").strip() or 0)
                # 🔴 2026-11-04 用户裁定：**能走范围 P 就是活动区边界**（P 外一律按远景处理）。
                # 末尾四列是 P 的世界矩形；读不到才退回旧的正方形（兼容老 CSV）。
                p = None
                try:
                    v = [float((r.get(k) or "").strip())
                         for k in ("能走_x0", "能走_y0", "能走_x1", "能走_y1")]
                    if v[2] > v[0] and v[3] > v[1]:
                        p = tuple(v)
                except Exception:
                    p = None
                return _clamp_far_to_map({"id": sid, "kind": r.get("kind"), "name": r.get("name"),
                                          "x": n("x"), "y": n("y"),
                                          "aw": n("活动区宽_m"), "ah": n("活动区高_m"),
                                          "w": n("每边外扩_m"),
                                          "fw": n("远景宽_m"), "fh": n("远景高_m"), "p": p})
    raise SystemExit("[scene] scene_list.csv 里找不到 %s" % sid)


def _clamp_far_to_map(sc):
    """远景框按地图边界裁剪 —— **实现只有一份**：`tools/scene_bounds.clamp_scene_to_map`。"""
    p = os.path.join(r'D:/BrainMaker/大镖客2解包分析', 'deliverable', 'terrain',
                     'outside', sc.get('id') or '', 'meta.json')
    if sc.get('id') and os.path.exists(p):
        return sc            # 框外场景（瓜玛）有自己的地形源，禁止按地图边界裁
    from scene_bounds import clamp_scene_to_map
    return clamp_scene_to_map(sc)


def rects(sc):
    """返回 (活动区, 远景)。活动区 = 能走范围 P（读不到才退回以 x,y 为中心的正方形）。"""
    x, y = sc["x"], sc["y"]
    if sc.get("p"):
        act = sc["p"]
    else:
        act = (x - sc["aw"] / 2, y - sc["ah"] / 2, x + sc["aw"] / 2, y + sc["ah"] / 2)
    far = (x - sc["fw"] / 2, y - sc["fh"] / 2, x + sc["fw"] / 2, y + sc["fh"] / 2)
    return act, far


def settlement_zones(csv_path=DEFAULT_CSV):
    """所有**据点**的「能走范围 P」矩形（世界坐标）。

    用途：野地场景可以包含城，但城在野地里必须**整座用远景碎片（lod）表示** ——
    玩家走近到据点边界会弹「进入 XX」切到据点场景（2026-11-04 用户裁定）。
    P = 切场景的触发边界，所以拿它当"城"的范围（**不是活动区**：活动区含城外一圈草地，
    拿它当范围会把城外植被/道具一起抹掉）。

    数据优先 `scene_specs.json` 的 `P`（由 `scene_overrides.json` 生成）；读不到才退回
    `scene_list.csv` 的活动区矩形（宁可范围大一点，也别让城里留高清）。
    """
    import json
    root = os.environ.get('RDR2_ROOT') or r'D:/BrainMaker/大镖客2解包分析'
    spec = os.path.join(root, '_scratch', 'settlement_plan', 'scene_specs.json')
    out = []
    if os.path.exists(spec):
        try:
            S = json.load(open(spec, encoding='utf-8')).get('settlements') or []
            for s in S:
                r = (s.get('P') or [None])[0]
                if not r or len(r) < 3:
                    continue
                xs = [q[0] for q in r]
                ys = [q[1] for q in r]
                out.append((min(xs), min(ys), max(xs), max(ys)))
        except Exception as e:
            print('[trim] 读 scene_specs.json 失败（%s），退回活动区矩形' % e)
            out = []
    if out:
        return out
    with open(csv_path, encoding="utf-8-sig", newline="") as fp:
        for r in csv.DictReader(fp):
            if (r.get("kind") or "").strip() != "settlement":
                continue
            try:
                x, y = float(r["x"]), float(r["y"])
                aw, ah = float(r["活动区宽_m"]), float(r["活动区高_m"])
            except Exception:
                continue
            out.append((x - aw / 2, y - ah / 2, x + aw / 2, y + ah / 2))
    return out


def build_bbox(sc, pad=128.0):
    """给 blender_continent.build_entities 的**原点**过滤框：远景范围外扩 pad。"""
    _, far = rects(sc)
    return (far[0] - pad, far[1] - pad, far[2] + pad, far[3] + pad)


# ------------------------------------------------------------------ 几何
def bb_of(o):
    # 🔴 刚建好的对象 matrix_world 可能还是单位阵（depsgraph 没跑），隐藏集合又不会自动刷新。
    # 无父级对象的 matrix_basis 一定是最新的（location/rotation/scale 直接算），用它。
    mw = o.matrix_world if o.parent else o.matrix_basis
    mn = Vector((1e18,) * 3)
    mx = Vector((-1e18,) * 3)
    for c in o.bound_box:
        p = mw @ Vector(c)
        for i in range(3):
            mn[i] = min(mn[i], p[i])
            mx[i] = max(mx[i], p[i])
    return mn, mx


def exact_bb(o):
    """逐顶点世界包围盒（裁剪过的对象必须用这个口径）。

    为什么不能复用 `bb_of`：`bound_box` 是**局部轴对齐**的盒，乘上带旋转的矩阵后，
    8 个角点会跑出一个比真实几何更大的世界盒 —— 物体贴着远景边界时就会假报"超界"。
    实测（sdn, 2026-11-04）：`cor_es_pipes_slod` 顶点 x≥511.2 全在框内，`bound_box`
    角点却报到 498.2（越界 8 m）。
    """
    import numpy as np
    mw = o.matrix_world if o.parent else o.matrix_basis
    n = len(o.data.vertices)
    if not n:
        return Vector((0.0, 0.0, 0.0)), Vector((0.0, 0.0, 0.0))
    co = np.empty(n * 3, dtype=np.float32)
    o.data.vertices.foreach_get("co", co)
    co = co.reshape(n, 3)
    m = np.array(mw, dtype=np.float64)
    w = co @ m[:3, :3].T + m[:3, 3]
    return (Vector((w[:, 0].min(), w[:, 1].min(), w[:, 2].min())),
            Vector((w[:, 0].max(), w[:, 1].max(), w[:, 2].max())))


def hit(mn, mx, r):
    return not (mx.x < r[0] or mn.x > r[2] or mx.y < r[1] or mn.y > r[3])


def unhide_all(lc):
    """隐藏集合里的对象 matrix_world 不更新 → 读包围盒前必须全展开。"""
    lc.exclude = False
    lc.hide_viewport = False
    lc.collection.hide_viewport = False
    lc.collection.hide_render = False
    for ch in lc.children:
        unhide_all(ch)


def clip_to_rect(o, far):
    """把几何裁到远景矩形内（只保留框内的部分）。

    🔴 网格是跨实例共享的（meshcache），裁剪前必须**复制成单用户**，
       否则裁一个实例会把同模型的所有实例一起改掉（实测裁成空网格）。
    返回 False 表示整块都被裁光了，调用方应删除该对象。

    🔴 2026-11-04 两处实锤修正（圣丹尼斯 cor_01_slod）：
      · **矩阵口径必须与 `bb_of` 一致** —— 新建对象在 depsgraph 跑之前 `matrix_world`
        还是单位阵，无父级对象只有 `matrix_basis` 准。原来这里用 `matrix_world`，
        切平面落到别处 ⇒ 网格一刀没切、却照样 `clipped += 1`（假"已裁"，包围盒仍在框外）。
      · **`bisect_plane` 的 clear 语义**（合成实验实测）：`clear_outer` 删**法线所指**那一侧，
        `clear_inner` 删**法线反向**那一侧。四条边的法线都朝框内（= 要保留的一侧），
        所以一律 `clear_inner=True` 删框外；原来写 `clear_outer=True` 删的是框内（方向反了）。
      · 不再乘 `det` 符号：逆转置已经正确处理镜像（负缩放），再乘一次反而把侧翻回去。
      · **法线变换方向**：切平面要世界→局部 `Mᵀ·n_w`；原写法 `(M⁻¹)ᵀ` 是局部→世界，
        对不旋转的物体恰好相同，一旋转就切错方向（实测 `cor_derricks_slod_09` 绕 Z 15°）。

    ⚠️ 原先还有一个 `inner=` 参数（把活动区内部挖空），已删除（2026-11-04）：
       ① **按构造它是空转** —— 只有包围盒与活动区不相交的对象才会进 `keep_ring`（见
          `trim_current_scene` 的 `elif`），几何不可能落在活动区里；
       ② 就算真要挖洞，顺序切四刀也不行（那会删掉"任一半空间之外"的全部几何 = 整块删光），
          必须做布尔差集。空转 + 实现错误，直接移除。
    """
    import bmesh
    if o.data.users > 1:
        o.data = o.data.copy()
    mw = o.matrix_world if o.parent else o.matrix_basis
    mwi = mw.inverted()
    # 🔴 法线要的是**世界→局部**：n_l = Mᵀ·n_w（由 n_w·(M·p_l + t − c_w)=0 推得）。
    #    原来写的是 (M⁻¹)ᵀ —— 那是**局部→世界**的变换，方向正好相反。
    #    不旋转的物体两者相同（所以早期单测全过、bla/wild_10 也没暴露），
    #    一旋转就切到错误方向（实测 sdn 的 cor_derricks_slod_09，绕 Z 15°）。
    nmat = mw.to_3x3().transposed()

    def _cut(bm, pco, pno):
        co = mwi @ Vector(pco)
        no = (nmat @ Vector(pno)).normalized()
        geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
        bmesh.ops.bisect_plane(bm, geom=geom, dist=1e-4, plane_co=co, plane_no=no,
                               clear_outer=False, clear_inner=True)

    bm = bmesh.new()
    bm.from_mesh(o.data)
    # 裁到远景框内（法线朝框内 → clear_inner 删掉法线反向的一侧 = 框外）
    for pco, pno in (((far[0], 0, 0), (1, 0, 0)), ((far[2], 0, 0), (-1, 0, 0)),
                     ((0, far[1], 0), (0, 1, 0)), ((0, far[3], 0), (0, -1, 0))):
        _cut(bm, pco, pno)
    n_left = len(bm.verts)
    bm.to_mesh(o.data)
    bm.free()
    o.data.update()
    return n_left > 0


def clip_to_outside_rect(o, rect):
    """把矩形**内部**从网格里挖掉（保留矩形外）。用于跨活动区的远景碎片。

    🔴 为什么是"切四刀 + 删内部面"，不是布尔：见 `clip_to_rect` 的注释 ——
       顺序四刀删的是"任一半空间之外"的全部几何，会整块删光。
       这里先只切不删（四刀把每个面切成要么全在矩形内、要么全在外），
       再删**中心严格在矩形内**的面；边界上的切面保留（它们是外侧那一半的封口）。
    返回 False 表示整块都在矩形内（复制件应丢弃）。
    """
    import bmesh
    if o.data.users > 1:
        o.data = o.data.copy()
    mw = o.matrix_world if o.parent else o.matrix_basis
    mwi = mw.inverted()
    nmat = mw.to_3x3().transposed()          # 世界 → 局部法线
    bm = bmesh.new()
    bm.from_mesh(o.data)
    for pco, pno in (((rect[0], 0, 0), (-1, 0, 0)), ((rect[2], 0, 0), (1, 0, 0)),
                     ((0, rect[1], 0), (0, -1, 0)), ((0, rect[3], 0), (0, 1, 0))):
        co = mwi @ Vector(pco)
        no = (nmat @ Vector(pno)).normalized()
        bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:],
                               dist=1e-4, plane_co=co, plane_no=no,
                               clear_outer=False, clear_inner=False)
    eps = 0.05
    dead = []
    for f in bm.faces:
        p = mw @ f.calc_center_median()
        if (rect[0] + eps < p.x < rect[2] - eps
                and rect[1] + eps < p.y < rect[3] - eps):
            dead.append(f)
    if dead:
        bmesh.ops.delete(bm, geom=dead, context='FACES')
    loose = [v for v in bm.verts if not v.link_faces]
    if loose:
        bmesh.ops.delete(bm, geom=loose, context='VERTS')
    n_left = len(bm.verts)
    bm.to_mesh(o.data)
    bm.free()
    o.data.update()
    return n_left > 0


# ------------------------------------------------------------------ 主流程
def _layer_of(name, node):
    if node.name == name:
        return node
    for ch in node.children:
        r = _layer_of(name, ch)
        if r is not None:
            return r
    return None


def verify_no_visible_lod_inside(rect):
    """活动区内不得有**可见**的远景碎片（逐顶点判定，比包围盒严）。

    rect = (x0, y0, x1, y1)，场景局部坐标（此时场景中心已在原点）。
    返回违规对象名列表；空 = 合格。
    """
    import numpy as np
    bad = []
    for o in bpy.data.objects:
        if o.type != "MESH" or o.get("cls_key") != "lod":
            continue
        try:
            if not o.visible_get():
                continue
        except Exception:
            continue
        me = o.data
        n = len(me.vertices)
        if not n:
            continue
        mw = o.matrix_world if o.parent else o.matrix_basis
        co = np.empty(n * 3, dtype=np.float32)
        me.vertices.foreach_get("co", co)
        co = co.reshape(n, 3)
        m = np.array(mw, dtype=np.float64)
        w = co @ m[:3, :3].T + m[:3, 3]
        inside = ((w[:, 0] >= rect[0]) & (w[:, 0] <= rect[2]) &
                  (w[:, 1] >= rect[1]) & (w[:, 1] <= rect[3]))
        if inside.any():
            bad.append(o.name)
    return bad


def restore_hidden_classes(ring_name=RING_COLLECTION):
    """收尾复原「整类默认隐藏」。

    背景：`write_manifest` 会把所有集合全开（为求 matrix_world），跑完不复原，
    于是分类阶段设的隐藏全被冲掉。这里按 `class_rules.DEFAULT_HIDDEN` 重新关一遍，
    并单独把远景集合打开。集合开关与视层眼睛两套都要设（AGENTS §4 的坑）。
    """
    from class_rules import DEFAULT_HIDDEN
    # decal 不在 DEFAULT_HIDDEN 里，但**启动器**会额外把它关掉（AGENTS/分类文档）。
    # 场景 blend 不经过启动器，这里一并关掉，否则地上会露出大片黑色贴花。
    hidden_keys = tuple(DEFAULT_HIDDEN) + ("decal",)
    root = bpy.context.view_layer.layer_collection
    hidden, shown = [], 0
    for col in bpy.data.collections:
        nm = col.name
        if not nm.startswith("C_"):
            continue
        key = None
        for k in hidden_keys:
            if nm.startswith("C_%s_" % k):
                key = k
                break
        if key is None:
            continue
        col.hide_viewport = True
        col.hide_render = True
        lc = _layer_of(nm, root)
        if lc is not None:
            lc.hide_viewport = True
        hidden.append(key)
    rc = bpy.data.collections.get(ring_name)
    if rc is not None:
        rc.hide_viewport = False
        rc.hide_render = False
        lc = _layer_of(rc.name, root)
        if lc is not None:
            lc.hide_viewport = False
        shown = len(rc.objects)
    # 说明（2026-11-04）：**不要**对 lod 做对象级 hide_set —— 分类面板切的是集合可见性，
    # 对象级隐藏会让"显示"按钮失效（用户实测看不见）。两类已拆开后，只靠集合开关即可。
    print("[trim] 复原默认隐藏：%s（%d 类）｜远景集合可见 %d 个"
          % (",".join(sorted(set(hidden))), len(set(hidden)), shown))


def trim_current_scene(sc, out="", report="", manifest="",
                       keep_terrain=True, keep_water=False, recenter=True, unhide=False,
                       town_zones=None):
    t0 = time.time()
    act, far = rects(sc)
    print("[trim] 场景 %s（%s）中心 (%.0f, %.0f)" % (sc["id"], sc["name"], sc["x"], sc["y"]))
    print("[trim] 活动区 %.0f×%.0f · 远景 %.0f×%.0f"
          % (sc["aw"], sc["ah"], sc["fw"], sc["fh"]))

    # 只在「从磁盘打开旧 blend」时才需要展开集合重算矩阵；本进程刚建的对象矩阵是准的，
    # 展开 9 万个对象会让 view_layer.update() 卡上几十分钟（2026-11-03 实测 57 分钟）。
    if unhide:
        unhide_all(bpy.context.view_layer.layer_collection)
        bpy.context.view_layer.update()

    keep_act, keep_ring, drop = [], [], []
    stats = collections.Counter()
    for o in list(bpy.context.scene.objects):
        if o.name.startswith("Terrain"):
            (keep_act if keep_terrain else drop).append(o)
            continue
        if o.name.startswith("Water"):
            (keep_act if keep_water else drop).append(o)
            continue
        if o.type != "MESH":
            keep_act.append(o)
            continue
        # 场景自带地形（deliverable/terrain 切的）—— 原 blend 里的地形块/地形 LOD
        # 按**常规规矩隐藏**（class_rules.DEFAULT_HIDDEN），不再删除（2026-11-03 用户裁定）
        mn, mx = bb_of(o)
        if not hit(mn, mx, far):
            drop.append(o)
            stats["删·远景范围外"] += 1
        elif hit(mn, mx, act) and not (
                town_zones and o.get("cls_key") == "lod"
                and any(hit(mn, mx, z) for z in town_zones)):
            keep_act.append(o)
            stats["留·活动区"] += 1
            # 🔴 跨活动区的 lod：原件照旧隐藏（不裁不删），另做一份「只保留 P 外」的
            # 可见副本归 dock 到远景圈。不做的话，合并 LOD 块（new_area_slod4 含西西卡
            # 292 面）会整块被打成 lod 隐藏 ⇒ 活动区外的另一座据点什么也看不到。
            if o.get("cls_key") == "lod":
                fully_inside = (mn.x >= act[0] and mx.x <= act[2]
                                and mn.y >= act[1] and mx.y <= act[3])
                if not fully_inside:
                    cp = o.copy()
                    cp.data = o.data.copy()
                    cp.name = o.name + '_out'
                    bpy.context.scene.collection.objects.link(cp)
                    cp.hide_viewport = False
                    cp.hide_render = False
                    try:
                        cp.hide_set(False)
                    except Exception:
                        pass
                    if clip_to_outside_rect(cp, act):
                        keep_ring.append(cp)
                        stats["跨边界lod副本"] += 1
                    else:
                        bpy.data.objects.remove(cp, do_unlink=True)
        elif o.get("cls_key") == "lod":
            keep_ring.append(o)
            stats["留·远景碎片"] += 1
            if os.environ.get("SCENE_TRIM_DEBUG") and stats["留·远景碎片"] <= 8:
                print("[dbg] ring %s loc=(%.0f,%.0f) bb x[%.0f,%.0f] y[%.0f,%.0f] far=%s"
                      % (o.name, o.location.x, o.location.y, mn.x, mx.x, mn.y, mx.y, far))
        else:
            drop.append(o)
            stats["删·圈内非远景碎片"] += 1
    print("[trim] 保留 活动区 %d · 远景 %d ｜ 删除 %d（%.1f s）"
          % (len(keep_act), len(keep_ring), len(drop), time.time() - t0))

    if keep_ring:
        col = bpy.data.collections.get(RING_COLLECTION)
        if col is None:
            col = bpy.data.collections.new(RING_COLLECTION)
            bpy.context.scene.collection.children.link(col)
        for o in keep_ring:
            o["ring"] = 1
            o["cls_key"] = "lod_out"      # 分类改成「远景碎片·区外」（2026-11-04 两类拆分）
            # 🔴 只挂「活动区外远景」集合，**从类集合里摘出来**（2026-11-04 用户要求两个区分）：
            #   不摘的话，"隐藏远景碎片类"对它们无效（它们同时属于可见的 O_ 集合，照样显示）。
            #   分类信息保留在对象的 cls_key 自定义属性里，分类器口径不变。
            for c in list(o.users_collection):
                if c is not col:
                    c.objects.unlink(o)
            if o.name not in col.objects:
                col.objects.link(o)

    # 跨出远景范围的残件（铁路/隧道 LOD 单块能横跨 2 km）→ 按远景框裁掉。
    # 先裁、后删：被裁光的对象并进 drop 一起删，避免拿到已释放的引用。
    # 🔴 判定前强制求值：新建对象的 bound_box 在 depsgraph 跑之前是默认 ±1 的盒，
    #    会被误判「在框内」而整块跳过裁剪（实测 sdn 的 cor_derricks_slod_09 漏了 7876 个顶点）。
    bpy.context.view_layer.update()
    clipped = 0
    clipped_names = set()
    for o in list(keep_act + keep_ring):
        if o.type != "MESH" or o.name.startswith(("Terrain", "Water")):
            continue
        mn, mx = bb_of(o)
        if (mn.x >= far[0] - 1 and mx.x <= far[2] + 1
                and mn.y >= far[1] - 1 and mx.y <= far[3] + 1):
            continue
        # 隐藏类地形片跨边界 → 直接丢（不裁剪；共面三角形会让 bisect 卡死）
        if o.get("cls_key") in HIDDEN_TERRAIN:
            (keep_act if o in keep_act else keep_ring).remove(o)
            drop.append(o)
            stats["删·隐藏地形跨边界"] += 1
            continue
        try:
            if not clip_to_rect(o, far):
                (keep_act if o in keep_act else keep_ring).remove(o)
                drop.append(o)
                stats["删·整块裁光"] += 1
                continue
            clipped += 1
            clipped_names.add(o.name)
        except Exception as e:
            print("[trim] 裁剪失败 %s：%s" % (o.name, e))
    if clipped:
        # 网格刚被改过：`bound_box` 要等 depsgraph 求值才更新，否则下面清单里记的仍是
        # 裁剪前的包围盒 —— 批量验收会误报"超出远景框"（2026-11-04 圣丹尼斯）。
        bpy.context.view_layer.update()
        print("[trim] 按远景框裁掉超界几何：%d 个对象" % clipped)

    for o in drop:
        bpy.data.objects.remove(o, do_unlink=True)
    if drop:
        bpy.context.view_layer.update()

    # 清单（平移前算，包围盒 = 世界坐标）
    kept = keep_act + keep_ring
    ca, cr = collections.Counter(), collections.Counter()
    rows = []
    mn = Vector((1e18,) * 3)
    mx = Vector((-1e18,) * 3)
    has_mesh = False
    for o in kept:
        if o.type != "MESH" or o.name.startswith(("Terrain", "Water")):
            continue                     # 灯/相机/地形/水面不进清单（对账只算实体）
        k = o.get("cls_key") or ("terrain" if o.name.startswith("Terrain") else
                                 "water" if o.name == "Water" else "mesh")
        ring = 1 if o.get("ring") else 0
        (cr if ring else ca)[k] += 1
        has_mesh = True
        # 被裁过的对象用逐顶点口径：bound_box 角点经旋转会外扩，贴着边界时假报超界。
        b0, b1 = exact_bb(o) if o.name in clipped_names else bb_of(o)
        for i in range(3):
            mn[i] = min(mn[i], b0[i])
            mx[i] = max(mx[i], b1[i])
        rows.append({"n": o.name, "c": k, "ring": ring,
                     "bb": [round(v, 2) for v in (b0.x, b0.y, b0.z, b1.x, b1.y, b1.z)],
                     "tid": o.get("tile") or ""})

    rep = {"scene": sc, "activity_rect": list(act), "far_rect": list(far),
           "kept_activity": sum(ca.values()), "kept_ring": sum(cr.values()),
           "dropped": len(drop), "clipped": clipped, "by_class_activity": dict(ca), "by_class_ring": dict(cr),
           "stats": dict(stats), "recentered": recenter,
           "content_bbox_world": [round(v, 1) for v in (mn.x, mn.y, mn.z, mx.x, mx.y, mx.z)]
           if has_mesh else [],
           "seconds": round(time.time() - t0, 1)}
    for k, v in sorted(ca.items(), key=lambda kv: -kv[1]):
        print("    活动区 %-14s %6d" % (k, v))
    for k, v in sorted(cr.items(), key=lambda kv: -kv[1]):
        print("    远景   %-14s %6d" % (k, v))
    print("[trim] 内容 bbox(世界) %s · 删除明细 %s" % (rep["content_bbox_world"], dict(stats)))

    if manifest:
        os.makedirs(os.path.dirname(manifest), exist_ok=True)
        with open(manifest, "w", encoding="utf-8") as fp:
            for r in rows:
                fp.write(json.dumps(r, ensure_ascii=False) + "\n")
        print("[trim] 清单 -> %s" % manifest)
    if report:
        os.makedirs(os.path.dirname(report), exist_ok=True)
        json.dump(rep, open(report, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("[trim] 报告 -> %s" % report)

    if recenter:
        off = Vector((-sc["x"], -sc["y"], 0.0))
        for o in kept:
            if o.name.startswith(("Terrain", "Water")):
                continue          # 地形与水面本来就是按局部坐标建的，不能再平移一次
            mw = (o.matrix_world if o.parent else o.matrix_basis).copy()
            mw.translation += off
            o.matrix_world = mw
        bpy.context.view_layer.update()
        print("[trim] 已平移 (%.0f, %.0f)" % (sc["x"], sc["y"]))

    # 复原「整类默认隐藏」（write_manifest 会把集合全开）+ 远景集合可见
    restore_hidden_classes()

    # 验收：活动区内不得有【可见】的远景碎片（逐个顶点判，比包围盒严）
    # 注意：此时场景已平移到以场景中心为原点 → 用局部矩形。
    bad = verify_no_visible_lod_inside((-sc["aw"] / 2, -sc["ah"] / 2,
                                        sc["aw"] / 2, sc["ah"] / 2))
    if bad:
        print("[trim] ❌ 活动区内仍有可见的远景碎片 %d 个：%s" % (len(bad), bad[:5]))
    else:
        print("[trim] ✅ 活动区内无可见远景碎片（逐顶点检查）")

    if out:
        os.makedirs(os.path.dirname(out), exist_ok=True)
        # 贴图外链 → 转成相对 blend 的路径（//tex/…），整个 scenes 目录可以整体搬走
        try:
            bpy.ops.file.make_paths_relative()
        except Exception as e:
            print("[trim] 贴图路径转相对失败：%s" % e)
        bpy.ops.wm.save_as_mainfile(filepath=out)
        print("[trim] saved %s %.2f GB（总 %.1f s）"
              % (out, os.path.getsize(out) / 1e9, time.time() - t0))
    return rep


# ------------------------------------------------------------------ 单独跑的入口
def _main():
    import argparse
    import sys
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    ap.add_argument("--out", default="")
    ap.add_argument("--csv", default=DEFAULT_CSV)
    ap.add_argument("--report", default="")
    ap.add_argument("--manifest", default="")
    ap.add_argument("--keep-terrain", action="store_true")
    ap.add_argument("--keep-water", action="store_true")
    ap.add_argument("--no-recenter", action="store_true")
    a = ap.parse_args(argv)
    sc = load_scene(a.scene, a.csv)
    man = a.manifest
    if not man and a.out:
        man = os.path.join(os.path.dirname(a.out), "manifest_%s.jsonl" % a.scene)
    trim_current_scene(sc, out=a.out, report=a.report, manifest=man,
                       keep_terrain=a.keep_terrain, keep_water=a.keep_water,
                       recenter=not a.no_recenter, unhide=True)


if __name__ == "__main__":
    _main()
