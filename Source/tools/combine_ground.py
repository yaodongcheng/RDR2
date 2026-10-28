"""把真地形色图与合成色图合成一张可用的地面贴图。

真色图（world_ground_1p0.png）：480 个 512 m 瓦片的 `<tile>_t`，1 m/px。
  但 RDR2 的城市地形是**挖空**的（瓦片上全黑），需要回填。
合成色图（world_color_4096.png）：全图覆盖，但只有 3 m/px。

规则：真色图有效像素优先；黑色/缺失处回填合成色图；城区（据点半径内）回填中性地面色。
"""
import os, json, csv
import numpy as np
from PIL import Image

ROOT = r'D:/BrainMaker/大镖客2解包分析'
G = os.path.join(ROOT, 'export/world/world_ground_1p0.png')
C = os.path.join(ROOT, 'export/world/world_color_4096.png')
OUT = os.path.join(ROOT, 'export/world/world_ground_final.png')
META = os.path.join(ROOT, 'export/world/world_meta.json')

X0, Y0, WORLD = -7684.0, -8196.0, 12296.0
YN = Y0 + WORLD

g = Image.open(G).convert('RGB')
W = g.size[0]
gnd = np.asarray(g)
print('ground', gnd.shape)
col = np.asarray(Image.open(C).convert('RGB').resize((W, W), Image.LANCZOS))
print('color', col.shape)

bad = gnd.reshape(-1, 3).max(1) < 10
bad = bad.reshape(W, W)
print('无效像素 %.1f%%' % (100.0 * bad.mean()))

out = gnd.copy()

# 缺失区域：按 128 m 粗网格取"邻近有效格"的颜色回填，再轻微模糊掉方格边。
G = 128  # 米
gn = int(WORLD / G) + 1
gs = W / gn
valid = ~bad
grid_col = np.zeros((gn, gn, 3), np.float32)
grid_ok = np.zeros((gn, gn), bool)
for j in range(gn):
    y0 = int(j * gs); y1 = min(W, int((j + 1) * gs))
    if y1 <= y0: continue
    for i in range(gn):
        x0 = int(i * gs); x1 = min(W, int((i + 1) * gs))
        if x1 <= x0: continue
        v = valid[y0:y1, x0:x1]
        if v.mean() > 0.45:
            px = gnd[y0:y1, x0:x1][v]
            grid_col[j, i] = np.median(px, axis=0)
            grid_ok[j, i] = True

# 迭代把有效格向缺失格扩散（8 邻域平均）
for _ in range(gn):
    if grid_ok.all(): break
    new_col = grid_col.copy(); new_ok = grid_ok.copy()
    for j in range(gn):
        for i in range(gn):
            if grid_ok[j, i]: continue
            acc = np.zeros(3, np.float32); n = 0
            for dj in (-1, 0, 1):
                for di in (-1, 0, 1):
                    jj, ii = j + dj, i + di
                    if 0 <= jj < gn and 0 <= ii < gn and grid_ok[jj, ii]:
                        acc += grid_col[jj, ii]; n += 1
            if n:
                new_col[j, i] = acc / n; new_ok[j, i] = True
    grid_col, grid_ok = new_col, new_ok

# 粗网格放大成整图像素，只在缺失处使用
yy = np.clip((np.arange(W) / gs).astype(np.int32), 0, gn - 1)
fill = grid_col[np.ix_(yy, yy)]
m = bad & grid_ok[np.ix_(yy, yy)]
out[m] = np.clip(fill[m], 0, 255).astype(np.uint8)
m2 = bad & ~m
out[m2] = col[m2]
print('邻近格回填 %.1f%%，色图回填 %.1f%%' % (100.0 * m.mean(), 100.0 * m2.mean()))

