# -*- coding: utf-8 -*-
"""One-shot probe: compare collection visibility **as saved** vs **after autoload.show_all()**.

Why: blender_autoload.py calls tour.show_all(), which sets col.hide_viewport=False on
every C_* collection under ENTITIES -- including the ones classify_entities.py saved as
DEFAULT_HIDDEN (lod / terrain_cell / veg). The file state is NOT the runtime state.

    blender -b deliverable/blender/continent/continent_v11.blend ^
        --python tools/_unbuffer.py -P tools/_probe_vis_state.py
"""
import bpy

WATCH = ('C_lod_', 'C_terrain_cell_', 'C_veg_')


def layer_col(col):
    top = bpy.context.view_layer.layer_collection
    for c in getattr(top, 'children', []):
        if c.collection == col:
            return c
        for c2 in getattr(c, 'children', []):
            if c2.collection == col:
                return c2
    return None


def dump(tag):
    print('')
    print('================ %s ================' % tag)
    t = bpy.data.objects.get('Terrain')
    if t is not None:
        mods = [(m.name, m.type, round(getattr(m, 'ratio', 0.0), 2), m.show_viewport)
                for m in t.modifiers]
        print('Terrain  verts=%d polys=%d  per_object_hidden=%s  modifiers=%s'
              % (len(t.data.vertices), len(t.data.polygons), t.hide_get(), mods))
    w = bpy.data.objects.get('Water')
    if w is not None:
        print('Water    verts=%d  per_object_hidden=%s'
              % (len(w.data.vertices), w.hide_get()))
    ent = bpy.data.collections.get('ENTITIES')
    if ent is None:
        print('ENTITIES missing')
        return
    # sample: per-object hide state inside a terrain_cell subcollection
    for c in ent.children:
        lc = layer_col(c)
        eye = lc.hide_viewport if lc is not None else None
        tag_w = ' <<<' if c.name.startswith(WATCH) else ''
        print('  %-28s objs=%-6d data.hide_viewport=%-5s layer_eye_off=%-5s%s'
              % (c.name, len(c.all_objects), c.hide_viewport, eye, tag_w))


def show_all():
    ent = bpy.data.collections.get('ENTITIES')
    for c in ent.children:
        c.hide_viewport = False
        c.hide_render = False
        for sub in c.children:
            sub.hide_viewport = False
            sub.hide_render = False


dump('AS SAVED (what a plain double-click shows)')

ent = bpy.data.collections.get('ENTITIES')
tc = None
for c in ent.children:
    if c.name.startswith('C_terrain_cell_'):
        tc = c
        break
if tc is not None and len(tc.all_objects):
    o = tc.all_objects[0]
    print('')
    print('sample terrain_cell object: %s  per_object_hidden=%s' % (o.name, o.hide_get()))
    print('  (collection-level hiding does NOT show up in hide_get() -- that is the trap)')

show_all()
dump('AFTER show_all() + autoload re-hide list (launcher path)')

# now replay exactly what autoload.py does AFTER show_all()
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import blender_tour as tour
for _k in ('贴花', '植被', '远景碎片', '地形块'):
    tour.cat_show(_k, False)
dump('AFTER the patched re-hide list (what the launcher should look like now)')

if tc is not None and len(tc.all_objects):
    o = tc.all_objects[0]
    print('sample terrain_cell object after show_all: %s  per_object_hidden=%s'
          % (o.name, o.hide_get()))
