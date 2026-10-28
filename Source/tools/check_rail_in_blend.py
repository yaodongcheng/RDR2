# -*- coding: utf-8 -*-
"""查 blend 里 RAILCELLS / rail 集合在桥区的实际落地情况（不渲染）。"""
import bpy, os, math
import numpy as np
from mathutils import Vector

X0, X1, Y0, Y1 = 1450, 1960, -1150, -600   # 圣丹尼斯西侧跨水栈桥段


def main():
    print('[chk] 场景对象 %d' % len(bpy.context.scene.objects))
    names = [c.name for c in bpy.data.collections]
    rail_colls = [n for n in names if n.lower().startswith('railcell') or n.lower().startswith('rail|')]
    print('[chk] 铁路集合:', rail_colls[:10], '... 共', len(rail_colls))
    # 收集候选对象
    pts = []
    for o in bpy.context.scene.objects:
        if o.type != 'MESH':
            continue
        inrail = any(c.name.lower().startswith(('railcell', 'rail|')) for c in o.users_collection)
        if not inrail:
            continue
        w = o.matrix_world.translation
        if X0 <= w.x <= X1 and Y0 <= w.y <= Y1:
            pts.append((o.name, w.x, w.y, w.z))
    print('[chk] 桥区铁路对象 %d 个' % len(pts))
    if not pts:
        print('[chk] ⚠ 桥区没有任何铁路对象 —— 这就是"断掉"')
        return
    P = np.array([[p[1], p[2]] for p in pts])
    c = P - P.mean(0)
    w_, v = np.linalg.eigh(c.T @ c)
    d = v[:, np.argmax(w_)]
    t = c @ d
    o_ = np.argsort(t)
    t = t[o_]
    g = np.diff(t)
    print('[chk] 沿轴长 %.0f m  相邻间距 中位 %.1f  P90 %.1f  最大 %.1f' % (
        t.max() - t.min(), np.median(g), np.percentile(g, 90), g.max()))
    big = [(float(t[i]), float(g[i])) for i in range(len(g)) if g[i] > 40]
    print('[chk] >40 m 缺口 %d 处' % len(big))
    for a, b in big[:10]:
        print('      沿轴 %8.1f 起空 %.1f' % (a, b))
    zs = np.array([p[3] for p in pts])
    print('[chk] z 范围 %.1f ~ %.1f' % (zs.min(), zs.max()))
    print('[chk] 前 10 个对象:')
    for i in o_[:10]:
        print('    %-40s (%8.1f,%9.1f,%6.1f)' % (pts[i][0][:40], pts[i][1], pts[i][2], pts[i][3]))
    # 全场景铁路总量
    tot = sum(1 for o in bpy.context.scene.objects
              if o.type == 'MESH' and any(c.name.lower().startswith(('railcell', 'rail|')) for c in o.users_collection))
    print('[chk] 全场景铁路对象 %d' % tot)


main()
