# -*- coding: utf-8 -*-
"""关掉水面，单看桥 / 铁轨 / 地形本身是否连续（判断"断桥"到底是缺模型还是被水盖住）。

    blender -b deliverable/blender/continent/continent.blend \
        -P tools/probe_bridge_nowater.py -- --shots <dir> [--radius 400]
"""
import bpy, os, sys, json, math
import numpy as np
from mathutils import Vector

ROOT = r'D:/BrainMaker/大镖客2解包分析'
SHOTS = os.path.join(ROOT, 'deliverable/blender/continent/shots')
BRIDGE = (2140.0, -1250.0)


def argv():
    a = sys.argv
    return a[a.index('--') + 1:] if '--' in a else []


def parse():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--shots', default=SHOTS)
    ap.add_argument('--radius', type=float, default=900.0)
    ap.add_argument('--res', default='1600x900')
    ap.add_argument('--samples', type=int, default=16)
    ap.add_argument('--prefix', default='nowater')
    return ap.parse_args(argv())


def hide_water():
    n = 0
    for o in bpy.context.scene.objects:
        nm = o.name.lower()
        if o.name == 'Water' or nm.startswith('water') or ('water' in nm and o.type == 'MESH'):
            o.hide_render = True
            o.hide_viewport = True
            n += 1
    print('[nowater] 隐藏水面对象 %d 个' % n)


def world_bbox(o):
    mn = Vector((1e18,) * 3); mx = Vector((-1e18,) * 3)
    for c in o.bound_box:
        p = o.matrix_world @ Vector(c)
        for i in range(3):
            mn[i] = min(mn[i], p[i]); mx[i] = max(mx[i], p[i])
    return mn, mx


def report(radius):
    bx, by = BRIDGE
    rows = []
    for o in bpy.context.scene.objects:
        if o.type != 'MESH':
            continue
        try:
            mn, mx = world_bbox(o)
        except Exception:
            continue
        cx, cy = (mn.x + mx.x) / 2, (mn.y + mx.y) / 2
        if math.hypot(cx - bx, cy - by) > radius:
            continue
        rows.append(dict(name=o.name,
                         c=[round(cx, 1), round(cy, 1)],
                         size=[round(mx.x - mn.x, 1), round(mx.y - mn.y, 1), round(mx.z - mn.z, 1)],
                         z=[round(mn.z, 1), round(mx.z, 1)],
                         verts=len(o.data.vertices) if o.data else 0))
    rows.sort(key=lambda r: -r['size'][0] * r['size'][1])
    print('[nowater] 桥区 %.0f m 内网格对象 %d 个' % (radius, len(rows)))
    kw = ('bridge', 'trestle', 'viaduct', 'train', 'rail', 'track', 'pier', 'strut', 'truss', 'girder')
    print('[nowater] 与桥/轨相关的前 40 个:')
    hit = 0
    for r in rows:
        if any(k in r['name'].lower() for k in kw):
            print('   %-42s c=(%7.1f,%8.1f) size=(%6.1f,%6.1f,%6.1f) z=[%6.1f,%6.1f] v=%d'
                  % (r['name'][:42], r['c'][0], r['c'][1], *r['size'], r['z'][0], r['z'][1], r['verts']))
            hit += 1
            if hit >= 40:
                break
    print('[nowater] 相关对象命中 %d' % hit)
    # 铁轨：名字含 rail 的全图统计（桥区外也算）
    zs = [r['z'][0] for r in rows]
    if zs:
        print('[nowater] 桥区对象 z 范围 %.1f ~ %.1f' % (min(zs), max(r['z'][1] for r in rows)))
    print('[nowater] 最大的 25 件:')
    for r in rows[:25]:
        print('   %-44s c=(%7.1f,%8.1f) size=(%6.1f,%6.1f,%6.1f) z=[%6.1f,%6.1f] v=%d'
              % (r['name'][:44], r['c'][0], r['c'][1], *r['size'], r['z'][0], r['z'][1], r['verts']))
    print('[nowater] 细长件（最长边>25 且 最短边<10）:')
    long_ = [r for r in rows if max(r['size']) > 25 and min(r['size']) < 10]
    for r in long_[:40]:
        print('   %-44s c=(%7.1f,%8.1f) size=(%6.1f,%6.1f,%6.1f) z=[%6.1f,%6.1f]'
              % (r['name'][:44], r['c'][0], r['c'][1], *r['size'], r['z'][0], r['z'][1]))
    print('[nowater] 细长件 %d 个' % len(long_))
    # 所属集合归类
    from collections import Counter
    cc = Counter()
    for o in bpy.context.scene.objects:
        if o.type != 'MESH': continue
        try: mn, mx = world_bbox(o)
        except Exception: continue
        cx, cy = (mn.x + mx.x)/2, (mn.y + mx.y)/2
        if math.hypot(cx-bx, cy-by) > radius: continue
        for col in o.users_collection:
            cc[col.name] += 1
    print('[nowater] 桥区对象所属集合 top15:', cc.most_common(15))
    # 地形在这一带的高度
    ter = bpy.data.objects.get('Terrain')
    if ter:
        n = len(ter.data.vertices)
        co = np.empty(n * 3, dtype=np.float64); ter.data.vertices.foreach_get('co', co)
        co = co.reshape(n, 3); M = np.array(ter.matrix_world)
        w = co @ M[:3, :3].T + M[:3, 3]
        d = np.hypot(w[:, 0] - bx, w[:, 1] - by)
        for r_ in (60, 120, 250):
            m = d < r_
            if m.any():
                print('[nowater] 地形 半径 %3d m: z 中位 %.2f  min %.2f  max %.2f' % (
                    r_, float(np.median(w[m, 2])), float(w[m, 2].min()), float(w[m, 2].max())))
    # rail / struct 集合里的样本名
    for tag in ('rail', 'struct'):
        names = []
        for o in bpy.context.scene.objects:
            if o.type != 'MESH': continue
            if not any(col.name.startswith(tag + '|') for col in o.users_collection): continue
            try: mn, mx = world_bbox(o)
            except Exception: continue
            cx, cy = (mn.x + mx.x)/2, (mn.y + mx.y)/2
            if math.hypot(cx-bx, cy-by) > radius: continue
            names.append((o.name, round(cx,1), round(cy,1), [round(v,1) for v in (mx-mn)]))
        print('[nowater] 集合 %s 在桥区 %d 个，样本:' % (tag, len(names)))
        for t in names[:12]:
            print('     ', t)
    json.dump(rows, open(os.path.join(ROOT, 'work/verify/bridge_nowater_objects.json'), 'w'),
              ensure_ascii=False, indent=1)
    return rows


