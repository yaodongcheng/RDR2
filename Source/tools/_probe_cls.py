# -*- coding: utf-8 -*-
"""Which class are the ground-covering neighbours in, and are they visible?"""
import bpy
NAMES = ('new_gar06_park_terrain', 'new_18_ter_a_03', 'new_18_ter_a_02',
         'new_gar_08_ground_cur', 'new_gar_bron_ground01', 'new_gar_07_mansiona')
parent = {}
for c in bpy.data.collections:
    for ch in c.children:
        parent[ch.name] = c.name
for n in NAMES:
    for o in [x for x in bpy.data.objects if x.name.startswith(n)]:
        seq = []
        for c in o.users_collection:
            p = c.name
            s = [p]
            while p in parent:
                p = parent[p]
                s.append(p)
            seq.append(' / '.join(reversed(s)))
        print('%-30s %-50s visible=%s' % (o.name, seq[0] if seq else '?', o.visible_get()))