# 城区（游戏里地形被挖空 → 瓦片全黑）：不要填成一块灰盘，
# 而是用**城市边缘一圈有效像素的中位色**回填，让城镇自然过渡进地形。
spots = []
p = os.path.join(ROOT, 'export/levels/world/settlements_bannerlord.csv')
for r in csv.DictReader(open(p, encoding='utf-8-sig')):
    try:
        u = float(r['u']); v = float(r['v']); w = float(r['size_w']); d = float(r['size_d'])
    except Exception:
        continue
    spots.append((-7684 + u * 14.5, 4100 - v * 14.5, max(260.0, 0.95 * max(w, d))))

ys, xs = np.mgrid[0:W, 0:W]
wx = X0 + (xs + 0.5) / W * WORLD
wy = YN - (ys + 0.5) / W * WORLD
for sx, sy, sr in spots:
    d2 = (wx - sx) ** 2 + (wy - sy) ** 2
    inner = d2 <= sr * sr
    if not inner.any():
        continue
    # 环带：0.9r ~ 1.25r 的有效像素，取中位色
    ring = (d2 > (sr * 0.9) ** 2) & (d2 < (sr * 1.25) ** 2) & (~bad)
    if ring.sum() < 50:
        continue
    med = np.median(out[ring], axis=0)
    m = inner & bad
    out[m] = med.astype(np.uint8)

print('城区按边缘色回填完成')

# 城市多边形（zones.json 的 TOWN）：多边形内被挖空的部分填"路面色 + 噪声"，
# 和 sdn.blend 的做法完全一致（pave 104,99,92）。
zones_p = os.path.join(ROOT, 'export/levels/world/zones.json')
if os.path.exists(zones_p):
    zones = json.load(open(zones_p, encoding='utf-8'))['zones']
    towns = [z for z in zones if z.get('type') == 'TOWN']
    print('TOWN 多边形 %d 个' % len(towns))
    rng = np.random.default_rng(7)
    pave = np.array([118, 124, 132], np.float32)   # 对齐 old sdn 的铺装色
    for z in towns:
        for poly in z.get('polygons', []):
            p = np.array(poly, np.float64)
            if len(p) < 3:
                continue
            xmin, ymin = p[:, 0].min(), p[:, 1].min()
            xmax, ymax = p[:, 0].max(), p[:, 1].max()
            c0 = int((xmin - X0) / WORLD * W); c1 = int((xmax - X0) / WORLD * W) + 1
            r0 = int((YN - ymax) / WORLD * W); r1 = int((YN - ymin) / WORLD * W) + 1
            c0 = max(0, c0); r0 = max(0, r0); c1 = min(W, c1); r1 = min(W, r1)
            if c1 <= c0 or r1 <= r0:
                continue
            yy, xx = np.mgrid[r0:r1, c0:c1]
            xs = X0 + (xx + 0.5) / W * WORLD
            ys = YN - (yy + 0.5) / W * WORLD
            inside = np.zeros(xs.shape, bool)
            n = len(p)
            for i in range(n):
                xa, ya = p[i]; xb, yb = p[(i + 1) % n]
                cond = ((ya > ys) != (yb > ys)) & (xs < (xb - xa) * (ys - ya) / (yb - ya + 1e-12) + xa)
                inside ^= cond
            # 和 old sdn 完全一致：只填多边形内"被挖空（黑）"的部分，
            # 其余保留真地形贴图（old 的 build_sdn_terrain_tex 也是这么做的）
            tgt = inside & bad[r0:r1, c0:c1]
            if tgt.any():
                nz = rng.normal(0, 7, (int(tgt.sum()), 1)).astype(np.float32)
                out[r0:r1, c0:c1][tgt] = np.clip(pave[None, :] + nz, 0, 255).astype(np.uint8)

Image.fromarray(out).save(OUT, optimize=True)
meta = json.load(open(META, encoding='utf-8'))
meta['ground_final'] = os.path.basename(OUT)
json.dump(meta, open(META, 'w'), ensure_ascii=False, indent=1)
print('→ %s  %.0f MB' % (OUT, os.path.getsize(OUT) / 1e6))
