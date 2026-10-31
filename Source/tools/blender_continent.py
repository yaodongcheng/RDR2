"""把整块大陆按「全量无损」装进 Blender。

地形：直接用 H4.npy（4 m/px 原始高程，3074²）建一整块网格，不做降采样；
   顶点色取 world_color_4096.png（3 m/px）。
建筑：从导出的无损模型库 glTF 里取网格，按实体表实例化（共享 mesh，不复制几何）。

用法：
 blender -b -P tools/blender_continent.py -- --out .../continent.blend --terrain-only
 blender -b -P tools/blender_continent.py -- --out .../continent.blend --lib .../lib.gltf
"""
import bpy
import os
import sys
import json
import math
import argparse
import struct
import numpy as np

ROOT = r'D:/BrainMaker/大镖客2解包分析'
# Blender 用 -P 跑脚本时不一定把 tools/ 放进 sys.path；材质模块（mat_rdr2）要能 import。
if os.path.join(ROOT, 'tools') not in sys.path:
    sys.path.insert(0, os.path.join(ROOT, 'tools'))
H4 = os.environ.get('RDR2_H4', os.path.join(ROOT, 'work/terrain/H4.npy'))
COLOR = os.path.join(ROOT, 'export/world/world_color_4096.png')
META = os.path.join(ROOT, 'export/world/world_meta.json')
GROUND_TEX = os.environ.get('RDR2_GROUND', os.path.join(ROOT, 'export/world/world_ground_final.png'))
GROUND_MASK = os.environ.get('RDR2_MASK', os.path.join(ROOT, 'export/world/world_ground_mask.png'))
TILES = os.path.join(ROOT, 'export/world/continent/tiles')
X0, Y0, RES = -7684.0, -8196.0, 4.0
BUILD_STATS = {}   # build_entities 的统计（遍历/缺模型/落地），给末尾一行校验用
USE_PAD = False    # 城区地台压平：只有显式 --pad 才开（地形与 ground_z 共用这个开关）
VEG_MODE = 'hide'  # 植被处理：hide 隐藏 / delete 真删 / keep 原样


def argv():
  a = sys.argv
  return a[a.index('--') + 1:] if '--' in a else []


def parse():
  ap = argparse.ArgumentParser()
  ap.add_argument('--out', required=True)
  ap.add_argument('--lib', default='')
  ap.add_argument('--terrain-only', action='store_true')
  ap.add_argument('--max-entities', type=int, default=0)
  ap.add_argument('--step', type=float, default=0)   # 0 = 原始 4 m
  ap.add_argument('--only-tile', default='')
  # 按世界坐标范围裁剪（TODO #7）。坐标系 = RDR2 原生 X 东 / Y 北 / Z 上，单位米。
  # ⚠️ 区域产物原则上应由全集 crop_blend.py 裁出来（最高原则 §二.2）；--bbox 是
  # 「小范围试验」用的快速子集，不替代裁剪管线。
  # 写法：`--bbox 2950 2150 3030 2230` 或 `--bbox 2950,2150,3030,2230`（必须是**一个**参数）。
  # 注意别在 cmd 里传逗号版本后又加空格 —— cmd 会把逗号当分隔符（已知坑）。
  ap.add_argument('--bbox', nargs='+', default=[],
                  help='只装这个矩形内的实体：x0 y0 x1 y1（米，RDR2 世界坐标）')
  ap.add_argument('--shots', default='')
  ap.add_argument('--res', default='1920x1080')
  # 2026-10-29：pad 改成**默认关**（最高原则 6.2）：城区压平会在公园顶穿 1.4~1.9 m、
  # 整片地形下压 1.12 m，属于「擅自改地形」。要压平必须显式写 --pad。
  ap.add_argument('--pad', action='store_true',
                  help='城区地台压平（默认关；地形只用原生 H4）')
  ap.add_argument('--no-pad', action='store_true',
                  help='兼容旧命令：等价于不开 --pad（现在本来就默认关）')
  ap.add_argument('--no-conj-quat', action='store_true')  # 默认取共轭（RDR2 四元数旋向与 Blender 相反）
  # 铁路：名字带 _r_c_ 且包围盒扁宽，会同时命中 TERRAIN_CELL / flat_wide 两条剔除规则。
  # 不开这个开关，全图铁路会被静默丢掉（2026-10-27 修正）。
  ap.add_argument('--rails', action='store_true', help='铁路豁免两条剔除规则（道砟/枕木/钢轨/桥/道岔）')
  ap.add_argument('--full', action='store_true',
                  help='完整构建链：几何 → classify_entities(12 类) → strip_vegetation(植被处理) '
                       '→ hide_terrain_patches(地形 patch 隐藏) → write_manifest(对象清单) → 校验。'
                       '**这是唯一正确的重建入口**；不加会让 N 面板和植被清理丢失（2026-10-28 教训）')
  ap.add_argument('--veg', default='hide', choices=['hide', 'delete', 'keep'],
                  help='植被处理方式：hide（默认，移入 HIDDEN_VEG 隐藏不删，最高原则 6.1）/ '
                       'delete（真删，省 1~2 GB 内存）/ keep（原样显示）')
  return ap.parse_args(argv())


_RAIL_H = None


def rail_hashes():
  """names.txt → joaat → 铁路类哈希集合（与 tools/add_rail_network.py 的 railish 同规则）。"""
  global _RAIL_H
  if _RAIL_H is not None:
    return _RAIL_H
  names = os.path.join(ROOT, 'tools/rdr2rpf/bin/Release/net9.0/names.txt')
  keys = ('rails', '_r_c_', '_r_b_sle', '_r_c_steel', 'rrcross', 'railroad')
  skip = ('_lod', '_decal', '_dec', '_det', '+hi')
  out = set()
  if os.path.exists(names):
    with open(names, encoding='latin1', errors='ignore') as f:
      for line in f:
        n = line.strip()
        if not n or n.startswith('#'):
          continue
        l = n.lower()
        if any(k in l for k in keys) and not any(k in l for k in skip):
          h = 0
          for c in l.encode():
            h = (h + c) & 0xFFFFFFFF
            h = (h + (h << 10)) & 0xFFFFFFFF
            h ^= h >> 6
          h = (h + (h << 3)) & 0xFFFFFFFF
          h ^= h >> 11
          h = (h + (h << 15)) & 0xFFFFFFFF
          out.add(h & 0xFFFFFFFF)
  print('rail hashes', len(out))
  _RAIL_H = out
  return out


