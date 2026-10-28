"""重建地面层：RDR2 地形颜色贴图 + 水体 + 城市地台。

背景（为什么要重做）：
  * 旧地形是 8 m 网格的纯色板，城市地面模型只覆盖 45% ⇒ 中间露出绿板 = "支离破碎"
  * 游戏里城市地形是**挖空**的（颜色图全黑），城市地面由建筑地面模型接管
  * 水体在 `mapzones.meta` 里只有**极简多边形**（4~6 个点），直接拉面会很"棱角"

做法：
  1. 地形网格 4 m，z 用 H4 真高程；UV 直接用 `<tile>_t` 烘出的区域颜色图（0.5 m/px）
  2. 水体：官方多边形 → Chaikin 平滑 → 与"地形低于水位"求交 → 生成水面网格
  3. 城市多边形内把地形压低 0.35 m（避免和路面贴花 z-fighting）

用法：
  blender -b export/levels/world/blender/sdn.blend -P tools/blender_rebuild_ground.py -- \
      --out export/levels/world/blender/sdn.blend --shots DIR --views overview,top
"""
import bpy
import os
import sys
import json
import math
import argparse
import numpy as np
from mathutils import Vector

ROOT = r'D:/BrainMaker/大镖客2解包分析'
H4 = os.path.join(ROOT, 'work/terrain/H4.npy')
GROUND_JSON = os.path.join(ROOT, 'export/levels/world/blender/terrain/sdn_ground.json')
GROUND_PNG = os.path.join(ROOT, 'export/levels/world/blender/terrain/sdn_ground.png')
ZONES = os.path.join(ROOT, 'export/levels/world/zones.json')
X0, Y0, RES = -7684.0, -8196.0, 4.0


def argv():
    a = sys.argv
    return a[a.index('--') + 1:] if '--' in a else []


def parse():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=os.path.join(ROOT, 'export/levels/world/blender/sdn.blend'))
    ap.add_argument('--shots', default=os.path.join(ROOT, 'export/levels/world/blender/shots'))
    ap.add_argument('--views', default='')
    ap.add_argument('--res', default='1600x900')
    ap.add_argument('--step', type=float, default=4.0)
    ap.add_argument('--gate', type=int, default=20,
                    help='水域范围门的外扩格数（2 m/格）。越大水越往多边形外走；默认 20 = 40 m')
    ap.add_argument('--water-level', type=float, default=41.8,
                    help='水面绝对高程（m）。三角洲参考：河床 0~40，港区 35~40，城区 ≥44.4。'
                         '调高=水更多；调低=露出更多浅滩')
    return ap.parse_args(argv())


# ---------------------------------------------------------------- 多边形工具
def chaikin(pts, it=3):
    p = np.asarray(pts, dtype=np.float64)
    for _ in range(it):
        q = []
        n = len(p)
        for i in range(n):
            a = p[i]
            b = p[(i + 1) % n]
            q.append(a * 0.75 + b * 0.25)
            q.append(a * 0.25 + b * 0.75)
        p = np.array(q)
    return p


def rasterize_bbox(p, xs, ys):
    """只在多边形 bbox 内做射线法，返回 (mask, i0, i1, j0, j1)"""
    px0, py0 = p[:, 0].min(), p[:, 1].min()
    px1, py1 = p[:, 0].max(), p[:, 1].max()
    i0 = max(0, int(np.searchsorted(xs, px0) - 1)); i1 = min(len(xs), int(np.searchsorted(xs, px1) + 2))
    j0 = max(0, int(np.searchsorted(ys, py0) - 1)); j1 = min(len(ys), int(np.searchsorted(ys, py1) + 2))
    if i1 <= i0 or j1 <= j0:
        return None
    xx, yy = np.meshgrid(xs[i0:i1], ys[j0:j1])
    inside = np.zeros(xx.shape, dtype=bool)
    n = len(p)
    for k in range(n):
        xa, ya = p[k]; xb, yb = p[(k + 1) % n]
        cond = ((ya > yy) != (yb > yy)) & (xx < (xb - xa) * (yy - ya) / (yb - ya + 1e-12) + xa)
        inside ^= cond
    return inside, i0, i1, j0, j1


