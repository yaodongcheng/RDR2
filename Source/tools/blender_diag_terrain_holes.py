"""诊断 continent.blend 里的地形空洞：把 Terrain 面中心栅格化，输出"有面/无面"图。

  blender -b deliverable/blender/continent/continent.blend -P tools/blender_diag_terrain_holes.py
"""
import bpy
import numpy as np

OUT = r'D:/BrainMaker/大镖客2解包分析/work/verify/terrain_faces_mask.png'
N = 1024

ob = bpy.data.objects.get('Terrain')
print('objects', len(bpy.data.objects))
print('collections', [c.name for c in bpy.data.collections])
if ob is None:
    print('!! no Terrain object')
else:
    me = ob.data
    print('Terrain verts', len(me.vertices), 'polys', len(me.polygons))
    co = np.zeros(len(me.vertices) * 3, dtype=np.float32)
    me.vertices.foreach_get('co', co)
    co = co.reshape(-1, 3)
    print('bbox', co.min(0), co.max(0))

    cent = np.zeros(len(me.polygons) * 3, dtype=np.float32)
    me.polygons.foreach_get('center', cent)
    cent = cent.reshape(-1, 3)

    x0, y0 = co[:, 0].min(), co[:, 1].min()
    x1, y1 = co[:, 0].max(), co[:, 1].max()
    print('grid x', x0, x1, 'y', y0, y1)
    gx = np.clip(((cent[:, 0] - x0) / (x1 - x0) * (N - 1)).astype(np.int32), 0, N - 1)
    gy = np.clip(((cent[:, 1] - y0) / (y1 - y0) * (N - 1)).astype(np.int32), 0, N - 1)
    m = np.zeros((N, N), np.uint8)
    m[gy, gx] = 1
    # 膨胀一格再腐蚀，避免因为面中心采样稀疏产生假洞
    from PIL import Image
    im = Image.fromarray(m * 255)
    m2 = np.asarray(im.filter(__import__('PIL.ImageFilter', fromlist=['MaxFilter']).MaxFilter(5)))
    m2 = np.asarray(Image.fromarray(m2).filter(__import__('PIL.ImageFilter', fromlist=['MinFilter']).MinFilter(3)))
    Image.fromarray(m2).save(OUT)
    print('missing %.2f%%  -> %s' % (100 * (m2 == 0).mean(), OUT))
    # 找出最大的空洞连通域（网格法）
    from scipy import ndimage
    lab, n = ndimage.label(m2 == 0)
    sizes = ndimage.sum(m2 == 0, lab, range(1, n + 1))
    order = np.argsort(sizes)[::-1][:10]
    for i in order:
        if sizes[i] < (N * N) * 0.001:
            continue
        ys, xs = np.where(lab == i + 1)
        print('  hole area %.2f%%  world x[%.0f,%.0f] y[%.0f,%.0f]' % (
            100 * sizes[i] / (N * N),
            x0 + xs.min() / (N - 1) * (x1 - x0), x0 + xs.max() / (N - 1) * (x1 - x0),
            y0 + ys.min() / (N - 1) * (y1 - y0), y0 + ys.max() / (N - 1) * (y1 - y0)))