def clear():
  bpy.ops.wm.read_factory_settings(use_empty=True)


def pad_field():
  """城区地台：按 100 m 网格取建筑基座中位标高，城区内把地形压平到该标高，边缘过渡。"""
  libp = os.path.join(ROOT, 'export/world/lib_native/index.json')
  try:
    models = json.load(open(libp, encoding='utf-8'))['models']
  except Exception as e:
    print('PAD skipped (lib index busy):', e)
    return None
  PAD = 100.0
  W = 12296.0
  N = int(W / PAD) + 1
  # 只在据点范围内定地台：否则植被/岩石也会被当成"建筑"，把半张图压平
  import csv
  spots = []
  csvp = os.path.join(ROOT, 'export/levels/world/settlements_bannerlord.csv')
  if os.path.exists(csvp):
    for r in csv.DictReader(open(csvp, encoding='utf-8-sig')):
      try:
        u = float(r['u']); v = float(r['v'])
        w = float(r['size_w']); d = float(r['size_d'])
      except Exception:
        continue
      sx = -7684.0 + u * 14.5
      sy = 4100.0 - v * 14.5
      spots.append((sx, sy, max(240.0, 0.85 * max(w, d))))  # size_w/d 单位是米
  print('settlements', len(spots))

  def near_spot(x, y):
    for sx, sy, sr in spots:
      if (x - sx) ** 2 + (y - sy) ** 2 <= sr * sr:
        return True
    return False

  # --- 扩展覆盖：所有"建筑密集网格"也参与地台对齐 ---
  # 原来只覆盖 46 个据点，导致野外建筑埋进地形 6.5 m。
  # 这里统计 100 m 网格里 ≥2 个非植被建筑，就把该格子纳入。
  import re as _re
  try:
    _NAMES = {}
    def _jh(t):
      h = 0
      for ch in t.lower().encode():
        h = (h + ch) & 0xffffffff; h = (h + (h << 10)) & 0xffffffff; h ^= h >> 6
      h = (h + (h << 3)) & 0xffffffff; h ^= h >> 11
      return (h + (h << 15)) & 0xffffffff
    for _ln in open(os.path.join(ROOT, 'tools/rdr2rpf/bin/Release/net9.0/names.txt'), encoding='latin1'):
      _ln = _ln.strip()
      if _ln:
        _NAMES[_jh(_ln)] = _ln
  except Exception:
    _NAMES = {}
  _VEG = _re.compile(r'tree|bush|shrub|grass|fern|rock|stone|cliff|log_|stump|reed|weed|foliage|canopy|_veg', _re.I)
  _joaat_cache = {}
  def _nm_of(h):
    if h in _joaat_cache:
      return _joaat_cache[h]
    v = ''
    try:
      if not _NAMES:
        pass
      v = _NAMES.get(h, '')
    except Exception:
      v = ''
    _joaat_cache[h] = v
    return v
  bcell = {}
  for _fn in os.listdir(TILES):
    if not _fn.endswith('.json'):
      continue
    try:
      _ents = json.load(open(os.path.join(TILES, _fn), encoding='utf-8'))
    except Exception:
      continue
    for _e in _ents:
      if _e[10] < 2:
        continue
      if hex(_e[0]) not in models:
        continue
      if _VEG.search(_nm_of(_e[0])):
        continue
      _i = int((_e[1] - (-7684.0)) / PAD)
      _j = int((_e[2] - (-8196.0)) / PAD)
      bcell[(_i, _j)] = bcell.get((_i, _j), 0) + 1
  dense = {k for k, v in bcell.items() if v >= 2}
  print('dense building cells', len(dense), 'of', len(bcell))

  def in_dense(x, y):
    return (int((x + 7684.0) / PAD), int((y + 8196.0) / PAD)) in dense

  cells = {}
  for fn in os.listdir(TILES):
    if not fn.endswith('.json'):
      continue
    for e in json.load(open(os.path.join(TILES, fn), encoding='utf-8')):
      if spots and not near_spot(e[1], e[2]):
        continue
      m = models.get(hex(e[0]))
      if not m:
        continue
      b = m['b']
      dx, dy, dz = b[3] - b[0], b[4] - b[1], b[5] - b[2]
      is_ground = (dz < 2.0 and max(dx, dy) >= 16)   # 路面/场地模型：真正决定街面高度
      if not is_ground and max(dx, dy, dz) < 6:
        continue           # 小道具不参与定地台
      i = int((e[1] - X0) / PAD); j = int((e[2] - Y0) / PAD)
      if 0 <= i < N and 0 <= j < N:
        cells.setdefault((i, j), []).append(e[3])
  level = np.full((N, N), np.nan, np.float32)
  for (i, j), zs in cells.items():
    if len(zs) >= 3:
      level[j, i] = float(np.median(zs))
  # 多遍盒式模糊（忽略 NaN）→ 把 100 m 网格的台阶抹成缓坡
  def blur(a, k):
    tot = np.zeros_like(a); cnt = np.zeros_like(a)
    r = k // 2
    for dj in range(-r, r + 1):
      for di in range(-r, r + 1):
        sl = np.roll(np.roll(a, dj, axis=0), di, axis=1)
        v = ~np.isnan(sl)
        tot += np.where(v, sl, 0.0); cnt += v
    return np.where(cnt > 0, tot / np.maximum(cnt, 1), np.nan)

  # 只做"高程修正量"，不压平：瓦伦丁这种坡地城镇必须保留坡度，否则低处房子被埋
  H = np.load(H4)
  delta = np.full((N, N), np.nan, np.float32)
  for (i, j), zs in cells.items():
    if len(zs) < 3:
      continue
    gx = X0 + (i + 0.5) * PAD; gy = Y0 + (j + 0.5) * PAD
    r = int(round((gy - Y0) / RES)); c = int(round((gx - X0) / RES))
    gv = float(H[r, c]) if (0 <= r < H.shape[0] and 0 <= c < H.shape[1]) else 0.0
    delta[j, i] = max(-12.0, min(12.0, float(np.median(zs)) - gv))

  # 城里压平：old sdn 的城市地面是一块平板，而 H4 在城里仍起伏 → 房子高低错落。
  # 对 zones.json 的 TOWN 多边形，delta 取该多边形内的中位值。
  zp = os.path.join(ROOT, 'export/levels/world/zones.json')
  if os.path.exists(zp):
    zones = json.load(open(zp, encoding='utf-8')).get('zones', [])
    tcount = 0
    for z in [q for q in zones if q.get('type') == 'TOWN']:
      polys = z.get('polygons', [])
      if not polys:
        continue
      xs = [p[0] for poly in polys for p in poly]; ys = [p[1] for poly in polys for p in poly]
      i0 = max(0, int((min(xs) - X0) / PAD)); i1 = min(N - 1, int((max(xs) - X0) / PAD))
      j0 = max(0, int((min(ys) - Y0) / PAD)); j1 = min(N - 1, int((max(ys) - Y0) / PAD))
      if i1 <= i0 or j1 <= j0:
        continue
      ii, jj = np.meshgrid(np.arange(i0, i1 + 1), np.arange(j0, j1 + 1))
      cx = X0 + (ii + 0.5) * PAD; cy = Y0 + (jj + 0.5) * PAD
      inside = np.zeros(ii.shape, bool)
      for poly in polys:
        pr = np.array(poly, np.float64); n = len(pr); mm = np.zeros(ii.shape, bool)
        for k in range(n):
          xa, ya = pr[k]; xb, yb = pr[(k + 1) % n]
          mm ^= ((ya > cy) != (yb > cy)) & (cx < (xb - xa) * (cy - ya) / (yb - ya + 1e-12) + xa)
        inside |= mm
      if not inside.any():
        continue
      vals = delta[jj[inside], ii[inside]]
      vals = vals[~np.isnan(vals)]
      if vals.size == 0:
        continue
      delta[jj[inside], ii[inside]] = float(np.median(vals))
      tcount += 1
    print('TOWN flattened %d polygons' % tcount)

  def blur(a, k):
    tot = np.zeros_like(a); cnt = np.zeros_like(a)
    r = k // 2
    for dj in range(-r, r + 1):
      for di in range(-r, r + 1):
        sl = np.roll(np.roll(a, dj, axis=0), di, axis=1)
        v = ~np.isnan(sl)
        tot += np.where(v, sl, 0.0); cnt += v
    return np.where(cnt > 0, tot / np.maximum(cnt, 1), np.nan)

  D = delta.copy()
  for _ in range(3):
    D = blur(D, 5)
  lvl = np.where(np.isnan(D), 0.0, D).astype(np.float32)   # 这里是"修正量"
  w = (~np.isnan(D)).astype(np.float32)
  print('PAD cells %d' % int((w > 0).sum()))
  return lvl, w, N, PAD


