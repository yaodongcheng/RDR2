# -*- coding: utf-8 -*-
"""按对象名前缀查材质：确认「无 albedo 的件」到底拿到了什么材质。

    blender -b <scene.blend> -P tools/_unbuffer.py -P tools/_probe_material.py -- i_c4db87de

输出每个命中对象的：材质名 / Base Color / 金属度 / 粗糙度。
判据：修好后应是 `ntex_wood` 一类（按类别猜的库贴图），不再是 `nonalbedo_warmgray`。
"""
import bpy
import sys

ARGS = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
PREFIX = ARGS[0] if ARGS else 'i_'

shown = 0
for ob in bpy.data.objects:
    if ob.type != 'MESH' or not ob.name.startswith(PREFIX):
        continue
    for slot in ob.material_slots:
        m = slot.material
        if not m:
            print('[mat] %-22s (无材质)' % ob.name)
            continue
        bc = ''
        if m.use_nodes:
            for n in m.node_tree.nodes:
                if n.type == 'BSDF_PRINCIPLED':
                    v = n.inputs['Base Color'].default_value
                    bc = '(%.2f, %.2f, %.2f)' % (v[0], v[1], v[2])
                    break
        print('[mat] %-22s 材质=%-22s 底色=%s 金属=%.2f 粗糙=%.2f'
              % (ob.name, m.name, bc, m.metallic, m.roughness))
        break
    shown += 1
    if shown >= 8:
        break
if not shown:
    print('[mat] 没有以 %r 开头的对象' % PREFIX)
print('[mat] === DONE ===')
