# -*- coding: utf-8 -*-
"""列出场景里被逐顶点贴地（snap_ground=1）的每一个对象：名字 / 所在类 / 尺寸 / 离地。

用途：核对「贴地」有没有误伤 —— 名单里若出现建筑、道具、载具、植被，就是误伤。

    blender -b <scene.blend> -P tools/_unbuffer.py -P tools/_probe_snap_list.py
"""
import bpy
import sys

ARGS = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []


def show_all():
    def walk(lc):
        lc.exclude = False
        lc.hide_viewport = False
        for c in lc.children:
            walk(c)
    walk(bpy.context.view_layer.layer_collection)
    bpy.context.view_layer.update()


show_all()

rows = []
for ob in bpy.data.objects:
    if ob.type != 'MESH' or not ob.get('snap_ground'):
        continue
    cls = ''
    for c in ob.users_collection:
        if c.name.startswith('C_') and '_' in c.name:
            cls = c.name[2:].split('_')[0]
            break
    d = ob.dimensions
    rows.append((cls, ob.name, d.x, d.y, d.z, ob.location.z))

print('[list] snap_ground 对象 %d 个' % len(rows))
for cls, n, dx, dy, dz, z in sorted(rows):
    print('[list] %-12s %-42s %6.1f x %6.1f x %5.2f m  z=%.1f'
          % (cls or '(no class)', n, dx, dy, dz, z))
print('[list] === DONE ===')
