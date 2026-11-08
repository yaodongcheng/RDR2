# -*- coding: utf-8 -*-
"""场景地形 —— 按两层口径，从 `deliverable/terrain` 交付物切一块场景地面。

数据源（**只读交付物，不碰 blend**）：
    <PROJ>/deliverable/terrain/scene_native/meta.json          世界框 / 分辨率 / z 区间
    <PROJ>/deliverable/terrain/scene_native/height_4m_16bit_native.png 16bit 原生高度（4 m，行 0 = 北）
    <PROJ>/deliverable/terrain/color_1m.png                    1 m 唯一地形材质图（裁一块当贴图）

做法：
    · **整块地形（活动区 + 远景）统一 4 m 网格**（2026-11-03 用户裁定：不分粗细，
      也不拼条带/留重叠，从根上消除分辨率分界与接缝）
    · 彩图按**远景范围**裁一块 PNG 当贴图，UV 按世界坐标算（1 m/px，比顶点色清楚）
    · 坐标是**场景局部坐标**（世界 x,y − 场景中心），和 scene_trim 的平移口径一致

用法（由 blender_continent.py --scene 自动调用；也可单独跑）：

    blender -b -P tools/scene_terrain.py -- --scene sod [--tex-dir ...]
"""

import bpy
import json
import math
import os
import time

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.dirname(HERE)
RDR2 = r"D:/BrainMaker/大镖客2解包分析"

_EXTENT = None


def scene_extent():
    """地图画面区 bbox `[x0, y0, x1, y1]`（`docs/世界与地编/scene_extent.json`，由
    `tools/gen_scene_extent.py` 生成）；读不到就返回 None（不裁剪，保持旧行为）。"""
    global _EXTENT
    if _EXTENT is None:
        p = os.path.join(SRC, 'docs', '世界与地编', 'scene_extent.json')
        try:
            d = json.load(open(p, encoding='utf-8'))
            _EXTENT = d.get('map') or ()
        except Exception:
            _EXTENT = ()
    return _EXTENT or None
TERRAIN = os.path.join(RDR2, "deliverable", "terrain", "scene_native")
DEFAULT_CSV = os.path.join(SRC, "docs", "世界与地编", "scene_list.csv")
DEFAULT_TEXDIR = os.path.join(RDR2, "deliverable", "blender", "scenes", "tex")

STEP = 4.0          # 全场统一最高精度（RDR2 原生高度图就是 4 m）

# tools/ 加进 sys.path，保证单独用 -P tools/scene_terrain.py 跑也能 import 到 core
import sys as _sys  # noqa: E402
if HERE not in _sys.path:
    _sys.path.insert(0, HERE)


# ------------------------------------------------------------------ 数据
# 采样口径**只有一份实现**：scene_terrain_core（纯 Python，被 check_scene_terrain.py 共用）。
# 这里只做转出，禁止在本文件里另写一份（分叉 = 检查失效）。
from scene_terrain_core import load_meta, heights, sample_h, axis as _core_axis, uv_of


def crop_color(meta, fx0, fy0, fx1, fy1, out_png):
    """按世界矩形从 1 m 彩图裁一块（不整图读进内存），返回贴图路径。

    🔴 城镇底下 RDR2 把地形彩图**涂黑**（城市地面由建筑/街道模型接管）。
    场景里 `road` 默认隐藏，黑区会裸露成黑块 → 这里把**近黑像素用周围地表色补掉**
    （只改我们自己的场景贴图，不动 `deliverable/terrain` 源文件）。
    """
    from PIL import Image
    os.makedirs(os.path.dirname(out_png), exist_ok=True)
    x0 = int(round((fx0 - meta["x0"]) / meta["cres"]))
    x1 = int(round((fx1 - meta["x0"]) / meta["cres"]))
    y0 = int(round((meta["y1"] - fy1) / meta["cres"]))
    y1 = int(round((meta["y1"] - fy0) / meta["cres"]))
    x0 = max(0, min(x0, meta["cw"] - 1)); x1 = max(x0 + 1, min(x1, meta["cw"]))
    y0 = max(0, min(y0, meta["ch"] - 1)); y1 = max(y0 + 1, min(y1, meta["ch"]))
    # 2026-11-03 用户裁定：城镇底下的黑块是**游戏原生数据**（城市地面预留洞），保持原样，不做修补
    Image.open(meta["cfile"]).crop((x0, y0, x1, y1)).convert("RGB").save(out_png)
    return out_png


