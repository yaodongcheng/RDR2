# -*- coding: utf-8 -*-
"""把已有 blend 里的水面换成一张蓝色平面（1 quad，z=40.5 游戏真值）。

原水面：2048² 采样 → 285,550 quads / 57 万三角面 / 半透明 → 视口 overdraw 卡顿。
用法：blender -b <blend> -P tools/replace_water_plane.py
"""
import bpy, os

ZW = 40.5
X0, Y0, WW = -7684.0, -8196.0, 12296.0


def main():
    old = bpy.data.objects.get('Water')
    if old is not None:
        bpy.data.objects.remove(old, do_unlink=True)
        print('[water] 已删除旧水面')
    me = bpy.data.meshes.new('Water')
    me.from_pydata([(X0, Y0, ZW), (X0 + WW, Y0, ZW),
                    (X0 + WW, Y0 + WW, ZW), (X0, Y0 + WW, ZW)], [], [(0, 1, 2, 3)])
    me.update()
    mat = bpy.data.materials.get('water') or bpy.data.materials.new('water')
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get('Principled BSDF')
    if bsdf:
        bsdf.inputs['Base Color'].default_value = (0.09, 0.22, 0.38, 1)
        bsdf.inputs['Roughness'].default_value = 0.15
        if 'Alpha' in bsdf.inputs:
            bsdf.inputs['Alpha'].default_value = 0.85
    try:
        mat.blend_method = 'BLEND'
    except Exception:
        pass
    me.materials.append(mat)
    ob = bpy.data.objects.new('Water', me)
    bpy.context.scene.collection.objects.link(ob)
    print('[water] 已替换为单平面 z=%.1f（1 quad）' % ZW)
    p = bpy.data.filepath
    bpy.ops.wm.save_mainfile()
    print('[water] saved %.2f GB' % (os.path.getsize(p) / 1e9))


main()