_PAD = None
_H4C = None
_SPOTS = None


def spots():
  global _SPOTS
  if _SPOTS is not None:
    return _SPOTS
  import csv
  out = []
  csvp = os.path.join(ROOT, 'export/levels/world/settlements_bannerlord.csv')
  if os.path.exists(csvp):
    for r in csv.DictReader(open(csvp, encoding='utf-8-sig')):
      try:
        u = float(r['u']); v = float(r['v'])
        w = float(r['size_w']); d = float(r['size_d'])
      except Exception:
        continue
      out.append((-7684.0 + u * 14.5, 4100.0 - v * 14.5, max(260.0, 0.95 * max(w, d))))
  _SPOTS = out
  return out


def in_town(x, y):
  for sx, sy, sr in spots():
    if (x - sx) ** 2 + (y - sy) ** 2 <= sr * sr:
      return True
  return False


def _pad():
  global _PAD
  if not USE_PAD:
    return None     # --pad 没开：不做地台，ground_z 就是原生 H4，别偷偷混进压平值
  if _PAD is None:
    _PAD = pad_field()
  return _PAD


def ground_z(x, y):
  """实体落点的高程：H4 与城区地台按权重混合（与地形网格同一套公式）。"""
  global _H4C
  if _H4C is None:
    _H4C = np.load(H4)
  H = _H4C
  r = int(round((y - Y0) / RES)); c = int(round((x - X0) / RES))
  z = float(H[r, c]) if (0 <= r < H.shape[0] and 0 <= c < H.shape[1]) else 0.0
  pf = _pad()
  if pf is None:
    return z
  lvl, wt, PN, PADM = pf
  fi = min(max((x - X0) / PADM - 0.5, 0.0), PN - 1.001)
  fj = min(max((y - Y0) / PADM - 0.5, 0.0), PN - 1.001)
  i0 = int(fi); j0 = int(fj)
  tx, ty = fi - i0, fj - j0
  i1 = min(i0 + 1, PN - 1); j1 = min(j0 + 1, PN - 1)
  L = (lvl[j0, i0] * (1 - tx) * (1 - ty) + lvl[j0, i1] * tx * (1 - ty)
     + lvl[j1, i0] * (1 - tx) * ty + lvl[j1, i1] * tx * ty)
  return z + L


