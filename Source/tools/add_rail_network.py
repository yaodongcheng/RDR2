# -*- coding: utf-8 -*-
"""把 RDR2 的**铁路网**装回 continent.blend（道砟 / 枕木 / 钢轨 / 桥 / 隧道 / 道岔）。

## 为什么需要这个脚本

`build_entities()` 有三条剔除规则：

    TERRAIN_CELL = re.compile(r'(_r_c_\\d+|_rc_\\d+|_ground\\d*$|_terrain)')   # 当地表贴片
    cell         = 64×64 / 128×128 的 LOD 分块
    flat_wide    = (dz < 2.0 and max(dx,dy) >= 16) or max(dx,dy) > 45         # 又扁又大

RDR2 的铁路资产长这样：`jklm_7_10_rails_c/jklm_7_10_r_c_01..70.ydr`、`j_710_r_b_sle00..17`（枕木）、
`j_710_r_c_steel00..02`（钢轨）、`j_710_r_b_bri*`（桥）、`tun`（隧道）、`tres*`（栈桥）、`rrcross`（道岔）。
包围盒又扁又宽（样例 22×14×1 m）→ **flat_wide 命中，整条铁路被丢掉**。

## 实测（2026-10-27，data 层，可复现）

| 项 | 数 |
|---|---|
| tiles 里精细铁路实例 | **1,382**（不按名反查则 1,359 在库） |
| 命中 `cell` 规则 | 0 |
| **命中 `flat_wide` 规则** | **1,024** ← 唯一杀手 |
| 两条都不命中（能装进 blend） | 335（基本是 `rrcross` 道岔） |
| 不在 `models.json`（故 TERRAIN_CELL 不看名字） | 1,107 |
| 覆盖范围 | x[−5984, 3401] y[−3789, 1792] ≈ **9.4 × 5.6 km** |

> ⚠️ 铁路**不能**用来验证四元数共轭：97.6% 的铁路地块 yaw = 0（轴对齐分块，轨道烘在网格里），
> 共轭/非共轭两种写法算出来的位置几乎完全一致（相邻段夹角 22.7° vs 23.0°，无区分度）。
> 共轭的正确性证据只有栅栏 `p_fence04bx` 那条（1.65 m → 0.56 m）。

## 两种用法

```bash
# ① 重建时就带上铁路（推荐，铁路不会再被剔掉）
blender -b -P tools/blender_continent.py -- --out <blend> --lib assets/lib_native --rails

# ② 给已经建好的 blend 打补丁（幂等：先删 RAILCELLS 再重建）
blender -b deliverable/blender/continent/continent.blend -P tools/add_rail_network.py
blender -b <blend> -P tools/add_rail_network.py -- --no-lift --out <out.blend>
```

旋向默认与 `blender_continent.py` 一致（共轭）；`--no-conj-quat` 可回退（仅用于对照，正常构建不要用）。
"""
import bpy
import os
import sys
import json
import glob
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import blender_continent as BC

ROOT = BC.ROOT
NAMES = os.path.join(ROOT, 'tools/rdr2rpf/bin/Release/net9.0/names.txt')
COLL = 'RAILCELLS'


def argv():
    a = sys.argv
    return a[a.index('--') + 1:] if '--' in a else []


def joaat(s):
    h = 0
    for c in s.lower().encode():
        h = (h + c) & 0xFFFFFFFF
        h = (h + (h << 10)) & 0xFFFFFFFF
        h ^= h >> 6
    h = (h + (h << 3)) & 0xFFFFFFFF
    h ^= h >> 11
    h = (h + (h << 15)) & 0xFFFFFFFF
    return h & 0xFFFFFFFF


def railish(name):
    l = name.lower()
    if not any(k in l for k in ('rails', '_r_c_', '_r_b_sle', '_r_c_steel', 'rrcross', 'railroad')):
        return False
    return not any(k in l for k in ('_lod', '_decal', '_dec', '_det', '+hi'))


