"""把室内布局按 **MLO 实例变换** 合并进 willard.blend。

关键：室内件的坐标是 MLO 局部空间，世界变换来自 area ymap 里的
`roc_hse_int_lod` 实例（pos / quat），不是房子实例本身。

    world = T_mlo + R_mlo @ local
    q_world = q_mlo @ q_local
"""
import bpy
import os
from mathutils import Vector, Quaternion

ROOT = r'D:/BrainMaker/大镖客2解包分析'
WILLARD = os.path.join(ROOT, 'deliverable/blender/willard/willard.blend')
INTERIOR = os.path.join(ROOT, 'deliverable/blender/willard/roc_interior.blend')
OUT = os.path.join(ROOT, 'deliverable/blender/willard/willard_full.blend')

# roc_hse_int_lod 实例（area ymap: roc_01_.ymap）
MLO_POS = Vector((2990.42, 2188.85, 168.44))
# ymap 存 (x,y,z,w)=(0,0,-0.574,0.819) → Blender (w,x,y,z)，再取共轭
_qx, _qy, _qz, _qw = 0.0, 0.0, -0.574, 0.819
MLO_QUAT = Quaternion((_qw, -_qx, -_qy, -_qz))

bpy.ops.wm.open_mainfile(filepath=WILLARD)
print('mlo pos', [round(v, 2) for v in MLO_POS], 'quat', [round(v, 3) for v in MLO_QUAT])

with bpy.data.libraries.load(INTERIOR, link=False) as (src, dst):
    dst.objects = [n for n in src.objects if n.startswith('i_')]
print('appended', len(dst.objects))

col = bpy.data.collections.new('INTERIOR')
bpy.context.scene.collection.children.link(col)
# 阴影代理（roc_hse_shadowproxy）只用于投影，13x11x6 的盒子，绝不能渲染
# 室内"壳/木结构/代理"一律不渲染（它们自带屋顶，会和外壳重叠）
SKIP_HASHES = {
    '54b00fdf',  # shadowproxy
    '51b78358',  # reflection
    'cba915be',  # shell_main
    'ac262389',  # shell_bed01
    'e6649809',  # shell_bed02
    'b56905d2',  # main_details01
    '82519f88',  # main_details02
    'ae28fb80',  # bed01_details01
    '4be4a68c',  # bed02_details01
    'b2afc32a',  # bed01_logs   ← 带屋顶的木结构
    'd6a5cf80',  # bed02_logs   ← 带屋顶的木结构
    'b93ccef5',  # beams
    'f0eaad82',  # woodchunks
}
SKIP_HASH = ''
for ob in dst.objects:
    if ob is None:
        continue
    skip = ob.name.startswith('i_') and ob.name[2:10] in SKIP_HASHES
    local = ob.location.copy()
    lq = ob.rotation_quaternion.copy()
    col.objects.link(ob)
    ob.location = MLO_POS + (MLO_QUAT @ local)
    ob.rotation_mode = 'QUATERNION'
    ob.rotation_quaternion = MLO_QUAT @ lq
    ob.hide_render = skip
    ob.hide_viewport = skip

bpy.context.view_layer.update()

import numpy as np
def wb(objs):
    mn = np.array([1e9]*3); mx = np.array([-1e9]*3)
    for o in objs:
        for c in o.bound_box:
            w = o.matrix_world @ Vector(c)
            mn = np.minimum(mn, [w.x, w.y, w.z]); mx = np.maximum(mx, [w.x, w.y, w.z])
    return mn, mx
h = bpy.data.objects.get('e_246ed9d0')
a, b = wb([h])

# --- 垂直对齐：可见室内件的最低点 = 房子地面 + 0.15 ---
vis = [o for o in bpy.data.objects if o.name.startswith('i_') and not o.hide_render]
if vis:
    vmn, vmx = wb(vis)
    dz = (a[2] + 0.15) - vmn[2]
    print('vertical align dz = %+.2f m (interior zmin %.2f -> %.2f)' % (dz, vmn[2], vmn[2] + dz))
    for o in bpy.data.objects:
        if o.name.startswith('i_'):
            o.location.z += dz
    bpy.context.view_layer.update()
shell = [o for o in bpy.data.objects if o.name.startswith('i_cba915be')]
s1, s2 = wb(shell)
print('HOUSE x[%.2f,%.2f] y[%.2f,%.2f] z[%.2f,%.2f]' % (a[0], b[0], a[1], b[1], a[2], b[2]))
print('SHELL x[%.2f,%.2f] y[%.2f,%.2f] z[%.2f,%.2f]' % (s1[0], s2[0], s1[1], s2[1], s1[2], s2[2]))

# --- 对齐：室内壳体 yaw = 房子 yaw（墙平行），位置按 bbox 居中，z 贴地形 ---
import math as _M

def _yaw_of(o):
    q = o.rotation_quaternion
    return _M.degrees(_M.atan2(2*(q.w*q.z + q.x*q.y), 1-2*(q.y*q.y + q.z*q.z)))

bpy.context.view_layer.update()
_ha, _hb = wb([h])
_HC = Vector(((_ha[0]+_hb[0])/2, (_ha[1]+_hb[1])/2, _ha[2]))
_yh = _yaw_of(h)
_shell = [o for o in bpy.data.objects if o.name.startswith('i_cba915be')][0]
_ys = _yaw_of(_shell)
_delta = _yh - _ys
print('shell yaw %.1f° -> house yaw %.1f° (delta %+.1f°)' % (_ys, _yh, _delta))

_q = Quaternion((0, 0, 1), _M.radians(_delta))
_inter = [o for o in bpy.data.objects if o.name.startswith('i_')]
for o in _inter:
    o.location = _HC + (_q @ (o.location - _HC))
    o.rotation_quaternion = _q @ o.rotation_quaternion
bpy.context.view_layer.update()

_vis = [o for o in _inter if not o.hide_render]
_mn, _mx = wb(_vis)
_dx = (_ha[0]+_hb[0])/2 - (_mn[0]+_mx[0])/2
_dy = (_ha[1]+_hb[1])/2 - (_mn[1]+_mx[1])/2
for o in _inter:
    o.location.x += _dx; o.location.y += _dy
bpy.context.view_layer.update()

# z：贴地形（不是房子 bbox 底）
_me = bpy.data.objects.get('Terrain').data
_co = np.empty(len(_me.vertices)*3, dtype=np.float32); _me.vertices.foreach_get('co', _co); _co = _co.reshape(-1,3)
_gx, _gy = (_ha[0]+_hb[0])/2, (_ha[1]+_hb[1])/2
_d2 = (_co[:,0]-_gx)**2 + (_co[:,1]-_gy)**2
_gz = float(_co[int(np.argmin(_d2)), 2])
_mn, _mx = wb(_vis)
_dz = (_gz + 0.02) - _mn[2]
for o in _inter:
    o.location.z += _dz
bpy.context.view_layer.update()
_mn, _mx = wb(_vis)
print('ALIGN yaw %.1f° dx=%+.2f dy=%+.2f dz=%+.2f  interior z[%.2f,%.2f] ground %.2f' % (
    _yaw_of(_shell), _dx, _dy, _dz, _mn[2], _mx[2], _gz))

bpy.ops.wm.save_as_mainfile(filepath=OUT)
print('SAVED', OUT)
