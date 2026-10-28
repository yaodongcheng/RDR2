# -*- coding: utf-8 -*-
"""把远景 LOD（*_area_slod* / *_slod* / *_em_slod* / *_dslod* / *_lod）藏进 HIDDEN_LOD。

## 为什么

全量装配把"远景合批"网格也装进来了：它们低模、整块（一个对象可覆盖 3~4 km²）、
多数没有 albedo，而且和真实几何重叠 —— 在视口里表现为地面上的一堆深灰碎片，
点哪儿都只能选中整块（用户报的"碎片选不中"）。

处理方式与地形 patch 一致：**隐藏不删**（最高原则 6.1），N 面板可随时切回。

    blender -b <blend> --python tools/_unbuffer.py -P tools/hide_lod.py [-- --shots]

`--shots` 会顺带渲 3 张检查图（lawn 特写 / city / wide）到 work/verify/。
"""
import bpy
import os
import sys
import argparse

ROOT = r'D:/BrainMaker/大镖客2解包分析'
KEYS = ('_area_slod', '_em_slod', '_dslod', '_slod', '_lod')
COL = 'HIDDEN_LOD'

SHOTS = {
    'lawn': (2442.0, -1219.0, 170.0, (760, 760)),   # 公园草坪特写（红框问题那块）
    'park': (2470.0, -1200.0, 420.0, (760, 760)),
    'city': (2560.0, -1450.0, 900.0, (900, 900)),
    'wide': (2400.0, -1200.0, 2600.0, (1100, 1100)),
}


def argv():
  a = sys.argv
  return a[a.index('--') + 1:] if '--' in a else []


def is_lod(n):
  ln = n.lower()
  return any(k in ln for k in KEYS)


def do_hide():
  ent = bpy.data.collections.get('ENTITIES')
  if ent is None:
    raise SystemExit('没有 ENTITIES 集合')
  hid = bpy.data.collections.get(COL)
  if hid is None:
    hid = bpy.data.collections.new(COL)
    bpy.context.scene.collection.children.link(hid)
  victims = [o for o in ent.all_objects if is_lod(o.name)]
  print('[lod] ENTITIES %d 个；命中 LOD %d 个' % (len(ent.all_objects), len(victims)))
  for o in victims:
    for c in list(o.users_collection):
      c.objects.unlink(o)
    hid.objects.link(o)
    o['hide_tag'] = 'lod'
  hid.hide_viewport = True
  hid.hide_render = True
  print('[lod] 已隐藏 %d 个 → %s（未删）' % (len(victims), COL))
  return len(victims)


def diagnose_namespike(word='park_terrain'):
  """打印指定对象的状态与材质（排查"草坪为什么不绿"）。"""
  for o in bpy.data.objects:
    if word in o.name.lower():
      cols = [c.name for c in o.users_collection]
      imgs = []
      for ms in (o.material_slots or []):
        m = ms.material
        if not m or not m.use_nodes:
          imgs.append('%s(no-node)' % (m.name if m else 'None'))
          continue
        tex = [n.image.name for n in m.node_tree.nodes
               if n.type == 'TEX_IMAGE' and n.image]
        imgs.append('%s→%s' % (m.name, tex[:2] or '无图'))
      print('[diag] %-34s col=%s hide(vp=%s,render=%s,get=%s) 材质=%s'
            % (o.name, cols, o.hide_viewport, o.hide_render, o.hide_get(), imgs))


def shoot(out_dir, tag):
  os.makedirs(out_dir, exist_ok=True)
  sc = bpy.context.scene
  sc.render.engine = 'BLENDER_WORKBENCH'
  sh = sc.display.shading
  sh.light = 'STUDIO'
  sh.color_type = 'TEXTURE'
  sh.show_shadows = False
  sh.show_cavity = False
  sc.view_settings.view_transform = 'Standard'
  cd = bpy.data.cameras.new('shot_cam')
  cd.type = 'ORTHO'
  cam = bpy.data.objects.new('shot_cam', cd)
  sc.collection.objects.link(cam)
  sc.camera = cam
  for name, (cx, cy, width, res) in SHOTS.items():
    cd.ortho_scale = width
    cam.location = (cx, cy, 900.0)
    cam.rotation_euler = (0.0, 0.0, 0.0)
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.resolution_percentage = 100
    sc.render.image_settings.file_format = 'PNG'
    sc.render.filepath = os.path.join(out_dir, '%s_%s.png' % (tag, name))
    print('[shot] %s → %s' % (name, sc.render.filepath))
    bpy.ops.render.render(write_still=True)


def main():
  ap = argparse.ArgumentParser()
  ap.add_argument('--shots', action='store_true')
  ap.add_argument('--no-save', action='store_true')
  ap.add_argument('--out', default=os.path.join(ROOT, 'work/verify'))
  ap.add_argument('--tag', default='v8lod')
  a = ap.parse_args(argv())
  n = do_hide()
  diagnose_namespike()
  if a.shots and n:
    shoot(a.out, a.tag)
  if not a.no_save:
    out = bpy.data.filepath
    bpy.ops.wm.save_as_mainfile(filepath=out)
    print('[lod] saved %s (%.2f GB)' % (out, os.path.getsize(out) / 1e9))


if __name__ == '__main__':
  main()