def terrain(step, use_pad=False):
  H = np.load(H4)
  ny, nx = H.shape
  print('H4', H.shape, 'res', RES, 'step', step)
  print('PAD %s' % ('ON（显式 --pad）' if use_pad else 'OFF（地形只用原生 H4，未压平）'))
  s = max(1, int(round(step / RES))) if step else 1   # 采样步长（格）
  rows = np.arange(0, ny, s)
  cols = np.arange(0, nx, s)
  X, Y = np.meshgrid(X0 + cols * RES, Y0 + rows * RES, indexing='xy')
  Z = H[np.ix_(rows, cols)].astype(np.float32)
  pf = pad_field() if use_pad else None
  if pf is not None:
    dl, wt, PN, PADM = pf
    fi = np.clip(((X - X0) / PADM - 0.5), 0, PN - 1.001)
    fj = np.clip(((Y - Y0) / PADM - 0.5), 0, PN - 1.001)
    i0 = np.floor(fi).astype(np.int32); j0 = np.floor(fj).astype(np.int32)
    i1 = np.minimum(i0 + 1, PN - 1); j1 = np.minimum(j0 + 1, PN - 1)
    tx = (fi - i0).astype(np.float32); ty = (fj - j0).astype(np.float32)
    L = (dl[j0, i0] * (1 - tx) * (1 - ty) + dl[j0, i1] * tx * (1 - ty)
       + dl[j1, i0] * (1 - tx) * ty + dl[j1, i1] * tx * ty)
    Wt = (wt[j0, i0] * (1 - tx) * (1 - ty) + wt[j0, i1] * tx * (1 - ty)
        + wt[j1, i0] * (1 - tx) * ty + wt[j1, i1] * tx * ty)
    # 城内把地形压低 1.2 m：RDR2 的街面模型普遍比原始地形低，不压会被地形盖住
    # （sdn.blend 也是同样做法，那边压 0.35 m）
    Z = Z + L - 1.2 * Wt
    print('PAD delta applied, mean %.2f m, max %.2f m' % (float(L.mean()), float(np.abs(L).max())))
  n = len(rows) * len(cols)
  print('terrain verts', n)

  co = np.stack([X.ravel(), Y.ravel(), Z.ravel()], axis=1).astype(np.float32)

  # 面（四边）：只保留有效区域，图幅外的无效高程会形成"阶梯墙"
  nyv, nxv = len(rows), len(cols)
  idx = np.arange(nyv * nxv, dtype=np.int32).reshape(nyv, nxv)
  a = idx[:-1, :-1].ravel()
  b = idx[:-1, 1:].ravel()
  c = idx[1:, :-1].ravel()
  d = idx[1:, 1:].ravel()
  quads = np.stack([a, b, d, c], axis=1).astype(np.int32)
  # 图幅外没有地表数据（地图矩形 ≠ 实际地图）→ 不建面，避免出现白色阶梯墙
  gm_p = GROUND_MASK
  if os.path.exists(gm_p):
    from PIL import Image as _PIL
    gm = np.asarray(_PIL.open(gm_p).convert('L'))
    H0, W0 = len(rows), len(cols)
    # PNG 行 0 = 北；rows 索引 0 = 南（Y0 最小）→ 必须翻转，否则空洞会南北镜像
    gi = np.clip(((ny - 1 - rows) / max(1, (ny - 1)) * (gm.shape[0] - 1)).astype(np.int32), 0, gm.shape[0] - 1)
    gj = np.clip((cols / max(1, (nx - 1)) * (gm.shape[1] - 1)).astype(np.int32), 0, gm.shape[1] - 1)
    ok = gm[np.ix_(gi, gj)] > 10
    qok = ok[:-1, :-1] | ok[:-1, 1:] | ok[1:, :-1] | ok[1:, 1:]
    quads = quads[qok.ravel()]
    print('ground-mask quads %d / %d' % (len(quads), int(qok.size)))

  me = bpy.data.meshes.new('Terrain')
  me.vertices.add(n)
  me.vertices.foreach_set('co', co.ravel())
  me.loops.add(quads.size)
  me.loops.foreach_set('vertex_index', quads.ravel())
  me.polygons.add(len(quads))
  me.polygons.foreach_set('loop_start', np.arange(0, quads.size, 4, dtype=np.int32))
  me.update(calc_edges=True)
  me.validate()

  # 顶点色：按世界坐标采样 4096² 颜色图
  from PIL import Image
  img = Image.open(COLOR).convert('RGB')
  cw, ch = img.size
  arr = np.asarray(img, dtype=np.float32) / 255.0
  meta = json.load(open(META))
  W = meta['world_m']
  px = ((X - X0) / W * (cw - 1)).astype(np.int32)
  py = ((Y0 + W - Y) / W * (ch - 1)).astype(np.int32)
  np.clip(px, 0, cw - 1, out=px)
  np.clip(py, 0, ch - 1, out=py)
  rgb = arr[py.ravel(), px.ravel()]
  # 城镇内：RDR2 的城市地形是挖空的（色图全黑），实际地面由路面/场地模型接管。
  # 我们的底色是合成色图（浅绿），露缝很扎眼 → 城区压成中性地面色，和路面接得上。
  tm = np.zeros(X.shape, bool)
  for sx, sy, sr in spots():
    tm |= ((X - sx) ** 2 + (Y - sy) ** 2) <= sr * sr
  tm = tm.ravel()
  if tm.any():
    rgb[tm] = rgb[tm] * 0.22 + np.array([0.31, 0.29, 0.25], np.float32) * 0.78
    print('town tint verts %d (%.1f%%)' % (int(tm.sum()), 100.0 * tm.mean()))
  rgba = np.concatenate([rgb, np.ones((len(rgb), 1), np.float32)], axis=1)
  col = me.color_attributes.new('Col', 'FLOAT_COLOR', 'POINT')
  col.data.foreach_set('color', rgba.ravel())

  # 整图 UV：世界西南角 = (0,0)，东北角 = (1,1)
  # UV 是 per-loop（每个面 4 个角），不是 per-vertex
  uvl = me.uv_layers.new(name='UVMap')
  _U = ((X.ravel() - X0) / W).astype(np.float32)
  # PNG 行 0 = 北；Blender 的 v=0 在图底(南) → V 用 (y-Y0)/W
  _V = ((Y.ravel() - Y0) / W).astype(np.float32)
  _loop = quads.ravel()
  uvl.data.foreach_set('uv', np.stack([_U[_loop], _V[_loop]], axis=1).ravel())

  ob = bpy.data.objects.new('Terrain', me)
  bpy.context.collection.objects.link(ob)

  mat = bpy.data.materials.new('terrain_ground')
  mat.use_nodes = True
  nt = mat.node_tree
  bsdf = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED')
  gp = GROUND_TEX
  if os.path.exists(gp):
    img = bpy.data.images.load(gp, check_existing=True)
    img.colorspace_settings.name = 'sRGB'
    node = nt.nodes.new('ShaderNodeTexImage')
    node.image = img
    node.extension = 'EXTEND'
    nt.links.new(node.outputs['Color'], bsdf.inputs['Base Color'])
    print('TERRAIN ground tex', os.path.basename(gp), img.size[:])
  else:
    attr = nt.nodes.new('ShaderNodeVertexColor')
    attr.layer_name = 'Col'
    nt.links.new(attr.outputs['Color'], bsdf.inputs['Base Color'])
    print('TERRAIN vertex color fallback')
  bsdf.inputs['Roughness'].default_value = 0.92
  me.materials.append(mat)
  print('TERRAIN OK', ob.name)
  return ob


MAGIC = b'RMDL1' + bytes(3)
SUB = struct.Struct('<I I I I I I I')


def _tex_name(texmeta, tid):
  """贴图 id → 贴图名字（库里存了名字；tid 越界/负数 → ''）"""
  if 0 <= tid < len(texmeta):
    return (texmeta[tid].get('n') or '').strip()
  return ''


def _mat_slug(name, limit=58):
  import re as _re
  s = _re.sub(r'[^0-9A-Za-z_.-]+', '_', name or '').strip('_')
  return s[:limit] or 'noname'


def _bsdf(mat):
  """取 Principled BSDF —— **按节点类型找，不按名字**。
  中文界面下这个节点叫「原理化 BSDF」，按名字查会 KeyError（2026-10-29 实测）。"""
  nt = mat.node_tree
  for n in nt.nodes:
    if n.type == 'BSDF_PRINCIPLED':
      return n
  return nt.nodes.new('ShaderNodeBsdfPrincipled')


