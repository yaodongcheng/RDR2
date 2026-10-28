# -*- coding: utf-8 -*-
"""修「铁轨陷进地面」：把轨道件（轨面/枕木/道床，不含桥墩栈桥）抬到地形上方。

判据：object bbox 底 zmin < 地形 z + gap  ⇒ 整体上移 (地形 z + gap - zmin)。
桥/栈桥（_bri/_tres）不动 —— 它们的底本来就该插进地里。

    blender -b <blend> -P tools/fix_rail_sink.py -- [--gap 0.15] [--apply]
"""
import bpy, numpy as np, math, sys, collections
from mathutils import Vector

CELL = 2.0


def argv():
    a = sys.argv
    return a[a.index('--') + 1:] if '--' in a else []


def wbb(o):
    mn = Vector((1e18,) * 3); mx = Vector((-1e18,) * 3)
    for c in o.bound_box:
        p = o.matrix_world @ Vector(c)
        for i in range(3):
            mn[i] = min(mn[i], p[i]); mx[i] = max(mx[i], p[i])
    return mn, mx


def main():
    args = argv()
    gap = 0.15
    if '--gap' in args:
        gap = float(args[args.index('--gap') + 1])
    apply_ = '--apply' in args

    ter = bpy.data.objects['Terrain']
    Minv = ter.matrix_world.inverted()
    dir_local = (Minv.to_3x3() @ Vector((0.0, 0.0, -1.0))).normalized()

    def tz(x, y):
        """从 (x,y,500) 垂直向下打射线打到 Terrain，返回命中点世界 z。"""
        o_local = Minv @ Vector((x, y, 500.0))
        hit, loc, nor, idx = ter.ray_cast(o_local, dir_local, distance=2000.0)
        if not hit:
            return float('nan')
        return float((ter.matrix_world @ loc).z)

    stat = collections.Counter()
    worst = collections.defaultdict(float)
    todo = []
    for o in bpy.context.scene.objects:
        if o.type != 'MESH' or 'n_1114_r_' not in o.name:
            continue
        l = o.name.lower()
        if '_bri' in l or '_tres' in l:
            stat['跳过(桥/栈桥)'] += 1
            continue
        mn, mx = wbb(o); c = (mn + mx) / 2
        t = tz(c.x, c.y)
        if math.isnan(t):
            stat['无地形'] += 1
            continue
        need = t + gap - mn.z
        if need > 0.02:
            line = 'r_a' if '_r_a_' in l else ('r_b' if '_r_b_' in l else 'r_c')
            stat[line] += 1
            worst[line] = max(worst[line], need)
            todo.append((o, need))
        else:
            stat['已正常'] += 1

    print('[lift] gap=%.2f  待抬升 %d 件' % (gap, len(todo)))
    for k, v in stat.items():
        print('    %-12s %d' % (k, v))
    for k, v in worst.items():
        print('    %s 最大抬升 %.2f m' % (k, v))
    if not apply_:
        print('[lift] dry-run，加 --apply 落盘')
        return
    for o, need in todo:
        o.location.z += need
    bpy.context.view_layer.update()
    print('[lift] 已抬升 %d 件' % len(todo))
    p = bpy.data.filepath
    bpy.ops.wm.save_mainfile()
    print('[lift] saved', p)


main()
