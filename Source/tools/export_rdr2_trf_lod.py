#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""RDR2 `.mdl` → **带 7 档 LOD 的 TRF**（Blender headless）。

## 为什么是 TRF（用户 2026-11-08 裁定）
FBX **带不了多档 LOD**（`<名>_lod` 当独立文件导入会被编辑器按 `<名>` 注册、撞名跳过）；
TRF 能：`<名>.<子网格序>` = LOD0，`<名>.lod<N>.<子网格序>` = 第 N 档
（依据 = `plans/rules/wheels.d/assets.md` §28.4，2026-10-26 圣丹尼斯实测）。
⇒ **交付主线 = TRF（多档）；FBX 保留作参照，等导入验证成功后再谈删除。**

## 口径（与 `Scripts/export_rdr2_trf_from_scenes.py` 的已验证配方一致）
- 减面：先 `remove_doubles(0.002)` + `normals_make_consistent(inside=False)`，再 `DECIMATE/COLLAPSE`
- 比率：`RATIOS = [1.0, 0.50, 0.30, 0.19, 0.12, 0.12, 0.12]`（LOD5/6 复用 LOD4 的 12%）
- **只给 ≥ `--lod-min-faces`（默认 2000）面的模型出多档**；小件只出 LOD0（原版也是小件不做 LOD）
- 材质：一个材质一个子网格（RDR2 数据天然如此）；材质名 = **albedo 贴图名原样**（TRF 无 63 字符限制）
- 坐标：`.mdl` 局部坐标（米，Z 上）；UV 的 V 翻成 `1-v`
  （🔴 2026-11-09 实机 A/B 定案：引擎认 `1-v`。翻 V 统一在 `read_mdl()` 做一次，
   全档一致；此前只有 `make_part()` 翻、LOD0 漏翻 → 近景采到 V 镜像的另一块图）
- 写法：复用 `tools/OpenTrf/trf_meta_mesh_exporter.py`（与引擎侧真样例对过账的同一份）