def _mat_for(ab_tid, nm_tid, ma_tid, texmeta, matcache, libdir):
  """一个槽位一张材质：漫反射 + 法线 + 材质(高光→ORM)。

  2026-10-30：法线/高光补全。三张图的节点图统一在 `tools/mat_rdr2.py`，
  与 `relink_materials.py` 共用同一份，避免"重建"和"重挂"出两种材质。
  没有 nm/ma 的槽位行为与以前完全一致（`nonalbedo_warmgray` / `alb_<名字>`）。
  """
  import mat_rdr2
  return mat_rdr2.get_or_make(ab_tid, nm_tid, ma_tid, texmeta, libdir, matcache)


def load_model_mesh(libdir, entry, texmeta, matcache, cache):
  """把一个 .mdl 建成 Blender mesh（顶点/索引一次 foreach_set 灌进去）。"""
  key = entry['f']
  if key in cache:
    return cache[key]
  buf = open(os.path.join(libdir, entry['f']), 'rb').read()
  if buf[:8] != MAGIC:
    cache[key] = None
    return None
  nsub = struct.unpack_from('<I', buf, 8)[0]
  head = 12 + 24 + nsub * SUB.size
  subs = []
  o = 12 + 24
  for _ in range(nsub):
    subs.append(SUB.unpack_from(buf, o))
    o += SUB.size

  verts_all = []
  nrm_all = []
  uv_all = []
  faces = []
  valid_subs = []
  base = 0
  for si, (tid, vc, ic, po, no, uo, io_) in enumerate(subs):
    pos = np.frombuffer(buf, dtype=np.float32, count=vc * 3, offset=po).reshape(-1, 3)
    nrm = np.frombuffer(buf, dtype=np.float32, count=vc * 3, offset=no).reshape(-1, 3)
    uv = np.frombuffer(buf, dtype=np.float32, count=vc * 2, offset=uo).reshape(-1, 2)
    idx = np.frombuffer(buf, dtype=np.uint32, count=ic, offset=io_)
    if ic == 0 or vc == 0 or int(idx.max()) >= vc:
      continue            # 索引越界/空段：丢掉这一段，别让整个模型崩
    valid_subs.append((tid, vc, ic, si))
    verts_all.append(pos)
    nrm_all.append(nrm)
    uv_all.append(uv)
    f = (idx[: ic - ic % 3].reshape(-1, 3) + base)
    faces.append(f)
    base += vc

  if not verts_all:
    cache[key] = None
    return None

  V = np.concatenate(verts_all, 0).astype(np.float32)
  N = np.concatenate(nrm_all, 0).astype(np.float32)
  U = np.concatenate(uv_all, 0).astype(np.float32)
  F = np.concatenate(faces, 0).astype(np.int32)

  me = bpy.data.meshes.new('m_%s' % entry['f'][:8])
  nv = len(V)
  nf = len(F)
  me.vertices.add(nv)
  me.vertices.foreach_set('co', V.ravel())
  me.loops.add(nf * 3)
  me.loops.foreach_set('vertex_index', F.ravel())
  me.polygons.add(nf)
  me.polygons.foreach_set('loop_start', np.arange(0, nf * 3, 3, dtype=np.int32))
  me.update()

  # UV：直接按面的顶点索引取值，不回读 loops（回读在某些模型上会串位）
  uvl = me.uv_layers.new(name='UVMap')
  uvl.data.foreach_set('uv', U[F.ravel()].ravel())

  # 材质：**一个子网格一个槽**，槽序 == 子网格序，不做槽去重。
  # 2026-10-29 根修（TODO #1）：以前按 tid 去重 → 槽数 ≠ 子网格数，
  # 外部脚本（relink_materials）没法把「第 i 个子网格」映射到材质槽，
  # 59,385 个网格被跳过。现在槽 i 恒等于 valid_subs[i]，可按索引重挂。
  # 2026-10-30：每个槽再带法线/高光（index 里 `st`，与 `s` 等长同序）。
  st = entry.get('st') or []
  mats = []
  for (tid, vc, ic, si) in valid_subs:
    pair = st[si] if 0 <= si < len(st) else None
    ntid = pair[0] if pair else -1
    mtid = pair[1] if pair else -1
    mats.append(_mat_for(tid, ntid, mtid, texmeta, matcache, libdir))
  for m in mats:
    me.materials.append(m)

  mi = np.empty(nf, np.int32)
  p0 = 0
  for slot, (tid, vc, ic, si) in enumerate(valid_subs):
    cnt = ic // 3
    mi[p0:p0 + cnt] = slot
    p0 += cnt
  me.polygons.foreach_set('material_index', mi)
  me.update()

  cache[key] = me
  return me


_NTEX_MATS = {}
_NTEX_RULES = [
  (r'tree|pine|fir|oak|cedar|maple|birch|lodgepole|pine_', (0.115, 0.20, 0.095, 1)),
  (r'bush|shrub|scrub|bramble',                        (0.150, 0.235, 0.110, 1)),
  (r'grass|weed|fern|reed|moss',                       (0.265, 0.285, 0.135, 1)),
  (r'rock|stone|cliff|boulder|scree',                  (0.340, 0.330, 0.310, 1)),
  (r'log|stump|plank|wood',                            (0.300, 0.225, 0.150, 1)),
]

def _ntex_cat(name):
  import re as _re
  n = name or ''
  for pat, col in _NTEX_RULES:
    if _re.search(pat, n, _re.I):
      return col
  return (0.30, 0.27, 0.23, 1)

def _ntex_mat(col):
  key = col
  m = _NTEX_MATS.get(key)
  if m:
    return m
  m = bpy.data.materials.new('ntex_%.2f_%.2f_%.2f' % (col[0], col[1], col[2]))
  m.use_nodes = True
  b = _bsdf(m)
  b.inputs['Base Color'].default_value = col
  b.inputs['Roughness'].default_value = 0.95
  m.diffuse_color = col          # Workbench / Solid 用这个色，不设就变默认灰白
  m.roughness = 0.95
  _NTEX_MATS[key] = m
  return m


