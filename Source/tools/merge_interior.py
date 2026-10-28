# -*- coding: utf-8 -*-
"""把某个室内包（`<pkg>_int`）的 MLO 布局，按**真实 MLO 实例变换**装进一个房子 blend。

与 `merge_interior_into_willard.py` 的区别：
- 不再硬编码 `roc_hse_int_lod` 替身；改为用 `tools/locate_interior_mlo.py` 的同一套查表逻辑，
  从 tiles 里取该包的 `<pkg>_int` / `<pkg>_int_lod` / `<pkg>_int_main` 实例（**这才是游戏真正的摆位**）。
- 默认 `--no-align`：只做 MLO 变换，不再"旋转到房子 yaw + bbox 居中"。
  那两步是为了补偿替身的 100° yaw 误差，用真实例时反而会破坏正确摆位。
- 需要时仍可用 `--align` 复刻老行为做对照。

用法：
    blender -b deliverable/blender/willard/willard.blend -P tools/merge_interior.py -- \
      --pkg roc_house_int --interior deliverable/blender/willard/roc_interior.blend \
      --out deliverable/blender/willard/willard_truemlo.blend --no-align
"""
import bpy
import os
import sys
import json
import glob
import math
import argparse
import numpy as np
from mathutils import Vector, Quaternion

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TILES = os.path.join(ROOT, 'export/world/continent/tiles')
NAMES = os.path.join(ROOT, 'tools/rdr2rpf/bin/Release/net9.0/names.txt')

# 默认：roc 这一栋的"假几何"表（其它房子要各自确认，见交接文档 §三）
SKIP_DEFAULT = '54b00fdf,51b78358,cba915be,ac262389,e6649809,b56905d2,82519f88,ae28fb80,4be4a68c,b2afc32a,d6a5cf80,b93ccef5,f0eaad82'


def argv():
    a = sys.argv
    return a[a.index('--') + 1:] if '--' in a else []


def joaat(s):
    h = 0
    for c in s.lower().encode():
        h = (h + c) & 0xFFFFFFFF
        h = (h + (h << 10)) & 0xFFFFFFFF
        h ^= h >> 6
    h = (h + (h << 3)) & 0xFFFFFFFF
    h ^= h >> 11
    return (h + (h << 15)) & 0xFFFFFFFF


