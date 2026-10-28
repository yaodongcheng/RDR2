"""把导出的圣丹尼斯 glTF 分块拼进 Blender：加地形、灯光、机位，存 .blend 并出图。

用法：
  blender -b -P tools/blender_assemble_sdn.py -- \
      --gltf "D:/BrainMaker/大镖客2解包分析/export/levels/world/gltf/sdn/tiles/*.gltf" \
      --out  "D:/BrainMaker/大镖客2解包分析/export/levels/world/blender/sdn.blend" \
      --shots "D:/BrainMaker/大镖客2解包分析/export/levels/world/blender/shots" \
      --views overview,top,street,landmark --res 1600x900
"""
import bpy
import os
import sys
import glob
import math
import argparse
import numpy as np
from mathutils import Vector

ROOT = r'D:/BrainMaker/大镖客2解包分析'
H4 = os.path.join(ROOT, 'work/terrain/H4.npy')
VALID = os.path.join(ROOT, 'work/terrain/valid4.npy')
X0, Y0, RES = -7684.0, -8196.0, 4.0


def argv():
    a = sys.argv
    return a[a.index('--') + 1:] if '--' in a else []


def parse():
    ap = argparse.ArgumentParser()
    ap.add_argument('--gltf', default=os.path.join(
        ROOT, 'export/levels/world/gltf/sdn/tiles/*.gltf'))
    ap.add_argument('--out', default=os.path.join(
        ROOT, 'export/levels/world/blender/sdn.blend'))
    ap.add_argument('--shots', default=os.path.join(
        ROOT, 'export/levels/world/blender/shots'))
    ap.add_argument('--views', default='overview,top,street,landmark')
    ap.add_argument('--res', default='1600x900')
    ap.add_argument('--no-terrain', action='store_true')
    ap.add_argument('--int-glob', default=os.path.join(
        ROOT, 'export/levels/world/gltf/sdn_interiors/*.gltf'))
    ap.add_argument('--no-int', action='store_true')
    ap.add_argument('--props-glob', default=os.path.join(
        ROOT, 'export/levels/world/gltf/sdn_props/tiles/*.gltf'))
    ap.add_argument('--no-props', action='store_true')
    ap.add_argument('--area', default='2050,-1700,3080,-600')
    ap.add_argument('--step', type=float, default=8.0)
    ap.add_argument('--samples', type=int, default=48)
    return ap.parse_args(argv())


def clear():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    for c in (bpy.data.meshes, bpy.data.materials, bpy.data.images):
        for x in list(c):
            try:
                c.remove(x)
            except Exception:
                pass


def import_tiles(pattern):
    files = sorted(glob.glob(pattern, recursive=True))
    print(f'TILES {len(files)}')
    for i, f in enumerate(files):
        try:
            bpy.ops.import_scene.gltf(filepath=f)
        except Exception as e:
            print('FAIL', f, e)
        if (i + 1) % 8 == 0:
            print(f'  ... {i+1}/{len(files)}')
    print('IMPORT DONE')


def import_collection(pattern, name):
    files = sorted(glob.glob(pattern, recursive=True))
    if not files:
        return
    col = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(col)
    vl = bpy.context.view_layer
    vl.active_layer_collection = vl.layer_collection.children[col.name]
    for f in files:
        try:
            bpy.ops.import_scene.gltf(filepath=f)
        except Exception as e:
            print('FAIL', f, e)
    print(f'COLLECTION {name}: {len(files)} files')


def add_terrain(area, step):
    if not (os.path.exists(H4) and os.path.exists(VALID)):
        print('NO TERRAIN DATA')
        return None
    Hm = np.load(H4)
    Vm = np.load(VALID)
    xmin, ymin, xmax, ymax = [float(x) for x in area.split(',')]
    xs = np.arange(xmin, xmax + 1e-6, step)
    ys = np.arange(ymin, ymax + 1e-6, step)
    nx, ny = len(xs), len(ys)
    verts = []
    for y in ys:
        r = int(round((y - Y0) / RES))
        row = []
        for x in xs:
            c = int(round((x - X0) / RES))
            z = float(Hm[r, c]) if (0 <= r < Hm.shape[0] and 0 <= c < Hm.shape[1]) else 0.0
            row.append((float(x), float(y), z))
        verts.extend(row)
    faces = []
    for j in range(ny - 1):
        for i in range(nx - 1):
            a = j * nx + i
            faces.append((a, a + 1, a + 1 + nx, a + nx))
    me = bpy.data.meshes.new('Terrain')
    me.from_pydata(verts, [], faces)
    me.update()
    ob = bpy.data.objects.new('Terrain', me)
    bpy.context.collection.objects.link(ob)
    mat = bpy.data.materials.new('ground')
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes['Principled BSDF']
    bsdf.inputs['Base Color'].default_value = (0.20, 0.21, 0.17, 1)
    bsdf.inputs['Roughness'].default_value = 0.95
    ob.data.materials.append(mat)
    print(f'TERRAIN {nx}x{ny} verts={len(verts)}')
    return ob