def build_entities(libdir, tiles_dir, max_ent=0, only_tile='', conj=False, rails=False,
                   bbox=None):
  # 名字表：给"无贴图模型"按类别上色用
  def _joaat(t):
    h = 0
    for c in t.lower().encode():
      h = (h + c) & 0xffffffff; h = (h + (h << 10)) & 0xffffffff; h ^= h >> 6
    h = (h + (h << 3)) & 0xffffffff; h ^= h >> 11
    return (h + (h << 15)) & 0xffffffff
  _NAMES = {}
  try:
    for _n in open(os.path.join(ROOT, 'tools/rdr2rpf/bin/Release/net9.0/names.txt'), encoding='latin1'):
      _n = _n.strip()
      if _n:
        _NAMES[_joaat(_n)] = _n
  except Exception:
    pass
  idx = json.load(open(os.path.join(libdir, 'index.json'), encoding='utf-8'))
  models = idx['models']
  texmeta = idx['tex']
  matcache = {}
  meshcache = {}

  lib_col = bpy.data.collections.new('LIB')
  bpy.context.scene.collection.children.link(lib_col)
  ent_col = bpy.data.collections.new('ENTITIES')
  bpy.context.scene.collection.children.link(ent_col)

  made = 0
  total = 0
  seen = 0            # 遍历到的实体条数（= 实体表总行数，除非 --only-tile/--max-entities）
  no_model = 0        # 库里没有这个 hash → 该实体缺模型
  no_model_bucket = {}  # 缺模型的分类桶（lod_block / real_ytyp / rpf_available / no_definition）
  bucket_of = {}
  mcp = os.path.join(ROOT, 'export/world/missing_classified.json')
  if os.path.exists(mcp):
    try:
      for k, v in (json.load(open(mcp, encoding='utf-8')).get('per_hash') or {}).items():
        bucket_of[int(k, 16)] = v.get('bucket', '?')
    except Exception as e:
      print('（missing_classified.json 读不了，缺模型不分类：%s）' % e)
  no_mesh = 0         # 库里有 index，但 .mdl 读不出来/无有效三角面
  skipped_flat = 0
  outside = 0         # --bbox 之外（按实体原点判；精确裁剪请用 crop_blend.py）
  # 地表分块网格（terrain 包里的 *_r_c_69.ydr 之类）与 H4 地形重复，必须剔掉
  src = {}
  mp = os.path.join(ROOT, 'export/world/continent/models.json')
  if os.path.exists(mp):
    src = json.load(open(mp, encoding='utf-8'))
  import re as _re
  # 只认「真正与 H4 地形重叠的分块」：地面 cell（_r_c_/ _rc_）与 hd_0 地形 patch。
  # 2026-10-29 修正：以前还带了 `_terrain` / `_ground\d*$`，把公园草坪
  # `new_gar06_park_terrain` 这类正常地面件也当成 cell 隐藏了（红框里该绿却是白）。
  TERRAIN_CELL = _re.compile(r'(_r_c_\d+|_rc_\d+|__hd_0_)', _re.I)
  RAIl_H = rail_hashes() if rails else set()
  rail_made = 0
  rail_dropped = 0
  files = sorted(f for f in os.listdir(tiles_dir) if f.endswith('.json'))
  if only_tile:
    files = [f for f in files if only_tile in f]
  for fn in files:
    ents = json.load(open(os.path.join(tiles_dir, fn), encoding='utf-8'))
    for e in ents:
      if max_ent and total >= max_ent:
        break
      seen += 1
      if bbox and not (bbox[0] <= e[1] <= bbox[2] and bbox[1] <= e[2] <= bbox[3]):
        outside += 1
        continue
      hx = '0x%08x' % e[0]   # 必须补零：hex() 会丢前导 0（e_777d697 就是这来的）
      ent = models.get(hx)
      if not ent:
        no_model += 1
        b = bucket_of.get(e[0])
        if b:
          no_model_bucket[b] = no_model_bucket.get(b, 0) + 1
        continue
      # 铁路豁免：道砟/枕木/钢轨/桥/道岔本来就是"又扁又宽"的长条件，
      # 会被 TERRAIN_CELL / cell / flat_wide 当成地表贴片丢掉（实测 1,024/1,359）。
      is_rail = bool(RAIl_H) and e[0] in RAIl_H
      bn = os.path.basename(src.get(hx, '')).lower()
      # 2026-10-28：用户要求「所有网格体都不剔除，只有植被默认不显示」。
      # 地形分块/贴片不再丢弃，改为打标记，构建后放进默认隐藏的分类。
      hide_tag = ''
      if bn and TERRAIN_CELL.search(bn) and not is_rail:
        hide_tag = 'terrain_cell'; skipped_flat += 1
      bb = ent['b']
      dx, dy, dz = bb[3] - bb[0], bb[4] - bb[1], bb[5] - bb[2]
      # 地表 LOD 分块（64×64 / 128×128）：任何地方都剔——和 H4 地形重复，且高度对不上，
      # 留着就是一块块浮在镇子上的褐色"岛"
      cell = (abs(dx - 64) < 2 and abs(dy - 64) < 2) or (abs(dx - 128) < 2 and abs(dy - 128) < 2)
      flat_wide = (dz < 2.0 and max(dx, dy) >= 16) or max(dx, dy) > 45
      if cell and not is_rail:
        hide_tag = 'terrain_cell'; skipped_flat += 1
      # RDR2 关卡设计把占位盒"停"在地图外 1 km（z ≈ −1002）：wll_tempbox2 / wli_tempbox /
      # wld_tempbox3 / wdl_tempbox4（TODO #9）。数据不改，只标记后藏进 HIDDEN_PARKED。
      if e[3] < -500.0:
        hide_tag = 'parked_offmap'
      if flat_wide and not is_rail:
        # 只做标记，不再丢弃（大跨度建筑如车站 45.4m 曾被误剔）
        if (not in_town(e[1], e[2])) or abs(e[3] - ground_z(e[1], e[2])) > 3.0:
          hide_tag = hide_tag or 'flat_piece'; skipped_flat += 1
      me = load_model_mesh(libdir, ent, texmeta, matcache, meshcache)
      if not me:
        no_mesh += 1
        continue
      _nm = _NAMES.get(e[0]) or ('e_%s' % hx[2:10])
      ob = bpy.data.objects.new(_nm, me)
      ob['hash'] = hx            # 原名给人和搜索用，hash 留给程序
      # 用实体原始 z：屋顶/塔楼/上层构件本来就高于地面，强行贴地会把整座镇拆散。
      # 地形已按"建筑基座中位标高"抬平，所以原始 z 与地面是对齐的。
      ob.location = (e[1], e[2], e[3])
      ob.rotation_mode = 'QUATERNION'
      # 实体存的是 (qx,qy,qz,qw)，Blender 的 rotation_quaternion 是 (w,x,y,z)
      ob.rotation_quaternion = (e[7], -e[4], -e[5], -e[6]) if conj else (e[7], e[4], e[5], e[6])
      ob.scale = (e[8], e[8], e[9])
      if hide_tag:
        ob['hide_tag'] = hide_tag
      if ent.get('s') and all((t < 0) for t, _, _ in ent['s']):
        try:
          ob.data.materials.clear()
          ob.data.materials.append(_ntex_mat(_ntex_cat(_NAMES.get(e[0], ''))))
        except Exception:
          pass
      ent_col.objects.link(ob)
      made += 1
      total += 1
      if is_rail:
        rail_made += 1
    print(' %s 实体 %d 网格 %d' % (fn, total, len(meshcache)))
  print('ENTITIES %d / 唯一网格 %d / 跳过扁平贴片 %d（标记不删）%s'
        % (made, len(meshcache), skipped_flat,
           (' / bbox 外 %d' % outside) if bbox else ''))
  print('ENTITY 覆盖：遍历 %d 条，缺模型 %d，库有但网格无效 %d，落地 %d'
        % (seen, no_model, no_mesh, made))
  BUILD_STATS.update({'seen': seen, 'no_model': no_model, 'no_mesh': no_mesh,
                      'made': made, 'outside': outside, 'buckets': no_model_bucket})
  if no_model_bucket:
    tot = sum(no_model_bucket.values())
    print('缺模型分类：' + ' / '.join('%s %d' % (k, v) for k, v in
                                    sorted(no_model_bucket.items(), key=lambda kv: -kv[1]))
          + '（已分类 %d / 缺 %d）' % (tot, no_model))
  if rails:
    print('RAILS %d（--rails 生效；关闭时这批会被 flat_wide 剔掉）' % rail_made)
  return ent_col


