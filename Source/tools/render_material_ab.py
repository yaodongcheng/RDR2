# -*- coding: utf-8 -*-
"""近距离 Eevee 出图：同机位 A/B —— 带法线+ORM vs 只留漫反射。

用途：证明"法线/高光真的进了场景"，不是只在 index.json 里有一行数字。

    blender -b <continent_v12.blend> -P tools/_unbuffer.py -P tools/render_material_ab.py -- --tag v12 --at 2560,-1450

产物：
    <out>/<tag>_on.png    三贴图材质
    <out>/<tag>_off.png   把 Normal / Metallic / Roughness 的连线全部断开（等同旧版）
"""
import bpy
import os
import sys
import math
import argparse
from mathutils import Vector

ROOT = r'D:/BrainMaker/大镖客2解包分析'


def argv():
    a = sys.argv
    return a[a.index('--') + 1:] if '--' in a else []


def pick_target(cx, cy, lo=4.0, hi=45.0):
    """在 (cx,cy) 附近挑一个"够大且完整"的网格当主体。"""
    best = None
    for o in bpy.data.objects:
        if o.type != 'MESH' or o.hide_render or o.hide_viewport:
            continue
        if o.name in ('Terrain', 'Water'):
            continue
        if o.get('cat') in ('terrain_cell', 'lod', 'veg'):
            continue
        try:
            bb = [o.matrix_world @ Vector(c) for c in o.bound_box]
        except Exception:
            continue
        xs = [v.x for v in bb]
        ys = [v.y for v in bb]
        zs = [v.z for v in bb]
        w = max(max(xs) - min(xs), max(ys) - min(ys))
        if not (lo <= w <= hi):
            continue
        ox, oy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
        d = math.hypot(ox - cx, oy - cy)
        if d > 220:
            continue
            # 分数：越近越好，但太小的不优先
        score = d - min(w, 30) * 2.0
        if best is None or score < best[0]:
            best = (score, o, (ox, oy, min(zs), max(zs), w))
    return best[1] if best else None, (best[2] if best else None)


def setup_world(sc):
    w = bpy.data.worlds.new('AB_W') if sc.world is None else sc.world
    sc.world = w
    w.use_nodes = True
    bg = w.node_tree.nodes.get('Background')
    if bg:
        bg.inputs['Color'].default_value = (0.55, 0.62, 0.72, 1.0)
        bg.inputs['Strength'].default_value = 1.0
    sun_d = bpy.data.lights.new('AB_Sun', 'SUN')
    sun_d.energy = 4.0
    sun_d.angle = math.radians(2.0)
    sun = bpy.data.objects.new('AB_Sun', sun_d)
    sc.collection.objects.link(sun)
    sun.rotation_euler = (math.radians(55), 0.0, math.radians(35))
    return sun


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--tag', default='v12')
    # ⚠️ 不要写成 `--at 2560,-1450`：cmd 会把逗号当分隔符，argparse 只会收到 2560（已知坑）
    ap.add_argument('--x', type=float, default=2560.0)
    ap.add_argument('--y', type=float, default=-1450.0)
    ap.add_argument('--out', default=r'D:/BrainMaker/_test/ab')
    ap.add_argument('--res', default='1280x720')
    a = ap.parse_args(argv())
    cx, cy = a.x, a.y
    os.makedirs(a.out, exist_ok=True)

    ob, info = pick_target(cx, cy)
    if ob is None:
        raise SystemExit('附近找不到合适的主体网格')
    ox, oy, zmin, zmax, w = info
    print('[ab] 主体 %s  centre=(%.1f,%.1f) z=[%.1f,%.1f] w=%.1f' % (ob.name, ox, oy, zmin, zmax, w))

    sc = bpy.context.scene
    for ep in ('BLENDER_EEVEE_NEXT', 'BLENDER_EEVEE'):
        try:
            sc.render.engine = ep
            break
        except Exception:
            continue
    print('[ab] engine=%s' % sc.render.engine)
    try:
        sc.eevee.taa_render_samples = 32
    except Exception:
        pass
    sc.view_settings.view_transform = 'Filmic' if 'Filmic' in [
        v.name for v in sc.view_settings.bl_rna.properties['view_transform'].enum_items] else 'Standard'

    setup_world(sc)

    # 相机：45° 俯角，正对主体
    dist = max(w * 1.5, 14.0)
    cam_d = bpy.data.cameras.new('AB_Cam')
    cam_d.lens = 40.0
    cam_d.clip_start = 0.1
    cam_d.clip_end = 20000.0
    cam = bpy.data.objects.new('AB_Cam', cam_d)
    sc.collection.objects.link(cam)
    sc.camera = cam
    tgt = Vector((ox, oy, zmin + (zmax - zmin) * 0.45))
    cam.location = tgt + Vector((dist * 0.72, -dist * 0.72, dist * 0.55))
    d = (tgt - cam.location)
    cam.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()

    rx, ry = [int(v) for v in a.res.split('x')]
    sc.render.resolution_x, sc.render.resolution_y = rx, ry
    sc.render.resolution_percentage = 100
    sc.render.image_settings.file_format = 'PNG'
    sc.render.film_transparent = False
    try:
        sc.eevee.use_raytracing = True
    except Exception:
        pass

    sc.render.filepath = os.path.join(a.out, '%s_on.png' % a.tag)
    print('[ab] 渲染 %s' % sc.render.filepath)
    bpy.ops.render.render(write_still=True)

    # ---- 关掉法线 / ORM：等同旧版（只有 albedo + 常量 0.85）
    n_nm = n_orm = 0
    for m in bpy.data.materials:
        if not m.use_nodes:
            continue
        nt = m.node_tree
        nm_nodes = [n for n in nt.nodes if n.type == 'NORMAL_MAP']
        sep_nodes = [n for n in nt.nodes if n.type in ('SEPARATE_COLOR', 'SEPARATE_RGB')]
        if not nm_nodes and not sep_nodes:
            continue
        bsdf = next((n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED'), None)
        drop = []
        for l in nt.links:
            if l.from_node in nm_nodes or l.from_node in sep_nodes:
                drop.append(l)
        for l in drop:
            nt.links.remove(l)
        if nm_nodes:
            n_nm += 1
        if sep_nodes:
            n_orm += 1
            if bsdf:
                bsdf.inputs['Roughness'].default_value = 0.85
                if 'Metallic' in bsdf.inputs:
                    bsdf.inputs['Metallic'].default_value = 0.0
    print('[ab] 断开法线 %d 个材质 / ORM %d 个材质' % (n_nm, n_orm))

    sc.render.filepath = os.path.join(a.out, '%s_off.png' % a.tag)
    print('[ab] 渲染 %s' % sc.render.filepath)
    bpy.ops.render.render(write_still=True)
    print('[ab] done')


if __name__ == '__main__':
    main()
