"""后台烘焙：把 INTERIOR_ROOT 的变换写进每个件，删 root，隐藏污渍。
用 bpy.ops.object.parent_clear(CLEAR_KEEP_TRANSFORM) —— Blender 内部保证世界变换不变。
"""
import bpy

DIRT = {'d3f79faf', '59f1bb50', '3933f9d1'}
root = bpy.data.objects.get('INTERIOR_ROOT')
inter = [o for o in bpy.data.objects if o.name.startswith('i_')]
print('interior:', len(inter), 'root:', root.name if root else None)

if root:
    bpy.ops.object.select_all(action='DESELECT')
    for o in inter:
        o.select_set(True)
    bpy.context.view_layer.objects.active = inter[0]
    bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')
    bpy.data.objects.remove(root, do_unlink=True)
    bpy.context.view_layer.update()
    print('parent cleared, root removed')

n = 0
for o in inter:
    if o.name[2:10] in DIRT:
        o.hide_render = True; o.hide_viewport = True; n += 1
print('dirt hidden:', n)

o = inter[0]
print('sample', o.name, 'loc (%.2f, %.2f, %.2f)' % tuple(o.location), 'parent', o.parent)

bpy.ops.wm.save_mainfile()
print('SAVED')
