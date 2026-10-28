# -*- coding: utf-8 -*-
# -*- coding: utf-8 -*-
"""在 Blender 里单独渲染「威拉德歇脚处」（夏洛蒂的屋子）。

只加载这套庄园的 7 个模型（主屋/棚/披屋/菜园/井/坟），十几秒出 4 个机位，
用来证明"这个屋子真的在解包地图上"。整块 continent.blend 有 8.4 GB，加载太慢，不适合做单点验证。

用法:
  blender -b -P tools/render_willard.py -- <项目根> <输出目录>
  blender -b -P tools/render_willard.py -- D:/BrainMaker/大镖客2解包分析 docs/世界与地编/img/willard
"""
import bpy, os, sys, json, struct, math, glob
import numpy as np
from mathutils import Vector

PROJ = sys.argv[sys.argv.index('--') + 1]
OUT = sys.argv[sys.argv.index('--') + 2]
os.makedirs(OUT, exist_ok=True)

ROOT = PROJ
LIB = os.path.join(ROOT, 'assets/lib_native')
IDX = json.load(open(os.path.join(LIB, 'index.json'), encoding='utf-8'))
MODELS = IDX['models']
TEX = {t['id']: t['f'] for t in IDX['tex']}
TEXN = {t['id']: t.get('n') for t in IDX['tex']}

MAGIC = b'RMDL1\0\0\0'
SUB = struct.Struct('<7I')


def joaat(s):
    h = 0
    for c in s.lower().encode():
        h = (h + c) & 0xffffffff
        h = (h + ((h << 10) & 0xffffffff)) & 0xffffffff
        h ^= h >> 6
    h = (h + ((h << 3) & 0xffffffff)) & 0xffffffff
    h ^= h >> 11
    h = (h + ((h << 15) & 0xffffffff)) & 0xffffffff
    return h


def load_mdl(path):
    buf = open(path, 'rb').read()
    if buf[:8] != MAGIC:
        return None
    nsub = struct.unpack_from('<I', buf, 8)[0]
    subs = []
    o = 12 + 24
    for _ in range(nsub):
        subs.append(SUB.unpack_from(buf, o))
        o += SUB.size
    verts, faces, uvs, face_tid = [], [], [], []
    base = 0
    for (tid, vc, ic, po, no, uo, io_) in subs:
        if ic == 0 or vc == 0:
            continue
        pos = np.frombuffer(buf, dtype=np.float32, count=vc * 3, offset=po).reshape(-1, 3)
        uv = np.frombuffer(buf, dtype=np.float32, count=vc * 2, offset=uo).reshape(-1, 2)
        idx = np.frombuffer(buf, dtype=np.uint32, count=ic, offset=io_)
        if int(idx.max()) >= vc:
            continue
        verts.append(pos)
        uvs.append(uv)
        tri = idx.reshape(-1, 3) + base
        faces.append(tri)
        face_tid += [tid] * len(tri)
        base += vc
    if not verts:
        return None
    v = np.vstack(verts)
    uv = np.vstack(uvs)
    f = np.vstack(faces)
    me = bpy.data.meshes.new('m')
    me.from_pydata(v.tolist(), [], f.tolist())
    me.update(calc_edges=True)
    me.uv_layers.new(name='UVMap')
    if len(me.uv_layers[0].data) == len(uv):
        me.uv_layers[0].data.foreach_set('uv', uv.ravel())
    return me, face_tid


def mat_for(tid):
    key = 'MAT_%s' % tid
    m = bpy.data.materials.get(key)
    if m:
        return m
    nm = (TEXN.get(tid) or '').lower()
    if 'roof' in nm or 'shingle' in nm:
        col = (0.16, 0.13, 0.11, 1)
    elif 'glass' in nm:
        col = (0.45, 0.55, 0.62, 1)
    elif 'stone' in nm or 'cem' in nm or 'plaster' in nm:
        col = (0.40, 0.39, 0.36, 1)
    elif 'metal' in nm or 'rust' in nm:
        col = (0.18, 0.18, 0.19, 1)
    elif 'moss' in nm:
        col = (0.24, 0.28, 0.16, 1)
    elif 'fabric' in nm or 'rope' in nm:
        col = (0.34, 0.29, 0.21, 1)
    elif 'wood' in nm or 'log' in nm or 'plank' in nm or 'beam' in nm or 'floor' in nm:
        col = (0.26, 0.20, 0.14, 1)
    elif tid < 0:
        col = (0.30, 0.28, 0.25, 1)
    else:
        col = (0.30, 0.26, 0.21, 1)
    m = bpy.data.materials.new(key)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    bsdf = nt.nodes.new('ShaderNodeBsdfPrincipled')
    nt.links.new(bsdf.outputs[0], out.inputs['Surface'])
    bsdf.inputs['Base Color'].default_value = col
    bsdf.inputs['Roughness'].default_value = 0.88
    return m


