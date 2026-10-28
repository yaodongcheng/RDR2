"""把室内 MLO 布局装配成 Blender 场景。

输入：
  raw/_scratch/roc_interior_layout.json   （tools/parse_interior_mlo.py 的产物）

输出：
  deliverable/blender/willard/roc_interior.blend + roc_interior.png

关键点：
  · entity 的 position 是**室内局部坐标**（±10 m），直接摆在原点周围即可
  · rotation 存 (x,y,z,w)，Blender 用 (w,x,y,z) → **取共轭**（和建筑同一问题）
  · 库里没有的模型跳过并统计
"""
import os
import sys
import json

import bpy
from mathutils import Vector, Quaternion

ROOT = r'D:/BrainMaker/大镖客2解包分析'
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import blender_continent as bc  # noqa: E402

LIB = os.path.join(ROOT, 'assets/lib_native')
LAYOUT = os.path.join(ROOT, 'raw/_scratch/roc_interior_layout.json')
OUT_BLEND = os.path.join(ROOT, 'deliverable/blender/willard/roc_interior.blend')
OUT_PNG = os.path.join(ROOT, 'deliverable/blender/willard/roc_interior.png')


def main():
    idx = json.load(open(os.path.join(LIB, 'index.json'), encoding='utf-8'))
    models, texmeta = idx['models'], idx['tex']
    lay = json.load(open(LAYOUT, encoding='utf-8'))['entities']
    print('layout entities:', len(lay))

    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    col = bpy.data.collections.new('INTERIOR')
    sc.collection.children.link(col)

    matcache, meshcache = {}, {}
    placed = skipped = 0
    for e in lay:
        key = hex(e['h'])
        ent = models.get(key)
        if not ent:
            skipped += 1
            continue
        me = bc.load_model_mesh(LIB, ent, texmeta, matcache, meshcache)
        if not me:
            skipped += 1
            continue
        ob = bpy.data.objects.new('i_%s_%d' % (key[2:10], placed), me)
        ob.location = tuple(e['p'])
        qx, qy, qz, qw = e['q']
        ob.rotation_mode = 'QUATERNION'
        ob.rotation_quaternion = (qw, -qx, -qy, -qz)   # 共轭
        col.objects.link(ob)
        placed += 1
    print('placed %d, skipped %d (model missing)' % (placed, skipped))

    # 无 albedo 的小道具（shader 用调色板/参数色）→ 按名字类别上近似色，
    # 避免整屋一片暗灰。真正根治要解析 shader 的 palette 贴图。
    import re as _re
    PALETTE = [
        (r'coin|gold|brass',            (0.72, 0.58, 0.24)),
        (r'can|tin|copper|pot|kettle|boiler|metal|iron', (0.46, 0.43, 0.39)),
        (r'book|paper|ledger|card',     (0.44, 0.33, 0.24)),
        (r'glass|bottle|jar',           (0.55, 0.62, 0.66)),
        (r'rag|cloth|curtain|cloth',    (0.50, 0.45, 0.40)),
        (r'wood|plank|log|stick',       (0.40, 0.31, 0.21)),
        (r'candle|lamp|light',          (0.85, 0.78, 0.55)),
    ]
    names = {}
    try:
        import json as _json
        _nm_path = os.path.join(ROOT, 'tools/rdr2rpf/bin/Release/net9.0/names.txt')
        _lay = _json.load(open(LAYOUT, encoding='utf-8'))['entities']
        def _joaat(s):
            h = 0
            for c in s.lower().encode():
                h = (h + c) & 0xffffffff; h = (h + (h << 10)) & 0xffffffff; h ^= h >> 6
            h = (h + (h << 3)) & 0xffffffff; h ^= h >> 11; h = (h + (h << 15)) & 0xffffffff
            return h
        for n in open(_nm_path, encoding='latin1'):
            n = n.strip()
            if n: names[_joaat(n)] = n
        for e in _lay:
            names.setdefault(e['h'], names.get(e['h'], ''))
    except Exception:
        pass
    tinted = 0
    for ob in bpy.data.objects:
        if ob.type != 'MESH' or not ob.name.startswith('i_'):
            continue
        m = ob.material_slots[0].material if ob.material_slots else None
        if not m or not m.use_nodes: continue
        if any(nn.type == 'TEX_IMAGE' and nn.image for nn in m.node_tree.nodes):
            continue
        # 取模型名判断类别
        mn = ''
        for h, n in names.items():
            if hex(h)[2:10] == ob.name[2:10]:
                mn = n; break
        col = (0.35, 0.32, 0.28)
        for pat, c in PALETTE:
            if _re.search(pat, mn, _re.I):
                col = c; break
        for nn in m.node_tree.nodes:
            if nn.type == 'BSDF_PRINCIPLED':
                nn.inputs['Base Color'].default_value = (col[0], col[1], col[2], 1.0)
        tinted += 1
    print('按类别上色 %d 个无贴图对象' % tinted)

    # 环境光 + 点光（室内没天光）
    w = bpy.data.worlds.new('W')
    sc.world = w
    w.use_nodes = True
    w.node_tree.nodes['Background'].inputs[0].default_value = (0.06, 0.06, 0.07, 1)
    w.node_tree.nodes['Background'].inputs[1].default_value = 1.0
    for i, (lx, ly, lz, en) in enumerate([(0, 0, 3.0, 600), (3, -2, 2.2, 300), (-3, 2, 2.2, 300)]):
        ld = bpy.data.lights.new('L%d' % i, 'POINT')
        ld.energy = en
        ld.shadow_soft_size = 0.6
        lo = bpy.data.objects.new('L%d' % i, ld)
        lo.location = (lx, ly, lz)
        sc.collection.objects.link(lo)

    cd = bpy.data.cameras.new('C')
    cam = bpy.data.objects.new('Camera', cd)
    sc.collection.objects.link(cam)
    # 隐藏墙壳/天花，只留家具，从上前方俯视验证布局
    for n in ['roc_hse_int_shell_main', 'roc_hse_main_details01', 'roc_hse_main_details02',
              'roc_hse_int_beams', 'roc_hse_shadowproxy']:
        for ob in bpy.data.objects:
            if ob.name.startswith('i_') and n in (ob.data.name if ob.data else ''):
                ob.hide_render = True
            elif ob.name.startswith('i_') and n.split('roc_')[1] in ob.name:
                ob.hide_render = True
    # 按 bbox 粗略隐藏大件（墙/梁），保留小家具
    for ob in bpy.data.objects:
        if ob.type == 'MESH' and ob.name.startswith('i_'):
            d = ob.dimensions
            if max(d.x, d.y, d.z) > 6.0:
                ob.hide_render = True
    cam.data.lens = 24
    cam.data.clip_end = 100
    cam.location = (7.0, -9.5, 7.5)
    cam.rotation_mode = 'QUATERNION'
    T = Vector((0.0, 0.0, 0.0))
    cam.rotation_quaternion = (T - cam.location).to_track_quat('-Z', 'Y')
    sc.camera = cam

    sc.render.resolution_x = 1280
    sc.render.resolution_y = 760
    sc.render.engine = 'BLENDER_EEVEE'
    sc.render.filepath = OUT_PNG
    bpy.ops.render.render(write_still=True)
    bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND)
    print('SAVED', OUT_BLEND)


if __name__ == '__main__':
    main()
