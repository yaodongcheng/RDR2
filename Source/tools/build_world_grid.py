"""把 RDR2 世界切成骑砍2 场景块，并生成**三套坐标的换算元数据**。
块边长可配置：848（骑砍2 默认场景尺寸）/ 2000（野外大块）。

三套坐标（一次定死，别再混）：
  ① 大地图 campaign：848 × 848 单位，左上角 = 世界西北外扩角，v 轴向下
  ② 世界 world：米，x 东 / y 北，范围 [-7684, 4612] × [-8196, 4100]
  ③ 场景 scene：块边长 T，原点在**块中心**
        three.js： sx = xw - cx,  sz = -(yw - cy)
        Bannerlord：bx = xw - cx,  by = yw - cy,  bz = 高程

网格是**居中**的：地块总覆盖 N×T，多出来的边距平均分到四周，
这样世界边界永远落在最外圈块的内部（不会成为某块的硬边）。

产物：
  export/world/tiles_848.json    15×15 = 225 块（精细，适合城池/密集区）
  export/world/tiles_2000.json   7×7  = 49 块（野外大块，默认）
用法：
  uv run python tools/build_world_grid.py                # 两档都生成
  uv run python tools/build_world_grid.py --size 2000
"""
import os
import json
import math
import numpy as np

ROOT = r'D:/BrainMaker/大镖客2解包分析'
H4 = os.path.join(ROOT, 'work/terrain/H4.npy')
OUT = os.path.join(ROOT, 'export/world')

X0, Y0, RES = -7684.0, -8196.0, 4.0
WORLD = 12296.0
XM1, YM1 = X0 + WORLD, Y0 + WORLD
MAP = 848.0
SCALE = WORLD / MAP                 # 14.5000 m / campaign unit

# 每档的 LOD 环参数（核心半边长必须是 coreStep 的整数倍，
# 且要能被外圈 step 整除，否则接缝会露缝）
PROFILES = {
    848: dict(core=416, core_step=8, r1=1536, r1_step=32, r2=6144, r2_step=128),
    2000: dict(core=1000, core_step=10, r1=2000, r1_step=40, r2=7000, r2_step=200),
}


def sample(H, x, y):
    fx = np.clip((x - X0) / RES, 0, H.shape[1] - 1.001)
    fy = np.clip((y - Y0) / RES, 0, H.shape[0] - 1.001)
    x0 = fx.astype(int); y0 = fy.astype(int)
    tx = fx - x0; ty = fy - y0
    return (H[y0, x0] * (1 - tx) * (1 - ty) + H[y0, x0 + 1] * tx * (1 - ty)
            + H[y0 + 1, x0] * (1 - tx) * ty + H[y0 + 1, x0 + 1] * tx * ty)


ANCHOR_CATS = ('大城市', '城镇', '庄园', '要塞监狱')


def load_towns():
    p = os.path.join(ROOT, 'export/levels/world/settlements.json')
    return json.load(open(p, encoding='utf-8'))['settlements']


def optimize_phase(size, towns, step=40):
    """选一个网格相位，让「没被锚定的据点」尽量靠近格中心。

    为什么要做：城镇坐标是游戏给的，均匀网格不可能让所有镇都居中；
    一次全局平移只能减小总体偏差。真正居中靠 anchors（见下）。
    """
    def cost(dx, dy):
        n = int(math.ceil(WORLD / size))
        pad = (n * size - WORLD) / 2
        gx0 = X0 - pad + dx
        gy1 = YM1 + pad + dy
        tot = 0.0
        for s in towns:
            if s.get('category') in ANCHOR_CATS:
                continue
            fx = (s['cx'] - gx0) / size
            fy = (gy1 - s['cy']) / size
            cx = (round(fx - 0.5) + 0.5) * size + gx0
            cy = gy1 - (round(fy - 0.5) + 0.5) * size
            d = math.hypot(s['cx'] - cx, s['cy'] - cy)
            w = 4.0 if s.get('category') in ('村庄',) else 2.0 if s.get('category') in ('藏身处',) else 1.0
            tot += w * d
        return tot

    best = None
    for dx in range(0, size, step):
        for dy in range(0, size, step):
            c = cost(dx, dy)
            if best is None or c < best[0]:
                best = (c, dx, dy)
    c0, bx, by = best
    for dx in range(bx - step, bx + step + 1, 10):
        for dy in range(by - step, by + step + 1, 10):
            c = cost(dx, dy)
            if c < best[0]:
                best = (c, dx, dy)
    return best[1], best[2]