def rasterize(polys, xs, ys):
    """polys: list of (N,2) arrays → bool mask (len(ys), len(xs))"""
    xx, yy = np.meshgrid(xs, ys)
    m = np.zeros(xx.shape, dtype=bool)
    for p in polys:
        inside = np.zeros(xx.shape, dtype=bool)
        n = len(p)
        for i in range(n):
            xa, ya = p[i]
            xb, yb = p[(i + 1) % n]
            cond = ((ya > yy) != (yb > yy)) & (xx < (xb - xa) * (yy - ya) / (yb - ya + 1e-12) + xa)
            inside ^= cond
        m |= inside
    return m


def boundary_points(p, step=6.0):
    out = []
    n = len(p)
    for i in range(n):
        a = p[i]; b = p[(i + 1) % n]
        d = float(np.hypot(*(b - a)))
        k = max(1, int(d / step))
        for t in range(k):
            out.append(a + (b - a) * (t / k))
    return np.array(out)


# ---------------------------------------------------------------- 地形 / 水
def build(step, water_level=41.8, gate_cells=20):
    LEVEL_FIXED = float(water_level)
    gj = json.load(open(GROUND_JSON, encoding='utf-8'))
    rx0, ry0, rx1, ry1 = gj['region']
    Hm = np.load(H4)
    zones = json.load(open(ZONES, encoding='utf-8'))['zones']

    xs = np.arange(rx0, rx1 + 1e-6, step)
    ys = np.arange(ry0, ry1 + 1e-6, step)       # 从南到北
    nx, ny = len(xs), len(ys)
    print(f'GRID {nx}x{ny} step={step}')

    def sample_h(x, y):
        r = np.clip(((y - Y0) / RES).astype(int), 0, Hm.shape[0] - 1)
        c = np.clip(((x - X0) / RES).astype(int), 0, Hm.shape[1] - 1)
        return Hm[r, c]

    XX, YY = np.meshgrid(xs, ys)
    Z = sample_h(XX, YY).astype(np.float64)

    # ---- 水体多边形（平滑 + 与低地求交）
    water_polys = []
    for b in zones:
        if b['type'] not in ('RIVER', 'LAKE', 'CREEK', 'POND', 'SWAMP', 'OCEAN'):
            continue
        bx = b['bbox']
        if bx[2] < rx0 or bx[0] > rx1 or bx[3] < ry0 or bx[1] > ry1:
            continue
        for ring in b['polygons']:
            if len(ring) < 3:
                continue
            sm = chaikin(ring, 3)
            water_polys.append((b['name'], sm))

    water_mask = np.zeros_like(Z, dtype=bool)
    water_level = np.full_like(Z, -1e9, dtype=np.float64)
    # 水体用 2 m 网格
    xs2 = np.arange(rx0, rx1 + 1e-6, step / 2)
    ys2 = np.arange(ry0, ry1 + 1e-6, step / 2)
    Z2 = sample_h(*np.meshgrid(xs2, ys2)).astype(np.float64)
    # ★ 三角洲统一水位：直接"地形低于水位即水面"。
    #   之前用 mapzones 多边形裁剪，直边会把低洼地切成细长沙洲楔形（港区口那几条）。
    #   RDR2 三角洲本身很平（37~40 m），40.9 m 水位下天然形成河网，岸线完全由等高线决定。
    LEVEL = LEVEL_FIXED
    # 水体多边形只当"水域范围的门"（再外扩 200 m），真正的岸线由地形等高线决定。
    # 这样既不会出现多边形直边切出的沙洲楔形，也不会把远处的低洼农田当水面。
    pmask = np.zeros_like(Z2, dtype=bool)
    for name, p in water_polys:
        r = rasterize_bbox(p, xs2, ys2)
        if r:
            inside, i0, i1, j0, j1 = r
            pmask[j0:j1, i0:i1] |= inside

    def _dilate(m, it):
        out = m.copy()
        for _ in range(it):
            n = out.copy()
            n[1:, :] |= out[:-1, :]
            n[:-1, :] |= out[1:, :]
            n[:, 1:] |= out[:, :-1]
            n[:, :-1] |= out[:, 1:]
            out = n
        return out

    gate = _dilate(pmask, gate_cells)   # 2 m 网格 → 外扩 gate_cells*2 m
    wm2 = gate & (Z2 < LEVEL)
    wl2 = np.where(wm2, LEVEL, -1e9)
    print('  水域门内 %.1f%%，水位 %.1f m，最终水面 %.1f%%' % (
        gate.mean() * 100, LEVEL, wm2.mean() * 100))

    water_mask = wm2
    water_level = wl2

    # ---- 城市地台：压低 0.35 m
    city = [z for z in zones if z['name'] == 'StDenis'][0]
    cm = rasterize([chaikin(r, 1) for r in city['polygons'] if len(r) >= 3], xs, ys)
    Z = Z - 0.35 * cm

    # 水面下方地形压低（4 m 地形网格，用 2 m 水位图最邻近采样）
    ci = np.clip((np.arange(len(xs)) * (len(xs2) / len(xs))).astype(int), 0, len(xs2) - 1)
    ri = np.clip((np.arange(len(ys)) * (len(ys2) / len(ys))).astype(int), 0, len(ys2) - 1)
    wm4 = water_mask[ri][:, ci]; wl4 = water_level[ri][:, ci]
    # 动态水位模式下不再挖河床：地形保持真实高程，水面平面自己"切"出岸线。
    # （调低水位时也就不会露出人为挖出来的沟）

    print('water cells %.1f%%  city cells %.1f%%' % (
        water_mask.mean() * 100, cm.mean() * 100))
    return dict(xs=xs, ys=ys, Z=Z, water_mask=wm4, water_level=wl4,
                water_mask_f=water_mask, water_level_f=water_level,
                region=(rx0, ry0, rx1, ry1))


