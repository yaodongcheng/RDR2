import bpy
from mathutils import Vector
def wbb(o):
    mn=Vector((1e18,)*3); mx=Vector((-1e18,)*3)
    for c in o.bound_box:
        p=o.matrix_world@Vector(c)
        for i in range(3): mn[i]=min(mn[i],p[i]); mx[i]=max(mx[i],p[i])
    return mn,mx
tg=[o for o in bpy.context.scene.objects if 'park_terrain' in o.name.lower() or 'park_glue' in o.name.lower()]
import os
print('[park] 文件', os.path.basename(bpy.data.filepath), ' 命中', len(tg))
for o in tg:
    mn,mx=wbb(o); c=(mn+mx)/2
    print('   %-34s c=(%8.1f,%8.1f,%7.2f) z[%7.2f,%7.2f] 跨度(%5.1f,%5.1f)'%(
        o.name[:34],c.x,c.y,c.z,mn.z,mx.z,mx.x-mn.x,mx.y-mn.y))
ter=bpy.data.objects.get('Terrain')
if ter and tg:
    from mathutils.bvhtree import BVHTree
    bvh=BVHTree.FromObject(ter, bpy.context.evaluated_depsgraph_get())
    for o in tg:
        mn,mx=wbb(o); cx,cy=(mn.x+mx.x)/2,(mn.y+mx.y)/2
        for dx,dy in ((0,0),(10,0),(0,10),(-10,0),(0,-10)):
            hit=bvh.ray_cast(Vector((cx+dx,cy+dy,600)),Vector((0,0,-1)),2000)
            if hit[0] is not None:
                print('   地形@(%+.0f,%+.0f) z=%7.2f   差(件底-地形)=%+6.2f'%(dx,dy,hit[0].z,mn.z-hit[0].z))