def water(step=8.0):
  """水面：一张蓝色平面（2026-10-28 用户要求）。

  原来的实现是 2048² 采样网格 → 285,550 个四边形（57 万三角面）+ 半透明，
  全屏 overdraw 导致视口卡顿，而且水位是重建值（42.75，比真值高 2.25 m，淹桥墩）。
  改为单 quad，高度用 RDR2 `water.xml` 的全局真值 40.5。
  """
  ZW = 40.5
  X0W, Y0W, WW = -7684.0, -8196.0, 12296.0
  old = bpy.data.objects.get('Water')
  if old is not None:
    bpy.data.objects.remove(old, do_unlink=True)
  me = bpy.data.meshes.new('Water')
  me.from_pydata([(X0W, Y0W, ZW), (X0W + WW, Y0W, ZW),
                  (X0W + WW, Y0W + WW, ZW), (X0W, Y0W + WW, ZW)], [], [(0, 1, 2, 3)])
  me.update()
  mat = bpy.data.materials.new('water')
  mat.use_nodes = True
  bsdf = _bsdf(mat)   # 按类型找，中文界面也认
  if bsdf:
    bsdf.inputs['Base Color'].default_value = (0.055, 0.135, 0.235, 1)
    bsdf.inputs['Roughness'].default_value = 0.08
    for k, v in (('IOR', 1.333), ('Alpha', 0.72)):
      if k in bsdf.inputs:
        bsdf.inputs[k].default_value = v
  # Blender 4.2+/5.x 用 surface_render_method；旧版是 blend_method。两个都试，
  # 只写 blend_method 在 5.2 上会被忽略 → 水面渲染成不透明灰板（TODO #3 的现象）。
  for attr, val in (('surface_render_method', 'BLENDED'), ('blend_method', 'BLEND')):
    try:
      setattr(mat, attr, val)
    except Exception:
      pass
  try:
    mat.use_backface_culling = False
  except Exception:
    pass
  # Workbench / Solid 模式不看节点树，只看材质的「视口显示色」；
  # 不设这个的话水面在默认视图里是一块**灰板**（TODO #3 的现象就是这么来的）。
  mat.diffuse_color = (0.10, 0.25, 0.42, 0.85)
  mat.roughness = 0.12
  mat['note'] = '非真值：单平面 + 中性水色（最高原则 §6.5）；水位 z=40.5 来自 water.xml'
  me.materials.append(mat)
  ob = bpy.data.objects.new('Water', me)
  bpy.context.scene.collection.objects.link(ob)
  print('WATER OK 单平面 z=%.1f（1 quad）' % ZW)
  return ob

def setup_world():
  w = bpy.data.worlds.new('Sky')
  w.use_nodes = True
  bg = w.node_tree.nodes['Background']
  bg.inputs['Color'].default_value = (0.62, 0.72, 0.85, 1.0)
  bg.inputs['Strength'].default_value = 1.1
  bpy.context.scene.world = w

  sun = bpy.data.lights.new('Sun', 'SUN')
  sun.energy = 2.6
  sun.angle = math.radians(2.5)
  so = bpy.data.objects.new('Sun', sun)
  so.rotation_euler = (math.radians(52), 0, math.radians(38))
  bpy.context.collection.objects.link(so)


def add_cam(loc, look, lens=35, ortho=None):
  cam = bpy.data.cameras.new('Cam')
  cam.lens = lens
  cam.clip_start = 0.5
  cam.clip_end = 60000.0   # 默认 100 m，整块大陆会被裁没
  if ortho:
    cam.type = 'ORTHO'
    cam.ortho_scale = ortho
  ob = bpy.data.objects.new('Cam', cam)
  ob.location = loc
  d = np.array(look, dtype=float) - np.array(loc, dtype=float)
  import mathutils
  v = mathutils.Vector(d.tolist())
  if abs(v.normalized().z) > 0.999:   # 正俯视：to_track_quat 会退化，直接给欧拉
    ob.rotation_euler = (0.0, 0.0, 0.0)
  else:
    ob.rotation_euler = v.to_track_quat('-Z', 'Y').to_euler()
  bpy.context.collection.objects.link(ob)
  return ob


def render_shots(outdir, res, views):
  os.makedirs(outdir, exist_ok=True)
  W, H = [int(x) for x in res.split('x')]
  sc = bpy.context.scene
  sc.render.resolution_x, sc.render.resolution_y = W, H
  sc.render.film_transparent = False
  try:
    sc.render.engine = 'BLENDER_EEVEE'
  except Exception:
    sc.render.engine = 'BLENDER_EEVEE'
  sc.eevee.taa_render_samples = 24
  sc.view_settings.view_transform = 'Standard'
  sc.view_settings.exposure = -0.2

  for name, loc, look, lens, ortho in views:
    cam = add_cam(loc, look, lens, ortho)
    sc.camera = cam
    sc.render.filepath = os.path.join(outdir, name + '.png')
    bpy.ops.render.render(write_still=True)
    print('SHOT', name)
    bpy.data.objects.remove(cam, do_unlink=True)


