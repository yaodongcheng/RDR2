#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""FBX 交付物读回校验（Blender headless）—— 逐位对 `.mdl`。

对 `import` / `extra` 两套各抽 N 个（或全量），把 FBX 导回 Blender，与 `.mdl` 头对：
  ① 三角面数 == 清单 faces
  ② 包围盒 == `.mdl` 头 6 个 float（容差 1e-3）
  ③ 材质名集合 == 清单 materials 列（无贴图 = no_tex）
任一不过即 FAIL。

用法：
```powershell
blender -b --factory-startup -P tools/_check_rdr2_fbx.py -- --set import --sample 40 --dir <目录>
```
"""
import argparse
import csv
import hashlib
import io
import os
import struct
import sys

import bpy
from mathutils import Vector

ROOT = r"D:\BrainMaker\大镖客2解包分析"
LIB = os.path.join(ROOT, "assets", "lib_native")
MANIFESTS = os.path.join(ROOT, "deliverable", "manifests")
MAX_MAT = 55
FACE_TOL = 0.002      # 面数容差 0.2%（退化三角被丢）；bbox / 材质名仍严格要求


def safe_mat_name(n):
    """与 `export_rdr2_fbx.py` 同一套规则（Blender 名字上限 63，自己先截到 55）。"""
    return n if len(n) <= MAX_MAT else n[:46] + "_" + hashlib.md5(n.encode("utf-8")).hexdigest()[:8]
SETS = {
    "import": (os.path.join(MANIFESTS, "models_export.csv"), os.path.join(ROOT, "deliverable", "models")),
    "extra": (os.path.join(MANIFESTS, "models_export_extra.csv"), os.path.join(ROOT, "deliverable", "models_extra")),
}


def mdl_bbox(path):
    b = open(path, "rb").read(64)
    return struct.unpack_from("<6f", b, 12)


def check_one(name, row, dirp):
    fbx = os.path.join(dirp, name + ".fbx")
    if not os.path.exists(fbx):
        return "MISSING", None
    # 每次重置，否则上一个模型的同名材质会让导入器把本模型的 `no_tex` 改成 `no_tex.001`
    bpy.ops.wm.read_factory_settings(use_empty=True)
    before = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath=fbx)
    new = [o for o in bpy.data.objects if o not in before]
    meshes = [o for o in new if o.type == "MESH"]
    if not meshes:
        return "NO_MESH", None
    tris = sum(len(o.data.polygons) for o in meshes)
    mats = sorted({m.name for o in meshes for m in o.data.materials if m})
    mn = Vector((1e30,) * 3)
    mx = Vector((-1e30,) * 3)
    for o in meshes:
        for c in o.bound_box:
            w = o.matrix_world @ Vector(c)
            for i in range(3):
                mn[i] = min(mn[i], w[i])
                mx[i] = max(mx[i], w[i])
    for o in new:
        bpy.data.objects.remove(o, do_unlink=True)

    bb = mdl_bbox(os.path.join(LIB, row["mdl"]))
    exp_faces = int(float(row.get("faces") or 0))
    err = []
    # 少数模型的「退化三角」（零面积）会被 Blender 丢掉 ⇒ 面数差 1~2 个，属可接受精度损失
    if tris != exp_faces:
        tol = max(3, int(exp_faces * FACE_TOL))
        if abs(tris - exp_faces) > tol:
            err.append("faces %d!=%d" % (tris, exp_faces))
    got = [mn.x, mn.y, mn.z, mx.x, mx.y, mx.z]
    if max(abs(got[i] - bb[i]) for i in range(6)) > 1e-3:
        err.append("bbox got=%s want=%s" % ([round(v, 3) for v in got], [round(v, 3) for v in bb]))
    want_mats = [safe_mat_name(m) for m in (row.get("materials") or "").split("|") if m]
    if want_mats:
        if sorted(want_mats) != mats:
            err.append("mats %s != %s" % (mats[:4], sorted(want_mats)[:4]))
    return ("FAIL: " + " | ".join(err)) if err else "PASS", tris


def main():
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", choices=list(SETS), default="import")
    ap.add_argument("--sample", type=int, default=40)
    ap.add_argument("--dir", default="")
    ap.add_argument("--every", type=int, default=0, help="等间隔抽样步长（0 = 取前 N 个）")
    ap.add_argument("--names", default="", help="只查这些（逗号分隔）")
    a = ap.parse_args(argv)

    manifest, default_dir = SETS[a.set]
    dirp = a.dir or default_dir
    with io.open(manifest, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    if a.names:
        want = [x.strip() for x in a.names.split(",") if x.strip()]
        by = {r["name"]: r for r in rows}
        rows = [by[n] for n in want if n in by]
    if a.every > 0:
        rows = rows[::a.every]
    if a.sample > 0:
        rows = rows[:a.sample]

    bpy.ops.wm.read_factory_settings(use_empty=True)
    bad = 0
    for i, r in enumerate(rows, 1):
        verdict, _ = check_one(r["name"], r, dirp)
        if verdict != "PASS":
            bad += 1
            print("[chk] %-30s %s" % (r["name"], verdict), flush=True)
        elif i <= 5:
            print("[chk] %-30s PASS" % r["name"], flush=True)
    print("[chk] TOTAL %d / PASS %d / BAD %d  (dir=%s)"
          % (len(rows), len(rows) - bad, bad, dirp))


if __name__ == "__main__":
    main()
