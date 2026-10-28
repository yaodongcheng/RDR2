# -*- coding: utf-8 -*-
"""体检：铁路对象是否被地形埋、线上是否有断口。

用法：blender -b deliverable/blender/sdn_full2/sdn_full2.blend -P tools/audit_rail_terrain.py
"""
import bpy, numpy as np, math, collections
from mathutils import Vector

CELL = 2.0   # 地形栅格


def wbb(o):
    mn = Vector((1e18,) * 3); mx = Vector((-1e18,) * 3)
    for c in o.bound_box:
        p = o.matrix_world @ Vector(c)
        for i in range(3):
            mn[i] = min(mn[i], p[i]); mx[i] = max(mx[i], p[i])
    return mn, mx


def main():
    ter = bpy.data.objects.get('Terrain')
    n = len(ter.data.vertices)
    co = np.empty(n * 3, dtype=np.float64)
    ter.data.vertices.foreach_get('co', co)
    co = co.reshape(n, 3)
    M = np.array(ter.matrix_world)
    w = co @ M[:3, :3].T + M[:3, 3]
    x0, y0 = w[:, 0].min(), w[:, 1].min()
    nx = int((w[:, 0].max() - x0) / CELL) + 1
    ny = int((w[:, 1].max() - y0) / CELL) + 1
    H = np.full((ny, nx), -1e9, np.float32)
    ci = np.clip(((w[:, 0] - x0) / CELL).astype(np.int32), 0, nx - 1)
    ri = np.clip(((w[:, 1] - y0) / CELL).astype(np.int32), 0, ny - 1)
    # 取每格最大高度（宁可判"埋"）
    np.maximum.at(H, (ri, ci), w[:, 2].astype(np.float32))
    H[H < -1e8] = np.nan
    print('[audit] 地形栅格 %dx%d  cell=%.1fm  z[%.1f,%.1f]' % (nx, ny, CELL, np.nanmin(H), np.nanmax(H)))

    def tz(x, y):
        c = int((x - x0) / CELL); r = int((y - y0) / CELL)
        if 0 <= r < ny and 0 <= c < nx:
            v = H[r, c]
            if not np.isnan(v):
                return float(v)
        # 邻域退化
        best = np.nan
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                rr, cc = r + dr, c + dc
                if 0 <= rr < ny and 0 <= cc < nx and not np.isnan(H[rr, cc]):
                    best = H[rr, cc] if np.isnan(best) else max(best, H[rr, cc])
        return float(best)

    groups = collections.defaultdict(list)
    for o in bpy.context.scene.objects:
        if o.type != 'MESH' or 'n_1114_r_' not in o.name:
            continue
        mn, mx = wbb(o)
        c = (mn + mx) / 2
        l = o.name.lower()
        line = 'r_a' if '_r_a_' in l else ('r_b' if '_r_b_' in l else 'r_c')
        groups[line].append((o.name, c.x, c.y, mn.z, mx.z))

    print('\n[audit] 铁路对象 %d' % sum(len(v) for v in groups.values()))
    for line, rows in sorted(groups.items()):
        buried = []
        for nm, x, y, zmin, zmax in rows:
            t = tz(x, y)
            if not math.isnan(t) and t > zmin - 0.2:      # 地形高过这条件的底
                buried.append((nm, x, y, zmin, zmax, t))
        print('\n=== %s：%d 件，埋地/贴地 %d 件 ===' % (line, len(rows), len(buried)))
        for b in sorted(buried, key=lambda r: r[1])[:25]:
            print('   %-34s (%8.1f,%9.1f) 铁路 z[%6.1f,%6.1f]  地形 %6.1f  差 %+5.1f' % (
                b[0][:34], b[1], b[2], b[3], b[4], b[5], b[3] - b[5]))
        # 断口
        P = np.array([[r[1], r[2]] for r in rows])
        ctr = P - P.mean(0)
        ww, v = np.linalg.eigh(ctr.T @ ctr)
        d = v[:, np.argmax(ww)]
        t = ctr @ d
        o_ = np.argsort(t)
        tt = t[o_]
        gaps = np.diff(tt)
        big = [(float(tt[i]), float(gaps[i])) for i in range(len(gaps)) if gaps[i] > 60]
        print('  沿轴长 %.0f m，>60 m 断口 %d 处' % (tt.max() - tt.min(), len(big)))
        for a, g in big[:8]:
            print('     沿轴 %8.1f m 起空 %.1f m' % (a, g))


main()