def scene_water_level(fx0, fy0, fx1, fy1, min_share=0.05):
    """该场景的水位 —— **全图只有两个值**：主水系 40.5 / 西盆地 −22（2026-11-07 用户裁定）。

    返回 `None` = 这个场景不该铺水面（范围里只有高山湖，或根本没有水）。

    🔴 旧版取"范围内所有水面像素的中位数"，把 40 个**高山小湖**（58~243 m）也算进去 ——
       山地场景因此得到 238.4 / 200.4 / 149.9 之类的第三、第四个值，一块 238 m 的平面
       盖住整个山谷。现在只认两大水系的**面积占比**：谁占比大用谁，两个都不足 5% 就不铺。
    """
    path = os.path.join(RDR2, "export", "world", "water_level_map_2lv.npy")
    if not os.path.exists(path):
        return 40.5
    lvl = np.load(path)
    if lvl.ndim != 2:
        return 40.5
    X0, Y0, WORLD = -7684.0, -8196.0, 12296.0
    P = lvl.shape[0]
    res = WORLD / P
    c0 = int(np.clip(round((fx0 - X0) / res), 0, P - 1))
    c1 = int(np.clip(round((fx1 - X0) / res), 0, P - 1))
    r0 = int(np.clip(round((fy0 - Y0) / res), 0, P - 1))
    r1 = int(np.clip(round((fy1 - Y0) / res), 0, P - 1))
    sub = lvl[min(r0, r1):max(r0, r1) + 1, min(c0, c1):max(c0, c1) + 1]
    v = sub[np.isfinite(sub)]
    if v.size == 0:
        return None
    main = float((np.abs(v - 40.5) < 0.6).sum()) / v.size
    west = float((np.abs(v + 22.0) < 0.6).sum()) / v.size
    if max(main, west) < min_share:
        return None
    return 40.5 if main >= west else -22.0


def _water_plane(fx0, fy0, fx1, fy1, level, cx, cy, _mat_tex=None):
    """一块覆盖远景范围的水面（局部坐标，z = 绝对水位）。"""
    verts = [(fx0 - cx, fy0 - cy, level), (fx1 - cx, fy0 - cy, level),
             (fx1 - cx, fy1 - cy, level), (fx0 - cx, fy1 - cy, level)]
    faces = [(0, 1, 2, 3)]
    me = bpy.data.meshes.new("Water")
    me.from_pydata(verts, [], faces)
    me.update()
    ob = bpy.data.objects.new("Water", me)
    ob.data.materials.append(_water_material())
    bpy.context.scene.collection.objects.link(ob)
    return ob


def _water_material():
    m = bpy.data.materials.get("water")
    if m and m.use_nodes:
        return m
    m = bpy.data.materials.new("water")
    m.use_nodes = True
    nt = m.node_tree
    bsdf = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (0.055, 0.135, 0.235, 1.0)
        bsdf.inputs["Roughness"].default_value = 0.08
        for k, v in (("IOR", 1.333), ("Alpha", 0.72)):
            if k in bsdf.inputs:
                bsdf.inputs[k].default_value = v
    for attr, val in (("surface_render_method", "BLENDED"), ("blend_method", "BLEND")):
        try:
            setattr(m, attr, val)
        except Exception:
            pass
    try:
        m.use_backface_culling = False
    except Exception:
        pass
    return m


def _mat(tex_path):
    key = "scene_terrain_" + os.path.basename(tex_path)
    m = bpy.data.materials.get(key)
    if m:
        return m
    m = bpy.data.materials.new(key)
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    img = bpy.data.images.load(tex_path, check_existing=True)
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = img
    tex.interpolation = "Linear"
    nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.95
    return m


def _mesh(name, verts, faces, uvs, mat):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in verts], [], faces)
    me.update()
    # 🔴 平滑着色（2026-11-03 用户实测）：不开的话每格都是硬边面，4 m 格子肉眼可见"颗粒感"；
    # 旧分区 18 的 Terrain 是平滑的，所以哪怕 8 m 网格看着也比我们顺。这只改显示，不动高度。
    for p in me.polygons:
        p.use_smooth = True
    uvl = me.uv_layers.new(name="UVMap")
    # 🔴 UV 是按 loop（面的角）存的，不是按顶点 —— 直接按顶点索引写会错位（渲染成棋盘格）
    for poly in me.polygons:
        for li in poly.loop_indices:
            vi = me.loops[li].vertex_index
            uvl.data[li].uv = (float(uvs[vi][0]), float(uvs[vi][1]))
    ob = bpy.data.objects.new(name, me)
    ob.data.materials.append(mat)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def _grid(meta, H, x0, y0, x1, y1, step, cx, cy, uv_box):
    """世界矩形 → 网格（局部坐标）+ UV。uv_box = (fx0, fy0, fx1, fy1)。"""
    # 顶点吸附全局格点（口径在 core.axis 里，只有一份）
    xs = _core_axis(x0, x1, step)
    ys = _core_axis(y0, y1, step)
    if xs[-1] < x1 - 1e-6:
        xs = np.append(xs, x1)
    if ys[-1] < y1 - 1e-6:
        ys = np.append(ys, y1)
    nx, ny = len(xs), len(ys)
    gx, gy = np.meshgrid(xs, ys)
    z = sample_h(meta, H, gx, gy)
    verts = np.stack([gx.ravel() - cx, gy.ravel() - cy, z.ravel()], axis=1)
    faces = []
    for j in range(ny - 1):
        for i in range(nx - 1):
            a = j * nx + i
            faces.append((a, a + 1, a + nx + 1, a + nx))
    fx0, fy0, fx1, fy1 = uv_box
    # 🔴 V 轴口径只有一份实现（scene_terrain_core.uv_of）：**v 随 y 增大**。
    # 写成 1 - (...) 会让整张贴图南北镜像（2026-11-04 黑水镇就是这个 bug）。
    u, v = uv_of(gx.ravel(), gy.ravel(), uv_box)
    uvs = np.stack([u, v], axis=1)
    return verts, faces, uvs


