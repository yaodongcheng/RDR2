"""把 RDR2 地形瓦片的**颜色图**（`<tile>_t`，2048²）拼成一张圣丹尼斯区域地面贴图。

RDR2 地形 patch 的 shader 是 `terrain_uber_*`：4 层 albedo 混合 + 一张 **颜色图/查找图**
（`<tile>_t` = 2048² sRGB）。这张图就是美术烘好的"地面着色"（草地/泥/沙/路面/植被），
比我们自己拿高度上色真实得多。城市区域在图上是**全黑**（地形在城里被挖掉，由建筑地面模型接管）。

输出：
  export/levels/world/blender/terrain/sdn_ground.png     4096² 区域地面颜色
  export/levels/world/blender/terrain/sdn_ground.json    区域/瓦片/朝向校验信息
"""
import os
import sys
import json
import glob
import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rdr2_ytd as T
from ytd_to_png import decode_one

ROOT = r'D:/BrainMaker/大镖客2解包分析'
TER = os.path.join(ROOT, 'work/sdn/ter2')
OUT = os.path.join(ROOT, 'export/levels/world/blender/terrain')
REGION = (1536.0, -2560.0, 3584.0, 0.0)   # xmin,ymin,xmax,ymax
SIZE = 4096


def joaat(s):
    h = 0
    for c in s.lower().encode():
        h = (h + c) & 0xffffffff
        h = (h + (h << 10)) & 0xffffffff
        h ^= h >> 6
    h = (h + (h << 3)) & 0xffffffff
    h ^= h >> 11
    h = (h + (h << 15)) & 0xffffffff
    return h


def tile_bboxes():
    """patch 名 → 世界坐标，推出每个 tile 的 bbox"""
    sys.path.insert(0, os.path.join(ROOT, 'tools'))
    import ymap_entities
    names = open(os.path.join(ROOT, 'tools/rdr2rpf/bin/Release/net9.0/names.txt'),
                 encoding='latin1').read().splitlines()
    nh = {}
    for n in names:
        n = n.strip()
        if n:
            nh[joaat(n)] = n
    pos = {}
    for f in glob.glob(os.path.join(ROOT, 'export/levels/map_metadata/**/*_strm_0.ymap'),
                       recursive=True):
        try:
            _s, _z, es = ymap_entities.extract(f)
        except Exception:
            continue
        for e in es:
            n = nh.get(e[0], '')
            if '__hd_0_' in n:
                pos[n] = (e[1], e[2])
    out = {}
    for n, (x, y) in pos.items():
        t = n.split('__hd_0_')[0]
        b = out.setdefault(t, [1e9, 1e9, -1e9, -1e9])
        b[0] = min(b[0], x); b[1] = min(b[1], y)
        b[2] = max(b[2], x); b[3] = max(b[3], y)
    for k, b in out.items():
        out[k] = (b[0] - 32, b[1] - 32, b[2] + 32, b[3] + 32)
    return out


def load_color(tile):
    """→ (HxW RGB ndarray, bbox)"""
    d = os.path.join(TER, tile)
    for f in glob.glob(os.path.join(d, '*.ytd')):
        try:
            y = T.Ytd(open(f, 'rb').read())
        except Exception:
            continue
        for t in y.textures():
            nm = t['name'].lower()
            if nm == tile + '_t' or nm == tile + '_t_hd':
                blob = y.gfx[t['gfx_off']:t['gfx_off'] + max(4096, t['w'] * t['h'] * 4)]
                im, fmt = decode_one(blob, t['w'], t['h'], t['fmt'])
                if im is None:
                    continue
                return np.asarray(im.convert('RGB')), (t['w'], t['h'])
    return None, None


def city_mask(w, h, region):
    """St Denis 多边形栅格化（用于判断朝向 + 填路面）"""
    z = json.load(open(os.path.join(ROOT, 'export/levels/world/zones.json'), encoding='utf-8'))['zones']
    town = [x for x in z if x['name'] == 'StDenis'][0]
    x0, y0, x1, y1 = region
    yy, xx = np.mgrid[0:h, 0:w]
    xs = x0 + (xx + 0.5) * (x1 - x0) / w
    ys = y0 + (yy + 0.5) * (y1 - y0) / h
    m = np.zeros((h, w), dtype=bool)
    for poly in town['polygons']:
        p = np.array(poly, dtype=np.float64)
        inside = np.zeros((h, w), dtype=bool)
        n = len(p)
        for i in range(n):
            xa, ya = p[i]
            xb, yb = p[(i + 1) % n]
            cond = ((ya > ys) != (yb > ys)) & (xs < (xb - xa) * (ys - ya) / (yb - ya + 1e-12) + xa)
            inside ^= cond
        m |= inside
    return m


