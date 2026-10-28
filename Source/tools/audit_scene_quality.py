# -*- coding: utf-8 -*-
"""任意 blend 的统一质量体检 —— 用来横向对比 continent / willard / sdn_full2。

输出统一口径的指标，方便回答「夏洛蒂好在哪、continent 差在哪」：

  1. 规模：网格对象数 / 顶点数 / 内容 bbox
  2. 贴地：建筑类对象的「底 − 地形」偏差分布、贴地率(±0.5m)、MAE
  3. 材质：材质总数、带贴图的、带法线贴图的、带 ORM 的
  4. 地形：顶点数、bbox
  5. 结构：集合前缀分类计数

用法：
    blender -b <blend> -P tools/audit_scene_quality.py -- [--report out.json]
"""
import bpy, os, sys, json, math, random, collections
from mathutils import Vector

SKIP_BUILD = ('_dec', 'decal', '_em', 'slod', 'vfx', 'rail', '_r_c_', '_r_b_', '_r_a_',
              'debris', 'p_', 'junk', 'veg', 'tree', 'grass', 'rock')


def argv():
    a = sys.argv
    return a[a.index('--') + 1:] if a and '--' in a else []


def wbb(o):
    mn = Vector((1e18,) * 3); mx = Vector((-1e18,) * 3)
    for c in o.bound_box:
        p = o.matrix_world @ Vector(c)
        for i in range(3):
            mn[i] = min(mn[i], p[i]); mx[i] = max(mx[i], p[i])
    return mn, mx


def main():
    a = argv()
    rep_path = a[a.index('--report') + 1] if '--report' in a else ''
    sc = bpy.context.scene
    meshes = [o for o in sc.objects if o.type == 'MESH']
    rep = {'file': os.path.basename(bpy.data.filepath),
           'size_gb': round(os.path.getsize(bpy.data.filepath) / 1e9, 2) if os.path.exists(bpy.data.filepath) else 0,
           'mesh_objects': len(meshes)}

    # 顶点 / bbox
    nv = 0
    mn = Vector((1e18,) * 3); mx = Vector((-1e18,) * 3)
    for o in meshes:
        nv += len(o.data.vertices) if o.data else 0
        a_, b_ = wbb(o)
        for i in range(3):
            mn[i] = min(mn[i], a_[i]); mx[i] = max(mx[i], b_[i])
    rep['vertices'] = nv
    rep['content_bbox'] = [round(v, 1) for v in mn] + [round(v, 1) for v in mx]

    # 集合结构
    cc = collections.Counter()
    for o in meshes:
        for c in o.users_collection:
            cc[c.name.split('|')[0].split('.')[0]] += 1
    rep['collections'] = dict(cc.most_common(15))

    # 材质
    mats = list(bpy.data.materials)
    rep['materials'] = len(mats)
    tex = nrm = orm = 0
    for m in mats:
        if not m.use_nodes:
            continue
        for n in m.node_tree.nodes:
            if n.type != 'TEX_IMAGE' or not n.image:
                continue
            tex += 1
            nm = (n.image.name or '').lower()
            if '_nm' in nm or 'normal' in nm:
                nrm += 1
            if '_ma' in nm or 'orm' in nm or 'rough' in nm:
                orm += 1
    rep['tex_nodes'] = tex
    rep['normal_tex'] = nrm
    rep['orm_tex'] = orm

    # 贴地
    ter = bpy.data.objects.get('Terrain')
    if ter:
        rep['terrain'] = {'verts': len(ter.data.vertices),
                          'bbox': [round(v, 1) for v in wbb(ter)[0]] + [round(v, 1) for v in wbb(ter)[1]]}
        from mathutils.bvhtree import BVHTree
        bvh = BVHTree.FromObject(ter, bpy.context.evaluated_depsgraph_get())
        cands = []
        for o in meshes:
            l = o.name.lower()
            if o.name == 'Terrain' or any(k in l for k in SKIP_BUILD):
                continue
            # 室内件不参与贴地统计（家具在地板/墙里，天然低于室外地形）
            if any(c.name.upper().startswith(('INTERIOR', 'INT')) for c in o.users_collection):
                continue
            bb0, bb1 = wbb(o)
            s = max(bb1.x - bb0.x, bb1.y - bb0.y)
            if s < 4 or s > 300:
                continue
            cands.append(o)
        random.seed(7)
        if len(cands) > 400:
            cands = random.sample(cands, 400)
        devs = []
        for o in cands:
            bb0, bb1 = wbb(o)
            cx, cy = (bb0.x + bb1.x) / 2, (bb0.y + bb1.y) / 2
            hit = bvh.ray_cast(Vector((cx, cy, 2000.0)), Vector((0, 0, -1)), 4000.0)
            if hit[0] is None:
                continue
            devs.append(bb0.z - hit[0].z)
        if devs:
            import statistics
            devs_sorted = sorted(devs)
            med = devs_sorted[len(devs) // 2]
            near = sum(1 for d in devs if abs(d) <= 0.5)
            rep['ground_fit'] = {
                'sampled': len(devs),
                'median': round(med, 2),
                'mean': round(sum(devs) / len(devs), 2),
                'mae': round(sum(abs(d) for d in devs) / len(devs), 2),
                'within_0.5m_pct': round(100 * near / len(devs), 1),
                'sunk_pct': round(100 * sum(1 for d in devs if d < -0.5) / len(devs), 1),
                'floating_pct': round(100 * sum(1 for d in devs if d > 0.5) / len(devs), 1),
            }

    print('[audit] %s  %.2f GB  网格 %d  顶点 %d' % (rep['file'], rep['size_gb'], rep['mesh_objects'], rep['vertices']))
    print('[audit] 材质 %d（贴图节点 %d / 法线 %d / ORM %d）' % (rep['materials'], tex, nrm, orm))
    if 'ground_fit' in rep:
        g = rep['ground_fit']
        print('[audit] 贴地：抽样 %d  中位 %+.2f  MAE %.2f  贴地率 %.1f%%（陷 %.1f%% / 浮 %.1f%%）' % (
            g['sampled'], g['median'], g['mae'], g['within_0.5m_pct'], g['sunk_pct'], g['floating_pct']))
    if 'terrain' in rep:
        print('[audit] 地形 顶点 %d' % rep['terrain']['verts'])
    print('[audit] 集合 top:', list(rep['collections'].items())[:6])

    if rep_path:
        os.makedirs(os.path.dirname(rep_path), exist_ok=True)
        json.dump(rep, open(rep_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print('[audit] 报告 ->', rep_path)


main()