def find_mlo(pkg):
    """pkg → (name, pos, quat_xyzw) ; 与 locate_interior_mlo.py 同规则。"""
    names = {}
    with open(NAMES, encoding='latin1', errors='ignore') as f:
        for l in f:
            n = l.strip()
            if n:
                names.setdefault(joaat(n), n.lower())
    want = [pkg, pkg + '_lod', pkg + '_main']
    hit = {}
    for p in glob.glob(os.path.join(TILES, '*.json')):
        for e in json.load(open(p, encoding='utf-8')):
            n = names.get(e[0])
            if not n:
                continue
            b = n.split('/')[-1]
            if b in want and b not in hit:
                hit[b] = e
    for w in want:
        if w in hit:
            e = hit[w]
            return w, Vector((e[1], e[2], e[3])), (e[4], e[5], e[6], e[7])
    return None, None, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pkg', required=True)
    ap.add_argument('--interior', required=True)
    ap.add_argument('--house', default='')
    ap.add_argument('--out', required=True)
    ap.add_argument('--align', action='store_true', help='复刻老行为：旋转到房子 yaw + bbox 居中 + 贴地形')
    ap.add_argument('--skip-hashes', default=SKIP_DEFAULT)
    ap.add_argument('--extra-yaw', type=float, default=0.0,
                    help='在 MLO 变换之上再绕 Z 转一度数（室内局部空间的额外旋转，默认 0）')
    ap.add_argument('--show-shell', action='store_true', help='把房间壳也显示出来（测量用）')
    a = ap.parse_args(argv())

    name, P, q = find_mlo(a.pkg)
    if P is None:
        raise SystemExit('找不到 %s 的 MLO 实例（见 tools/locate_interior_mlo.py）' % a.pkg)
    Q = Quaternion((q[3], -q[0], -q[1], -q[2]))   # 共轭（与全图一致）
    print('[merge] MLO %s pos %s yaw %.1f°' % (name, [round(v, 2) for v in P],
          math.degrees(math.atan2(2 * (q[3] * q[2] + q[0] * q[1]), 1 - 2 * (q[1] ** 2 + q[2] ** 2)))))

    with bpy.data.libraries.load(a.interior, link=False) as (src, dst):
        dst.objects = [n for n in src.objects if n.startswith('i_')]
    col = bpy.data.collections.new('INTERIOR')
    bpy.context.scene.collection.children.link(col)
    skipset = {s.strip() for s in a.skip_hashes.split(',') if s.strip()}
    for ob in dst.objects:
        if ob is None:
            continue
        skip = ob.name[2:10] in skipset
        local = ob.location.copy()
        lq = ob.rotation_quaternion.copy()
        col.objects.link(ob)
        ob.location = P + (Q @ local)
        ob.rotation_mode = 'QUATERNION'
        ob.rotation_quaternion = Q @ lq
        ob.hide_render = skip and not (a.show_shell and ob.name.startswith('i_cba915be'))
        ob.hide_viewport = skip and not (a.show_shell and ob.name.startswith('i_cba915be'))
    if a.extra_yaw:
        R = Quaternion((0, 0, 1), math.radians(a.extra_yaw))
        for ob in dst.objects:
            if ob is None:
                continue
            ob.location = P + (R @ (ob.location - P))
            ob.rotation_quaternion = R @ ob.rotation_quaternion
        print('[merge] extra yaw %+.1f°' % a.extra_yaw)
    bpy.context.view_layer.update()

    def wb(objs):
        mn = np.array([1e18] * 3); mx = np.array([-1e18] * 3)
        for o in objs:
            if o.type != 'MESH':
                continue
            for c in o.bound_box:
                w = o.matrix_world @ Vector(c)
                mn = np.minimum(mn, [w.x, w.y, w.z]); mx = np.maximum(mx, [w.x, w.y, w.z])
        return mn, mx

    house = bpy.data.objects.get('e_246ed9d0')
    if house is None:
        cands = [o for o in bpy.data.objects if o.type == 'MESH' and o.name.startswith('e_')]
        house = max(cands, key=lambda o: len(o.data.polygons)) if cands else None
    inter = [o for o in bpy.data.objects if o.name.startswith('i_')]

    if a.align and house is not None:
        ha, hb = wb([house])
        HC = Vector(((ha[0] + hb[0]) / 2, (ha[1] + hb[1]) / 2, ha[2]))
        def yaw_of(o):
            qq = o.rotation_quaternion
            return math.degrees(math.atan2(2 * (qq.w * qq.z + qq.x * qq.y), 1 - 2 * (qq.y ** 2 + qq.z ** 2)))
        shells = [o for o in inter if o.name.startswith('i_cba915be')]
        if shells:
            delta = yaw_of(house) - yaw_of(shells[0])
            rq = Quaternion((0, 0, 1), math.radians(delta))
            for o in inter:
                o.location = HC + (rq @ (o.location - HC))
                o.rotation_quaternion = rq @ o.rotation_quaternion
            bpy.context.view_layer.update()
            print('[merge] align: 旋转 %+.1f°' % delta)
        vis = [o for o in inter if not o.hide_render]
        mn, mx = wb(vis)
        dx = (ha[0] + hb[0]) / 2 - (mn[0] + mx[0]) / 2
        dy = (ha[1] + hb[1]) / 2 - (mn[1] + mx[1]) / 2
        for o in inter:
            o.location.x += dx; o.location.y += dy
        bpy.context.view_layer.update()
        print('[merge] align: 居中 dx=%+.2f dy=%+.2f' % (dx, dy))

    if house is not None:
        ha, hb = wb([house])
        vis = [o for o in inter if not o.hide_render]
        ca, cb = wb(vis)
        print('[merge] HOUSE x[%.2f,%.2f] y[%.2f,%.2f] z[%.2f,%.2f]' % (ha[0], hb[0], ha[1], hb[1], ha[2], hb[2]))
        print('[merge] INTER x[%.2f,%.2f] y[%.2f,%.2f] z[%.2f,%.2f]' % (ca[0], cb[0], ca[1], cb[1], ca[2], cb[2]))
        print('[merge] 四边间隙 X左%+.2f X右%+.2f Y下%+.2f Y上%+.2f  z 底%+.2f 顶%+.2f' % (
            ca[0] - ha[0], hb[0] - cb[0], ca[1] - ha[1], hb[1] - cb[1], ca[2] - ha[2], hb[2] - cb[2]))

    bpy.ops.wm.save_as_mainfile(filepath=a.out)
    print('[merge] saved', a.out)


if __name__ == '__main__':
    main()
