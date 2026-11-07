# -*- coding: utf-8 -*-
"""构建「交付口径」的大地图 blend（continent_v25）。

为什么要单独建：老的 continent_v23 / lod_split_v24 用的是
  · 12,296 m 的 H4 全图（比地图框大一圈，框外没地表色）
  · 原生 H4 高度（和交付给骑砍2 的改造版高度图差最多 603 m）
  · 一张 40.5 m 的平板水面（把西部盆地淹掉）
  · 还带着瓜玛（45 件碎片在地图框外）

本脚本按交付物本身重建：
  范围 = 地图框 10,768 × 8,024 m（x[-6844,3924] y[-4800,3224]）
  高度 = deliverable/terrain/stages/01_plateau_plain/height_16bit_4m.png
         （**原生 H4 + 自然界过渡**：西北高原 720 m + fBm + 150 m 高斯过渡、东南平原 42 m；
          2026-11-07 用户裁定用这一级，不用 continent_height_4m.png 那版「挖水系」的）
  地表 = deliverable/terrain/final/color_1m.png（1 m/px，平面 UV）
  水面 = **两块**（西 −22 / 东 40.5，分割线默认 x=-1000），各自由 `water_mask.png`
         （= `terrain/weights/w_water.png`，同一张图）裁切 —— 水只出现在该有的地方
  碎片 = continent_lod_split_v24.blend 里的 S_*/W_*（不含 G_* 瓜玛、不含地形远景块）

用法：
    blender -b --factory-startup -P tools\\_unbuffer.py -P tools\\build_continent_map.py -- \
        --out "D:\\BrainMaker\\大镖客2解包分析\\deliverable\\blender\\continent\\continent_v25.blend"

    # 只看参数不建：
    blender -b --factory-startup -P tools\\build_continent_map.py -- --dry-run
"""
import argparse
import json
import os
import sys

import numpy as np
from PIL import Image

import bpy

ROOT = r"D:/BrainMaker/大镖客2解包分析"
DELIV = os.path.join(ROOT, "deliverable")
HEIGHT = os.path.join(DELIV, "terrain", "stages", "01_plateau_plain", "height_16bit_4m.png")
HEIGHT_META = os.path.join(DELIV, "terrain", "stages", "01_plateau_plain", "meta.json")
COLOR = os.path.join(DELIV, "terrain", "final", "color_1m.png")
MASK = os.path.join(DELIV, "heightmap", "water_mask.png")
LOD = os.path.join(DELIV, "blender", "continent", "continent_lod_split_v24.blend")
SCENES = os.path.join(DELIV, "blender", "scenes")

# 世界框（= 交付高度图 = 官方地图画面区）
X0, X1 = -6844.0, 3924.0
Y0, Y1 = -4800.0, 3224.0
RES = 4.0

ZN = 40.5      # 主水系
ZW = -22.0     # 西盆地
WEST_SCENES = ("wild_09", "wild_10", "wild_12")

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []


