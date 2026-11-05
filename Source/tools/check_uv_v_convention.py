# -*- coding: utf-8 -*-
"""UV V 约定自检 —— 判 RDR2 模型 UV 是不是「左上原点」（v 随高度递减）。

    python tools/check_uv_v_convention.py                # 默认扫 val 场景用到的模型
    python tools/check_uv_v_convention.py --scene sdn
    python tools/check_uv_v_convention.py --models 3a/0x3adbe18d.mdl 9b/0x9b527830.mdl
    python tools/check_uv_v_convention.py --png 3a/0x3adbe18d.mdl 10 --out _scratch/uv_ab.png

## 判据（有分辨力，别再拿"u 随 x 递增"当判据 —— 它看不见 V）

竖立面上，RDR2 的 v 必须**随世界 z 递减**（v=0 在图片顶端）。逐子网格按**三角形边投票**
（`dv/dz` 的符号，避免多块面板把整条相关拉平）：
· 80% 以上的边数朝同一方向才算这一块"有结论"；
· 全局 **'递减' 占 ≥ 80% ⇒ PASS**（基线实测 val 场景 **671/769 = 87%**，剩下 13% 是本来就
  按 v 朝上贴的玻璃/贴花/旋转贴图，属正常）；
· 真回归时比例会翻到 ≈13% ⇒ **FAIL**。

**负面测试**：`--selftest` 会把 v 就地翻一次再判，必须从 PASS 变 FAIL。

证据与结论见 `tools/rdr2_uv.py`。
"""
import argparse
import json
import os
import struct
import sys

import numpy as np

ROOT = r'D:/BrainMaker/大镖客2解包分析'
LIB = os.path.join(ROOT, 'assets/lib_native')
SCENES = os.path.join(ROOT, 'deliverable/blender/scenes')
MAGIC = b'RDR1' + b'\x00'
SUB = struct.Struct('<I I I I I I I')


def read_subs(path):
    try:
        buf = open(path, 'rb').read()
    except OSError:
        return []
    if buf[:8] != b'RMDL1' + bytes(3):
        return []
    n = struct.unpack_from('<I', buf, 8)[0]
    o = 12 + 24
    tabs = []
    for _ in range(n):
        tabs.append(SUB.unpack_from(buf, o))
        o += SUB.size
    out = []
    for (tid, vc, ic, po, no, uo, io_) in tabs:
        if vc == 0 or ic < 3:
            continue
        out.append(dict(
            tid=tid,
            pos=np.frombuffer(buf, np.float32, vc * 3, po).reshape(-1, 3),
            uv=np.frombuffer(buf, np.float32, vc * 2, uo).reshape(-1, 2),
            idx=np.frombuffer(buf, np.uint32, ic, io_).reshape(-1, 3)))
    return out


def _slope_votes(pos, uv, F):
    """逐三角形边投票：v 随 z 升高而**下降** = 正确（左上原点）。

    🔴 为什么不用整条的 Pearson 相关：一个子网格里常常有多块面板（招牌左半 + 右半），
    两块各自的 v 区间不同，合起来算相关会被拉平（实测 `val_03_saloon_ext` 的招牌整条只有
    −0.46，反而漏掉最该判的那块）。逐边投票只看"局部朝哪边走"，不受面板偏移影响。
    """
    tri, tuv = pos[F], uv[F]
    dz, dv = tri[:, :, 2], tuv[:, :, 1]
    down = up = 0
    for a, b in ((0, 1), (1, 2), (2, 0)):
        d = dz[:, a] - dz[:, b]
        m = np.abs(d) > 0.05
        if not m.any():
            continue
        s = (dv[:, a] - dv[:, b])[m] / d[m]
        down += int((s < 0).sum())
        up += int((s > 0).sum())
    return down, up


def score_model(subs, flip=False):
    """→ (负相关个数, 正相关个数, 明细)

    只统计**竖立面**（面积加权法线 |nz| < 0.35）—— 屋顶/坡道/地板虽然 z 与 v 也线性相关，
    但它们的 v 方向不代表贴图原点，会把闸门带偏（实测全景 83 个假阳性就是这么来的）。
    """
    neg = pos_ = 0
    rows = []
    for i, s in enumerate(subs):
        F = s['idx']
        if len(F) < 4:
            continue
        v0, v1, v2 = s['pos'][F[:, 0]], s['pos'][F[:, 1]], s['pos'][F[:, 2]]
        fn = np.cross(v1 - v0, v2 - v0)
        area = np.linalg.norm(fn, axis=1)
        if area.sum() <= 1e-9:
            continue
        N = (fn * area[:, None]).sum(0)
        N /= (np.linalg.norm(N) + 1e-9)
        if abs(float(N[2])) > 0.35:          # 不是竖立面
            continue
        z = s['pos'][:, 2]
        if z.max() - z.min() < 0.3:
            continue
        down, up = _slope_votes(s['pos'], s['uv'], F)
        if down + up < 6:
            continue
        if flip:
            down, up = up, down
        if down >= (down + up) * 0.8:
            neg += 1
            rows.append((i, 'down', down, up))
        elif up >= (down + up) * 0.8:
            pos_ += 1
            rows.append((i, 'up', down, up))
    return neg, pos_, rows