def make_cam(loc, look, lens):
    c = bpy.data.cameras.new('c'); c.lens = lens; c.clip_start = 0.1; c.clip_end = 40000
    o = bpy.data.objects.new('c', c); bpy.context.scene.collection.objects.link(o)
    o.location = loc
    o.rotation_euler = (Vector(look) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    return o


def render(path, cam, res, samples):
    sc = bpy.context.scene
    sc.camera = cam
    for _e in ('BLENDER_EEVEE', 'BLENDER_EEVEE_NEXT'):
        try:
            sc.render.engine = _e; break
        except Exception:
            continue
    try: sc.eevee.taa_render_samples = samples
    except Exception: pass
    w, h = [int(x) for x in res.split('x')]
    sc.render.resolution_x, sc.render.resolution_y = w, h
    sc.render.resolution_percentage = 100
    sc.render.image_settings.file_format = 'PNG'
    try: sc.view_settings.view_transform = 'Standard'
    except Exception: pass
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    print('SHOT ->', path)


def main():
    a = parse()
    os.makedirs(a.shots, exist_ok=True)
    os.makedirs(os.path.join(ROOT, 'work/verify'), exist_ok=True)
    hide_water()
    report(a.radius)
    bx, by = BRIDGE
    cams = {
        # 对应截图1：东南高处俯视，看公路桥 + 铁路桁架桥
        'top': ((bx + 150, by - 185, 120.0), (bx - 30, by + 10, 40.0), 20),
        # 对应截图2：贴近桥面/水面平视
        'low': ((bx + 78, by - 62, 46.0), (bx - 30, by + 8, 44.0), 24),
        # 正俯视：查桥/轨在平面上是否连成一条
        'plan': ((bx + 0.01, by, 300.0), (bx, by, 40.0), 35),
        # 侧视：沿桥轴线垂直方向看，查纵向有没有缺口
        'side': ((bx - 290, by - 40, 62.0), (bx, by, 42.0), 30),
    }
    for k, (loc, look, lens) in cams.items():
        render(os.path.join(a.shots, '%s_%s.png' % (a.prefix, k)), make_cam(loc, look, lens), a.res, a.samples)


if __name__ == '__main__':
    main()