# ---------------------------------------------------------------- Blender 构建
def ensure_light():
    if not bpy.data.objects.get('Sun'):
        sun = bpy.data.lights.new('Sun', 'SUN')
        sun.energy = 3.2
        sun.angle = math.radians(2.5)
        so = bpy.data.objects.new('Sun', sun)
        bpy.context.scene.collection.objects.link(so)
        so.rotation_euler = (math.radians(48), math.radians(6), math.radians(28))
    if bpy.context.scene.world is None:
        w = bpy.data.worlds.new('Sky')
        bpy.context.scene.world = w
        w.use_nodes = True
        bg = next(n for n in w.node_tree.nodes if n.type == 'BACKGROUND')
        bg.inputs[0].default_value = (0.42, 0.55, 0.75, 1)
        bg.inputs[1].default_value = 0.8


def clear_old():
    for n in ('Terrain', 'Water'):
        o = bpy.data.objects.get(n)
        if o:
            bpy.data.objects.remove(o, do_unlink=True)
    for m in list(bpy.data.materials):
        if m.name.startswith('ground_tex') or m.name.startswith('water_'):
            bpy.data.materials.remove(m)


def make_terrain(d):
    xs, ys, Z = d['xs'], d['ys'], d['Z']
    rx0, ry0, rx1, ry1 = d['region']
    nx, ny = len(xs), len(ys)
    verts = []
    for j in range(ny):
        for i in range(nx):
            verts.append((float(xs[i]), float(ys[j]), float(Z[j, i])))
    faces = []
    for j in range(ny - 1):
        for i in range(nx - 1):
            a = j * nx + i
            faces.append((a, a + 1, a + 1 + nx, a + nx))
    me = bpy.data.meshes.new('Terrain')
    me.from_pydata(verts, [], faces)
    me.update()
    # UV
    uv = me.uv_layers.new(name='UVMap')
    for poly in me.polygons:
        for li in poly.loop_indices:
            vi = me.loops[li].vertex_index
            v = me.vertices[vi].co
            uv.data[li].uv = ((v.x - rx0) / (rx1 - rx0), (v.y - ry0) / (ry1 - ry0))
    ob = bpy.data.objects.new('Terrain', me)
    bpy.context.scene.collection.objects.link(ob)

    mat = bpy.data.materials.new('ground_tex')
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED')
    bsdf.inputs['Roughness'].default_value = 0.95
    bsdf.inputs['Metallic'].default_value = 0.0
    tex = nt.nodes.new('ShaderNodeTexImage')
    img = bpy.data.images.load(GROUND_PNG, check_existing=True)
    try:
        img.colorspace_settings.name = 'sRGB'
    except Exception:
        pass
    tex.image = img
    tex.interpolation = 'Linear'
    nt.links.new(tex.outputs['Color'], bsdf.inputs['Base Color'])
    ob.data.materials.append(mat)
    print('TERRAIN verts', len(verts))
    return ob