def models_from_scene(scene):
    p = os.path.join(SCENES, 'placement_%s.jsonl' % scene)
    if not os.path.exists(p):
        sys.exit('找不到 %s' % p)
    idx = json.load(open(os.path.join(LIB, 'index.json'), encoding='utf-8'))['models']
    seen, out = set(), []
    for line in open(p, encoding='utf-8'):
        h = json.loads(line)['model_hash']
        if h in seen:
            continue
        seen.add(h)
        e = idx.get(h)
        if e and e.get('f'):
            out.append((h, e['f']))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--scene', default='val')
    ap.add_argument('--models', nargs='*', default=[])
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--selftest', action='store_true', help='负面测试：翻一次 v，必须 FAIL')
    ap.add_argument('--png', nargs=2, metavar=('MDL', 'SUB'), default=None,
                    help='输出某个子网格的 A/B 图（原样 vs 翻 V）')
    ap.add_argument('--out', default=os.path.join(ROOT, '_scratch/uv_ab.png'))
    ap.add_argument('-v', '--verbose', action='store_true')
    a = ap.parse_args()

    if a.png:
        return render_ab(a.png[0], int(a.png[1]), a.out)

    if a.models:
        pairs = [('-', m) for m in a.models]
    else:
        pairs = models_from_scene(a.scene)
    if a.limit:
        pairs = pairs[:a.limit]

    neg = pos = skipped = 0
    per_model = []
    for h, rel in pairs:
        subs = read_subs(os.path.join(LIB, rel))
        n, p, rows = score_model(subs, flip=a.selftest)
        if n + p == 0:
            skipped += 1
            continue
        neg += n
        pos += p
        per_model.append((rel, n, p))
        if a.verbose:
            print('  %-42s 负 %2d / 正 %2d   %s' % (rel, n, p, rows[:4]))

    total = neg + pos
    print('\n模型 %d 个（无竖立面 UV 的跳过 %d）· 计入子网格 %d'
          % (len(pairs), skipped, total))
    print('  v 随高度递减（左上原点，正确）: %d' % neg)
    print('  v 随高度递增（被翻过，错误）  : %d' % pos)
    if total == 0:
        print('!! 没有可判定的子网格 —— 换 --models 指定带竖立面的模型')
        return 2
    # 阈值 80%：基线实测 671/769 = 87%（剩下 13% 是本来就按 v 朝上贴的玻璃/贴花/旋转贴图，
    # 属正常）。真正回归时这个比例会翻过来（≈13%），所以 80% 有足够分辨力又有余量。
    ok = neg >= total * 0.80
    print('\n=== %s ===' % ('PASS 源数据是左上原点（Blender 侧必须翻 V）' if ok else
                            'FAIL 源数据 V 方向不对，查管线是否有二次翻转'))
    if a.selftest:
        print('（--selftest：v 已就地翻转，期望 FAIL）')
    if per_model:
        print('明细（前 8 个）：')
        for rel, n, p in per_model[:8]:
            print('  %-42s 负 %2d / 正 %2d' % (rel, n, p))
    return 0 if ok else 1


def render_ab(model, si, out):
    """离线把某个子网格按两种 V 约定各烘一张，拼成对照图。只读。"""
    from PIL import Image, ImageDraw
    idx = json.load(open(os.path.join(LIB, 'index.json'), encoding='utf-8'))
    texmeta = idx['tex']
    subs = read_subs(os.path.join(LIB, model))
    if si >= len(subs):
        sys.exit('sub %d 越界（共 %d）' % (si, len(subs)))
    s = subs[si]
    tp = texmeta[s['tid']].get('f') if 0 <= s['tid'] < len(texmeta) else ''
    if not tp:
        sys.exit('该子网格没有贴图')
    tex = np.asarray(Image.open(os.path.join(LIB, tp)).convert('RGBA'))
    a = _raster(s, tex, False)
    b = _raster(s, tex, True)
    cv = Image.new('RGB', (max(a.shape[1], b.shape[1]), a.shape[0] + b.shape[0] + 44),
                   (252, 252, 252))
    d = ImageDraw.Draw(cv)
    d.text((6, 4), 'A  v as-is  (Blender 底层约定：错)', fill=(20, 20, 20))
    cv.paste(Image.fromarray(a), (0, 18))
    d.text((6, a.shape[0] + 24), 'B  v flipped (rdr2_uv.to_blender_uv：对)', fill=(190, 0, 0))
    cv.paste(Image.fromarray(b), (0, a.shape[0] + 38))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    cv.save(out)
    print('->', out, cv.size)
    return 0