def build(scene, step=STEP, tex_dir=DEFAULT_TEXDIR, verbose=True):
    """场景地形：活动区一块 + 远景四条带（结构不变），**精度全部用同一个最细网格**。

    2026-11-03 用户裁定：不要粗细两级 —— 活动区和远景都用 4 m。
    """
    t0 = time.time()
    meta = load_meta(scene_id=scene.get("id"))
    H = heights(meta)
    cx, cy = scene["x"], scene["y"]
    # 🔴 2026-11-04：活动区 = 能走范围 P（P 外一律按远景处理）。地形仍按**整块远景框**
    # 铺满，只是"活动区/远景条带"的分界改用 P 的矩形（P 不一定以场景中心对称）。
    if scene.get("p"):
        ax0, ay0, ax1, ay1 = scene["p"]
    else:
        ax0, ay0 = cx - scene["aw"] / 2, cy - scene["ah"] / 2
        ax1, ay1 = cx + scene["aw"] / 2, cy + scene["ah"] / 2
    fx0, fy0 = cx - scene["fw"] / 2, cy - scene["fh"] / 2
    fx1, fy1 = cx + scene["fw"] / 2, cy + scene["fh"] / 2
    fx0, fy0 = max(fx0, meta["x0"]), max(fy0, meta["y0"])
    fx1, fy1 = min(fx1, meta["x1"]), min(fy1, meta["y1"])
    ax0, ay0 = max(ax0, fx0), max(ay0, fy0)
    ax1, ay1 = min(ax1, fx1), min(ay1, fy1)

    tex = crop_color(meta, fx0, fy0, fx1, fy1, os.path.join(tex_dir, "%s_color.png" % scene["id"]))
    mat = _mat(tex)
    uv_box = (fx0, fy0, fx1, fy1)

    made = []
    v, f, uv = _grid(meta, H, ax0, ay0, ax1, ay1, step, cx, cy, uv_box)
    _mesh("Terrain", v, f, uv, mat)
    made.append(("Terrain", len(v)))
    if verbose:
        print("[terrain] 活动区 %d 顶点 / %d 面（%.0f m 网格）" % (len(v), len(f), step))

    pad = step      # 条带往活动区压一格，避免开口（一格 = 网格步长）
    strips = [
        ("Terrain_Far_N", fx0, ay1 - pad, fx1, fy1),
        ("Terrain_Far_S", fx0, fy0, fx1, ay0 + pad),
        ("Terrain_Far_W", fx0, ay0 + pad, ax0 + pad, ay1 - pad),
        ("Terrain_Far_E", ax1 - pad, ay0 + pad, fx1, ay1 - pad),
    ]
    for nm, sx0, sy0, sx1, sy1 in strips:
        if sx1 - sx0 < 1 or sy1 - sy0 < 1:
            continue
        v, f, uv = _grid(meta, H, sx0, sy0, sx1, sy1, step, cx, cy, uv_box)
        _mesh(nm, v, f, uv, mat)
        made.append((nm, len(v)))
        if verbose:
            print("[terrain] %s %d 顶点 / %d 面（%.0f m 网格）" % (nm, len(v), len(f), step))
    # 水面：**一块大平面**（2026-11-04 用户裁定：一个场景不会同时有两种水位，
    # 只有大地图才有两级）。水位取该场景范围内的水位中位数。
    try:
        lvl = scene_water_level(fx0, fy0, fx1, fy1)
        if lvl is None:
            print("[terrain] 水面：该场景只有高山湖（或无水），**不铺水面**")
        else:
            _water_plane(fx0, fy0, fx1, fy1, lvl, cx, cy, mat)
            print("[terrain] 水面：单平面 z=%.1f m（覆盖远景范围）" % lvl)
    except Exception as e:
        print("[terrain] 水面构建失败（跳过）：%s" % e)
    print("[terrain] 场景地形完成（%.1f s，贴图 %s）" % (time.time() - t0, os.path.basename(tex)))
    return made


def _main():
    import argparse
    import sys
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    ap.add_argument("--csv", default=DEFAULT_CSV)
    ap.add_argument("--tex-dir", default=DEFAULT_TEXDIR)
    a = ap.parse_args(argv)
    sys.path.insert(0, HERE)
    import scene_trim
    build(scene_trim.load_scene(a.scene, a.csv), tex_dir=a.tex_dir)


if __name__ == "__main__":
    _main()