# ---------------- 载入实例 ----------------
def load_instances():
    out = []
    for fn in glob.glob(os.path.join(ROOT, 'export/world/continent/tiles/*.json')):
        for e in json.load(open(fn)):
            if abs(e[1] - 2990) < 70 and abs(e[2] - 2195) < 70:
                out.append(e)
    return out


WHITE = ('roc_01_ext_home01', 'roc_shed_01', 'roc_leanto', 'roc_01_gravefresh',
         'roc_01_graveyearsold', 'roc_01_garden01_nice', 'roc_01_garden01_die')
WHITE_H = {joaat(n) for n in WHITE}

inst = load_instances()
print('instances near:', len(inst))
placed = 0
for e in inst:
    if e[0] not in WHITE_H:
        continue
    hx = '0x%08x' % e[0]
    ent = MODELS.get(hx)
    if not ent:
        continue
    path = os.path.join(LIB, ent['f'])
    if not os.path.exists(path):
        continue
    got = load_mdl(path)
    if not got:
        continue
    me, face_tid = got
    ob = bpy.data.objects.new('e_%s' % hx[2:], me)
    bz = ent.get('b')[2] if ent.get('b') else 0.0
    ob.location = (e[1], e[2], e[3] - bz)
    ob.rotation_mode = 'QUATERNION'
    ob.rotation_quaternion = (e[7], e[4], e[5], e[6])   # (w,x,y,z)
    s = e[8] if len(e) > 8 else 1.0
    ob.scale = (s, s, e[9] if len(e) > 9 else s)
    # 每个子网格各自的 texId → 各自的材质
    order = []
    for t in face_tid:
        if t not in order:
            order.append(t)
    for t in order:
        me.materials.append(mat_for(t))
    slot = {t: i for i, t in enumerate(order)}
    for i, p in enumerate(me.polygons):
        p.material_index = slot.get(face_tid[i], 0)
    bpy.context.scene.collection.objects.link(ob)
    placed += 1
print('placed', placed)

# ---------------- 场景 ----------------
scene = bpy.context.scene
scene.render.engine = 'BLENDER_EEVEE'
scene.render.resolution_x = 1280
scene.render.resolution_y = 720
scene.render.film_transparent = False
scene.view_settings.view_transform = 'Standard'
world = bpy.data.worlds.new('W')
scene.world = world
world.use_nodes = True
wnt = world.node_tree
for _n in list(wnt.nodes): wnt.nodes.remove(_n)
_wo = wnt.nodes.new('ShaderNodeOutputWorld')
_wb = wnt.nodes.new('ShaderNodeBackground')
_wb.inputs[0].default_value = (0.42, 0.52, 0.68, 1)
_wb.inputs[1].default_value = 0.35
wnt.links.new(_wb.outputs[0], _wo.inputs['Surface'])

sun = bpy.data.objects.new('Sun', bpy.data.lights.new('Sun', 'SUN'))
bpy.context.scene.collection.objects.link(sun)
sun.data.energy = 3.4
sun.rotation_euler = (math.radians(55), 0, math.radians(120))

# 地面（草地）占位，帮助判断"站在地上"
bpy.ops.mesh.primitive_plane_add(size=300, location=(2989, 2200, 168.45))
gp = bpy.context.object
gm = bpy.data.materials.new('ground')
gm.use_nodes = True
_gnt = gm.node_tree
for _n in list(_gnt.nodes): _gnt.nodes.remove(_n)
_go = _gnt.nodes.new('ShaderNodeOutputMaterial')
_gb = _gnt.nodes.new('ShaderNodeBsdfPrincipled')
_gb.inputs['Base Color'].default_value = (0.13, 0.16, 0.09, 1)
_gb.inputs['Roughness'].default_value = 1.0
_gnt.links.new(_gb.outputs[0], _go.inputs['Surface'])
gp.data.materials.append(gm)

cam_data = bpy.data.cameras.new('C')
cam = bpy.data.objects.new('C', cam_data)
bpy.context.scene.collection.objects.link(cam)
scene.camera = cam
cam_data.lens = 45
cam_data.clip_end = 20000
TARGET = Vector((2989.5, 2192.0, 169.5))


def shoot(name, pos):
    cam.location = Vector(pos)
    d = TARGET - cam.location
    cam.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    scene.render.filepath = os.path.join(OUT, name + '.png')
    bpy.ops.render.render(write_still=True)
    print('[shot]', scene.render.filepath)


shoot('w01_south_35m', (2991, 2156, 176))
shoot('w02_west_38m', (2952, 2188, 177))
shoot('w03_air_150m', (2920, 2090, 250))
shoot('w04_north_42m', (2985, 2228, 176))
print('DONE')
