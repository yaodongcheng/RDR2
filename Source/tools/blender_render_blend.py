"""打开 .blend 并出图（不重新导入）。用于反复调机位/灯光。

用法：
  blender -b <sdn.blend> -P tools/blender_render_blend.py -- \
      --shots DIR --views top,street,landmark --res 1600x900
"""
import bpy
import os
import sys
import math
import argparse
from mathutils import Vector


def argv():
    a = sys.argv
    return a[a.index('--') + 1:] if '--' in a else []


def parse():
    ap = argparse.ArgumentParser()
    ap.add_argument('--shots', required=True)
    ap.add_argument('--views', default='top')
    ap.add_argument('--res', default='1600x900')
    ap.add_argument('--samples', type=int, default=48)
    ap.add_argument('--cam', default='', help='自定义机位 x,y,z,lookx,looky,lookz,lens')
    return ap.parse_args(argv())


def bbox():
    mn = Vector((1e18, 1e18, 1e18))
    mx = Vector((-1e18, -1e18, -1e18))
    for o in bpy.context.scene.objects:
        if o.type != 'MESH' or o.name == 'Terrain':
            continue
        for c in o.bound_box:
            p = o.matrix_world @ Vector(c)
            for i in range(3):
                mn[i] = min(mn[i], p[i])
                mx[i] = max(mx[i], p[i])
    return mn, mx


def cam(loc, look, lens=35):
    c = bpy.data.cameras.new('c')
    c.lens = lens
    c.clip_start = 0.1
    c.clip_end = 40000
    o = bpy.data.objects.new('c', c)
    bpy.context.collection.objects.link(o)
    o.location = loc
    o.rotation_euler = (Vector(look) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    return o


def render(c, out, res, samples):
    sc = bpy.context.scene
    sc.camera = c
    sc.render.engine = 'BLENDER_EEVEE'
    try:
        sc.eevee.taa_render_samples = samples
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
    os.makedirs(a.shots, exist_ok=True)
    mn, mx = bbox()
    ctr = (mn + mx) / 2
    span = max(mx.x - mn.x, mx.y - mn.y)
    print('BBOX', tuple(round(v, 1) for v in mn), tuple(round(v, 1) for v in mx), 'span', round(span, 1))
    eye = ctr.z
    presets = {
        'overview': (ctr + Vector((span * .62, -span * .72, span * .55)), ctr, 40),
        'overview2': (ctr + Vector((-.7 * span, .55 * span, .45 * span)), ctr, 40),
        'top': (ctr + Vector((0.01, 0, span * 1.3)), ctr, 50),
        'north': (ctr + Vector((0, span * .75, span * .30)), ctr, 40),
        'street': (Vector((2500, -1200, eye + 2.0)), Vector((2500, -1080, eye + 3.5)), 24),
        'street2': (Vector((2450, -1105, eye + 2.0)), Vector((2600, -1105, eye + 3.0)), 26),
        'landmark': (Vector((2470, -1175, eye + 10)), Vector((2520, -1262, eye + 16)), 30),
        'canal': (Vector((2560, -1130, eye + 6)), Vector((2660, -1060, eye + 4)), 28),
    }
    if a.cam:
        v = [float(x) for x in a.cam.split(',')]
        render(cam(Vector(v[:3]), Vector(v[3:6]), v[6] if len(v) > 6 else 35),
               os.path.join(a.shots, 'custom.png'), a.res, a.samples)
        return
    for v in a.views.split(','):
        v = v.strip()
        if v not in presets:
            continue
        loc, look, lens = presets[v]
        render(cam(loc, look, lens), os.path.join(a.shots, f'{v}.png'), a.res, a.samples)


if __name__ == '__main__':
    main()
