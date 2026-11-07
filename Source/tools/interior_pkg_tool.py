# -*- coding: utf-8 -*-
"""室内包工具（**在 Blender 里跑**，不是命令行脚本）。

用法（Blender → Scripting 工作区 → 打开本文件 → Run Script）：
  1. 先选**任意一个**室内件（右侧「自定义属性」里能看到 `int_pkg` 的那种）；
  2. 跑本脚本 → 它会：
       · 按 `int_pkg` 把**整包**一次选中（之后你可以 G / R 整包拖转）；
       · 打印这个包的件数、中心、以及**相对构建时位置**的累计位移。
  3. 拖完之后再跑一次 → 它会打印**可以直接粘进**
     `docs/世界与地编/interior_fit_overrides.csv` 的一行。

为什么需要它：场景 blend 是构建产物，室内件没有"包"这层父级，Blender 里没法整体抓取；
而且手动改**下次重建会被覆盖** —— 要把改动固化，必须写进修正表再重建。
"""
import bpy

PKG_KEY = 'int_pkg'
BUILT_KEY = 'built_loc'


def _pkg_of(ob):
    return ob.get(PKG_KEY) if ob else None


def main():
    ob = bpy.context.object
    pkg = _pkg_of(ob)
    if not pkg:
        # 没选中时，退而求其次：从所有对象里找一个有 int_pkg 的，只用于提示
        cands = sorted({o.get(PKG_KEY) for o in bpy.data.objects if o.get(PKG_KEY)})
        print('[pkg] 请先选中一个室内件。本场景的室内包：%s' % (', '.join(cands[:12]) or '(无)'))
        return

    objs = [o for o in bpy.data.objects if o.type == 'MESH' and o.get(PKG_KEY) == pkg]
    if not objs:
        print('[pkg] 包里没有对象：%s' % pkg)
        return

    # 1) 整包选中
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]

    # 2) 相对构建值的位移（多件取平均，刚体平移时每件相同）
    dx = dy = dz = 0.0
    n = 0
    for o in objs:
        b = o.get(BUILT_KEY)
        if not b:
            continue
        dx += o.location.x - float(b[0])
        dy += o.location.y - float(b[1])
        dz += o.location.z - float(b[2])
        n += 1
    if n:
        dx, dy, dz = dx / n, dy / n, dz / n

    print('[pkg] ===== %s =====' % pkg)
    print('[pkg] 已选中 %d 件（整包，可直接 G / R 拖转）' % len(objs))
    print('[pkg] 相对构建时位置：(%+.3f, %+.3f, %+.3f) m%s'
          % (dx, dy, dz, '' if n else ' —— 该包没有 built_loc 属性（旧版构建，重建一次即可）'))
    print('[pkg] 要把这个改动固化，请把下面这行的数字报给构建侧（或直接写进修正表）：')
    print('[pkg] %s,dx=%+.2f,dy=%+.2f,dz=%+.2f' % (pkg, dx, dy, dz))
    print('[pkg] === DONE ===')


main()
