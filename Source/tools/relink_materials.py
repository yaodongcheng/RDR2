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
  tex = {t['id']: t['n'] for t in d['tex']}
  return d['models'], tex


def make_material(tid, texname):
  name = 'm_%d' % tid
  m = bpy.data.materials.get(name)
  if m:
    return m
  m = bpy.data.materials.new(name)
  m.use_nodes = True
  nt = m.node_tree
  bsdf = next((n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED'), None)
  if bsdf is None:
    return m
  fp = os.path.join(LIB, 'tex', '%04d.png' % tid)
  if os.path.exists(fp):
    t = nt.nodes.new('ShaderNodeTexImage')
    t.image = bpy.data.images.load(fp, check_existing=True)
    t.location = (-380, 200)
    nt.links.new(t.outputs['Color'], bsdf.inputs['Base Color'])
    bsdf.inputs['Roughness'].default_value = 0.72
    if 'Specular IOR Level' in bsdf.inputs:
      bsdf.inputs['Specular IOR Level'].default_value = 0.25
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
    # 构建期按"贴图去重"建槽：同一个 tid 只建一个材质槽，槽序=首次出现顺序。
    # 所以目标槽 = s 里按首次出现去重后的 tid 序列。
    uniq = []
    for tid, _vc, _ic in s:
      if tid < 0:
        if None not in uniq:
          uniq.append(None)
        continue
      if tid not in uniq:
        uniq.append(tid)
    targets = [None if t is None else make_material(t, tex.get(t)) for t in uniq]
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
