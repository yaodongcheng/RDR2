# -*- coding: utf-8 -*-
"""把「被误标成地形 patch」的对象从 HIDDEN_TERRAIN_CELL 放回可见。

## 背景（2026-10-29 用户报的 bug）

构建时 `TERRAIN_CELL` 正则写得太宽：
    (_r_c_\\d+|_rc_\\d+|_ground\\d*$|_terrain)
于是名字**以 `_terrain` 结尾**的正常地面件（例如公园草坪
`new_gar06_park_terrain`）也被当成 `__hd_0_` 地形 cell，跟着一起被隐藏 ——
用户看到的就是"红框里该是草坪，结果露出白色地形色图"。

真正该隐藏的是 `__hd_0_` 地形 patch（它们与 H4 地形完全重叠）。
本脚本的判定与 `hide_terrain_patches.py` 一致：**名字里没有 `__hd_0_` 的一律放回可见**。

    blender -b <blend> --python tools/_unbuffer.py -P tools/fix_mis_tagged_hidden.py [-- --dry]

注意：会存盘（原地）。改前建议先确认 `*.blend1` 备份存在。
"""
import bpy
import os
import sys
import argparse

COL = 'HIDDEN_TERRAIN_CELL'


def argv():
  a = sys.argv
  return a[a.index('--') + 1:] if '--' in a else []


def main():
  ap = argparse.ArgumentParser()
  ap.add_argument('--dry', action='store_true')
  ap.add_argument('--col', default=COL)
  a = ap.parse_args(argv())

  hid = bpy.data.collections.get(a.col)
  if hid is None:
    print('[fix] 没有集合 %s，无事可做' % a.col)
    return
  ent = bpy.data.collections.get('ENTITIES')
  if ent is None:
    raise SystemExit('没有 ENTITIES 集合')

  victims = [o for o in hid.all_objects if '__hd_0_' not in o.name.lower()]
  print('[fix] %s 共 %d 个；其中名字不含 __hd_0_ 的 %d 个（应放回可见）'
        % (a.col, len(hid.all_objects), len(victims)))
  for o in victims[:20]:
    print('      - %s (tag=%s)' % (o.name, o.get('hide_tag', '')))

  if a.dry or not victims:
    print('[fix] dry-run / 无需处理')
    return

  for o in victims:
    for c in list(o.users_collection):
      c.objects.unlink(o)
    ent.objects.link(o)
    # 清掉错误的 hide_tag，避免下一轮又被当成地形 cell
    if o.get('hide_tag') == 'terrain_cell':
      o['hide_tag'] = ''
  # 重新打开集合可见性（放回的对象要能看见）
  hid.hide_viewport = True
  hid.hide_render = True
  print('[fix] 已放回 ENTITIES：%d 个；集合 %s 仍隐藏（保留真正的 __hd_0_ patch）'
        % (len(victims), a.col))

  out = bpy.data.filepath
  bpy.ops.wm.save_as_mainfile(filepath=out)
  print('[fix] saved %s (%.2f GB)' % (out, os.path.getsize(out) / 1e9))


if __name__ == '__main__':
  main()
