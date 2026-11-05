# -*- coding: utf-8 -*-
"""把一个 .blend 里**所有网格的 UV 层**就地翻 V，另存为新文件。

## 为什么需要它

场景 blend 里的**远景碎片**不是当场从 `.mdl` 建的，而是
`blender_continent.append_lod_groups()` 用 `bpy.data.libraries.load(..., link=False)`
从 `deliverable/blender/continent/continent_lod_split_v23.blend` 整块 append 进来的 ——
那些网格的 UV 在 2026-11-01 建库时就烘死了，**重跑场景修不到它们**。
（室内件不在此列：`scene_interiors.py` 是当场调 `load_model_mesh()`，自动吃到修复。）

本脚本就是给这类「预建资产库」补一刀：整体翻一次 V，等价于用修好的 loader 重建。

## 用法（一次性，产物写新文件名，不覆盖源）

    "C:\\Program Files\\Blender Foundation\\Blender 5.2\\blender.exe" -b ^
        "D:\\BrainMaker\\大镖客2解包分析\\deliverable\\blender\\continent\\continent_lod_split_v23.blend" ^
        --python "D:\\BrainMaker\\大镖客2解包分析\\tools\\flip_uv_in_blend.py" -- ^
        --out "D:\\BrainMaker\\大镖客2解包分析\\deliverable\\blender\\continent\\continent_lod_split_v24.blend"

## 安全阀

* **幂等**：跑过会在场景上写 `uv_v_flipped=1`，再跑一次直接报错退出（防止翻两遍）。
* **不覆盖源**：`--out` 必填，且必须与源不同。
* **自检**：翻完抽样统计 UV 的 v 均值变化，并打印前 3 个网格的名字/UV 层数。
"""
import os
import sys

import bpy
import numpy as np


def argv():
    a = sys.argv
    return a[a.index('--') + 1:] if '--' in a else []


def parse():
    args = argv()
    out = ''
    if '--out' in args:
        out = args[args.index('--out') + 1]
    if not out:
        raise SystemExit('缺 --out <新文件.blend>（本脚本禁止覆盖源文件）')
    return out


def main():
    out = parse()
    src = bpy.data.filepath
    if os.path.abspath(out) == os.path.abspath(src):
        raise SystemExit('--out 与源文件相同，拒绝执行')
    sc = bpy.context.scene
    if sc.get('uv_v_flipped'):
        raise SystemExit('这个 blend 已经翻过 V（uv_v_flipped=1），再翻会翻回去 —— 拒绝执行')

    n_mesh = n_layer = n_v = 0
    v_before = v_after = 0.0
    samples = []
    for me in bpy.data.meshes:
        if not me.uv_layers:
            continue
        n_mesh += 1
        for uvl in me.uv_layers:
            n = len(uvl.data)
            if n == 0:
                continue
            uvs = np.empty(n * 2, dtype=np.float32)
            uvl.data.foreach_get('uv', uvs)
            v_before += float(uvs[1::2].sum())
            n_v += n
            uvs[1::2] = 1.0 - uvs[1::2]      # 只翻 V，不动 U
            v_after += float(uvs[1::2].sum())
            uvl.data.foreach_set('uv', uvs)
            n_layer += 1
        if len(samples) < 3:
            samples.append((me.name, len(me.uv_layers), len(me.vertices)))

    print('[flip_uv] 网格 %d 个 / UV 层 %d 个 / 顶点合计 %d'
          % (n_mesh, n_layer, sum(m[2] for m in samples)))
    if n_v:
        print('[flip_uv] v 均值 前 %.4f → 后 %.4f（1−前 = %.4f，应相等）'
              % (v_before / n_v, v_after / n_v, 1.0 - v_before / n_v))
    for nm, nl, nv in samples:
        print('[flip_uv]   样例 %-40s 层 %d 顶点 %d' % (nm, nl, nv))
    if n_layer == 0:
        raise SystemExit('[flip_uv] 一个 UV 层都没找到 —— 文件选错了？')

    sc['uv_v_flipped'] = 1
    sc['uv_v_flipped_from'] = os.path.basename(src)
    sc['uv_v_flipped_meshes'] = n_mesh
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=out, compress=True, copy=True)
    print('[flip_uv] 已写出 %s' % out)


if __name__ == '__main__':
    main()