def _raster(s, tex, flip_v, size=1300):
    """沿**面积加权法线**做正交投影（世界 +z 朝上）+ 按 V 约定采样贴图。

    🔴 别用"丢掉跨度最小的轴"来选投影面：招牌这类薄板的 y 跨度（1.87 m）可能比 z（1.52 m）
    还大，会被误判成"厚度"而丢掉竖轴，渲出来只剩一条斜线（2026-11-05 踩过）。
    """
    pos, uv, F = s['pos'], s['uv'], s['idx']
    v0, v1, v2 = pos[F[:, 0]], pos[F[:, 1]], pos[F[:, 2]]
    fn = np.cross(v1 - v0, v2 - v0)
    ar = np.linalg.norm(fn, axis=1)
    N = (fn * ar[:, None]).sum(0)
    N /= (np.linalg.norm(N) + 1e-9)
    up = np.array([0.0, 0.0, 1.0])
    if abs(float(N @ up)) > 0.95:
        up = np.array([0.0, 1.0, 0.0])
    U = np.cross(up, N); U /= (np.linalg.norm(U) + 1e-9)
    V = np.cross(N, U)
    p2 = np.stack([pos @ U, pos @ V], 1)
    sc = (size - 2) / max(float(p2[:, 0].max() - p2[:, 0].min()), 1e-6)
    qx = (p2[:, 0] - p2[:, 0].min()) * sc + 1
    qy = (p2[:, 1].max() - p2[:, 1]) * sc + 1     # 摆正：V 大 → 图像上方
    W = int(qx.max()) + 2
    H = int(qy.max()) + 2
    img = np.full((H, W, 3), 240, np.uint8)
    zb = np.full((H, W), -1e9, np.float32)
    th, tw = tex.shape[:2]
    depth = pos @ N
    for ia, ib, ic in F:
        A = (qx[ia], qy[ia]); B = (qx[ib], qy[ib]); C = (qx[ic], qy[ic])
        x0 = max(int(min(A[0], B[0], C[0])), 0); x1 = min(int(max(A[0], B[0], C[0])) + 1, W)
        y0 = max(int(min(A[1], B[1], C[1])), 0); y1 = min(int(max(A[1], B[1], C[1])) + 1, H)
        if x1 <= x0 or y1 <= y0:
            continue
        den = (B[1] - C[1]) * (A[0] - C[0]) + (C[0] - B[0]) * (A[1] - C[1])
        if abs(den) < 1e-9:
            continue
        xs, ys = np.meshgrid(np.arange(x0, x1) + 0.5, np.arange(y0, y1) + 0.5)
        l1 = ((B[1] - C[1]) * (xs - C[0]) + (C[0] - B[0]) * (ys - C[1])) / den
        l2 = ((C[1] - A[1]) * (xs - C[0]) + (A[0] - C[0]) * (ys - C[1])) / den
        l3 = 1 - l1 - l2
        m = (l1 >= -1e-4) & (l2 >= -1e-4) & (l3 >= -1e-4)
        if not m.any():
            continue
        zz = l1 * depth[ia] + l2 * depth[ib] + l3 * depth[ic]
        t = l1[..., None] * uv[ia] + l2[..., None] * uv[ib] + l3[..., None] * uv[ic]
        tx = np.clip((t[..., 0] % 1.0 * (tw - 1)).astype(np.int32), 0, tw - 1)
        vv = t[..., 1] % 1.0
        ty = np.clip((vv if flip_v else 1.0 - vv) * (th - 1), 0, th - 1).astype(np.int32)
        rgb = tex[ty, tx, :3]
        zs = zb[y0:y1, x0:x1]; ss = img[y0:y1, x0:x1]
        take = m & (zz > zs)
        zs[take] = zz[take]; ss[take] = rgb[take]
    return img


if __name__ == '__main__':
    sys.exit(main())
