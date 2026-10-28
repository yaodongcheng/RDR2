"""给 sdn.blend 配一套"自然天空 + 太阳光"。

要点：
  1. 世界用 **Sky Texture (Nishita)** —— 物理大气散射，有真实的天空渐变、地平线雾化、日照色温
  2. **Sun 灯与天空太阳同向**，阴影方向一致
  3. 让视口的 **材质预览** 也显示场景世界（否则永远是灰底 studio HDRI）
  4. 可选：轻微的空气透视（距离雾），让 2.6 km 外不至于"一刀切"

用法：
  blender -b export/levels/world/blender/sdn.blend -P tools/blender_setup_sky.py -- \
      --out export/levels/world/blender/sdn.blend --shots DIR --views street,overview
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


def parse():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=os.path.join(ROOT, 'export/levels/world/blender/sdn.blend'))
    ap.add_argument('--shots', default=os.path.join(ROOT, 'export/levels/world/blender/shots'))
    ap.add_argument('--views', default='')
    ap.add_argument('--res', default='1600x900')
    ap.add_argument('--elevation', type=float, default=32.0, help='太阳高度角（度）')
    ap.add_argument('--rotation', type=float, default=135.0, help='太阳方位角（度）')
    ap.add_argument('--strength', type=float, default=0.42, help='天空强度')
    ap.add_argument('--sun-energy', type=float, default=3.5)
    return ap.parse_args(argv())


def setup_world(elev, rot, strength):
    w = bpy.data.worlds.get('Sky') or bpy.data.worlds.new('Sky')
    bpy.context.scene.world = w
    w.use_nodes = True
    nt = w.node_tree
    nt.nodes.clear()

    out = nt.nodes.new('ShaderNodeOutputWorld')
    bg = nt.nodes.new('ShaderNodeBackground')
    sky = nt.nodes.new('ShaderNodeTexSky')
    for t in ('MULTIPLE_SCATTERING', 'SINGLE_SCATTERING', 'NISHITA'):
        try:
            sky.sky_type = t
            break
        except Exception:
            continue
    sky.sun_elevation = math.radians(elev)
    sky.sun_rotation = math.radians(rot)
    for k, v in (('altitude', 200.0), ('air_density', 1.0),
                 ('aerosol_density', 1.6), ('dust_density', 1.6),
                 ('ozone_density', 1.0)):
        try:
            setattr(sky, k, v)
        except Exception:
            pass
    try:
        sky.sun_disc = False          # 不用贴图里的太阳盘，避免和 Sun 灯重复/错位
        sky.sun_size = math.radians(0.6)
    except Exception:
        pass

    nt.links.new(sky.outputs['Color'], bg.inputs['Color'])
    bg.inputs['Strength'].default_value = strength
    nt.links.new(bg.outputs['Background'], out.inputs['Surface'])
    print('WORLD: Nishita elev=%.0f rot=%.0f strength=%.2f' % (elev, rot, strength))


def setup_sun(elev, rot, energy):
    o = bpy.data.objects.get('Sun')
    if o is None:
        light = bpy.data.lights.new('Sun', 'SUN')
        o = bpy.data.objects.new('Sun', light)
        bpy.context.scene.collection.objects.link(o)
    o.data.energy = energy
    o.data.angle = math.radians(1.2)
    o.data.color = (1.0, 0.96, 0.90)
    # 让太阳灯从与天空太阳一致的方向照下来
    # Blender 的 Sun 沿 -Z 发光；先绕 X 抬起，再绕 Z 转到方位
    o.rotation_euler = (math.radians(90.0 - elev), 0.0, math.radians(rot - 90.0))
    print('SUN: energy=%.1f elev=%.0f rot=%.0f' % (energy, elev, rot))


def enable_scene_world_in_viewports():
    n = 0
    for scr in bpy.data.screens:
        for area in scr.areas:
            if area.type != 'VIEW_3D':
                continue
            sp = area.spaces.active
            try:
                sp.shading.use_scene_world = True
                n += 1
            except Exception:
                pass
            try:
                sp.clip_start = 1.0
                sp.clip_end = 20000.0
            except Exception:
                pass
    print('VIEWPORT scene world on:', n)


def add_cam(loc, look, lens=35):
    c = bpy.data.cameras.new('c')
    c.lens = lens
    c.clip_start = 1.0
    c.clip_end = 40000
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
        sc.eevee.taa_render_samples = 48
        sc.eevee.use_raytracing = True
    except Exception:
        pass
    w, h = [int(x) for x in res.split('x')]
    sc.render.resolution_x, sc.render.resolution_y = w, h
    sc.render.resolution_percentage = 100
    sc.render.image_settings.file_format = 'PNG'
    try:
        sc.view_settings.view_transform = 'AgX'
        sc.view_settings.look = 'AgX - Punchy'
        sc.view_settings.exposure = 0.3
    except Exception:
        pass
    sc.render.filepath = out
    bpy.ops.render.render(write_still=True)
    print('SHOT ->', out)


def main():
    a = parse()
    setup_world(a.elevation, a.rotation, a.strength)
    setup_sun(a.elevation, a.rotation, a.sun_energy)
    enable_scene_world_in_viewports()

    # 世界雾（空气透视）在 EEVEE 里会把整幅画面压黑，默认不加；需要时用 Mist 通道后期加

    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=a.out)
    print('SAVED', a.out)

    if a.views:
        os.makedirs(a.shots, exist_ok=True)
        views = {
            'street': (Vector((2500, -1200, 52.5)), Vector((2500, -1040, 55)), 24),
            'street2': (Vector((2620, -1180, 53)), Vector((2760, -1120, 56)), 28),
            'overview': (Vector((3050, -1950, 780)), Vector((2550, -1150, 45)), 40),
            'canal': (Vector((2560, -1130, 58)), Vector((2700, -1040, 52)), 28),
        }
        for v in a.views.split(','):
            if v not in views:
                continue
            loc, look, lens = views[v]
            render(add_cam(loc, look, lens), os.path.join(a.shots, f'sky_{v}.png'), a.res)


if __name__ == '__main__':
    main()
