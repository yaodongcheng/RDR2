"""把 props2 的分块 glTF 并入 sdn.blend，替换旧的 Props 集合。"""
import bpy, os, sys, glob, argparse
from mathutils import Vector
ROOT = r'D:/BrainMaker/大镖客2解包分析'
def parse():
    ap=argparse.ArgumentParser()
    ap.add_argument('--glob', default=os.path.join(ROOT,'export/levels/world/gltf/sdn_props2/tiles/*.gltf'))
    ap.add_argument('--out', default=os.path.join(ROOT,'export/levels/world/blender/sdn.blend'))
    ap.add_argument('--shots', default=os.path.join(ROOT,'export/levels/world/blender/shots'))
    ap.add_argument('--views', default='')
    ap.add_argument('--res', default='1600x900')
    return ap.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])

a=parse()
# 1) 删掉旧 Props 集合（旧的 660 个 p_new_01 道具，避免重复）
old=bpy.data.collections.get('Props')
n_old=0
if old:
    for o in list(old.objects):
        bpy.data.objects.remove(o, do_unlink=True); n_old+=1
    bpy.data.collections.remove(old)
print('removed old props', n_old)

# 2) 新建集合导入
col=bpy.data.collections.new('Props')
bpy.context.scene.collection.children.link(col)
vl=bpy.context.view_layer
vl.active_layer_collection=vl.layer_collection.children[col.name]
files=sorted(glob.glob(a.glob))
print('tiles', len(files))
for i,f in enumerate(files):
    try:
        bpy.ops.import_scene.gltf(filepath=f)
    except Exception as e:
        print('FAIL', f, e)
    if (i+1)%8==0: print('  ... %d/%d'%(i+1,len(files)))
print('objects now', len(bpy.data.objects))

bpy.ops.wm.save_as_mainfile(filepath=a.out)
print('SAVED', a.out)

if a.views:
    os.makedirs(a.shots, exist_ok=True)
    sc=bpy.context.scene; sc.render.engine='BLENDER_EEVEE'
    sc.render.resolution_x, sc.render.resolution_y=[int(x) for x in a.res.split('x')]
    views={
     'overview':(Vector((3060,-1960,760)),Vector((2550,-1150,45)),40),
     'street':(Vector((2500,-1215,53.2)),Vector((2520,-1010,57)),24),
     'market':(Vector((2640,-1300,60)),Vector((2620,-1180,52)),22),
    }
    for v in a.views.split(','):
        if v not in views: continue
        loc,look,lens=views[v]
        cam=bpy.data.cameras.new('c_'+v); cam.lens=lens; cam.clip_start=0.5; cam.clip_end=20000
        co=bpy.data.objects.new('c_'+v,cam); bpy.context.collection.objects.link(co)
        co.location=loc; co.rotation_euler=(look-loc).to_track_quat('-Z','Y').to_euler()
        sc.camera=co; sc.render.filepath=os.path.join(a.shots,f'props_{v}.png')
        bpy.ops.render.render(write_still=True); print('SHOT',sc.render.filepath)
