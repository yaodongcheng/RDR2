"""用"补完版"输入重建 continent.blend 里的 Terrain 对象。

做了两件事：
  1. 修 blender_continent.terrain() 里地面掩码南北翻转的 bug（已在源码里修）
  2. 用 H4_full.npy（含 outskirts 外延地形）+ world_ground_mask_full.png 重建整块地形

用法：
  RDR2_H4=... RDR2_MASK=... RDR2_GROUND=... \
  blender -b deliverable/blender/continent/continent.blend -P tools/blender_rebuild_terrain_fixed.py
"""
import bpy
import os
import sys
import importlib.util

ROOT = r'D:/BrainMaker/大镖客2解包分析'

H4 = os.environ.get('RDR2_H4', os.path.join(ROOT, 'work/terrain/H4_full.npy'))
MASK = os.environ.get('RDR2_MASK', os.path.join(ROOT, 'export/world/world_ground_mask_full.png'))
GROUND = os.environ.get('RDR2_GROUND', os.path.join(ROOT, 'export/world/world_ground_final_out.png'))

spec = importlib.util.spec_from_file_location('bc', os.path.join(ROOT, 'tools/blender_continent.py'))
bc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bc)

bc.H4 = H4
bc.GROUND_MASK = MASK
bc.GROUND_TEX = GROUND
print('rebuild Terrain with')
print('  H4    ', H4)
print('  MASK  ', MASK)
print('  GROUND', GROUND)

old = bpy.data.objects.get('Terrain')
old_mat = None
if old is not None:
    old_mat = old.data.materials[0] if old.data.materials else None
    me = old.data
    bpy.data.objects.remove(old, do_unlink=True)
    if me.users == 0:
        bpy.data.meshes.remove(me)
    print('old Terrain removed; material kept:', old_mat.name if old_mat else None)

bc.terrain(0)

ob = bpy.data.objects['Terrain']
# 复用原材质（保持节点/贴图设置），把新网格指回去
if old_mat is not None:
    ob.data.materials.clear()
    ob.data.materials.append(old_mat)
    # 材质里的地面贴图指向补完版
    nt = old_mat.node_tree
    for n in nt.nodes:
        if n.type == 'TEX_IMAGE':
            img = bpy.data.images.load(GROUND, check_existing=True)
            img.colorspace_settings.name = 'sRGB'
            n.image = img
            print('material texture →', img.name, tuple(img.size))

print('new Terrain verts', len(ob.data.vertices), 'polys', len(ob.data.polygons))
bpy.ops.wm.save_mainfile()
print('SAVED')
