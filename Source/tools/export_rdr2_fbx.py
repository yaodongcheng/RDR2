#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""RDR2 `.mdl`(RMDL1) → **FBX**（Blender headless）—— 交付包模型格式（2026-11-08 起 = FBX）。

## 为什么是 FBX
用户 2026-11-08 裁定：**角色和模型只认 FBX**。旧的第一版是自写的 ASCII `.trf`
（单档 LOD0），改成 FBX 后：① 走编辑器标准导入路径 ② 同模型体积约为 TRF 的 1/3.7
③ 保留材质名（= albedo 贴图名），材质接线口径不变。

## 口径（与 `Scripts/export_rdr2_trf_mdl.py` 逐条一致，只换容器）
- 坐标 = `.mdl` 模型局部坐标（**米，Z 上**），不做轴变换；导出用 `--axis Z-up`
  ⇒ FBX 里的包围盒与 `.mdl` 头**逐位相同**（已用读回校验确认）。
- UV 的 V 翻成 `1 - v`。
- 一个子网格 = 一个材质槽；材质名 = albedo 贴图名（无贴图 = `no_tex`）。
- **不导贴图**：贴图在 `deliverable/textures/{alb,nm,ma}/`，按材质名另建（同 TRF 口径）。

## 用法
```powershell
# 抽样（先验 20 个）
blender -b --factory-startup -P tools/export_rdr2_fbx.py -- --set import --limit 20

# 全量（导入子集 24,716）
blender -b --factory-startup -P tools/export_rdr2_fbx.py -- --set import

# 全量（额外的 20,012）
blender -b --factory-startup -P tools/export_rdr2_fbx.py -- --set extra
```
`--set` 决定读哪张清单、写哪个目录（与 TRF 第一版同源）：

| `--set` | 清单 | 输出目录 |
|---|---|---|
| `import` | `manifests/models_export.csv` | `deliverable/models/` |
| `extra`  | `manifests/models_export_extra.csv` | `deliverable/models_extra/` |