def main():
  a = parse()
  global USE_PAD, VEG_MODE
  USE_PAD = bool(a.pad)
  VEG_MODE = a.veg
  clear()
  setup_world()
  terrain(a.step, use_pad=USE_PAD)
  water()
  if a.lib and not a.terrain_only:
    bb = None
    if a.bbox:
      try:
        parts = []
        for tok in a.bbox:
          parts.extend(t for t in tok.replace(';', ',').split(',') if t.strip())
        v = [float(x) for x in parts]
        if len(v) != 4:
          raise ValueError('需要 4 个数 x0 y0 x1 y1')
        bb = (min(v[0], v[2]), min(v[1], v[3]), max(v[0], v[2]), max(v[1], v[3]))
      except Exception as e:
        print('--bbox 解析失败（%s），忽略这个开关' % e)
        bb = None
      if bb:
        print('BBOX x[%.0f,%.0f] y[%.0f,%.0f]' % bb)
    print('BUILD ENTITIES from', a.lib)
    build_entities(a.lib, TILES, a.max_entities, a.only_tile, not a.no_conj_quat, a.rails, bb)

  os.makedirs(os.path.dirname(a.out), exist_ok=True)
  if a.shots:
    views = [
      ('overview', (0, -9000, 5200), (0, 0, 100), 32, None),
      ('top', (0, 0, 9000), (0, 0, 0), 32, 13000),
      ('valley', (-1500, -3000, 900), (500, 500, 200), 35, None),
      ('sdn', (3600, -2400, 420), (2555, -1151, 40), 40, None),
    ]
    render_shots(a.shots, a.res, views)

  bpy.ops.wm.save_as_mainfile(filepath=a.out, compress=False)
  size = os.path.getsize(a.out) / 1e9
  print('SAVED %s %.2f GB' % (a.out, size))

  if a.full:
    run_postprocess(a.out)


def run_postprocess(out):
  """--full：分类 → 删植被 → 地形 patch 归隐藏 → manifest + 校验。

  全部在本进程内跑，避免二次加载 6.4 GB。
  2026-10-29：`hide_terrain_patches` 以前是手工补跑，导致 `--full` 的产物和 v5 不一致
  （地形 patch 留在 ENTITIES 里 → 视口多 2.8 万个对象）。现已纳入链内。
  """
  import importlib, sys as _sys, os as _os
  _tools = _os.path.dirname(_os.path.abspath(__file__))
  if _tools not in _sys.path:
    _sys.path.insert(0, _tools)

  def _run(mod_name, args):
    old = _sys.argv[:]
    _sys.argv = [mod_name] + ['--'] + args
    try:
      if mod_name in _sys.modules:
        del _sys.modules[mod_name]
      mod = importlib.import_module(mod_name)
      mod.main()
    finally:
      _sys.argv = old

  print('=== [full] 1/4 分类（12 类集合树） ===')
  _run('classify_entities', ['--apply', '--out', out])

  if VEG_MODE == 'keep':
    print('=== [full] 2/4 植被：keep（按要求原样保留） ===')
  else:
    print('=== [full] 2/4 植被：%s ===' % VEG_MODE)
    _run('strip_vegetation', ['--out', out, '--mode', VEG_MODE])

  print('=== [full] 3/5 地形 patch 归 HIDDEN_TERRAIN_CELL（隐藏不删） ===')
  _run('hide_terrain_patches', [])

  # 2026-10-29 补进链：远景 LOD 碎片与 HD 几何重叠、点不中，按文档口径「隐藏不删」。
  # 这一步以前不在任何自动链里 → 每次重建都重新露出来（v8/v9 都没有 HIDDEN_LOD）。
  print('=== [full] 4/5 远景 LOD 碎片归 HIDDEN_LOD（隐藏不删） ===')
  _run('hide_lod', [])

  print('=== [full] 5/5 输出对象清单 manifest.jsonl（之后验证不必再开 blend） ===')
  _run('write_manifest', ['--out', out])

  verify(out)


def verify(out):
  """AGENTS.md §3 要的那一行数字。数字一律取自刚写好的 manifest 汇总，
  免得「构建里一套口径、清单里另一套」。"""
  d = os.path.dirname(os.path.abspath(out))
  p = os.path.join(d, 'manifest.json')
  try:
    s = json.load(open(p, encoding='utf-8'))
  except Exception as e:
    print('VERIFY 读不到 %s：%s' % (p, e))
    return False
  st = BUILD_STATS
  seen = st.get('seen', 0)
  miss = st.get('no_model', 0)
  ok = s.get('verdict') == 'PASS'
  print('VERIFY ENTITIES %d / 12 类 %d/12 / 植被类 %d（应删未删 %d）/ 隐藏地形 %d / '
        '缺模型 %d/%d (%.1f%%) / 贴图用 %d → %s'
        % (s.get('entities', 0), s.get('classes_n', 0), s.get('veg_left', 0),
           s.get('veg_should_delete', -1), s.get('hidden_terrain', 0),
           miss, seen, 100.0 * miss / max(1, seen), s.get('textures_used', 0),
           'PASS' if ok else 'FAIL'))
  print('VERIFY TMAPS 带法线对象 %d（%d 张法线图）/ 带高光(ORM)对象 %d（%d 张 _ma 图）'
        % (s.get('with_normal_objects', 0), s.get('normal_textures_used', 0),
           s.get('with_orm_objects', 0), s.get('orm_textures_used', 0)))
  cls = s.get('classes', {})
  print('[full] 分类明细 %s' % ', '.join('%s:%d' % (k, cls[k]) for k in sorted(cls)))
  bk = BUILD_STATS.get('buckets') or {}
  if bk:
    print('[full] 缺模型拆分（见 docs/世界与地编/RDR2_整图覆盖率核查_20261026.md §10）：%s'
          % ', '.join('%s:%d' % (k, bk[k]) for k in sorted(bk, key=lambda x: -bk[x])))
  print('[full] 清单 %s（对象级 %s）' % (p, s.get('objects_file', '')))
  return ok


if __name__ == '__main__':
  main()
