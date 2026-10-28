"""方案 B：修地面贴花（decal）的材质层级。

症状：街面上一块块深色/灰色补丁，叠在石板路上，像贴错层。
原因：
  1. 147 个贴花面片用的是 **BLEND / HASHED**（不写深度）⇒ 相互重叠时排序错乱；
  2. 其中 72 个材质的贴图**没接 Alpha**（或根本没有贴图）⇒ alpha=1，整片实心盖住地面；
  3. 贴花离路面只有几毫米 ⇒ 与路面 z-fighting。

做法：
  1. 有贴图的材质：把 Image.Alpha 接到 Principled.Alpha（没接的补上）
  2. 全部改成 **CLIP（alpha 裁剪 0.5）** ⇒ 写深度、按像素裁剪，不再有排序问题
  3. 完全没有贴图的贴花对象：直接删掉（它们只是灰色面板）
  4. 贴花整体抬高 2 cm，消除与路面的 z-fighting

用法：
  blender -b export/levels/world/blender/sdn.blend -P tools/fix_decal_materials.py -- \
      --out export/levels/world/blender/sdn.blend --shots DIR --views street
"""
import bpy
import os
import sys
import argparse
from mathutils import Vector

ROOT = r'D:/BrainMaker/大镖客2解包分析'


def argv():
    a = sys.argv
    return a[a.index('--') + 1:] if '--' in a else []


def parse():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=os.path.join(ROOT, 'export/levels/world/blender/sdn.blend'))
    ap.add_argument('--cutoff', type=float, default=0.5)
    ap.add_argument('--offset', type=float, default=0.02, help='贴花抬高（m）')
    ap.add_argument('--shots', default='')
    ap.add_argument('--views', default='street')
    ap.add_argument('--res', default='1600x900')
    ap.add_argument('--tag', default='after')
    return ap.parse_args(argv())


def is_decal(o):
    n = o.name.lower()
    return o.type == 'MESH' and ('decal' in n or n.endswith('_dec') or '_dec_' in n or n.endswith('_decals'))


def fix_material(m, cutoff):
    """→ 'ok' | 'notex'"""
    nt = m.node_tree
    if nt is None:
        return 'notex'
    tex = next((n for n in nt.nodes if n.type == 'TEX_IMAGE' and n.image), None)
    bsdf = next((n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED'), None)
    if tex is None or bsdf is None:
        return 'notex'
    # 补 Alpha 连线
    a = bsdf.inputs['Alpha']
    if not a.is_linked:
        try:
            nt.links.new(tex.outputs['Alpha'], a)
        except Exception:
            pass
    # 改成裁剪
    try:
        m.blend_method = 'CLIP'
    except Exception:
        pass
    try:
        m.alpha_threshold = cutoff
    except Exception:
        pass
    try:
        m.use_backface_culling = False
    except Exception:
        pass
    return 'ok'


def main():
    a = parse()
    decals = [o for o in bpy.data.objects if is_decal(o)]
    print('DECAL objects', len(decals))

    fixed, notex_mats = set(), set()
    for o in decals:
        for m in o.data.materials:
            if not m or m.name in fixed or m.name in notex_mats:
                continue
            r = fix_material(m, a.cutoff)
            (fixed if r == 'ok' else notex_mats).add(m.name)
    print('materials fixed', len(fixed), 'no-texture', len(notex_mats))

    # 抬高 + 删除纯灰面板
    removed = 0
    for o in list(decals):
        mats = [m for m in o.data.materials if m]
        if mats and all(m.name in notex_mats for m in mats):
            bpy.data.objects.remove(o, do_unlink=True)
            removed += 1
            continue
        o.location.z += a.offset
    print('removed placeholder decals', removed, 'raised', len(decals) - removed, 'by %.3f m' % a.offset)

    bpy.ops.wm.save_as_mainfile(filepath=a.out)
    print('SAVED', a.out)

    if a.shots:
        os.makedirs(a.shots, exist_ok=True)
        views = {
            'street': (Vector((2500, -1215, 53.2)), Vector((2520, -1010, 57)), 24),
            'street2': (Vector((2620, -1185, 53.0)), Vector((2760, -1120, 56)), 26),
            'market': (Vector((2470, -1180, 54.5)), Vector((2560, -1230, 52)), 24),
        }
        sc = bpy.context.scene
        sc.render.engine = 'BLENDER_EEVEE'
        sc.render.resolution_x, sc.render.resolution_y = [int(x) for x in a.res.split('x')]
        for v in a.views.split(','):
            if v not in views:
                continue
            loc, look, lens = views[v]
            cam = bpy.data.cameras.new('c_' + v)
            cam.lens = lens
            cam.clip_start = 0.5
            cam.clip_end = 20000
            co = bpy.data.objects.new('c_' + v, cam)
            bpy.context.collection.objects.link(co)
            co.location = loc
            co.rotation_euler = (look - loc).to_track_quat('-Z', 'Y').to_euler()
            sc.camera = co
            sc.render.filepath = os.path.join(a.shots, f'decal_{a.tag}_{v}.png')
            bpy.ops.render.render(write_still=True)
            print('SHOT ->', sc.render.filepath)


if __name__ == '__main__':
    main()