## 用法
```powershell
blender -b --factory-startup -P tools/export_rdr2_trf_lod.py -- --set import --limit 5
blender -b --factory-startup -P tools/export_rdr2_trf_lod.py -- --set import
```
可续跑：默认跳过已存在且已含 LOD 的 `.trf`（`--overwrite` 强制重出）。
"""
import argparse
import importlib.util
import io
import csv
import json
import math
import os
import struct
import sys

import numpy as np
import bpy

RDR2 = r"D:\BrainMaker\大镖客2解包分析"
LIB = os.path.join(RDR2, "assets", "lib_native")
MANIFESTS = os.path.join(RDR2, "deliverable", "manifests")
LWN = r"h:\SteamLibrary\steamapps\common\Mount & Blade II Bannerlord\Modules\LivingWorldNpcs"
EXPORTER = os.path.join(LWN, "tools", "OpenTrf", "trf_meta_mesh_exporter.py")

MAGIC = b"RMDL1" + bytes(3)
SUB = struct.Struct("<7I")
RATIOS = [1.0, 0.50, 0.30, 0.19, 0.12, 0.12, 0.12]
MIN_POLY = 8

SETS = {
    "import": (os.path.join(MANIFESTS, "models_export.csv"),
               os.path.join(RDR2, "deliverable", "models")),
    "extra": (os.path.join(MANIFESTS, "models_export_extra.csv"),
              os.path.join(RDR2, "deliverable", "models_extra")),
}

spec = importlib.util.spec_from_file_location("trfexp", EXPORTER)
trfexp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(trfexp)


# ------------------------------------------------------------------ .mdl 读取
def read_mdl(path, tex_names):
    """→ ({mat: [(pos, nrm, uv, tri)]})  按材质归并（一个材质一个子网格）"""
    buf = open(path, "rb").read()
    if buf[:8] != MAGIC:
        raise ValueError("bad RMDL1: %s" % path)
    nsub = struct.unpack_from("<I", buf, 8)[0]
    o = 12 + 24
    groups = {}
    for _ in range(nsub):
        tid, vc, ic, po, no, uo, io_ = SUB.unpack_from(buf, o)
        o += SUB.size
        if vc <= 0 or ic <= 0:
            continue
        pos = np.frombuffer(buf, dtype="<f4", count=vc * 3, offset=po).reshape(-1, 3)
        nrm = (np.frombuffer(buf, dtype="<f4", count=vc * 3, offset=no).reshape(-1, 3)
               if no else np.zeros((vc, 3), dtype=np.float32))
        uv = (np.frombuffer(buf, dtype="<f4", count=vc * 2, offset=uo).reshape(-1, 2)
              if uo else np.zeros((vc, 2), dtype=np.float32)).copy()
        # 🔴 2026-11-09 实机 A/B 定案：引擎按「左下原点」采样，TRF 里必须写 1-v
        #    （原始 .ydr 是左上原点）。这一步以前只在 make_part() 里做 ⇒ LOD0 漏翻，
        #    近景网格采样到 V 镜像的另一块图（花园十字消失）。统一在这里翻一次。
        uv[:, 1] = 1.0 - uv[:, 1]
        idx = np.frombuffer(buf, dtype="<u4", count=ic, offset=io_).reshape(-1, 3)
        good = (idx < vc).all(axis=1)
        if not good.all():
            idx = idx[good]
        if len(idx) == 0:
            continue
        mat = "no_tex"
        if tid not in (0xFFFFFFFF, None) and tid < len(tex_names):
            mat = tex_names[tid] or "no_tex"
        g = groups.setdefault(mat, {"pos": [], "nrm": [], "uv": [], "tri": [], "base": 0})
        g["pos"].append(pos)
        g["nrm"].append(nrm)
        g["uv"].append(uv)
        g["tri"].append(idx + g["base"])
        g["base"] += vc
    out = {}
    for mat, g in groups.items():
        out[mat] = (np.concatenate(g["pos"]), np.concatenate(g["nrm"]),
                    np.concatenate(g["uv"]), np.concatenate(g["tri"]))
    return out


# ------------------------------------------------------------ Blender 构 mesh
def make_part(name, mat, pos, nrm, uv, tri):
    me = bpy.data.meshes.new(name)
    me.from_pydata(pos.tolist(), [], tri.tolist())
    me.update()
    uvl = me.uv_layers.new(name="UVMap")
    co = np.array(uv, dtype=np.float32, copy=True)   # read_mdl 已统一翻 V（全档一致），这里不再翻
    loop_uv = np.empty((len(me.loops), 2), dtype=np.float32)
    for i, lp in enumerate(me.loops):
        loop_uv[i] = co[lp.vertex_index]
    uvl.data.foreach_set("uv", loop_uv.reshape(-1))
    try:
        nrm = np.array(nrm, dtype=np.float64, copy=True)
        ln = np.linalg.norm(nrm, axis=1)
        bad = (~np.isfinite(nrm).all(axis=1)) | (ln < 1e-8)
        if bad.any():
            nrm[bad] = (0.0, 0.0, 1.0)
            ln = np.linalg.norm(nrm, axis=1)
        nrm = nrm / ln[:, None]
        me.normals_split_custom_set_from_vertices(nrm.tolist())
    except Exception as e:
        print("[trf-lod] WARN normals %s: %r" % (name, e), flush=True)
    m = bpy.data.materials.get(mat) or bpy.data.materials.new(mat)
    me.materials.append(m)
    ob = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(ob)
    return ob


def cleanup(ob, dist=0.002):
    bpy.ops.object.select_all(action="DESELECT")
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.remove_doubles(threshold=dist)
    bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.object.mode_set(mode="OBJECT")


def decimate(ob, ratio):
    """减面（焊接已在 numpy 侧做完，这里只做 COLLAPSE）。"""
    if ratio >= 0.999 or len(ob.data.polygons) < MIN_POLY:
        return
    bpy.ops.object.select_all(action="DESELECT")
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    mod = ob.modifiers.new(name="lod", type="DECIMATE")
    mod.decimate_type = "COLLAPSE"
    mod.ratio = max(0.01, ratio)
    bpy.ops.object.modifier_apply(modifier=mod.name)


# --------------------------------------------------------------- 快速 TRF 写出
# ⚠️ 为什么不用 `trfexp.create_trf_mesh`：它逐顶点建 Python 对象再逐行写，
#    实测 2.2 秒/模型 ⇒ 全量 15 小时。这里直接从 Blender 数组批量拼字符串，
#    **输出格式与它逐字段一致**（rfver 4 / 每顶点一条 FVF 三行 / 末尾 end）。
COLOR_WHITE = 4294967295


def mesh_arrays(ob):
    """→ (pos[N,3], nrm[N,3], uv[N,2], tri[M,3])，全部按**顶点**取（源 .mdl 就是逐顶点）。"""
    me = ob.data
    n = len(me.vertices)
    pos = np.empty(n * 3, dtype=np.float32)
    me.vertices.foreach_get("co", pos)
    pos = pos.reshape(-1, 3)

    nl = len(me.loops)
    lv = np.empty(nl, dtype=np.int32)
    me.loops.foreach_get("vertex_index", lv)

    nn = np.empty(nl * 3, dtype=np.float32)
    try:
        me.corner_normals.foreach_get("vector", nn)
    except Exception:
        me.calc_normals_split()
        me.corner_normals.foreach_get("vector", nn)
    nn = nn.reshape(-1, 3)

    uv_l = np.zeros((nl, 2), dtype=np.float32)
    if me.uv_layers.active:
        me.uv_layers.active.data.foreach_get("uv", uv_l.reshape(-1))

    # 每顶点取它第一条 loop 的法线/UV（源数据本就是逐顶点，一致）
    _, first = np.unique(lv, return_index=True)
    nrm = np.zeros((n, 3), dtype=np.float32)
    uv = np.zeros((n, 2), dtype=np.float32)
    nrm[lv[first]] = nn[first]
    uv[lv[first]] = uv_l[first]

    me.calc_loop_triangles()
    m = len(me.loop_triangles)
    tl = np.empty(m * 3, dtype=np.int32)
    me.loop_triangles.foreach_get("loops", tl)
    tri = lv[tl.reshape(-1, 3)]
    return pos, nrm, uv, tri


def write_trf_fast(path, parts):
    """parts: [(name, material, pos, nrm, uv, tri)] → 写 .trf（格式同 OpenTrf 导出器）"""
    out = ["rfver 4", "mesh %d" % len(parts)]
    for name, mat, pos, nrm, uv, tri in parts:
        n = len(pos)
        out.append("%s 0 %s" % (name, mat))
        out.append(str(n))
        # 顶点
        out.extend(["%.6f %.6f %.6f" % (x, y, z) for x, y, z in pos.tolist()])
        out.append("0")
        out.append(str(n))
        # FVF：一顶点一条，三行（index color nx ny nz / u v / u2 v2）
        idx = range(n)
        nz = zip(nrm.tolist(), uv.tolist())
        for i, (nn_, uu_) in zip(idx, nz):
            out.append("%d %d %.6f %.6f %.6f" % (i, COLOR_WHITE, nn_[0], nn_[1], nn_[2]))
            out.append("%.6f %.6f" % (uu_[0], uu_[1]))
            out.append("0.000000 0.000000")
        out.append("0")            # morph_key_count
        out.append(str(len(tri)))
        out.extend(["%d %d %d" % (a, b, c) for a, b, c in tri.tolist()])
    out.append("end")
    with io.open(path, "w", encoding="utf-8", errors="replace", newline="\n") as f:
        f.write("\n".join(out))
        f.write("\n")


def _drop(ob):
    me = ob.data
    bpy.data.objects.remove(ob, do_unlink=True)
    try:
        if me.users == 0:
            bpy.data.meshes.remove(me)
    except Exception:
        pass


def weld_arrays(pos, nrm, uv, tri, eps=0.002):
    """numpy 焊接重合顶点（等价 `remove_doubles(0.002)`，但不会退化成 O(n²)）。

    🔴 为什么不用 `bpy.ops.mesh.remove_doubles`：实测在 `p_car_int_armdrwdressing01x`
    这种「同一位置堆了几百个重合顶点」的旧道具上会卡 **10 分钟以上**（单模型）。
    """
    if len(pos) == 0:
        return pos, nrm, uv, tri
    q = np.round(pos / eps).astype(np.int64)
    _, first, inv = np.unique(q, axis=0, return_index=True, return_inverse=True)
    out_tri = inv[tri]
    # 焊接后产生退化三角（两个角同点）就丢掉
    keep = (out_tri[:, 0] != out_tri[:, 1]) & (out_tri[:, 1] != out_tri[:, 2]) & (out_tri[:, 0] != out_tri[:, 2])
    out_tri = out_tri[keep]
    return pos[first], nrm[first], uv[first], out_tri


def make_box_stub(pos, nrm, uv, tri):
    """把一件压成一个**包围盒**（12 个三角），给"只在室内用"的模型做远档。

    依据（原版实测，`archhitecture_empire.tpac` 534 个 Metamesh）：
    原版**从不用空网格**（0 面 LOD 的数量 = 0），最远的档是缩成 2~12 面的小片；
    小物件照样给 LOD（`empire_lord_pot_a` 1152→512→224）。
    ⇒ 室内件的远档也照这个做，而不是"凭空消失"。
    """
    if len(pos) == 0:
        return pos, nrm, uv, tri
    mn = pos.min(axis=0)
    mx = pos.max(axis=0)
    c = (mn + mx) * 0.5
    e = np.maximum((mx - mn) * 0.5, 1e-3)
    corners = np.array([[sx, sy, sz] for sz in (-1, 1) for sy in (-1, 1) for sx in (-1, 1)],
                       dtype=np.float32)           # v0..v7
    v = corners * e + c
    box_tri = np.array([[0, 2, 1], [0, 3, 2],      # -Z
                        [4, 5, 6], [4, 6, 7],      # +Z
                        [0, 1, 5], [0, 5, 4],      # -Y
                        [3, 7, 6], [3, 6, 2],      # +Y
                        [0, 4, 7], [0, 7, 3],      # -X
                        [1, 2, 6], [1, 6, 5]],     # +X
                       dtype=np.int64)
    bn = v - c
    ln = np.linalg.norm(bn, axis=1)
    ln[ln < 1e-8] = 1.0
    bn = (bn / ln[:, None]).astype(np.float32)
    buv = np.zeros((8, 2), dtype=np.float32)
    return v.astype(np.float32), bn, buv, box_tri


def export_one(name, parts_def, out_path, lod_min_faces, stub_from=0):
    """parts_def: [(material, pos, nrm, uv, tri)] → 写多档（或单档）TRF。

    `stub_from > 0`（只给"只在室内用"的模型）：LOD0..stub_from-1 正常，
    之后每一档都压成 12 面小盒子（学原版，不凭空消失）。
    """
    base_faces = sum(len(t) for _, _, _, _, t in parts_def)
    big = base_faces >= lod_min_faces
    if stub_from:
        normal_ratios = RATIOS[:stub_from] if big else [1.0] * stub_from
        total_levels = stub_from + (7 - stub_from)
    else:
        normal_ratios = RATIOS if big else [1.0]
        total_levels = len(normal_ratios)

    mats = [p[0] for p in parts_def]
    parts_out = []
    lod_faces = {}
    cached = {}
    for lv in range(total_levels):
        is_stub = stub_from and lv >= stub_from
        if is_stub:
            stub = [make_box_stub(p[1], p[2], p[3], p[4]) for p in parts_def]
            stub_faces = sum(len(a[3]) for a in stub)
            prev_faces = lod_faces.get(lv - 1, 10 ** 9)
            # 小件本来就只有几面：盒子（每件 12 面）可能比它还胖 ⇒ 直接用上一档，别换成更重的
            arrays = stub if stub_faces < prev_faces else cached[lv - 1]
        elif lv > 0 and lv < len(normal_ratios) and abs(normal_ratios[lv] - normal_ratios[lv - 1]) < 1e-9:
            arrays = cached[lv - 1]
        else:
            arrays = []
            ratio = normal_ratios[lv] if lv < len(normal_ratios) else 1.0
            for i, (mat, pos, nrm, uv, tri) in enumerate(parts_def):
                if lv == 0 or ratio >= 0.999:
                    arrays.append((pos, nrm, uv, tri))
                    continue
                wpos, wnrm, wuv, wtri = weld_arrays(pos, nrm, uv, tri)
                ob = make_part("%s.%d" % (name, i), mat, wpos, wnrm, wuv, wtri)
                try:
                    decimate(ob, ratio)
                    arrays.append(mesh_arrays(ob))
                finally:
                    _drop(ob)
        cached[lv] = arrays
        lod_faces[lv] = sum(len(a[3]) for a in arrays)
        for i, (pos, nrm, uv, tri) in enumerate(arrays):
            nm = ("%s.%d" % (name, i)) if lv == 0 else ("%s.lod%d.%d" % (name, lv, i))
            parts_out.append((nm, mats[i], pos, nrm, uv, tri))
    write_trf_fast(out_path, parts_out)
    return base_faces, lod_faces


def main():
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", choices=list(SETS), default="import")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--only", default="")
    ap.add_argument("--only-file", default="")
    ap.add_argument("--out", default="")
    ap.add_argument("--overwrite", action="store_true")
    ap.add_argument("--lod-min-faces", type=int, default=2000)
    ap.add_argument("--interior-list", default="",
                    help="只在室内用的模型名清单（逗号分隔的文本文件）；这些模型的 LOD 从 --stub-from 起压成小盒子")
    ap.add_argument("--stub-from", type=int, default=0,
                    help="第几档开始压成 12 面盒子（0 = 不做；配合 --interior-list 用，默认 3）")
    ap.add_argument("--no-manifest", action="store_true")
    a = ap.parse_args(argv)

    manifest, default_out = SETS[a.set]
    out_dir = a.out or default_out
    os.makedirs(out_dir, exist_ok=True)

    idx = json.load(io.open(os.path.join(LIB, "index.json"), encoding="utf-8"))
    tex_names = [(t.get("n") or "") for t in idx["tex"]]

    with io.open(manifest, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    if a.only or a.only_file:
        want = [x.strip() for x in a.only.split(",") if x.strip()]
        if a.only_file:
            raw = io.open(a.only_file, encoding="utf-8").read()
            want += [x.strip() for x in raw.replace("\n", ",").split(",") if x.strip()]
        by = {r["name"]: r for r in rows}
        rows = [by[n] for n in want if n in by]
    if a.limit > 0:
        rows = rows[:a.limit]

    bpy.ops.wm.read_factory_settings(use_empty=True)

    interior_names = set()
    if a.interior_list:
        raw = io.open(a.interior_list, encoding="utf-8").read()
        interior_names = {x.strip() for x in raw.replace("\n", ",").split(",") if x.strip()}
        print("[trf-lod] 室内专用模型 %d 个，LOD%d 起压成小盒子"
              % (len(interior_names), a.stub_from or 3))

    ok = skip = fail = 0
    out_rows, fails = [], []
    total = len(rows)
    for n, r in enumerate(rows, 1):
        name = r["name"]
        out_path = os.path.join(out_dir, name + ".trf")
        if os.path.exists(out_path) and not a.overwrite:
            skip += 1
            # 🔴 2026-11-10：跳过时**保留清单里已有的 LOD 字段**。
            # 原来这里写空串，续跑一次就把 lod_faces / lod_levels 冲成空（实测踩过）。
            out_rows.append([name, name + ".trf", r.get("trf_faces") or r.get("faces", ""),
                             r.get("lod_faces", ""), r.get("lod_levels", ""),
                             os.path.getsize(out_path)])
            continue
        try:
            parts = read_mdl(os.path.join(LIB, r["mdl"]), tex_names)
            if not parts:
                raise ValueError("no submesh")
            parts_def = [(m, v[0], v[1], v[2], v[3]) for m, v in parts.items()]
            stub = (a.stub_from or 3) if name in interior_names else 0
            base, lods = export_one(name, parts_def, out_path, a.lod_min_faces, stub)
            out_rows.append([name, name + ".trf", base,
                             "/".join(str(lods[k]) for k in sorted(lods)),
                             len(lods), os.path.getsize(out_path)])
            ok += 1
        except Exception as e:
            fail += 1
            fails.append((name, repr(e)))
            print("[trf-lod] FAIL %s: %r" % (name, e), flush=True)
        if n % 200 == 0 or n == total:
            print("[trf-lod] %d/%d ok=%d skip=%d fail=%d" % (n, total, ok, skip, fail), flush=True)

    if not a.no_manifest:
        _write_manifest(manifest, out_rows)

    print("[trf-lod] DONE set=%s ok=%d skip=%d fail=%d out=%s" % (a.set, ok, skip, fail, out_dir))
    for nm, err in fails[:20]:
        print("[trf-lod]   failed: %s -> %s" % (nm, err))


def _write_manifest(manifest, out_rows):
    with io.open(manifest, encoding="utf-8-sig") as f:
        all_rows = list(csv.DictReader(f))
        fields = list(all_rows[0].keys()) if all_rows else []
    got = {r[0]: r for r in out_rows}
    for r in all_rows:
        g = got.get(r["name"])
        if not g:
            continue
        r["trf"] = g[1]
        r["trf_faces"] = g[2]
        r["lod_faces"] = g[3]
        r["lod_levels"] = g[4]
        r["trf_lod_bytes"] = g[5]
        r["bytes"] = g[5]          # 文件本体大小也一起刷新（否则重出 LOD 后这列是旧值）
    for fld in ("trf", "trf_faces", "lod_faces", "lod_levels", "trf_lod_bytes"):
        if fld not in fields:
            fields.append(fld)
    with io.open(manifest, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(all_rows)


if __name__ == "__main__":
    main()
