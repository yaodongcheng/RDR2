"""室内目录：逐个导入 sdn_interiors/*.gltf，自动取景渲染一张图（供 HTML/PIL 拼目录）。

用法：
  blender -b -P tools/blender_render_interiors.py -- \
      --glob "D:/BrainMaker/大镖客2解包分析/export/levels/world/gltf/sdn_interiors/*.gltf" \
      --out  "D:/BrainMaker/大镖客2解包分析/export/levels/world/blender/interiors" \
      --res 720x540
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
    ap.add_argument('--glob', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--res', default='720x540')
    ap.add_argument('--samples', type=int, default=24)
    return ap.parse_args(argv())


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def setup_lights():
    w = bpy.data.worlds.new('W')
    bpy.context.scene.world = w
    w.use_nodes = True
    bg = w.node_tree.nodes['Background']
    bg.inputs[0].default_value = (0.55, 0.62, 0.72, 1)
    bg.inputs[1].default_value = 1.1
    # 室内没有阳光直射 → 用顶光 + 环境光把空间照亮
    sun = bpy.data.lights.new('Sun', 'SUN')
    sun.energy = 2.2
    sun.angle = math.radians(25)
    o = bpy.data.objects.new('Sun', sun)
    bpy.context.collection.objects.link(o)
    o.rotation_euler = (math.radians(20), 0, math.radians(30))
    pt = bpy.data.lights.new('P', 'POINT')
    pt.energy = 120000
    pt.shadow_soft_size = 6
    po = bpy.data.objects.new('P', pt)
    bpy.context.collection.objects.link(po)
    return po


def bbox():
    mn = Vector((1e18,) * 3)
    mx = Vector((-1e18,) * 3)
    for o in bpy.context.scene.objects:
        if o.type != 'MESH':
            continue
        for c in o.bound_box:
            p = o.matrix_world @ Vector(c)
            for i in range(3):
                mn[i] = min(mn[i], p[i])
                mx[i] = max(mx[i], p[i])
    return mn, mx


def main():
    a = parse()
    files = sorted(glob.glob(a.glob))
    os.makedirs(a.out, exist_ok=True)
    print('FILES', len(files))
    w, h = [int(x) for x in a.res.split('x')]
    for f in files:
        name = os.path.splitext(os.path.basename(f))[0]
        reset()
        try:
            bpy.ops.import_scene.gltf(filepath=f)
        except Exception as e:
            print('FAIL', name, e)
            continue
        mn, mx = bbox()
        if mn.x > 1e17:
            continue
        ctr = (mn + mx) / 2
        size = mx - mn
        r = max(size) * 1.25 + 3
        setup_lights()
        # 顶光放在几何中心上方
        for o in bpy.context.scene.objects:
            if o.type == 'LIGHT' and o.data.type == 'POINT':
                o.location = ctr + Vector((0, 0, max(size.z, 3) * 0.9))
        cam = bpy.data.cameras.new('c')
        cam.lens = 32
        cam.clip_start = 0.05
        cam.clip_end = 20000
        co = bpy.data.objects.new('c', cam)
        bpy.context.collection.objects.link(co)
        loc = ctr + Vector((r * 0.75, -r * 0.75, r * 0.55))
        co.location = loc
        co.rotation_euler = (ctr - loc).to_track_quat('-Z', 'Y').to_euler()
        sc = bpy.context.scene
        sc.camera = co
        sc.render.engine = 'BLENDER_EEVEE'
        try:
            sc.eevee.taa_render_samples = a.samples
        except Exception:
            pass
        sc.render.resolution_x, sc.render.resolution_y = w, h
        sc.render.resolution_percentage = 100
        sc.render.image_settings.file_format = 'PNG'
        try:
            sc.view_settings.view_transform = 'Standard'
        except Exception:
            pass
        sc.render.filepath = os.path.join(a.out, name + '.png')
        bpy.ops.render.render(write_still=True)
        print('SHOT', name)


if __name__ == '__main__':
    main()
