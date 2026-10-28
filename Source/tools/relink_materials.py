# -*- coding: utf-8 -*-
"""按当前 `index.json` 重新给已有 blend 的网格挂材质（修"贴图串号/陈旧绑定"）。

## 为什么需要

blend 里的材质名是 `m_<tid>`，tid 指向 `assets/lib_native/tex/<tid>.png`。
只要之后又跑了 `rebind_textures.py`（按名字重绑），库里的 `s` 会变成**正确**的 tid，
但**已经存盘的 blend 不会自动更新** —— 于是同一个对象还挂着旧材质：

    实测（v8 公园草坪）
      blend 里：m_352 = p_doornbd39x_ab, m_353 = p_door34x_2_ab   ← 门皮（发黄）
      库里现在：s = [[2607 草], [2606 土], …]                        ← 正确

本脚本用对象自带的 `ob['hash']` 查当前 `s`，把每个网格的材质槽重挂一遍
（只改材质引用，不碰网格/变换/隐藏状态），缺的材质按需创建。

    blender -b <blend> --python tools/_unbuffer.py -P tools/relink_materials.py [-- --dry]
"""
import bpy
import os
import sys
import json
import argparse

ROOT = r'D:/BrainMaker/大镖客2解包分析'
LIB = os.path.join(ROOT, 'assets/lib_native')
INDEX = os.path.join(LIB, 'index.json')


def argv():
  a = sys.argv
  return a[a.index('--') + 1:] if '--' in a else []


def load_index():
    d = json.load(open(INDEX, encoding='utf-8'))
    tex = {t['id']: t for t in d['tex']}       # id -> {'n': 名字, 'f': tex/xxxxx.png}
    return d['models'], tex


def _slug(name, limit=58):
  import re as _re
  s = _re.sub(r'[^0-9A-Za-z_.-]+', '_', (name or '')).strip('_')
  return s[:limit] or 'noname'


def _img_nodes(m):
  return [n for n in (m.node_tree.nodes if m and m.use_nodes else [])
          if n.type == 'TEX_IMAGE']


def _set_image(m, fp, texname):
  """把材质里的贴图换成 fp（名字相同但文件变了时必须刷新，否则还是旧图）。"""
  nt = m.node_tree
  nodes = _img_nodes(m)
  cur = nodes[0] if nodes else None
  if cur is not None and cur.image and os.path.abspath(bpy.path.abspath(cur.image.filepath)) == os.path.abspath(fp):
    return
  img = bpy.data.images.load(fp, check_existing=True)
  img.colorspace_settings.name = 'sRGB'
  if cur is None:
    cur = nt.nodes.new('ShaderNodeTexImage')
    cur.location = (-380, 200)
    bsdf = next((n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED'), None)
    if bsdf is None:
      return
    nt.links.new(cur.outputs['Color'], bsdf.inputs['Base Color'])
  cur.image = img
  cur.label = texname


def make_material(tid, tinfo):
  """按**贴图名字**建/取材质（与 blender_continent._mat_for 同一套命名：`alb_<名字>`）。

  2026-10-29 根修（TODO #1）：旧版按 `m_<tid>` 命名，贴图池一变（3,025→5,292）
  `m_352` 就指向别人的图 —— "门长草/草坪发黄"都是这么来的。

  2026-10-29 二改（贴图表按名字重建）：`tex` 表整表重建后，同名材质的**图片文件路径会变**
  （`tex/0352.png` → `tex/00523.png`），所以已存在的同名材质必须**刷新图片**，不能直接返回。
  """
  texname = (tinfo or {}).get('n') or ''
  rel = (tinfo or {}).get('f') or ''
  name = ('alb_' + _slug(texname)) if texname else 'nonalbedo_warmgray'
  fp = os.path.join(LIB, rel.replace('/', os.sep)) if rel else ''
  m = bpy.data.materials.get(name)
  if m:
    if texname and fp and os.path.exists(fp):
      m['albedo'] = texname
      _set_image(m, fp, texname)
    return m
  m = bpy.data.materials.new(name)
  m.use_nodes = True
  nt = m.node_tree
  bsdf = next((n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED'), None)
  if bsdf is None:
    return m
  if texname and fp and os.path.exists(fp):
    m['albedo'] = texname
    _set_image(m, fp, texname)
    bsdf.inputs['Roughness'].default_value = 0.72
    if 'Specular IOR Level' in bsdf.inputs:
      bsdf.inputs['Specular IOR Level'].default_value = 0.25
  else:
    bsdf.inputs['Base Color'].default_value = (0.30, 0.27, 0.23, 1.0)
    bsdf.inputs['Roughness'].default_value = 0.85
    m.diffuse_color = (0.30, 0.27, 0.23, 1.0)   # Workbench/Solid 用的视口色，别留默认灰白
  m.roughness = 0.85
  return m


def main():
  ap = argparse.ArgumentParser()
  ap.add_argument('--dry', action='store_true')
  ap.add_argument('--limit', type=int, default=0)
  a = ap.parse_args(argv())

  models, tex = load_index()
  print('[relink] 库内模型 %d，贴图 %d' % (len(models), len(tex)))

  done = 0
  changed = 0
  miss_hash = 0
  miss_model = 0
  mism = 0
  for ob in bpy.data.objects:
    if ob.type != 'MESH':
      continue
    hx = ob.get('hash')
    if not hx:
      miss_hash += 1
      continue
    e = models.get(hx)
    if not e:
      miss_model += 1
      continue
    s = e.get('s') or []
    me = ob.data
    # 目标槽：**一个子网格一个槽，槽序 == 子网格序**（2026-10-29 起构建不再做槽去重）。
    # 老 blend（去重版）的槽数会 ≠ 子网格数 → 走 `mism` 分支跳过，不硬挂（避免又串号）。
    targets = [make_material(tid, tex.get(tid)) if tid is not None and tid >= 0
               else None for tid, _vc, _ic in s]
    if a.dry:
      done += 1
      continue
    cur = list(me.materials)
    if len(cur) != len(targets):
      mism += 1
      continue
    for i, m in enumerate(targets):
      if m is None:          # 该子网格没有 albedo → 保留原有兜底材质，不清空
        continue
      if cur[i] is not m:
        me.materials[i] = m
        changed += 1
    done += 1
    if a.limit and done >= a.limit:
      break

  print('[relink] 处理网格 %d，换材质槽 %d 个；长度不匹配跳过 %d，无 hash %d，库无此模型 %d'
        % (done, changed, mism, miss_hash, miss_model))
  if a.dry:
    print('[relink] dry-run，不存盘')
    return
  out = bpy.data.filepath
  bpy.ops.wm.save_as_mainfile(filepath=out)
  print('[relink] saved %s (%.2f GB)' % (out, os.path.getsize(out) / 1e9))


if __name__ == '__main__':
  main()
