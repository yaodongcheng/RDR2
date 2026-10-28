"""在 Blender GUI 里跑（Scripting → Open → Run Script）。

结果同时写入：
  D:/BrainMaker/大镖客2解包分析/raw/_scratch/walls_report.txt
跑完直接把这个 txt 发给我（或告诉我已生成）。
"""
import bpy
import os
import numpy as np
from mathutils import Vector

OUT = r'D:/BrainMaker/大镖客2解包分析/raw/_scratch/walls_report.txt'
LINES = []

def p(*args):
    s = ' '.join(str(a) for a in args)
    LINES.append(s)

def wall_pts(o, nz_max=0.35):
    mw = o.matrix_world
    me = o.data
    nm = mw.to_3x3().inverted().transposed()
    idx = set()
    for poly in me.polygons:
        n = (nm @ poly.normal).normalized()
        if abs(n.z) < nz_max:
            idx.update(poly.vertices)
    if not idx:
        return np.zeros((0, 3))
    return np.array([(mw @ me.vertices[i].co)[:] for i in idx], dtype=np.float64)

def foot(pts, tag):
    if len(pts) == 0:
        p('%-14s EMPTY' % tag); return None, None
    mn = pts.min(0); mx = pts.max(0)
    p('%-14s n=%-6d  X[%9.2f,%9.2f] Y[%9.2f,%9.2f] Z[%8.2f,%8.2f]  占地 %.2f x %.2f' % (
        tag, len(pts), mn[0], mx[0], mn[1], mx[1], mn[2], mx[2], mx[0]-mn[0], mx[1]-mn[1]))
    return mn, mx

p('=' * 76)
house = bpy.data.objects.get('e_246ed9d0')
if house:
    hp = wall_pts(house)
    hmn, hmx = foot(hp, 'HOUSE walls')

p('')
p('房间壳:')
allp = []
for nm, hx in [('shell_main', 'cba915be'), ('bed01', 'ac262389'), ('bed02', 'e6649809')]:
    objs = [o for o in bpy.data.objects if o.name.startswith('i_' + hx)]
    if not objs:
        p('%-14s MISSING' % nm); continue
    pts = wall_pts(objs[0])
    foot(pts, nm)
    if len(pts): allp.append(pts)

if allp and house:
    a = np.vstack(allp)
    amn, amx = foot(a, 'ROOMS ALL')
    p('')
    p('对比:')
    p('  house  %.2f x %.2f' % (hmx[0]-hmn[0], hmx[1]-hmn[1]))
    p('  rooms  %.2f x %.2f  (%.1f%% x %.1f%%)' % (
        amx[0]-amn[0], amx[1]-amn[1],
        100*(amx[0]-amn[0])/(hmx[0]-hmn[0]), 100*(amx[1]-amn[1])/(hmx[1]-hmn[1])))
    p('  house center (%.2f, %.2f)' % ((hmn[0]+hmx[0])/2, (hmn[1]+hmx[1])/2))
    p('  rooms center (%.2f, %.2f)' % ((amn[0]+amx[0])/2, (amn[1]+amx[1])/2))
    p('  shift needed dx=%+.2f dy=%+.2f' % (
        (hmn[0]+hmx[0])/2 - (amn[0]+amx[0])/2,
        (hmn[1]+hmx[1])/2 - (amn[1]+amx[1])/2))

root = bpy.data.objects.get('INTERIOR_ROOT')
if root:
    p('')
    p('INTERIOR_ROOT:')
    p('  location (%.2f, %.2f, %.2f)' % tuple(root.location))
    p('  rotation Z %.2f deg' % (root.rotation_euler.z * 57.2957795))

p('=' * 76)

os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, 'w', encoding='utf-8') as f:
    f.write('\n'.join(LINES))
print('\n'.join(LINES))
print('\n>>> 已写入:', OUT)
