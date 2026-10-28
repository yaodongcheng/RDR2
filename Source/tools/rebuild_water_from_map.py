# -*- coding: utf-8 -*-
"""用 water_level_map.npy（每像素水位，NaN=陆地）重建 Water 网格。在 Blender 里跑。"""
import bpy, os, numpy as np
ROOT = r'D:/BrainMaker/大镖客2解包分析'
LVP = os.path.join(ROOT, 'export/world/water_level_map.npy')
X0, Y0 = -7684.0, -8196.0
P = 2048; RES = 12296.0 / P

lvl = np.load(LVP)
wet = ~np.isnan(lvl)
s = max(1, int(round(8.0 / RES)))
rows = np.arange(0, P - s, s); cols = np.arange(0, P - s, s)
W4 = wet[np.ix_(rows, cols)] & wet[np.ix_(rows, cols + s)] & wet[np.ix_(rows + s, cols)] & wet[np.ix_(rows + s, cols + s)]
Lv = lvl[np.ix_(rows, cols)]
ny, nx = len(rows), len(cols)
X, Y = np.meshgrid(X0 + cols * RES, Y0 + rows * RES, indexing='xy')
co_all = np.stack([X.ravel(), Y.ravel(), Lv.ravel()], axis=1).astype(np.float32)
idx2 = np.arange(ny * nx, dtype=np.int32).reshape(ny, nx)
a_ = idx2[:-1, :-1].ravel(); b_ = idx2[:-1, 1:].ravel(); c_ = idx2[1:, :-1].ravel(); d_ = idx2[1:, 1:].ravel()
quads = np.stack([a_, b_, d_, c_], axis=1)[W4[:-1, :-1].ravel()]
# 只保留被四边形引用到的顶点（否则干地顶点会留 NaN 的 z）
used = np.unique(quads)
remap = np.full(len(co_all), -1, np.int64); remap[used] = np.arange(len(used))
quads = remap[quads]
co = co_all[used]
print('[W] quads', len(quads))
old = bpy.data.objects.get('Water')
mat = old.data.materials[0] if old and old.data.materials else None
if old: bpy.data.objects.remove(old, do_unlink=True)
me = bpy.data.meshes.new('Water')
me.vertices.add(len(co)); me.vertices.foreach_set('co', co.ravel())
me.loops.add(quads.size); me.loops.foreach_set('vertex_index', quads.ravel())
me.polygons.add(len(quads)); me.polygons.foreach_set('loop_start', np.arange(0, quads.size, 4, dtype=np.int32))
me.update()
if mat: me.materials.append(mat)
ob = bpy.data.objects.new('Water', me)
bpy.context.scene.collection.objects.link(ob)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(ROOT, 'deliverable/blender/continent/continent.blend'))
print('[W] saved')