def parse():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="")
    ap.add_argument("--height", default=HEIGHT)
    ap.add_argument("--height-meta", default=HEIGHT_META,
                    help="高度图的编码元数据（zmin/zmax 必须与高度图同源）")
    ap.add_argument("--color", default=COLOR)
    ap.add_argument("--mask", default=MASK)
    ap.add_argument("--lod", default=LOD)
    ap.add_argument("--res", type=float, default=RES)
    ap.add_argument("--water-res", type=float, default=8.0, help="(旧口径保留，不再使用)")
    ap.add_argument("--water-split-x", type=float, default=-1000.0,
                    help="东西两块水面的分割线（世界 x），默认 -1000")
    ap.add_argument("--no-water", action="store_true")
    ap.add_argument("--skip-lod", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    return ap.parse_args(ARGS)


def load_height(path):
    im = Image.open(path)
    a = np.asarray(im)
    print("[map] height %s %s %s" % (os.path.basename(path), im.size, im.mode))
    if a.dtype == np.uint16 or a.max() > 255:
        # 16 bit 灰度：0..65535
        return a.astype(np.float32) / 65535.0
    return a.astype(np.float32) / 255.0


def west_rects():
    rects = []
    for sid in WEST_SCENES:
        p = os.path.join(SCENES, "scene_report_%s.json" % sid)
        with open(p, encoding="utf-8") as f:
            r = json.load(f)["far_rect"]
        rects.append((min(r[0], r[2]), min(r[1], r[3]), max(r[0], r[2]), max(r[1], r[3])))
    print("[map] west basin rects:", rects)
    return rects


def build_terrain(z_norm, res, zmin, zmax, color_path, out_path):
    H, W = z_norm.shape
    VW, VH = W + 1, H + 1
    print("[map] terrain grid %d x %d verts (%.2f M), %d x %d faces" %
          (VW, VH, VW * VH / 1e6, W, H))

    z = zmin + z_norm * (zmax - zmin)
    zi = np.clip(np.arange(VH), 0, H - 1)
    xi = np.clip(np.arange(VW), 0, W - 1)
    zz = z[np.ix_(zi, xi)]

    xs = (X0 + np.arange(VW) * res).astype(np.float32)
    ys = (Y1 - np.arange(VH) * res).astype(np.float32)

    verts = np.empty((VW * VH, 3), np.float32)
    verts[:, 0] = np.tile(xs, VH)
    verts[:, 1] = np.repeat(ys, VW)
    verts[:, 2] = zz.ravel()

    j = np.arange(H, dtype=np.int32)[:, None]
    i = np.arange(W, dtype=np.int32)[None, :]
    base = (j * VW + i)
    # 顶点顺序必须逆时针（从 +Z 看）：NW → SW → SE → NE，否则法线朝下
    loops = np.empty((H, W, 4), np.int32)
    loops[..., 0] = base
    loops[..., 1] = base + VW
    loops[..., 2] = base + VW + 1
    loops[..., 3] = base + 1

    uvs = np.empty((H, W, 4, 2), np.float32)
    u0 = (i / float(W)).astype(np.float32)
    u1 = ((i + 1) / float(W)).astype(np.float32)
    v0 = (1.0 - j / float(H)).astype(np.float32)
    v1 = (1.0 - (j + 1) / float(H)).astype(np.float32)
    uvs[..., 0, 0] = u0
    uvs[..., 1, 0] = u0
    uvs[..., 2, 0] = u1
    uvs[..., 3, 0] = u1
    uvs[..., 0, 1] = v0
    uvs[..., 1, 1] = v1
    uvs[..., 2, 1] = v1
    uvs[..., 3, 1] = v0

    me = bpy.data.meshes.new("Terrain")
    me.vertices.add(len(verts))
    me.vertices.foreach_set("co", verts.ravel())
    me.loops.add(loops.size)
    me.loops.foreach_set("vertex_index", loops.ravel())
    me.polygons.add(H * W)
    me.polygons.foreach_set("loop_start", (np.arange(H * W, dtype=np.int32) * 4))
    me.polygons.foreach_set("loop_total", np.full(H * W, 4, np.int32))
    me.update(calc_edges=False)

    uvl = me.uv_layers.new(name="UVMap")
    uvl.data.foreach_set("uv", uvs.reshape(-1, 2).ravel())

    ob = bpy.data.objects.new("Terrain", me)
    bpy.context.scene.collection.objects.link(ob)

    mat = bpy.data.materials.new("terrain_ground")
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.location = (-400, 200)
    img = bpy.data.images.load(color_path, check_existing=False)
    img.colorspace_settings.name = "sRGB"
    tex.image = img
    nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.9
    me.materials.append(mat)
    # 相对路径：blend 与 color_1m 不在同一个目录
    img.filepath = bpy.path.relpath(color_path, start=os.path.dirname(out_path))
    print("[map] terrain material -> %s" % img.filepath)
    return ob


def append_fragments(lod_path):
    print("[map] append fragments from %s" % lod_path)
    with bpy.data.libraries.load(lod_path, link=False) as (src, dst):
        names = [n for n in src.collections if not n.startswith("ONLY_terrain_lod")]
        dst.collections = names
    removed = 0
    for c in list(bpy.data.collections):
        if c.name.startswith("G_"):
            for o in list(c.all_objects):
                bpy.data.objects.remove(o, do_unlink=True)
                removed += 1
            bpy.data.collections.remove(c)
    root = bpy.data.collections.get("ONLY_lod_远景碎片")
    if root and root.name not in [c.name for c in bpy.context.scene.collection.children]:
        bpy.context.scene.collection.children.link(root)
    groups = [c for c in bpy.data.collections if c.name.startswith(("S_", "W_"))]
    objs = sum(len(c.all_objects) for c in groups)
    print("[map] fragments: %d groups / %d objects; removed guarma objects %d" %
          (len(groups), objs, removed))
    return groups, objs


def water_material():
    mat = bpy.data.materials.new("water")
    mat.use_nodes = True
    mat.diffuse_color = (0.05, 0.30, 0.40, 1.0)   # Workbench 预览也显蓝
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (0.02, 0.10, 0.14, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.15
    bsdf.inputs["Metallic"].default_value = 0.0
    return mat


def build_water(mask_path, res, rects, mat, split_x=-1000.0):
    """**两块矩形平面**（用户原则：只允许两个 plane，禁止自造水面）。

    尺寸/范围可调（不必铺满地图）：东块默认盖住主湖与东部河网，西块盖住西南河道；
    两个矩形之外没有水面，南方陆地因此不会出水。
    """
    def make(name, r, level):
        x0, y0, x1, y1 = r
        verts = np.array([
            [x0, y1, 0.0],
            [x0, y0, 0.0],
            [x1, y0, 0.0],
            [x1, y1, 0.0],
        ], np.float32)
        loops = np.array([0, 1, 2, 3], np.int32)   # 逆时针，法线朝上
        me = bpy.data.meshes.new(name)
        me.vertices.add(4)
        me.vertices.foreach_set("co", verts.ravel())
        me.loops.add(4)
        me.loops.foreach_set("vertex_index", loops)
        me.polygons.add(1)
        me.polygons.foreach_set("loop_start", np.array([0], np.int32))
        me.polygons.foreach_set("loop_total", np.array([4], np.int32))
        me.update(calc_edges=False)
        me.materials.append(mat)
        ob = bpy.data.objects.new(name, me)
        ob.location = (0.0, 0.0, level)
        bpy.context.scene.collection.objects.link(ob)
        print("[map] water %s: plane x[%.0f,%.0f] y[%.0f,%.0f] z=%.1f" %
              (name, x0, x1, y0, y1, level))
        return ob

    make("Water_west", (X0, Y0, split_x, Y1), ZW)
    make("Water_main", (split_x, Y0, X1, Y1), ZN)


def main():
    a = parse()
    print("[map] height=%s" % a.height)
    print("[map] color =%s" % a.color)
    print("[map] mask  =%s" % a.mask)
    print("[map] lod   =%s" % a.lod)
    z = load_height(a.height)
    H, W = z.shape
    print("[map] expected verts: %d x %d (%.2f M)" % (W + 1, H + 1, (W + 1) * (H + 1) / 1e6))
    print("[map] frame: x[%.0f,%.0f] y[%.0f,%.0f] = %.0f x %.0f m, res %.0f m" %
          (X0, X1, Y0, Y1, X1 - X0, Y1 - Y0, a.res))
    rects = west_rects()
    if a.dry_run:
        print("[map] DRY RUN OK")
        return
    if not a.out:
        raise SystemExit("缺 --out")

    bpy.ops.wm.read_factory_settings(use_empty=True)
    meta = json.load(open(a.height_meta, encoding="utf-8"))
    zmin = meta["height"]["zmin"]
    zmax = meta["height"]["zmax"]
    print("[map] z encoding: %.3f .. %.3f" % (zmin, zmax))

    build_terrain(z, a.res, zmin, zmax, a.color, a.out)
    if not a.skip_lod and os.path.exists(a.lod):
        append_fragments(a.lod)
    if not a.no_water:
        build_water(a.mask, a.water_res, rects, water_material(), a.water_split_x)

    # 统计
    n_obj = len(bpy.data.objects)
    n_coll = len([c for c in bpy.data.collections if c.name.startswith(("S_", "W_"))])
    print("[map] total objects %d, fragment groups %d" % (n_obj, n_coll))

    bpy.context.preferences.filepaths.save_version = 0
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=a.out, compress=True)
    print("[map] SAVED %s %.2f GB" % (a.out, os.path.getsize(a.out) / 1e9))


if __name__ == "__main__":
    main()
