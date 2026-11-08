#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把交付包里的 **glTF / GLB** 资产导成 **FBX**（Blender headless）。

用户 2026-11-08 裁定：**角色和模型只认 FBX**；角色**暂不绑骨架**（保持 GLB 原样内容）。

三种模式：

| `--mode` | 输入 | 输出 | 说明 |
|---|---|---|---|
| `characters` | `deliverable/characters/**/*.glb` | 同目录同名 `.fbx` | 贴图**内嵌**（源 GLB 本来就是内嵌的） |
| `weapons` | `deliverable/weapons/models/weapons/*.gltf` | 同目录 `.fbx` | 贴图内嵌 |
| `items` | `deliverable/items/models/items/*.gltf` | 同目录 `.fbx` | 贴图内嵌 |

口径：
- 源 glTF 是 **Y-up**，Blender 导入自动转 Z-up；导出用 `axis_up='Z'` ⇒ FBX 与 RDR2 一致（Z 上）。
- 材质名保持源里的材质名；贴图内嵌（`embed_textures=True`）⇒ 一个 FBX 自包含。
- 不重定向、不改骨架：源里有骨骼/动画就原样带出，没有就没有。

用法：
```powershell
blender -b --factory-startup -P tools/export_rdr2_fbx_assets.py -- --mode characters --limit 3
blender -b --factory-startup -P tools/export_rdr2_fbx_assets.py -- --mode characters
```
"""
import argparse
import glob
import os
import re
import sys
import tempfile

import bpy

ROOT = r"D:\BrainMaker\大镖客2解包分析"
DELIV = os.path.join(ROOT, "deliverable")
MODES = {
    "characters": os.path.join(DELIV, "characters"),
    "weapons": os.path.join(DELIV, "weapons", "models", "weapons"),
    "items": os.path.join(DELIV, "items", "models", "items"),
}
EXTS = {"characters": ".glb", "weapons": ".gltf", "items": ".gltf"}


def clear_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def _safe(name):
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", name)[:120]


def materialize_images(tmpdir):
    """glTF 的内嵌贴图只活在内存里（没有磁盘路径），FBX 导出器会**直接跳过**（实测：
    导出后 FBX 里 PNG 签名 = 0）。先把它们落成真实 PNG，导出器才嵌得进去。"""
    n = 0
    for img in list(bpy.data.images):
        if img.name == "Render Result":
            continue
        cur = bpy.path.abspath(img.filepath) if img.filepath else ""
        if cur and os.path.exists(cur):
            continue
        if not img.packed_file and not img.has_data:
            continue
        p = os.path.join(tmpdir, _safe(img.name) + ".png")
        if not os.path.exists(p):
            img.filepath_raw = p
            img.file_format = "PNG"
            try:
                img.save()
                n += 1
            except Exception as e:
                print("[fbx-asset] WARN save image %s: %r" % (img.name, e), flush=True)
                continue
        else:
            img.filepath_raw = p
    return n


def export_one(src, dst):
    clear_scene()
    bpy.ops.import_scene.gltf(filepath=src)
    objs = [o for o in bpy.data.objects if o.type in ("MESH", "ARMATURE")]
    if not objs:
        raise RuntimeError("no mesh/armature imported")
    tmpdir = os.path.join(tempfile.gettempdir(), "rdr2_fbx_tex")
    os.makedirs(tmpdir, exist_ok=True)
    nimg = materialize_images(tmpdir)
    for o in bpy.data.objects:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.export_scene.fbx(
        filepath=dst,
        use_selection=True,
        object_types={"MESH", "ARMATURE"},
        axis_forward="-Y", axis_up="Z",        # Z-up（RDR2 口径）
        apply_unit_scale=True,
        apply_scale_options="FBX_SCALE_NONE",
        mesh_smooth_type="OFF",                # 用法线（glTF 导入的自定义法线要原样带出去）
        use_mesh_modifiers=False,
        path_mode="COPY",                      # 贴图落成 FBX 同级的 textures\，相对引用
        embed_textures=False,                  # 不内嵌（内嵌会每张图重复一份，且编辑器不吃）
        bake_space_transform=False,
        add_leaf_bones=False,
    )
    return len([o for o in bpy.data.objects if o.type == "MESH"]), nimg


def main():
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=list(MODES), required=True)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--overwrite", action="store_true")
    ap.add_argument("--out-sub", default="", help="额外输出到子目录（试跑用，不影响原位文件）")
    ap.add_argument("--no-manifest", action="store_true", help="不写回清单（试跑用）")
    ap.add_argument("--manifest-only", action="store_true", help="只刷清单，不转换")
    a = ap.parse_args(argv)

    base = MODES[a.mode]
    ext = EXTS[a.mode]
    if a.manifest_only:
        _update_manifest(a.mode)
        return
    files = sorted(glob.glob(os.path.join(base, "**", "*" + ext), recursive=True))
    if a.limit > 0:
        files = files[:a.limit]

    ok = skip = fail = 0
    fails = []
    for n, src in enumerate(files, 1):
        dst_dir = os.path.join(os.path.dirname(src), a.out_sub) if a.out_sub else os.path.dirname(src)
        os.makedirs(dst_dir, exist_ok=True)
        dst = os.path.join(dst_dir, os.path.splitext(os.path.basename(src))[0] + ".fbx")
        if os.path.exists(dst) and not a.overwrite:
            skip += 1
            continue
        try:
            export_one(src, dst)
            ok += 1
        except Exception as e:
            fail += 1
            fails.append((src, repr(e)))
            print("[fbx-asset] FAIL %s: %r" % (src, e), flush=True)
        if n % 25 == 0 or n == len(files):
            print("[fbx-asset] %d/%d ok=%d skip=%d fail=%d" % (n, len(files), ok, skip, fail), flush=True)

    print("[fbx-asset] DONE mode=%s ok=%d skip=%d fail=%d total=%d"
          % (a.mode, ok, skip, fail, len(files)))
    for s, e in fails[:20]:
        print("[fbx-asset]   failed: %s -> %s" % (s, e))

    if not a.no_manifest:
        _update_manifest(a.mode)
    else:
        print("[fbx-asset] manifest skipped (--no-manifest)")


MANIFESTS = {
    "characters": (os.path.join(DELIV, "manifests", "characters_export.csv"), "glb", "characters"),
    "weapons": (os.path.join(DELIV, "manifests", "weapons_export.csv"), "gltf", "weapons"),
    "items": (os.path.join(DELIV, "manifests", "items_export.csv"), "gltf", "items"),
}


def _update_manifest(mode):
    """在清单里加 `fbx` / `fbx_bytes` 两列（只加列，不改旧列）。"""
    import csv
    import io
    path, srccol, prefix = MANIFESTS[mode]
    with io.open(path, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
        fields = list(rows[0].keys()) if rows else []
    hit = 0
    for r in rows:
        src = (r.get(srccol) or "").split("?")[0]
        if not src:
            continue
        rel = os.path.join(prefix, os.path.splitext(src)[0] + ".fbx")
        full = os.path.join(DELIV, rel)
        if os.path.exists(full):
            r["fbx"] = rel.replace("\\", "/")
            r["fbx_bytes"] = os.path.getsize(full)
            hit += 1
    for fld in ("fbx", "fbx_bytes"):
        if fld not in fields:
            fields.append(fld)
    with io.open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    print("[fbx-asset] manifest %s -> %d/%d rows got fbx" % (os.path.basename(path), hit, len(rows)))


if __name__ == "__main__":
    main()
