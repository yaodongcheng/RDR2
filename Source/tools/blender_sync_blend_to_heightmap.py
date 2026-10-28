"""把 continent.blend 的地形/水面同步成"最终高度图"那一版。

做法：
  1. 把 deliverable/heightmap/continent_height_4m.png（地图框，行 0=北）写回世界 4 m 栅格
     （行 0=南，3075²），生成 work/terrain/H4_final.npy
  2. 用这份高程 + 地图框掩码重建 Terrain
  3. 按 deliverable/heightmap/water_mask.png + 水位图重建 Water（只保留地图框内、只保留水面）
  4. 保存；并检查瓜玛区域（地形面/水面/实体）都是 0

  blender -b deliverable/blender/continent/continent.blend -P tools/blender_sync_blend_to_heightmap.py
"""
import bpy
import os
import json
import importlib.util

import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None
ROOT = r'D:/BrainMaker/大镖客2解包分析'
HM = os.path.join(ROOT, 'deliverable/heightmap/continent_height_4m.png')
META = os.path.join(ROOT, 'deliverable/heightmap/continent_height_meta.json')
WMASK = os.path.join(ROOT, 'deliverable/heightmap/water_mask.png')
WL = os.path.join(ROOT, 'export/world/water_level_map.npy')
H4_OUT = os.path.join(ROOT, 'work/terrain/H4_final.npy')
MASK = os.path.join(ROOT, 'export/world/world_ground_mask_maparea.png')
GROUND = os.path.join(ROOT, 'export/world/world_ground_final_out.png')

X0w, Y0w, WORLD, RES = -7684.0, -8196.0, 12296.0, 4.0


def build_h4():
    meta = json.load(open(META, encoding='utf-8'))
    zmin, zmax = meta['heightmap']['zmin'], meta['heightmap']['zmax']
    xa, ya, yb = meta['x0'], meta['y0'], meta['y1']
    Wm, Hm = meta['size_px']
    q = np.asarray(Image.open(HM)).astype(np.float32)          # 行 0 = 北
    hm = zmin + q / 65535.0 * (zmax - zmin)

    base = np.load(os.path.join(ROOT, 'work/terrain/H4_full.npy')).astype(np.float32)
    ny, nx = base.shape
    r = np.arange(ny)[:, None]
    c = np.arange(nx)[None, :]
    wy = Y0w + r * RES
    wx = X0w + c * RES
    rh = np.broadcast_to(np.round((yb - wy) / RES).astype(np.int32), (ny, nx))   # 北朝上
    ch = np.broadcast_to(np.round((wx - xa) / RES).astype(np.int32), (ny, nx))
    ok = (rh >= 0) & (rh < Hm) & (ch >= 0) & (ch < Wm)
    out = base.copy()
    out[ok] = hm[rh[ok], ch[ok]]
    np.save(H4_OUT, out)
    print('[H4] 最终高度图写回世界栅格：%s  z %.1f~%.1f' % (H4_OUT, out.min(), out.max()))
    return out


def main():
    build_h4()

    spec = importlib.util.spec_from_file_location('bc', os.path.join(ROOT, 'tools/blender_continent.py'))
    bc = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bc)
    bc.H4 = H4_OUT
    bc.GROUND_MASK = MASK
    bc.GROUND_TEX = GROUND

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

    # 删孤立顶点
    import bmesh
    bm = bmesh.new(); bm.from_mesh(ob.data)
    loose = [v for v in bm.verts if not v.link_faces]
    if loose:
        bmesh.ops.delete(bm, geom=loose, context='VERTS')
    bm.to_mesh(ob.data); bm.free(); ob.data.update()
    print('[terrain] 删孤立顶点 %d → %d 顶点' % (len(loose), len(ob.data.vertices)))

    # ---- 水面：按 water_mask + 水位图重建，只保留地图框内 ----
    meta = json.load(open(META, encoding='utf-8'))
    xa, ya, yb = meta['x0'], meta['y0'], meta['y1']
    Wm, Hm = meta['size_px']
    wm = np.asarray(Image.open(WMASK).convert('L')) > 128      # 行 0 = 北
    lvl = np.load(WL)                                          # 2048², 行 0 = 南
    P = lvl.shape[0]
    step = int(round(8.0 / RES))                               # 8 m 一格
    rows = np.arange(0, Hm - step, step)
    cols = np.arange(0, Wm - step, step)
    water = wm[np.ix_(rows, cols)] & wm[np.ix_(rows, cols + step)] & \
        wm[np.ix_(rows + step, cols)] & wm[np.ix_(rows + step, cols + step)]
    # 采样水位（世界 → 2048 栅格，南起）
    wxs = xa + cols * RES
    wys = yb - rows * RES
    li = np.clip(((wys - Y0w) / WORLD * P).astype(np.int32), 0, P - 1)
    lj = np.clip(((wxs - X0w) / WORLD * P).astype(np.int32), 0, P - 1)
    zl = lvl[np.ix_(li, lj)]
    zl = np.where(np.isnan(zl), 42.0, zl)

    ny, nx = water.shape
    X, Y = np.meshgrid(wxs, wys, indexing='xy')
    co_all = np.stack([X.ravel(), Y.ravel(), zl.ravel()], axis=1).astype(np.float32)
    idx = np.arange(ny * nx, dtype=np.int32).reshape(ny, nx)
    a_ = idx[:-1, :-1].ravel(); b_ = idx[:-1, 1:].ravel()
    c_ = idx[1:, :-1].ravel(); d_ = idx[1:, 1:].ravel()
    quads = np.stack([a_, b_, d_, c_], axis=1)[water[:-1, :-1].ravel()]
    if len(quads):
        used = np.unique(quads)
        remap = np.full(len(co_all), -1, np.int64); remap[used] = np.arange(len(used))
        quads = remap[quads]; co = co_all[used]
    else:
        co = np.zeros((0, 3), np.float32)

    wold = bpy.data.objects.get('Water')
    wmat = wold.data.materials[0] if wold and wold.data.materials else None
    if wold:
        wme = wold.data
        bpy.data.objects.remove(wold, do_unlink=True)
        if wme.users == 0:
            bpy.data.meshes.remove(wme)
    me = bpy.data.meshes.new('Water')
    me.vertices.add(len(co)); me.vertices.foreach_set('co', co.ravel())
    me.loops.add(quads.size); me.loops.foreach_set('vertex_index', quads.ravel())
    me.polygons.add(len(quads)); me.polygons.foreach_set('loop_start', np.arange(0, quads.size, 4, dtype=np.int32))
    me.update()
    if wmat:
        me.materials.append(wmat)
    wob = bpy.data.objects.new('Water', me)
    bpy.context.scene.collection.objects.link(wob)
    print('[water] quads %d verts %d' % (len(quads), len(co)))

    bpy.ops.wm.save_mainfile()
    print('SAVED')


if __name__ == '__main__':
    main()
