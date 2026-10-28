"""在裁剪后的 blend 里，按官方地图框范围量地形覆盖（射线穿地法）。"""
import bpy, json
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

A=json.load(open(r'D:/BrainMaker/大镖客2解包分析/export/world/map_area.json',encoding='utf-8'))
ob=bpy.data.objects['Terrain']
bvh=BVHTree.FromObject(ob, bpy.context.evaluated_depsgraph_get())
N=180
xs=np.linspace(A['x0'],A['x1'],N); ys=np.linspace(A['y0'],A['y1'],N)
hit=np.zeros((N,N),np.uint8)
for j,y in enumerate(ys):
    for i,x in enumerate(xs):
        loc,_,_,_=bvh.ray_cast(Vector((float(x),float(y),5000.0)),Vector((0,0,-1)))
        hit[j,i]= loc is not None
print('地图框内覆盖率 %.2f%%'%(100*hit.mean()))
# 最大空洞（按 4 邻域）
from collections import deque
lab=np.zeros((N,N),np.int32); cur=0; comps=[]
for j in range(N):
    for i in range(N):
        if hit[j,i]==0 and lab[j,i]==0:
            cur+=1; q=deque([(j,i)]); lab[j,i]=cur; cells=[]
            while q:
                a,b=q.popleft(); cells.append((a,b))
                for da,db in ((1,0),(-1,0),(0,1),(0,-1)):
                    na,nb=a+da,b+db
                    if 0<=na<N and 0<=nb<N and hit[na,nb]==0 and lab[na,nb]==0:
                        lab[na,nb]=cur; q.append((na,nb))
            comps.append(cells)
comps.sort(key=len,reverse=True)
dx=(A['x1']-A['x0'])/(N-1); dy=(A['y1']-A['y0'])/(N-1)
for cells in comps[:6]:
    area=len(cells)*dx*dy/1e6
    if area<0.2: continue
    js=[c[0] for c in cells]; ii=[c[1] for c in cells]
    print('  空洞 %.2f km²  x[%.0f,%.0f] y[%.0f,%.0f]'%(area,A['x0']+min(ii)*dx,A['x0']+max(ii)*dx,A['y0']+min(js)*dy,A['y0']+max(js)*dy))
print('Water faces', len(bpy.data.objects['Water'].data.polygons), 'objects', len(bpy.data.objects))
