import bpy, numpy as np

CX, CY = 2989.5, 2189.4
R_AREA = 90.0      # 只改这个半径内的地形
R_W = 45.0         # anchor 参与半径
POWER = 2.0

# 1) 收集锚点：roc 区域内、非高瘦（排除树）的对象底部 z
anchors = []
for o in bpy.data.objects:
    if o.type != 'MESH' or o.name == 'Terrain':
        continue
    dx, dy = o.location.x - CX, o.location.y - CY
    if dx*dx + dy*dy > R_AREA*R_AREA:
        continue
    vs = o.data.vertices
    zmin = min(v.co.z for v in vs) + o.location.z
    zmax = max(v.co.z for v in vs) + o.location.z
    h = zmax - zmin
    if h > 12.0 or h < 2.5:   # 排除树和小物件，只让建筑主体决定地面
        continue
    anchors.append((o.location.x, o.location.y, zmin, h))
print('anchors', len(anchors))
for a in sorted(anchors, key=lambda t: t[2])[:12]:
    print('   (%.1f, %.1f) 底 z=%.2f 高 %.1f' % a)

A = np.array([[a[0], a[1], a[2]] for a in anchors], dtype=np.float64)

# 2) 改地形
t = bpy.data.objects['Terrain']
me = t.data
n = len(me.vertices)
co = np.empty(n*3, dtype=np.float32)
me.vertices.foreach_get('co', co)
co = co.reshape(-1, 3)

sel = (np.abs(co[:, 0]-CX) < R_AREA) & (np.abs(co[:, 1]-CY) < R_AREA)
idx = np.where(sel)[0]
print('terrain verts in area', len(idx))

P = co[idx, :2].astype(np.float64)
out = np.empty(len(idx), dtype=np.float32)
BATCH = 4000
for s in range(0, len(idx), BATCH):
    p = P[s:s+BATCH]
    d2 = ((p[:, None, :] - A[None, :, :2])**2).sum(axis=2)      # (m,k)
    w = 1.0 / np.maximum(d2, 1.0) ** (POWER / 2.0)
    w[d2 > R_W*R_W] = 0.0
    sw = w.sum(axis=1)
    z = (w * A[None, :, 2]).sum(axis=1) / np.maximum(sw, 1e-9)
    bad = sw < 1e-9
    z[bad] = co[idx[s:s+BATCH], 2][bad]      # 无锚点区域保持原样
    # 与原始地形混合，避免远处被拉出尖峰
    z = np.where(np.abs(z - co[idx[s:s+BATCH], 2]) > 12.0, co[idx[s:s+BATCH], 2], z)
    out[s:s+BATCH] = z.astype(np.float32)

before = co[idx, 2].copy()
co[idx, 2] = out
me.vertices.foreach_set('co', co.ravel())
me.update()
delta = out - before
print('terrain z changed: min %+.2f med %+.2f max %+.2f, changed verts %d'
      % (delta.min(), np.median(delta), delta.max(), int((np.abs(delta) > 0.05).sum())))

bpy.ops.wm.save_mainfile()
print('SAVED')