**可续跑**：默认跳过已存在的 `.fbx`（`--overwrite` 强制重出）。
跑完把 `fbx` / `fbx_bytes` 两列写回同一张清单（新增列，不动旧列）。
"""
import os

import bpy  # noqa: E402  （Blender 内置）
import sys
import io
import csv
import struct
import json
import argparse
import hashlib

import numpy as np

ROOT = r"D:\BrainMaker\大镖客2解包分析"
LIB = os.path.join(ROOT, "assets", "lib_native")
MANIFESTS = os.path.join(ROOT, "deliverable", "manifests")
MAGIC = b"RMDL1" + bytes(3)
SUB = struct.Struct("<7I")

SETS = {
    "import": (os.path.join(MANIFESTS, "models_export.csv"),
               os.path.join(ROOT, "deliverable", "models")),
    "extra": (os.path.join(MANIFESTS, "models_export_extra.csv"),
              os.path.join(ROOT, "deliverable", "models_extra")),
}

# 🔴 Blender 的材质 datablock 名字上限 63 字节，超了会被**截断并加哈希**
#    （实测：88 字符 → `…_e69b97f`）⇒ 材质名不再等于 albedo 贴图名，编辑器就接不上贴图。
#    做法（抄 wheels.d/assets.md §28.6 的配方）：自己先截到 55，`前46字 + _ + md5[0:8]`，
#    并把「别名 → 原名」写进 manifests/material_alias.csv，接材质时按别名查。
MAX_MAT = 55
_ALIASES = {}


def safe_mat_name(n):
    if len(n) <= MAX_MAT:
        return n
    alias = n[:46] + "_" + hashlib.md5(n.encode("utf-8")).hexdigest()[:8]
    _ALIASES[alias] = n
    return alias


# --------------------------------------------------------------- .mdl 读取
def read_mdl(path, tex_names):
    """→ (V[n,3], F[m,3], uv_subs[list[n,2]], mat_names_per_sub)"""
    buf = open(path, "rb").read()
    if buf[:8] != MAGIC:
        raise ValueError("bad RMDL1: %s" % path)
    nsub = struct.unpack_from("<I", buf, 8)[0]
    subs = []
    o = 12 + 24
    for _ in range(nsub):
        subs.append(SUB.unpack_from(buf, o))
        o += SUB.size

    verts, faces, uv_subs, mat_subs = [], [], [], []
    nrms = []
    base = 0
    for (tid, vc, ic, po, no, uo, io_) in subs:
        if vc <= 0 or ic <= 0:
            continue
        pos = np.frombuffer(buf, dtype="<f4", count=vc * 3, offset=po).reshape(-1, 3)
        nrm = (np.frombuffer(buf, dtype="<f4", count=vc * 3, offset=no).reshape(-1, 3)
               if no else None)
        uv = (np.frombuffer(buf, dtype="<f4", count=vc * 2, offset=uo).reshape(-1, 2)
              if uo else np.zeros((vc, 2), dtype=np.float32))
        idx = np.frombuffer(buf, dtype="<u4", count=ic, offset=io_)
        if idx.size != ic:
            continue
        # 少数地形块（*_hd_*，不进游戏）的索引越界 —— 整块丢给 Blender 会 IndexError。
        # 做法：只保留三个角都在本子网格顶点范围内的三角形；全没了就跳过这个子网格。
        tri = idx.reshape(-1, 3)
        good = (tri < vc).all(axis=1)
        if not good.all():
            dropped = int((~good).sum())
            print("[fbx] WARN %s sub(tid=%s) 丢弃越界三角 %d/%d"
                  % (os.path.basename(path), tid, dropped, len(tri)), flush=True)
            tri = tri[good]
            if len(tri) == 0:
                continue
            idx = tri.reshape(-1)
            ic = idx.size
        mat = "no_tex"
        if tid not in (0xFFFFFFFF, None) and tid < len(tex_names):
            mat = tex_names[tid] or "no_tex"
        verts.append(pos)
        uv_subs.append(uv)
        nrms.append(nrm)
        mat_subs.append(mat)
        faces.append(idx.reshape(-1, 3) + base)
        base += vc
    if not verts:
        raise ValueError("no submesh")
    return (np.concatenate(verts), np.concatenate(faces), uv_subs, mat_subs,
            [n if n is not None else np.zeros((len(u), 3), dtype=np.float32)
             for n, u in zip(nrms, uv_subs)])


# --------------------------------------------------------------- Blender 构建
def build_mesh_object(name, V, F, uv_subs, uniq_mats, sub_mat_idx, nrm_subs=None):
    me = bpy.data.meshes.new(name)
    me.from_pydata(V.tolist(), [], F.tolist())
    me.update()

    # 法线：`.mdl` 存的是**平滑法线**（实测与面法线差最多 88°）⇒ 必须写回自定义法线，
    # 否则 Blender 按几何重算 = 全部变成平面着色，圆的东西会有棱。
    if nrm_subs:
        nrm = np.concatenate(nrm_subs).astype(np.float64)
        # 归一化 + 兜底：零长度/NaN 的法线会让 Blender 的 custom-normal 结构写坏（实测会
        # EXCEPTION_ACCESS_VIOLATION），先替换成 (0,0,1)
        ln = np.linalg.norm(nrm, axis=1)
        bad = (~np.isfinite(nrm).all(axis=1)) | (ln < 1e-8)
        if bad.any():
            nrm[bad] = (0.0, 0.0, 1.0)
            ln = np.linalg.norm(nrm, axis=1)
        nrm = nrm / ln[:, None]
        try:
            me.normals_split_custom_set_from_vertices(nrm.tolist())
        except Exception as e:
            print("[fbx] WARN custom normals %s: %r" % (name, e), flush=True)

    # UV（per-loop）
    uvl = me.uv_layers.new(name="UVMap")
    co = np.zeros((len(V), 2), dtype=np.float32)
    start = 0
    for uv in uv_subs:
        co[start:start + len(uv)] = uv
        start += len(uv)
    co[:, 1] = 1.0 - co[:, 1]
    loop_uv = np.empty((len(me.loops), 2), dtype=np.float32)
    for i, lp in enumerate(me.loops):
        loop_uv[i] = co[lp.vertex_index]
    uvl.data.foreach_set("uv", loop_uv.reshape(-1))

    for mname in uniq_mats:
        m = bpy.data.materials.get(mname)
        if m is None:
            m = bpy.data.materials.new(mname)
            m.use_nodes = True
        me.materials.append(m)

    # 逐面材质槽：按首顶点所属子网格
    slot_of_vert = np.zeros(len(V), dtype=np.int32)
    start = 0
    for si, k in enumerate(sub_mat_idx):
        slot_of_vert[start:start + len(uv_subs[si])] = k
        start += len(uv_subs[si])
    mi = np.empty(len(me.polygons), dtype=np.int32)
    for i, poly in enumerate(me.polygons):
        mi[i] = slot_of_vert[poly.vertices[0]]
    me.polygons.foreach_set("material_index", mi)
    me.update()

    ob = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(ob)
    return ob


def export_fbx(ob, path):
    bpy.ops.object.select_all(action="DESELECT")
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.export_scene.fbx(
        filepath=path,
        use_selection=True,
        object_types={"MESH"},
        axis_forward="-Y", axis_up="Z",     # Z-up（与 RDR2/.mdl 一致）
        apply_unit_scale=True,
        apply_scale_options="FBX_SCALE_NONE",
        mesh_smooth_type="OFF",            # 用法线，不写平面/边平滑（否则自定义法线被覆盖）
        use_mesh_modifiers=False,
        path_mode="AUTO",
        embed_textures=False,
        bake_space_transform=False,
    )


def main():
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", choices=list(SETS), default="import")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--out", default="")
    ap.add_argument("--overwrite", action="store_true")
    ap.add_argument("--min-faces", type=int, default=0)
    ap.add_argument("--only", default="", help="只导这些模型（逗号分隔）")
    ap.add_argument("--only-file", default="", help="只导这些模型（逗号分隔的文本文件）")
    ap.add_argument("--no-manifest", action="store_true",
                    help="不写回清单（样本/试跑用，避免把清单指向临时目录）")
    a = ap.parse_args(argv)

    manifest, default_out = SETS[a.set]
    out_dir = a.out or default_out
    os.makedirs(out_dir, exist_ok=True)

    idx = json.load(io.open(os.path.join(LIB, "index.json"), encoding="utf-8"))
    tex_names = [(t.get("n") or "") for t in idx["tex"]]

    with io.open(manifest, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    if a.min_faces > 0:
        rows = [r for r in rows if int(float(r.get("faces") or 0)) >= a.min_faces]
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

    ok = skip = fail = 0
    out_rows = []
    fails = []
    total = len(rows)
    for n, r in enumerate(rows, 1):
        name = r["name"]
        fbx = os.path.join(out_dir, name + ".fbx")
        if os.path.exists(fbx) and not a.overwrite:
            skip += 1
            out_rows.append([name, r["model_hash"], r["mdl"], name + ".fbx",
                             r["faces"], os.path.getsize(fbx)])
            continue
        ob = None
        try:
            V, F, uv_subs, mat_subs, nrm_subs = read_mdl(os.path.join(LIB, r["mdl"]), tex_names)
            uniq = []
            for m in mat_subs:
                sm = safe_mat_name(m)
                if sm not in uniq:
                    uniq.append(sm)
            sub_mat_idx = [uniq.index(safe_mat_name(m)) for m in mat_subs]
            ob = build_mesh_object(name, V, F, uv_subs, uniq, sub_mat_idx, nrm_subs)
            export_fbx(ob, fbx)
            out_rows.append([name, r["model_hash"], r["mdl"], name + ".fbx",
                             r["faces"], os.path.getsize(fbx)])
            ok += 1
        except Exception as e:
            fail += 1
            fails.append((name, repr(e)))
            print("[fbx] FAIL %s: %r" % (name, e), flush=True)
        finally:
            if ob is not None:
                me = ob.data
                bpy.data.objects.remove(ob, do_unlink=True)
                if me.users == 0:
                    bpy.data.meshes.remove(me)

        if n % 500 == 0 or n == total:
            print("[fbx] %d/%d ok=%d skip=%d fail=%d" % (n, total, ok, skip, fail), flush=True)

    # 回写清单（加列，不动旧列）
    if not a.no_manifest:
        _write_manifest(manifest, out_rows)

    if _ALIASES:
        _merge_aliases()

    print("[fbx] DONE set=%s ok=%d skip=%d fail=%d out=%s"
          % (a.set, ok, skip, fail, out_dir))
    for nm, err in fails[:20]:
        print("[fbx]   failed: %s -> %s" % (nm, err))


def _merge_aliases():
    """把「过长的材质名」的别名并进 manifests/material_alias.csv（键 = 别名）。"""
    path = os.path.join(MANIFESTS, "material_alias.csv")
    old = {}
    if os.path.exists(path):
        with io.open(path, encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                old[r["alias"]] = r.get("original", "")
    old.update(_ALIASES)
    with io.open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["alias", "original", "chars"])
        for k in sorted(old):
            w.writerow([k, old[k], len(old[k])])
    print("[fbx] aliases %d -> %s" % (len(old), path))


def _write_manifest(manifest, out_rows):
    with io.open(manifest, encoding="utf-8-sig") as f:
        all_rows = list(csv.DictReader(f))
        fields = list(all_rows[0].keys()) if all_rows else []
    got = {r[0]: r for r in out_rows}
    for r in all_rows:
        g = got.get(r["name"])
        # 只覆盖「本次真的产出到正式目录」的行（--out 指到别处时不会走到这里）
        if not g:
            continue
        r["fbx"] = g[3]
        r["fbx_bytes"] = g[5]
    for fld in ("fbx", "fbx_bytes"):
        if fld not in fields:
            fields.append(fld)
    with io.open(manifest, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(all_rows)


if __name__ == "__main__":
    main()
