# -*- coding: utf-8 -*-
"""离线汇总「用户在 Blender 里改过的分类」：读每个对象的 cls_ui，与 cls_key 对比。

    blender -b <blend> -P tools/collect_class_ui.py
    # 或由驱动批量跑（见 tools/build_regions.py 的 --collect-ui）

输出（stdout）：每行 `名字<TAB>原类<TAB>用户改成的类`，并给一份按「原类->新类」的统计。
用途：用户手工标的对象 → 推导名字规则 → 回填纠错清单/class_rules。
"""
import collections

import bpy


def main():
    rows = []
    tagged = 0
    for ob in bpy.context.scene.objects:
        v = ob.get('cls_ui_key')     # 下拉选中的字符串 key（update 回调写入）
        if not v or v == '__keep__':
            continue
        tagged += 1
        cur = ob.get('cls_key') or ''
        rows.append((ob.name, cur, v))
    stat = collections.Counter('%s->%s' % (c, v) for _, c, v in rows)
    changed = sum(1 for _, c, v in rows if c != v)
    print('[clsui] tagged=%d changed=%d / objects=%d'
          % (tagged, changed, len(bpy.context.scene.objects)))
    for k, n in sorted(stat.items(), key=lambda kv: -kv[1]):
        print('[clsui] %-30s %d' % (k, n))
    for name, cur, v in sorted(rows):
        mark = '=' if cur == v else '->'
        print('%s\t%s\t%s\t%s' % (name, cur, mark, v))


main()
