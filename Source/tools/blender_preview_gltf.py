"""Blender 无头预览：导入 glTF / 一组 glTF，自动取景渲染几张图。

用法：
  blender -b -P tools/blender_preview_gltf.py -- --glob "work/sdn/gltf_test/tiles/*.gltf" \
      --out work/sdn/shots --views iso,front,top --res 1280x720
"""
import bpy
import os
import sys
import glob
import math
import argparse
from mathutils import Vector


def argv():
    a = sys.argv
    return a[a.index('--') + 1:] if '--' in a else []


def parse():
    ap = argparse.ArgumentParser()
    ap.add_argument('--file', default='')
    ap.add_argument('--glob', default='')
    ap.add_argument('--out', required=True)
    ap.add_argument('--views', default='iso,front,top')
    ap.add_argument('--res', default='1280x720')
    ap.add_argument('--frame', default='')
    ap.add_argument('--engine', default='BLENDER_EEVEE')
    ap.add_argument('--samples', type=int, default=32)
    ap.add_argument('--dist', type=float, default=0.0)
    ap.add_argument('--look', default='')
    ap.add_argument('--skip', default='')
    ap.add_argument('--workbench', action='store_true')
    return ap.parse_args(argv())


def clear():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def import_files(files):
    n = 0
    for f in files:
        try:
            bpy.ops.import_scene.gltf(filepath=f)
            n += 1
        except Exception as e:
            print('IMPORT FAIL', f, e)
    return n


def scene_bbox(objs):
    mn = Vector((1e18, 1e18, 1e18))
    mx = Vector((-1e18, -1e18, -1e18))
    for o in objs:
        if o.type != 'MESH':
            continue
        for c in o.bound_box:
            w = o.matrix_world @ Vector(c)
            for i in range(3):
                mn[i] = min(mn[i], w[i])
                mx[i] = max(mx[i], w[i])
    return mn, mx


def setup_world():
    w = bpy.data.worlds.new('W')
    bpy.context.scene.world = w
    w.use_nodes = True
    bg = w.node_tree.nodes['Background']
    bg.inputs[0].default_value = (0.62, 0.72, 0.86, 1)
    bg.inputs[1].default_value = 0.55
    # 太阳
    sun = bpy.data.lights.new('Sun', 'SUN')
    sun.energy = 2.6
    sun.angle = math.radians(6)
    so = bpy.data.objects.new('Sun', sun)
    bpy.context.collection.objects.link(so)
    so.rotation_euler = (math.radians(52), 0, math.radians(35))


def add_cam(name, loc, look):
    cam = bpy.data.cameras.new(name)
    cam.lens = 35
    cam.clip_start = 0.1
    cam.clip_end = 20000
    o = bpy.data.objects.new(name, cam)
    bpy.context.collection.objects.link(o)
    o.location = loc
    d = (Vector(look) - Vector(loc))
    o.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    return o


def render(cam, out, res, engine, samples):
    sc = bpy.context.scene
    sc.camera = cam
    sc.render.engine = engine
    if getattr(render, 'workbench', False):
        sc.render.engine = 'BLENDER_WORKBENCH'
    try:
        sc.eevee.taa_render_samples = samples
    except Exception:
        pass
    w, h = [int(x) for x in res.split('x')]
    sc.render.resolution_x = w
    sc.render.resolution_y = h
    sc.render.resolution_percentage = 100
    sc.render.film_transparent = False
    sc.render.image_settings.file_format = 'PNG'
    try:
        sc.view_settings.view_transform = 'Standard'
        sc.view_settings.exposure = 0.0
        sc.view_settings.gamma = 1.0
    except Exception:
        pass
    sc.render.filepath = out
    bpy.ops.render.render(write_still=True)
    print('RENDER ->', out)


def main():
    a = parse()
    clear()
    files = []
    if a.file:
        files = [a.file]
    if a.glob:
        files = sorted(glob.glob(a.glob, recursive=True))
    print(f'IMPORT {len(files)} files')
    n = import_files(files)
    if a.skip:
        pats = [x.strip().lower() for x in a.skip.split(',') if x.strip()]
        rm = [o for o in bpy.context.scene.objects if any(p in o.name.lower() for p in pats)]
        print('SKIP objects', len(rm))
        for o in rm:
            bpy.data.objects.remove(o, do_unlink=True)
    objs = list(bpy.context.scene.objects)
    meshes = [o for o in objs if o.type == 'MESH']
    print(f'objects {len(objs)} meshes {len(meshes)}')
    if not meshes:
        print('NO MESH')
        return
    mn, mx = scene_bbox(meshes)
    ctr = (mn + mx) / 2
    size = mx - mn
    print('BBOX', tuple(round(v, 2) for v in mn), tuple(round(v, 2) for v in mx),
          'size', tuple(round(v, 2) for v in size))
    # 三角数
    tri = 0
    for o in meshes:
        me = o.data
        me.calc_loop_triangles()
        tri += len(me.loop_triangles)
    print('TRIS', tri)

    setup_world()
    r = max(size) * 1.15 + 5
    look = Vector(a.look.split(',')) if a.look else ctr
    views = {
        'iso': (ctr + Vector((r * 0.8, -r * 0.8, r * 0.55)), look),
        'iso2': (ctr + Vector((-r * 0.8, r * 0.7, r * 0.5)), look),
        'front': (ctr + Vector((0, -r * 1.25, r * 0.12)), look),
        'top': (ctr + Vector((0, 0, r * 1.4)), look),
        'street': (ctr + Vector((r * 0.10, -r * 0.22, r * 0.03)), ctr + Vector((0, 0, size.z * 0.15))),
    }
    os.makedirs(a.out, exist_ok=True)
    for v in a.views.split(','):
        if v not in views:
            continue
        loc, lk = views[v]
        if a.dist > 0:
            d = (loc - look).normalized() * a.dist
            loc = look + d
        cam = add_cam('cam_' + v, loc, lk)
        render(cam, os.path.join(a.out, f'{v}.png'), a.res, a.engine, a.samples)


if __name__ == '__main__':
    main()