def setup_light():
    w = bpy.data.worlds.new('Sky')
    bpy.context.scene.world = w
    w.use_nodes = True
    bg = w.node_tree.nodes['Background']
    bg.inputs[0].default_value = (0.42, 0.55, 0.75, 1)
    bg.inputs[1].default_value = 0.8
    sun = bpy.data.lights.new('Sun', 'SUN')
    sun.energy = 3.2
    sun.angle = math.radians(2.5)
    so = bpy.data.objects.new('Sun', sun)
    bpy.context.collection.objects.link(so)
    so.rotation_euler = (math.radians(48), math.radians(6), math.radians(28))


def city_bbox():
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


def add_cam(loc, look, lens=35):
    cam = bpy.data.cameras.new('cam')
    cam.lens = lens
    cam.clip_start = 0.2
    cam.clip_end = 30000
    o = bpy.data.objects.new('cam', cam)
    bpy.context.collection.objects.link(o)
    o.location = loc
    d = Vector(look) - Vector(loc)
    o.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    return o


def render(cam, out, res, samples):
    sc = bpy.context.scene
    sc.camera = cam
    sc.render.engine = 'BLENDER_EEVEE'
    try:
        sc.eevee.taa_render_samples = samples
    except Exception:
        pass
    w, h = [int(x) for x in res.split('x')]
    sc.render.resolution_x = w
    sc.render.resolution_y = h
    sc.render.resolution_percentage = 100
    sc.render.image_settings.file_format = 'PNG'
    try:
        sc.view_settings.view_transform = 'Standard'
        sc.view_settings.exposure = 0.0
    except Exception:
        pass
    sc.render.filepath = out
    bpy.ops.render.render(write_still=True)
    print('SHOT ->', out)


def main():
    a = parse()
    clear()
    import_tiles(a.gltf)
    if not a.no_props:
        import_collection(a.props_glob, 'Props')
    if not a.no_int:
        import_collection(a.int_glob, 'Interiors')
    if not a.no_terrain:
        add_terrain(a.area, a.step)
    setup_light()
    mn, mx = city_bbox()
    ctr = (mn + mx) / 2
    span = max(mx.x - mn.x, mx.y - mn.y, mx.z - mn.z)
    print('CITY BBOX', tuple(round(v, 1) for v in mn), tuple(round(v, 1) for v in mx),
          'span', round(span, 1))

    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    bpy.ops.file.make_paths_relative()
    bpy.ops.wm.save_as_mainfile(filepath=a.out)
    print('SAVED', a.out)

    if not a.shots:
        return
    os.makedirs(a.shots, exist_ok=True)
    eye = ctr.z
    views = {
        'overview': (add_cam(ctr + Vector((span * 0.62, -span * 0.72, span * 0.55)), ctr, 40), ),
        'overview2': (add_cam(ctr + Vector((-span * 0.7, span * 0.55, span * 0.45)), ctr, 40), ),
        'top': (add_cam(ctr + Vector((0.01, 0, span * 1.35)), ctr, 50), ),
        'street': (add_cam(Vector((2500, -1200, eye + 2.0)), Vector((2500, -1080, eye + 3.0)), 24), ),
        'landmark': (add_cam(Vector((2470, -1180, eye + 12)), Vector((2520, -1265, eye + 14)), 30), ),
    }
    for v in a.views.split(','):
        v = v.strip()
        if v not in views:
            continue
        render(views[v][0], os.path.join(a.shots, f'{v}.png'), a.res, a.samples)


if __name__ == '__main__':
    main()