def main():
    os.makedirs(OUT, exist_ok=True)
    x0, y0, x1, y1 = REGION
    canvas = np.zeros((SIZE, SIZE, 3), dtype=np.uint8)
    filled = np.zeros((SIZE, SIZE), dtype=bool)
    boxes = tile_bboxes()

    # 1) 先判断颜色图朝向：用城市"全黑"区域与 St Denis 多边形比对
    test = [t for t in boxes if t.startswith('p_15') or t.startswith('p_14')]
    cmask = city_mask(SIZE // 8, SIZE // 8, REGION)

    def score(flipx, flipy):
        s = 0
        for t in test:
            img, sz = load_color(t)
            if img is None:
                continue
            im = Image.fromarray(img).resize((SIZE // 8, SIZE // 8))
            a = np.asarray(im)
            dark = a.sum(axis=2) < 60
            if flipx:
                dark = dark[:, ::-1]
            if flipy:
                dark = dark[::-1, :]
            # 黑块应落在城市里
            s += int((dark & cmask).sum()) - int((dark & ~cmask).sum())
        return s

    best = None
    for fx in (0, 1):
        for fy in (0, 1):
            sc = score(fx, fy)
            print(f'  orientation flipx={fx} flipy={fy} score={sc}')
            if best is None or sc > best[0]:
                best = (sc, fx, fy)
    # ★ UV 拟合已证实：u→+x、v→−y（v=0 是北）。启发式分数不可靠，直接固定。
    FX, FY = 0, 0
    print('朝向固定 flipx=0 flipy=0（依据 patch UV 拟合：u→+x, v→−y）')

    # 2) 逐 tile 贴进画布（先做亮度归一化，消掉瓦片接缝）
    meta = []
    loaded = {}
    for t, bb in sorted(boxes.items()):
        img, sz = load_color(t)
        if img is None:
            continue
        a = img.reshape(-1, 3).astype(np.float32)
        bright = a[a.sum(1) > 90]
        loaded[t] = (img, float(np.median(bright)) if len(bright) else 128.0)
    if loaded:
        ref = float(np.median([v[1] for v in loaded.values()]))
        print('亮度参考 %.1f（%d 个瓦片）' % (ref, len(loaded)))
    for t, bb in sorted(boxes.items()):
        if t not in loaded:
            continue
        img, med = loaded[t]
        if med > 1:
            k = float(np.clip(ref / med, 0.75, 1.33))
            img = np.clip(img.astype(np.float32) * k, 0, 255).astype(np.uint8)
        bx0, by0, bx1, by1 = bb
        if bx1 < x0 or bx0 > x1 or by1 < y0 or by0 > y1:
            continue
        # 与区域求交，裁剪图像
        ix0 = max(bx0, x0); iy0 = max(by0, y0)
        ix1 = min(bx1, x1); iy1 = min(by1, y1)
        if ix1 <= ix0 or iy1 <= iy0:
            continue
        iw, ih = img.shape[1], img.shape[0]
        fx0 = int(round((ix0 - bx0) / (bx1 - bx0) * iw)); fx1 = int(round((ix1 - bx0) / (bx1 - bx0) * iw))
        fy0 = int(round((by1 - iy1) / (by1 - by0) * ih)); fy1 = int(round((by1 - iy0) / (by1 - by0) * ih))
        img = img[max(0, fy0):min(ih, fy1), max(0, fx0):min(iw, fx1)]
        if img.size == 0:
            continue
        if FX:
            img = img[:, ::-1]
        if FY:
            img = img[::-1, :]
        # 目标像素矩形
        px0 = int(round((ix0 - x0) / (x1 - x0) * SIZE))
        px1 = int(round((ix1 - x0) / (x1 - x0) * SIZE))
        py0 = int(round((iy0 - y0) / (y1 - y0) * SIZE))
        py1 = int(round((iy1 - y0) / (y1 - y0) * SIZE))
        w = max(1, px1 - px0); h = max(1, py1 - py0)
        im = Image.fromarray(img).resize((w, h), Image.LANCZOS)
        # 画布 y 轴：py0 对应 y0（南）→ 图像行从上到下 = y 从大到小
        top = max(0, min(SIZE - h, SIZE - py1))
        px0 = max(0, min(SIZE - w, px0))
        canvas[top:top + h, px0:px0 + w] = np.asarray(im)
        filled[top:top + h, px0:px0 + w] = True
        meta.append(dict(tile=t, bbox=[bx0, by0, bx1, by1], px=[px0, top, w, h]))

    # 3) 黑区处理：
    #    a) 城市多边形内 → 铺"路面石"色（城市地面在游戏里由建筑地面模型接管，地形是挖空的）
    #    b) 其它黑区（瓦片缝隙）→ 用邻近有效像素 inpaint
    cm = city_mask(SIZE, SIZE, REGION)
    dark = canvas.sum(axis=2) < 70
    print('覆盖像素 %.1f%%，黑区 %.1f%%，其中城市内 %.1f%%' % (
        filled.mean() * 100, dark.mean() * 100, (dark & cm).mean() * 100))
    valid = (~dark) & filled
    # inpaint：反复用 3x3 邻域均值填
    rgb = canvas.astype(np.float32)
    vmask = valid.copy()
    for it in range(40):
        if vmask.all():
            break
        acc = np.zeros_like(rgb)
        cnt = np.zeros((SIZE, SIZE), dtype=np.float32)
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                acc += np.roll(np.roll(rgb, dy, 0), dx, 1) * vmask[..., None]
                cnt += np.roll(np.roll(vmask.astype(np.float32), dy, 0), dx, 1)
        fillable = (~vmask) & (cnt > 0)
        rgb[fillable] = acc[fillable] / cnt[fillable][:, None]
        vmask |= fillable
    canvas = rgb.astype(np.uint8)
    # 城市：覆盖一层路面色（保留一点噪声）
    rng = np.random.default_rng(7)
    pave = np.array([104, 99, 92], dtype=np.float32)
    noise = rng.normal(0, 7, (int(cm.sum()), 1)).astype(np.float32)
    target = cm & (canvas.sum(axis=2) < 110)
    canvas[target] = np.clip(pave[None, :] + noise[:target.sum()], 0, 255).astype(np.uint8)

    Image.fromarray(canvas).save(os.path.join(OUT, 'sdn_ground.png'))
    json.dump(dict(region=list(REGION), size=SIZE, flipx=FX, flipy=FY,
                   tiles=meta), open(os.path.join(OUT, 'sdn_ground.json'), 'w'),
              ensure_ascii=False, indent=1)
    print('->', os.path.join(OUT, 'sdn_ground.png'))


if __name__ == '__main__':
    main()
