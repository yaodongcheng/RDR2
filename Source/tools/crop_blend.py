# -*- coding: utf-8 -*-
"""从全集 blend 裁剪出区域子集 —— 「分块即裁剪」的唯一合法入口。

见 docs/最高原则_单一管线与分块即裁剪.md：
    任何区域（圣丹尼斯 / 夏洛蒂的家 / …）都只能由 continent.blend 裁剪得到，
    不允许为某个区域另写装配管线，否则两边必然不等价。

## 用法

    blender -b deliverable/blender/continent/continent.blend -P tools/crop_blend.py -- \
        --bbox 1300,-1910,3160,-510 \
        --out deliverable/blender/crop/sdn_from_continent.blend \
        [--keep-touch] [--report work/verify/crop_sdn.json]

## 规则

1. 对象全保留条件：**包围盒与 bbox 相交**（跨边界的大件如桥、铁路不断成两截）；
   加 `--center-only` 则改用「包围盒中心落在范围内」。
2. `Terrain` 整块保留（它本身就是全集的一部分；切地形网格会让裁剪结果与全集不可比）。
3. 输出报告：对象总数、各分类计数（按集合名前缀）、bbox、地形顶点数/包围盒，用于等价性回归。
"""
import bpy, os, sys, json, collections
from mathutils import Vector


def argv():
    a = sys.argv
    return a[a.index('--') + 1:] if '--' in a else []


def parse():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--bbox', required=True, help='x0,y0,x1,y1')
    ap.add_argument('--out', required=True)
    ap.add_argument('--report', default='')
    ap.add_argument('--center-only', action='store_true')
    return ap.parse_args(argv())


def wbb(o):
    mn = Vector((1e18,) * 3); mx = Vector((-1e18,) * 3)
    for c in o.bound_box:
        p = o.matrix_world @ Vector(c)
        for i in range(3):
            mn[i] = min(mn[i], p[i]); mx[i] = max(mx[i], p[i])
    return mn, mx


def main():
    a = parse()
    x0, y0, x1, y1 = [float(v) for v in a.bbox.split(',')]
    print('[crop] 范围 x[%.0f,%.0f] y[%.0f,%.0f]' % (x0, x1, y0, y1))

    keep, drop = [], []
    for o in list(bpy.context.scene.objects):
        if o.name == 'Terrain' or o.type != 'MESH':
            keep.append(o)
            continue
        mn, mx = wbb(o)
        if a.center_only:
            cx, cy = (mn.x + mx.x) / 2, (mn.y + mx.y) / 2
            inside = x0 <= cx <= x1 and y0 <= cy <= y1
        else:
            inside = not (mx.x < x0 or mn.x > x1 or mx.y < y0 or mn.y > y1)
        (keep if inside else drop).append(o)

    print('[crop] 保留 %d，删除 %d（地形无条件保留）' % (len(keep), len(drop)))
    if drop:
        bpy.ops.object.select_all(action='DESELECT')
        for o in drop:
            o.select_set(True)
        bpy.ops.object.delete()
        bpy.context.view_layer.update()

    # 报告
    rep = {'bbox': [x0, y0, x1, y1], 'kept': len(keep), 'dropped': len(drop),
           'by_collection': {}, 'by_prefix': {}}
    mn = Vector((1e18,) * 3); mx = Vector((-1e18,) * 3)
    for o in bpy.context.scene.objects:
        if o.type != 'MESH':
            continue
        a_, b_ = wbb(o)
        for i in range(3):
            mn[i] = min(mn[i], a_[i]); mx[i] = max(mx[i], b_[i])
        pfx = o.name.split('|')[0] if '|' in o.name else o.name.split('_')[0]
        rep['by_prefix'][pfx] = rep['by_prefix'].get(pfx, 0) + 1
        for c in o.users_collection:
            rep['by_collection'][c.name.split('|')[0]] = rep['by_collection'].get(c.name.split('|')[0], 0) + 1
    rep['content_bbox'] = [round(v, 1) for v in mn] + [round(v, 1) for v in mx]
    ter = bpy.data.objects.get('Terrain')
    if ter:
        tv = len(ter.data.vertices)
        rep['terrain'] = {'verts': tv}
    print('[crop] 内容 bbox', rep['content_bbox'])
    print('[crop] 网格总数', sum(rep['by_collection'].values()))
    for k, v in sorted(rep['by_collection'].items(), key=lambda kv: -kv[1])[:12]:
        print('    %-12s %d' % (k, v))

    if a.report:
        os.makedirs(os.path.dirname(a.report), exist_ok=True)
        json.dump(rep, open(a.report, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print('[crop] 报告 ->', a.report)

    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=a.out)
    print('[crop] saved', a.out, '%.2f GB' % (os.path.getsize(a.out) / 1e9))


main()