def mat_for(tid, texmeta, matcache, libdir):
    """材质：这份 blend 是中文界面保存的，节点默认名不是 'Principled BSDF'，要按类型找。
    tex_id < 0 时给中性灰（与 blender_continent 的修法一致，避免纯白块）。"""
    if tid in matcache:
        return matcache[tid]
    mat = bpy.data.materials.new('m_%d' % tid)
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = next((n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED'), None)
    if tid >= 0 and tid < len(texmeta):
        p = os.path.join(libdir, texmeta[tid]['f'])
        img = bpy.data.images.load(p, check_existing=True)
        img.colorspace_settings.name = 'sRGB'
        node = nt.nodes.new('ShaderNodeTexImage')
        node.image = img
        nt.links.new(node.outputs['Color'], bsdf.inputs['Base Color'])
        bsdf.inputs['Roughness'].default_value = 0.85
    else:
        bsdf.inputs['Base Color'].default_value = (0.34, 0.32, 0.29, 1.0)
        bsdf.inputs['Roughness'].default_value = 0.95
    matcache[tid] = mat
    return mat


def main():
    t0 = time.time()
    ar = argv()
    conj = '--no-conj-quat' not in ar
    lift = '--no-lift' not in ar
    out = ''
    if '--out' in ar:
        out = ar[ar.index('--out') + 1]
    if not out:
        out = bpy.data.filepath
    if not out:
        raise SystemExit('no --out and no loaded blend')

    names = [l.strip() for l in open(NAMES, encoding='latin1', errors='ignore') if l.strip()]
    tab = {}
    for n in names:
        tab.setdefault(joaat(n), n)
    rail_h = {h for h, n in tab.items() if railish(n)}
    print('[rail] name table %d / rail hashes %d' % (len(tab), len(rail_h)))

    libdir = os.path.join(ROOT, 'assets/lib_native')
    idx = json.load(open(os.path.join(libdir, 'index.json'), encoding='utf-8'))
    models, texmeta = idx['models'], idx['tex']

    ents, seen, dup, noent, nolib = [], set(), 0, 0, 0
    for f in sorted(glob.glob(os.path.join(BC.TILES, '*.json'))):
        for e in json.load(open(f, encoding='utf-8')):
            if e[0] not in rail_h:
                continue
            noent += 1
            hx = hex(e[0])
            if hx not in models:
                nolib += 1
                continue
            key = (e[0], round(e[1], 2), round(e[2], 2), round(e[3], 2))
            if key in seen:
                dup += 1
                continue
            seen.add(key)
            ents.append(e)
    print('[rail] 候选 %d / 去重掉 %d / 库缺 %d / 待装配 %d' % (noent, dup, nolib, len(ents)))

    old = bpy.data.collections.get(COLL)
    if old is not None:
        n_old = len(old.objects)
        for o in list(old.objects):
            bpy.data.objects.remove(o, do_unlink=True)
        bpy.data.collections.remove(old)
        print('[rail] 清掉旧集合 %d 个对象' % n_old)
    col = bpy.data.collections.new(COLL)
    bpy.context.scene.collection.children.link(col)

    BC._mat_for = mat_for
    matcache, meshcache = {}, {}
    made = 0
    xs, ys, zs = [], [], []
    for e in ents:
        hx = hex(e[0])
        try:
            me = BC.load_model_mesh(libdir, models[hx], texmeta, matcache, meshcache)
        except Exception as ex:
            print('[rail] load fail %s %s' % (hx, ex))
            continue
        if not me:
            continue
        ob = bpy.data.objects.new('r_%s_%d' % (hx[2:8], made), me)
        ob.location = (e[1], e[2], e[3])
        ob.rotation_mode = 'QUATERNION'
        # 与 blender_continent 同一约定：RDR2 的旋向与 Blender 相反 → 取共轭
        ob.rotation_quaternion = (e[7], -e[4], -e[5], -e[6]) if conj else (e[7], e[4], e[5], e[6])
        ob.scale = (e[8], e[8], e[9])
        col.objects.link(ob)
        made += 1
        xs.append(e[1]); ys.append(e[2]); zs.append(e[3])
    print('[rail] objects %d meshes %d conj=%s %.0fs' % (made, len(meshcache), conj, time.time() - t0))
    if made:
        print('[rail] extent x[%.0f,%.0f] y[%.0f,%.0f] z[%.0f,%.0f]'
              % (min(xs), max(xs), min(ys), max(ys), min(zs), max(zs)))

    if lift:
        from mathutils import Vector
        from mathutils.bvhtree import BVHTree
        ter = bpy.data.objects.get('Terrain')
        if ter is not None:
            bvh = BVHTree.FromObject(ter, bpy.context.evaluated_depsgraph_get())
            moved = 0
            for o in col.objects:
                hit = bvh.ray_cast(Vector((o.location.x, o.location.y, 2000.0)), Vector((0, 0, -1)), 4000.0)
                if hit[0] is None:
                    continue
                if o.location.z < hit[0].z - 0.2:
                    o.location.z = hit[0].z + 0.05
                    moved += 1
            print('[rail] lifted %d' % moved)
        else:
            print('[rail] 没有 Terrain 对象，跳过贴地')

    bpy.ops.wm.save_as_mainfile(filepath=out)
    print('[rail] saved %s (%.2f GB)' % (out, os.path.getsize(out) / 1e9))


if __name__ == '__main__':
    main()