def build(size):
    H = np.load(H4).astype(np.float32)
    towns = load_towns()
    n = int(math.ceil(WORLD / size))
    total = n * size
    pad = (total - WORLD) / 2
    dx, dy = optimize_phase(size, towns)
    gx0 = X0 - pad + dx            # 网格西边界（带相位）
    gy1 = YM1 + pad + dy           # 网格北边界
    prof = PROFILES.get(size, PROFILES[2000] if size >= 1500 else PROFILES[848])
    # 核心半边长不能超过半个块
    core_half = min(prof['core'], size / 2)
    tiles = []
    for j in range(n):
        for i in range(n):
            x0 = gx0 + i * size
            x1 = x0 + size
            y1 = gy1 - j * size
            y0 = y1 - size
            cx, cy = x0 + size / 2, y0 + size / 2
            xs = np.linspace(x0, x1, 33); ys = np.linspace(y0, y1, 33)
            XX, YY = np.meshgrid(xs, ys)
            Z = sample(H, XX, YY)
            gx, gy = np.gradient(Z, size / 32, size / 32)
            sl = np.sqrt(gx * gx + gy * gy)
            k = 4
            sl_l = sl[k:-k, k:-k]
            # 落点 = 中心附近 + 尽量平（代价 = 归一化距离 + 坡度），避免落到块边缘
            cc = np.array([sl_l.shape[0] / 2, sl_l.shape[1] / 2])
            yy, xx = np.mgrid[0:sl_l.shape[0], 0:sl_l.shape[1]]
            dist = np.sqrt((yy - cc[0]) ** 2 + (xx - cc[1]) ** 2) / max(1e-6, cc[0])
            cost = dist + np.clip(sl_l, 0, 1) * 2.2
            oy, ox = np.unravel_index(int(np.argmin(cost)), cost.shape)
            oy += k; ox += k
            covered = (max(x0, X0) < min(x1, XM1)) and (max(y0, Y0) < min(y1, YM1))
            tiles.append(dict(
                id='wild%d_%02d_%02d' % (size, i, j), i=i, j=j,
                world=[round(x0, 1), round(y0, 1), round(x1, 1), round(y1, 1)],
                center=[round(cx, 1), round(cy, 1)],
                z=[round(float(Z.min()), 2), round(float(Z.max()), 2), round(float(Z.mean()), 2)],
                relief=round(float(Z.max() - Z.min()), 2),
                spawn=[round(float(xs[ox]), 1), round(float(ys[oy]), 1), round(float(Z[oy, ox]), 2)],
                in_world=bool(covered),
                neighbors=dict(
                    n=('wild%d_%02d_%02d' % (size, i, j - 1)) if j > 0 else None,
                    s=('wild%d_%02d_%02d' % (size, i, j + 1)) if j < n - 1 else None,
                    w=('wild%d_%02d_%02d' % (size, i - 1, j)) if i > 0 else None,
                    e=('wild%d_%02d_%02d' % (size, i + 1, j)) if i < n - 1 else None,
                ),
            ))

    # 据点锚定场景：重要城镇各自有一个**以自己为中心**的场景框，
    # 不参与均匀网格切分（否则就会出现"圣丹尼斯正好压在四块交界"）
    anchors = []
    for s in towns:
        if s.get('category') not in ANCHOR_CATS:
            continue
        sz = float(s.get('scene_m') or 1000)
        anchors.append(dict(
            id='site_%s' % s['code'], code=s['code'], name=s['name_en'], zh=s['name_zh'],
            category=s.get('category'), size_m=sz,
            center=[round(s['cx'], 1), round(s['cy'], 1)],
            bbox=[round(s['cx'] - sz / 2, 1), round(s['cy'] - sz / 2, 1),
                  round(s['cx'] + sz / 2, 1), round(s['cy'] + sz / 2, 1)],
            u=s.get('u'), v=s.get('v'),
        ))

    meta = dict(
        version=3, profile=size, anchors=anchors, grid_phase=[dx, dy],
        world_m=WORLD, world_origin=[X0, Y0], world_max=[XM1, YM1],
        scene_size_m=size, grid=[n, n], count=len(tiles),
        grid_origin=[round(gx0, 2), round(gy1, 2)], grid_pad=round(pad, 2),
        campaign=dict(map_units=MAP, m_per_unit=round(SCALE, 4),
                      origin_world=[X0, YM1],
                      desc='x = -7684 + u*14.5 ; y = 4100 - v*14.5'),
        scene=dict(
            desc='scene 原点在块中心；three.js 的 z 为世界 -y（南）',
            threejs='sx = xw - cx ; sz = -(yw - cy)',
            bannerlord='bx = xw - cx ; by = yw - cy ; bz = 高程(m)',
        ),
        apron=dict(core_half=core_half, core_step=prof['core_step'],
                   ring1_m=prof['r1'], ring1_step=prof['r1_step'],
                   ring2_m=prof['r2'], ring2_step=prof['r2_step'],
                   desc='核心 + 两级外圈，全部同源 H4；边界取 step 整数倍保证无接缝'),
        tiles=tiles,
    )
    p = os.path.join(OUT, 'tiles_%d.json' % size)
    json.dump(meta, open(p, 'w'), ensure_ascii=False, indent=1)
    print('%4d m × %d×%d = %3d 块  覆盖 %d m（外扩 %.0f m，相位 %d,%d）  锚定场景 %d 个  -> %s'
          % (size, n, n, len(tiles), total, pad, dx, dy, len(anchors), os.path.basename(p)))
    return meta


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--size', type=int, default=0, help='0 = 两档都生成')
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    for s in ([a.size] if a.size else [2000, 848]):
        m = build(s)
        print('     relief min/median/max = %.0f / %.0f / %.0f m' % (
            min(t['relief'] for t in m['tiles']),
            sorted(t['relief'] for t in m['tiles'])[len(m['tiles']) // 2],
            max(t['relief'] for t in m['tiles'])))


if __name__ == '__main__':
    main()