def make_water(d):
    # 水体单独用 2 m 网格（4 m 网格的水岸会有明显台阶）
    rx0, ry0, rx1, ry1 = d['region']
    step = 2.0
    xs = np.arange(rx0, rx1 + 1e-6, step)
    ys = np.arange(ry0, ry1 + 1e-6, step)
    mask = d['water_mask_f'] if 'water_mask_f' in d else d['water_mask']
    lvl = d['water_level_f'] if 'water_level_f' in d else d['water_level']
    if mask.shape != (len(ys), len(xs)):
        # 用最邻近放大
        ri = np.clip((np.arange(len(ys)) * (mask.shape[0] / len(ys))).astype(int), 0, mask.shape[0]-1)
        ci = np.clip((np.arange(len(xs)) * (mask.shape[1] / len(xs))).astype(int), 0, mask.shape[1]-1)
        mask = mask[ri][:, ci]; lvl = lvl[ri][:, ci]
    nx, ny = len(xs), len(ys)
    verts = []
    idx = {}
    faces = []

    def vid(i, j):
        k = (i, j)
        if k in idx:
            return idx[k]
        idx[k] = len(verts)
        verts.append((float(xs[i]), float(ys[j]), float(lvl[j, i])))
        return idx[k]

    for j in range(ny - 1):
        for i in range(nx - 1):
            if mask[j, i] and mask[j, i + 1] and mask[j + 1, i] and mask[j + 1, i + 1]:
                a = vid(i, j); b = vid(i + 1, j); c = vid(i + 1, j + 1); e = vid(i, j + 1)
                faces.append((a, b, c, e))
    if not faces:
        print('NO WATER')
        return None
    me = bpy.data.meshes.new('Water')
    me.from_pydata(verts, [], faces)
    me.update()
    ob = bpy.data.objects.new('Water', me)
    bpy.context.scene.collection.objects.link(ob)
    mat = bpy.data.materials.new('water_sdn')
    mat.use_nodes = True
    bsdf = next(n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    bsdf.inputs['Base Color'].default_value = (0.055, 0.10, 0.105, 1)
    bsdf.inputs['Roughness'].default_value = 0.08
    bsdf.inputs['Metallic'].default_value = 0.0
    try:
        bsdf.inputs['Specular IOR Level'].default_value = 0.6
    except Exception:
        pass
    ob.data.materials.append(mat)
    try:
        ob.visible_shadow = False       # 水面不投影：平水面在 EEVEE 里会产生条状阴影伪影
    except Exception:
        pass
    print('WATER verts %d faces %d' % (len(verts), len(faces)))
    return ob


def make_water_dynamic(d, level):
    """动态水面：一整块平面放在 z=level，地形自然把它"切"出岸线。
    平面上挂自定义属性 water_level + 驱动器 ⇒ 在 Blender 里改数值，水面**立刻**升降。"""
    rx0, ry0, rx1, ry1 = d['region']
    pad = 300.0
    verts = [(rx0 - pad, ry0 - pad, 0.0), (rx1 + pad, ry0 - pad, 0.0),
             (rx1 + pad, ry1 + pad, 0.0), (rx0 - pad, ry1 + pad, 0.0)]
    me = bpy.data.meshes.new('Water')
    me.from_pydata(verts, [], [(0, 1, 2, 3)])
    me.update()
    ob = bpy.data.objects.new('Water', me)
    bpy.context.scene.collection.objects.link(ob)
    ob.location = (0.0, 0.0, float(level))

    mat = bpy.data.materials.new('water_sdn')
    mat.use_nodes = True
    bsdf = next(n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    bsdf.inputs['Base Color'].default_value = (0.055, 0.10, 0.105, 1)
    bsdf.inputs['Roughness'].default_value = 0.08
    bsdf.inputs['Metallic'].default_value = 0.0
    ob.data.materials.append(mat)
    try:
        ob.visible_shadow = False
    except Exception:
        pass

    # 自定义属性 + 驱动器（改 water_level → 平面 z 跟着变）
    ob['water_level'] = float(level)
    ob.id_properties_ui('water_level').update(
        min=35.0, max=50.0, soft_min=38.0, soft_max=46.0,
        description='水面高程（m）。改这个数值，水面立刻升降，岸线自动变化')
    fc = ob.driver_add('location', 2)
    drv = fc.driver
    drv.type = 'SCRIPTED'
    var = drv.variables.new()
    var.name = 'lvl'
    var.type = 'SINGLE_PROP'
    var.targets[0].id_type = 'OBJECT'
    var.targets[0].id = ob
    var.targets[0].data_path = '["water_level"]'
    drv.expression = 'lvl'
    print('WATER(动态平面) level=%.2f  size=%.0fx%.0f m' % (level, verts[2][0] - verts[0][0], verts[2][1] - verts[0][1]))
    return ob


def city_bbox():
    mn = Vector((1e18,) * 3)
    mx = Vector((-1e18,) * 3)
    for o in bpy.context.scene.objects:
        if o.type != 'MESH' or o.name in ('Terrain', 'Water'):
            continue
        for c in o.bound_box:
            p = o.matrix_world @ Vector(c)
            for i in range(3):
                mn[i] = min(mn[i], p[i]); mx[i] = max(mx[i], p[i])
    return mn, mx


def cam(loc, look, lens=35, clip_end=40000):
    c = bpy.data.cameras.new('c')
    c.lens = lens
    c.clip_start = 0.2
    c.clip_end = clip_end
    o = bpy.data.objects.new('c', c)
    bpy.context.collection.objects.link(o)
    o.location = loc
    o.rotation_euler = (Vector(look) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    return o


def render(c, out, res):
    sc = bpy.context.scene
    sc.camera = c
    sc.render.engine = 'BLENDER_EEVEE'
    try:
        sc.eevee.taa_render_samples = 32
    except Exception:
        pass
    w, h = [int(x) for x in res.split('x')]
    sc.render.resolution_x, sc.render.resolution_y = w, h
    sc.render.resolution_percentage = 100
    sc.render.image_settings.file_format = 'PNG'
    try:
        sc.view_settings.view_transform = 'Standard'
    except Exception:
        pass
    sc.render.filepath = out
    bpy.ops.render.render(write_still=True)
    print('SHOT ->', out)


def main():
    a = parse()
    clear_old()
    ensure_light()
    d = build(a.step, a.water_level, a.gate)
    make_terrain(d)
    make_water_dynamic(d, a.water_level)
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    try:
        import json as _json
        cfg = os.path.join(ROOT, 'export/levels/world/blender/terrain/water_level.json')
        _json.dump(dict(water_level=a.water_level), open(cfg, 'w'), indent=1)
    except Exception:
        pass
    bpy.ops.wm.save_as_mainfile(filepath=a.out)
    print('SAVED', a.out)
    if a.views:
        mn, mx = city_bbox()
        if mn.x > 1e17:   # 没有城市物体（测试场景）→ 用区域中心
            rx0, ry0, rx1, ry1 = d['region']
            mn = Vector((rx0, ry0, 0)); mx = Vector((rx1, ry1, 60))
        ctr = (mn + mx) / 2
        span = max(mx.x - mn.x, mx.y - mn.y)
        os.makedirs(a.shots, exist_ok=True)
        views = {
            'overview': (ctr + Vector((span * .62, -span * .72, span * .55)), ctr, 40),
            'top': (ctr + Vector((0.01, 0, span * 1.3)), ctr, 50),
            'wide': (Vector((2510, -1250, 900)), Vector((2800, -900, 20)), 32),
            'street': (Vector((2500, -1200, 54)), Vector((2500, -1060, 55)), 24),
        }
        for v in a.views.split(','):
            if v not in views:
                continue
            loc, look, lens = views[v]
            render(cam(loc, look, lens), os.path.join(a.shots, f'{v}.png'), a.res)


if __name__ == '__main__':
    main()
