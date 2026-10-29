# -*- coding: utf-8 -*-
"""One-shot probe: why are new_gar_rds_008 / new_gar_rds_006b_decal in the same class,
and why does the road mesh look partly transparent.

    blender -b <blend> --python tools/_unbuffer.py -P tools/_probe_rds.py
"""
import bpy
import os
from collections import Counter

TARGETS = ('new_gar_rds_008', 'new_gar_rds_006b_decal')

parent = {}
for c in bpy.data.collections:
    for ch in c.children:
        parent[ch.name] = c.name


def chain(o):
    out = []
    for c in o.users_collection:
        p = c.name
        seq = [p]
        while p in parent:
            p = parent[p]
            seq.append(p)
        out.append(' / '.join(reversed(seq)))
    return out


def mat_info(m):
    d = {'name': m.name, 'users': m.users}
    d['surface_render_method'] = getattr(m, 'surface_render_method', 'n/a')
    d['blend_method'] = getattr(m, 'blend_method', 'n/a')
    d['backface_cull'] = getattr(m, 'use_backface_culling', 'n/a')
    d['diffuse'] = tuple(round(x, 3) for x in m.diffuse_color)
    if m.use_nodes:
        imgs, alpha_link = [], False
        for n in m.node_tree.nodes:
            if n.type == 'TEX_IMAGE' and n.image:
                im = n.image
                p = bpy.path.abspath(im.filepath) if im.filepath else ''
                imgs.append('%s [%dx%d ch=%s depth=%s alpha=%s exists=%s]'
                            % (im.name, im.size[0], im.size[1], getattr(im, 'channels', '?'),
                               getattr(im, 'depth', '?'), im.alpha_mode, os.path.exists(p)))
            if n.type == 'BSDF_PRINCIPLED':
                for inp in n.inputs:
                    if inp.name in ('Alpha', 'Base Color') and inp.is_linked:
                        src = inp.links[0].from_socket
                        if inp.name == 'Alpha':
                            alpha_link = True
                        else:
                            d['basecolor_from'] = src.node.type
        d['images'] = imgs
        d['alpha_linked'] = alpha_link
    return d


for t in TARGETS:
    print('')
    print('################ %s ################' % t)
    hits = [o for o in bpy.data.objects if o.name.startswith(t)]
    print('objects: %d' % len(hits))
    for o in hits[:4]:
        print('  %-28s type=%s hide_tag=%s' % (o.name, o.type, o.get('hide_tag', '(none)')))
        print('     class: %s' % ' | '.join(chain(o)))
        try:
            print('     visible_get=%s hide_get=%s' % (o.visible_get(), o.hide_get()))
        except Exception as e:
            print('     visibility err %s' % e)
        if o.type != 'MESH':
            continue
        me = o.data
        print('     mesh: verts=%d polys=%d uv=%s slots=%d'
              % (len(me.vertices), len(me.polygons), [u.name for u in me.uv_layers],
                 len(me.materials)))
        arr = [0] * len(me.polygons)
        if len(arr):
            me.polygons.foreach_get('material_index', arr)
        cnt = Counter(arr)
        for i, m in enumerate(me.materials):
            info = mat_info(m) if m else {'name': '(empty slot)'}
            print('       slot %d  polys=%-6d %s' % (i, cnt.get(i, 0), info))
        # other objects sharing the same mesh data
        same = [x.name for x in bpy.data.objects if x.data == me and x.name != o.name]
        if same:
            print('       same mesh used by: %s%s' % (same[:5], ' ...' if len(same) > 5 else ''))
