"""把大陆裁剪成"官方地图框"范围，并把瓜玛岛从大陆场景里彻底去掉。

做的事：
  1. 按 export/world/map_area.json 生成裁剪掩码（框外一律不铺地面）
  2. 用补完高程 H4_full + 新掩码 + 补完色图重建 Terrain（面只在框内）
  3. 删掉框外的实体（瓜玛在 y≈-7000，整个在框外 → 自动清空）
  4. 用 water_level_map.npy 重建 Water，且只保留框内水面
  5. 删掉没有面的孤立顶点，减小体积

  blender -b deliverable/blender/continent/continent.blend -P tools/blender_crop_continent_to_map.py
"""
import bpy
import os
import sys
import json
import importlib.util

import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None
ROOT = r'D:/BrainMaker/大镖客2解包分析'
AREA = json.load(open(os.path.join(ROOT, 'export/world/map_area.json'), encoding='utf-8'))
H4 = os.path.join(ROOT, 'work/terrain/H4_full.npy')
GROUND = os.path.join(ROOT, 'export/world/world_ground_final_out.png')
BASE_MASK = os.path.join(ROOT, 'export/world/world_ground_mask_full.png')
MASK_OUT = os.path.join(ROOT, 'export/world/world_ground_mask_maparea.png')
LVP = os.path.join(ROOT, 'export/world/water_level_map.npy')
X0w, Y0w, WORLD = -7684.0, -8196.0, 12296.0


def build_mask():
    m = np.asarray(Image.open(BASE_MASK).convert('L')) > 10          # 行 0 = 北
    H, W = m.shape
    px0 = int(round(area_x0 := AREA['x0'] - X0w)); px1 = int(round(AREA['x1'] - X0w))
    py0 = int(round(Y0w + WORLD - AREA['y1'])); py1 = int(round(Y0w + WORLD - AREA['y0']))
    keep = np.zeros_like(m)
    keep[max(0, py0):py1, max(0, px0):px1] = True
    out = (m & keep).astype(np.uint8) * 255
    Image.fromarray(out).save(MASK_OUT)
    print('[mask] 框内保留 %.2f km²（原 %.2f km²）' % (out.mean() / 255 * WORLD * WORLD / 1e6,
                                                       m.mean() * WORLD * WORLD / 1e6))
    return MASK_OUT


def main():
    mask = build_mask()

    spec = importlib.util.spec_from_file_location('bc', os.path.join(ROOT, 'tools/blender_continent.py'))
    bc = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bc)
    bc.H4 = H4
    bc.GROUND_TEX = GROUND
    bc.GROUND_MASK = mask

    old = bpy.data.objects.get('Terrain')
    old_mat = old.data.materials[0] if old and old.data.materials else None
    if old:
        me = old.data
        bpy.data.objects.remove(old, do_unlink=True)
        if me.users == 0:
            bpy.data.meshes.remove(me)
    bc.terrain(0)
    ob = bpy.data.objects['Terrain']
    if old_mat is not None:
        ob.data.materials.clear()
        ob.data.materials.append(old_mat)
        for n in old_mat.node_tree.nodes:
            if n.type == 'TEX_IMAGE':
                n.image = bpy.data.images.load(GROUND, check_existing=True)
    print('[terrain] verts %d polys %d' % (len(ob.data.vertices), len(ob.data.polygons)))

    # 删孤立顶点（框外那部分顶点没有面）
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    loose = [v for v in bm.verts if not v.link_faces]
    n_loose = len(loose)
    if loose:
        bmesh.ops.delete(bm, geom=loose, context='VERTS')
    bm.to_mesh(ob.data)
    bm.free()
    ob.data.update()
    print('[terrain] 删除孤立顶点 %d → 剩 %d 顶点' % (n_loose, len(ob.data.vertices)))

    # 删框外实体（LIB 是模型库，保留）
    x0, x1, y0, y1 = AREA['x0'], AREA['x1'], AREA['y0'], AREA['y1']
    killed = 0
    keep_cols = {'LIB'}
    for c in bpy.data.collections:
        if c.name in keep_cols:
            continue
        for o in list(c.objects):
            lx, ly = o.matrix_world.translation.x, o.matrix_world.translation.y
            if not (x0 <= lx <= x1 and y0 <= ly <= y1):
                bpy.data.objects.remove(o, do_unlink=True)
                killed += 1
    print('[entities] 框外删除 %d 个对象，剩 %d' % (killed, len(bpy.data.objects)))

    # 重建水面（两级：Water_Main / Water_West），只保留框内
    #   2026-11-02：瀑布以西的新奥斯汀盆地比主水系低约 62 m，不能再用一个平面。
    if os.path.join(ROOT, 'tools') not in sys.path:
        sys.path.insert(0, os.path.join(ROOT, 'tools'))
    import water_two_levels as W
    made = W.build(box=(x0, x1, y0, y1), mat=W.water_material())
    print('[water] %s' % ', '.join('%s %d 面' % (k, len(v.data.polygons)) for k, v in made.items()))

    bpy.ops.wm.save_mainfile()
    print('SAVED')


if __name__ == '__main__':
    main()
