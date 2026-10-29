# -*- coding: utf-8 -*-
"""What does OUR Terrain look like at the road spot? (game uses layered terrain shading)"""
import bpy, numpy as np
from mathutils import Vector

t = bpy.data.objects.get('Terrain')
me = t.data
print('#### Terrain material:', me.materials[0].name if me.materials else '(none)')
for m in me.materials:
    if not m or not m.use_nodes: continue
    for n in m.node_tree.nodes:
        if n.type == 'TEX_IMAGE':
            print('    TEX_IMAGE ->', n.image.name if n.image else '?', n.image.filepath if n.image else '')
        if n.type == 'VERTEX_COLOR':
            print('    VERTEX_COLOR layer =', n.layer_name)
print('#### color attributes:', [a.name for a in me.color_attributes])

a = bpy.data.objects.get('new_gar_rds_008')
cs = [a.matrix_world @ Vector(c) for c in a.bound_box]
xs = [v.x for v in cs]; ys = [v.y for v in cs]; zs = [v.z for v in cs]
cx, cy = (min(xs)+max(xs))/2, (min(ys)+max(ys))/2
hx, hy = (max(xs)-min(xs))/2, (max(ys)-min(ys))/2

# sample the 'Col' attribute inside the road bbox
if me.color_attributes:
    ca = me.color_attributes[0]
    n = len(me.vertices)
    co = np.empty(n*3, np.float32); me.vertices.foreach_get('co', co); co = co.reshape(-1,3)
    col = np.empty(n*4, np.float32); ca.data.foreach_get('color', col); col = col.reshape(-1,4)
    m = (np.abs(co[:,0]-cx) < hx) & (np.abs(co[:,1]-cy) < hy)
    if m.any():
        print('#### Col over road bbox: %d verts  mean rgb = (%.3f, %.3f, %.3f)'
              % (m.sum(), col[m,0].mean(), col[m,1].mean(), col[m,2].mean()))
        print('####   greenish? %.2f   (0 = grey/brown, 1 = green)' % ((col[m,1].mean()-col[m,0].mean())))

tmp = bpy.data.collections.new('TMP'); bpy.context.scene.collection.children.link(tmp); tmp.objects.link(t)
def find_lc(name, lc):
    for c in lc.children:
        if c.collection.name == name: return c
        r = find_lc(name, c)
        if r is not None: return r
find_lc('ENTITIES', bpy.context.view_layer.layer_collection).exclude = True
for nm in ('Water','Sun'):
    o = bpy.data.objects.get(nm)
    if o: o.hide_render = True

sc = bpy.context.scene
cd = bpy.data.cameras.new('T_Cam'); cam = bpy.data.objects.new('T_Cam', cd)
sc.collection.objects.link(cam)
cam.location = (cx, cy, max(zs)+150); cam.rotation_euler = (0,0,0)
cd.type='ORTHO'; cd.ortho_scale = max(hx,hy)*2.2; cd.clip_start=0.1; cd.clip_end=20000
sc.camera = cam
sc.render.engine='BLENDER_WORKBENCH'
sh = sc.display.shading
sh.light='FLAT'; sh.show_shadows=False; sh.show_cavity=False; sh.show_object_outline=False
sc.render.resolution_x=900; sc.render.resolution_y=900
sc.render.image_settings.file_format='PNG'
for ct in ('VERTEX','TEXTURE'):
    try:
        sh.color_type = ct
    except Exception as e:
        print('#### color_type %s not available: %s' % (ct, e)); continue
    sc.render.filepath = 'D:/BrainMaker/大镖客2解包分析/export/previews/rds008_20261029/_terrain_%s.png' % ct.lower()
    bpy.ops.render.render(write_still=True)
    print('#### wrote', sc.render.filepath)
