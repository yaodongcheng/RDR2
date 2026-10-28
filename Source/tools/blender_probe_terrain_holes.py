"""在 Blender 里用射线法精确判定 Terrain 在哪些世界坐标"没有面"。

  blender -b deliverable/blender/continent/continent.blend -P tools/blender_probe_terrain_holes.py -- [N]
输出：work/verify/terrain_hole_probe.json（每格 61.5 m）+ 控制台打印最大空洞 bbox
"""
import bpy
import sys
import json
import numpy as np
from collections import deque

argv = sys.argv
N = int(argv[argv.index('--') + 1]) if '--' in argv else 160
OUT = r'D:/BrainMaker/大镖客2解包分析/work/verify/terrain_hole_probe.json'

ob = bpy.data.objects['Terrain']
me = ob.data
print('Terrain verts', len(me.vertices), 'polys', len(me.polygons))

from mathutils.bvhtree import BVHTree
bvh = BVHTree.FromObject(ob, bpy.context.evaluated_depsgraph_get())

x0, x1 = -7680.0, 4612.0
y0, y1 = -8192.0, 4100.0
xs = np.linspace(x0, x1, N)
ys = np.linspace(y0, y1, N)
hit = np.zeros((N, N), np.uint8)
from mathutils import Vector
for j, y in enumerate(ys):
    for i, x in enumerate(xs):
        loc, nor, idx, dist = bvh.ray_cast(Vector((float(x), float(y), 5000.0)), Vector((0, 0, -1)))
        if loc is not None:
            hit[j, i] = 1
print('coverage %.2f%%  (%d/%d)' % (100.0 * hit.mean(), int(hit.sum()), hit.size))

# 连通域（4 邻域）
lab = np.zeros((N, N), np.int32)
cur = 0
comps = []
for j in range(N):
    for i in range(N):
        if hit[j, i] == 0 and lab[j, i] == 0:
            cur += 1
            q = deque([(j, i)])
            lab[j, i] = cur
            cells = []
            while q:
                a, b = q.popleft()
                cells.append((a, b))
                for da, db in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    na, nb = a + da, b + db
                    if 0 <= na < N and 0 <= nb < N and hit[na, nb] == 0 and lab[na, nb] == 0:
                        lab[na, nb] = cur
                        q.append((na, nb))
            comps.append(cells)
comps.sort(key=len, reverse=True)
dx = (x1 - x0) / (N - 1); dy = (y1 - y0) / (N - 1)
res = []
print('空洞（按面积降序，前 12）：')
for cells in comps[:12]:
    area = len(cells) * dx * dy / 1e6
    if area < 0.3:
        continue
    js = [c[0] for c in cells]; ii = [c[1] for c in cells]
    bx = [x0 + min(ii) * dx, x0 + max(ii) * dx]
    by = [y0 + min(js) * dy, y0 + max(js) * dy]
    res.append(dict(area_km2=round(area, 2), x=[round(bx[0]), round(bx[1])], y=[round(by[0]), round(by[1])]))
    print('  %.1f km2  x[%.0f,%.0f] y[%.0f,%.0f]' % (area, bx[0], bx[1], by[0], by[1]))
json.dump(dict(N=N, x=[x0, x1], y=[y0, y1], holes=res), open(OUT, 'w'), indent=1)
print('→', OUT)
