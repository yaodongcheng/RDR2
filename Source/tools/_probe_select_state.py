# -*- coding: utf-8 -*-
"""诊断：哪些对象「看得见但选不中」。

判据（Blender 数据层）：
  · `Object.hide_select` = True  → 视口里点不中（Outliner 仍能选）
  · 对象挂在**多个集合**里 → 一处藏、一处显，状态容易对不上
  · 对象不在任何集合里（游离）→ 不会画，也不会被点中
  · 所在集合的 LayerCollection `exclude=True` → 不在当前视层（不画、不可选）
  · 所在集合的 LayerCollection `hide_viewport=True` → 不画
另外打印 `hide_get()`（逐对象眼睛）为 True 的对象。

    blender -b <blend> -P tools/_probe_select_state.py -- [--out <json>]
"""
import json
import os
import sys

import bpy

argv = sys.argv
ARGS = argv[argv.index('--') + 1:] if '--' in argv else []
OUT = r'D:/BrainMaker/_probe/select_state.json'
NAMES = []
if '--out' in ARGS:
    OUT = ARGS[ARGS.index('--out') + 1]
if '--names' in ARGS:
    NAMES = [x for x in ARGS[ARGS.index('--names') + 1].split(',') if x]
os.makedirs(os.path.dirname(OUT), exist_ok=True)

vl = bpy.context.view_layer


def walk_lc(lc):
    yield lc
    for c in lc.children:
        yield from walk_lc(c)


LC = {lc.name: lc for lc in walk_lc(vl.layer_collection)}

rows = []
for ob in bpy.data.objects:
    states = []
    for c in ob.users_collection:
        lc = LC.get(c.name)
        states.append({
            'col': c.name,
            'in_vl': lc is not None,
            'exclude': bool(lc.exclude) if lc is not None else None,
            'eye_off': bool(lc.hide_viewport) if lc is not None else None,
            'col_hide': bool(c.hide_viewport),
        })
    visible = any(s['in_vl'] and not s['exclude'] and not s['eye_off'] for s in states)
    rows.append({
        'name': ob.name,
        'type': ob.type,
        'parent': ob.parent.name if ob.parent else None,
        'hide_select': bool(ob.hide_select),
        'hide_get': bool(ob.hide_get()),
        'visible': visible,
        'cols': [s['col'] for s in states],
        'states': states,
        'dims': [round(float(x), 2) for x in ob.dimensions],
    })

n_vis = sum(1 for r in rows if r['visible'])
hs = [r for r in rows if r['hide_select']]
hg = [r for r in rows if r['hide_get']]
multi = [r for r in rows if len(r['cols']) > 1]
orphan = [r for r in rows if not r['cols']]
vis_nosel = [r for r in rows if r['visible'] and r['hide_select']]
vis_multi = [r for r in rows if r['visible'] and len(r['cols']) > 1]

print('[sel] objects=%d visible=%d hide_select=%d hide_get=%d multi=%d orphan=%d'
      % (len(rows), n_vis, len(hs), len(hg), len(multi), len(orphan)))
print('[sel] 可见但 hide_select=%d  可见且多集合=%d' % (len(vis_nosel), len(vis_multi)))

for tag, arr, n in (('hide_select', hs, 30), ('hide_get', hg, 30),
                    ('multi', multi, 30), ('orphan', orphan, 30)):
    for r in arr[:n]:
        print('  %-12s %-34s dims=%s cols=%s' % (tag, r['name'], r['dims'], r['cols']))

# 只存可疑项，避免 JSON 太大
susp = [r for r in rows if r['hide_select'] or r['hide_get'] or len(r['cols']) != 1]
json.dump(susp, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False)
print('[sel] wrote %s（可疑项 %d）' % (OUT, len(susp)))

# 点名对象：打印完整状态（对照用）
for nm in NAMES:
    ob = bpy.data.objects.get(nm)
    if ob is None:
        print('[sel] MISSING object: %s' % nm)
        continue
    print('[sel] === %s ===' % nm)
    print('[sel]   type=%s hide_select=%s hide_get=%s hide_viewport=%s visible_get=%s parent=%s'
          % (ob.type, ob.hide_select, ob.hide_get(), ob.hide_viewport,
             ob.visible_get(), ob.parent.name if ob.parent else None))
    print('[sel]   dims=%s loc=%s' % ([round(x, 2) for x in ob.dimensions],
                                      [round(x, 2) for x in ob.location]))
    for c in ob.users_collection:
        lc = LC.get(c.name)
        print('[sel]   col=%-34s col.hide_viewport=%-5s col.hide_select=%-5s | in_vl=%-5s exclude=%-5s eye_off=%-5s'
              % (c.name, c.hide_viewport, getattr(c, 'hide_select', None),
                 lc is not None, (lc.exclude if lc else None), (lc.hide_viewport if lc else None)))

# 集合级 hide_select 统计（整个场景）
badcols = [c.name for c in bpy.data.collections if getattr(c, 'hide_select', False)]
print('[sel] 集合 hide_select=True：%d %s' % (len(badcols), badcols[:10]))
