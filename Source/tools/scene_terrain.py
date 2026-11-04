# -*- coding: utf-8 -*-
"""场景地形 —— 按两层口径，从 `deliverable/terrain` 交付物切一块场景地面。

数据源（**只读交付物，不碰 blend**）：
    <PROJ>/deliverable/terrain/final/meta.json          世界框 / 分辨率 / z 区间
    <PROJ>/deliverable/terrain/final/height_4m_16bit.png 16bit 高度（4 m，行 0 = 北）
    <PROJ>/deliverable/terrain/final/color_1m.png        1 m 彩图（裁一块当贴图）

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
import os
import time

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.dirname(HERE)
RDR2 = r"D:/BrainMaker/大镖客2解包分析"
TERRAIN = os.path.join(RDR2, "deliverable", "terrain", "final")
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
from scene_terrain_core import load_meta, heights, sample_h, axis as _core_axis  # noqa: E402


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
    u = (gx.ravel() - fx0) / max(1e-6, fx1 - fx0)
    v = 1.0 - (gy.ravel() - fy0) / max(1e-6, fy1 - fy0)
    uvs = np.stack([u, v], axis=1)
    return verts, faces, uvs


def build(scene, step=STEP, tex_dir=DEFAULT_TEXDIR, verbose=True):
    """场景地形：活动区一块 + 远景四条带（结构不变），**精度全部用同一个最细网格**。

    2026-11-03 用户裁定：不要粗细两级 —— 活动区和远景都用 4 m。
    """
    t0 = time.time()
    meta = load_meta()
    H = heights(meta)
    cx, cy = scene["x"], scene["y"]
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
