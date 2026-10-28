# -*- coding: utf-8 -*-
"""构建末尾输出「对象级清单」，之后核对一律读清单，不再为看一眼打开 6.4 GB blend。

AGENTS.md §3：验证要数字，不靠肉眼；打开 6 GB blend 每次 10~20 分钟 → 必须走 manifest。

产物（与 blend 同目录）：
    manifest_<blend名>.jsonl   每行一个对象（流式写，内存友好）
    manifest_<blend名>.json    汇总（计数/分类/材质→贴图/包围盒/PASS 判定）
    manifest.json              恒定指向最新一次的汇总（小文件，内含 objects_file）

jsonl 每行字段（**短键是为了省空间，13 万行**）：
    n  对象名（RDR2 原名，查不到时 e_<hash>）
    h  hash（0x 补零 8 位）
    c  分类（rail/struct/decal/veg/rock/veh/bldg/part/junk/prop/int/unknown，
       HIDDEN_TERRAIN_CELL 里的是 hidden_terrain，地形 Terrain、Water 单列）
    tid 地块（集合名 <cat>|<tid> 的后半段）
    hid 0/1 是否默认隐藏（对象或所属集合任一关可见性即算）
    tag hide_tag 原值（terrain_cell / flat_piece）
    p  位置 x,y,z（2 位小数）
    bb 世界包围盒 minx,miny,minz,maxx,maxy,maxz（2 位小数；非网格对象省略）
    t  该对象用到的贴图名（≤4 个；来自 LIB 索引 tex 表）
    nt 1 = 有无 albedo 的兜底纯色材质（ntex_*），贴图核对时要单独看

用法：
    blender -b <blend> -P tools/write_manifest.py -- --out <blend>
（`--full` 构建链末尾会自动调用）
"""
import bpy
import os
import sys
import json
import time
import argparse

ROOT = r'D:/BrainMaker/大镖客2解包分析'
CLASSES = ('rail', 'struct', 'decal', 'veg', 'rock', 'veh', 'bldg', 'part',
           'junk', 'prop', 'int', 'unknown')
HIDDEN_COL = 'HIDDEN_TERRAIN_CELL'
HIDDEN_VEG = 'HIDDEN_VEG'
HIDDEN_PARKED = 'HIDDEN_PARKED'

# 「应删未删」要用和 strip_vegetation 完全同一个正则（口径不一致会互相打脸：
# classify 的 veg 类还把常春藤/盆栽/种植园算进去，那些是**故意保留**的）。
try:
  import sys as _sys, os as _os
  _t = _os.path.dirname(_os.path.abspath(__file__))
  if _t not in _sys.path:
    _sys.path.insert(0, _t)
  from strip_vegetation import VEG as SHOULD_DEL
except Exception as _e:     # 兜底：与 strip_vegetation.py 保持字面一致
  import re
  SHOULD_DEL = re.compile(
    r'(^|/)(p_tree|p_bush|p_shrub|p_grass|p_plant|p_fern|p_cactus|p_palm|p_reed|p_lily|p_ivy|p_vine)'
    r'|rdr_bush|_tree_|_bush_|_shrub|_fern_|_grass_|_cactus', re.I)
  print('[mf] 复用 strip_vegetation.VEG 失败，用内置副本：%s' % _e)


def argv():
  a = sys.argv
  return a[a.index('--') + 1:] if '--' in a else []


def tex_names():
  """LIB 索引 tex 表：tex_id → 贴图名（材质名 m_<id> 就是靠它翻译回名字的）。"""
  out = {}
  p = os.path.join(ROOT, 'assets/lib_native/index.json')
  try:
    idx = json.load(open(p, encoding='utf-8'))
    for t in idx.get('tex', []):
      try:
        tid = int(t['id'])
      except Exception:
        continue
      out[tid] = t.get('n') or os.path.splitext(os.path.basename(t.get('f', '')))[0]
  except Exception as e:
    print('[mf] 贴图名表读取失败（贴图列会空）：%s' % e)
  return out


def _mat_tex(mat, names):
  """材质 → 贴图名；返回 (名字, 是否兜底纯色)。

  2026-10-29 起构建按**贴图名字**建材质（`alb_<name>` / `nonalbedo_warmgray`），
  旧的 `m_<tid>` 只在更早的 blend 里存在，两条都认。
  """
  n = mat.name
  if n.startswith('alb_'):
    return n[4:], False
  if n.startswith('nonalbedo') or n.startswith('ntex_'):
    return '', True
  if n.startswith('m_'):
    try:
      tid = int(n[2:])
    except Exception:
      return n, False
    if tid < 0 or tid >= 0xFFFFFFF0:      # -1 / 0xFFFFFFFF = submesh 没有 albedo
      return '', True
    nm = names.get(tid)
    return (nm, False) if nm else ('tex%d' % tid, False)
  return n, False


def mesh_tex(me, names, cache):
  k = me.name
  if k in cache:
    return cache[k]
  out = []
  ntex = False
  for m in me.materials:
    if m is None:
      continue
    nm, fb = _mat_tex(m, names)
    if fb:
      ntex = True
    if nm and nm not in out:
      out.append(nm)
  res = (tuple(out[:4]), ntex)
  cache[k] = res
  return res


def bbox_world(ob):
  try:
    bb = ob.bound_box
  except Exception:
    return None
  if not bb:
    return None
  mw = ob.matrix_world
  xs = []
  ys = []
  zs = []
  for c in bb:
    v = mw @ __import__('mathutils').Vector((c[0], c[1], c[2]))
    xs.append(v.x); ys.append(v.y); zs.append(v.z)
  return [min(xs), min(ys), min(zs), max(xs), max(ys), max(zs)]


def obj_class(ob):
  cat = ''
  tid = ''
  hidden = bool(ob.hide_viewport or ob.hide_render)
  for c in ob.users_collection:
    k = c.get('cat')
    if k:
      cat = k
      tid = c.get('tile') or tid
    if c.hide_viewport or c.hide_render:
      hidden = True
    if c.name == HIDDEN_COL:
      cat = 'hidden_terrain'
    elif c.name == HIDDEN_VEG:
      cat = 'veg_hidden'
    elif c.name == HIDDEN_PARKED:
      cat = 'parked_hidden'
  if not cat:
    nm = ob.name
    if nm == 'Terrain' or nm.startswith('terrain'):
      cat = 'terrain'
    elif nm == 'Water':
      cat = 'water'
    elif nm == 'Sun':
      cat = 'light'
    elif nm.startswith('Cam'):
      cat = 'camera'
    else:
      cat = 'other'
  return cat, tid, hidden


def r2(v):
  return round(float(v), 2)


def main():
  ap = argparse.ArgumentParser()
  ap.add_argument('--out', default='')
  a = ap.parse_args(argv())

  out = a.out or bpy.data.filepath
  if not out:
    raise SystemExit('没有 --out，也不在 .blend 里')
  out = os.path.abspath(out)
  d = os.path.dirname(out)
  base = os.path.splitext(os.path.basename(out))[0]
  jl_path = os.path.join(d, 'manifest_%s.jsonl' % base)
  js_path = os.path.join(d, 'manifest_%s.json' % base)

  names = tex_names()
  print('[mf] 贴图名表 %d 条' % len(names))

  t0 = time.time()
  objs = list(bpy.context.scene.objects)
  print('[mf] 场景对象 %d' % len(objs))

  cache = {}
  cls_cnt = {}
  hidden_cnt = 0
  ntex_cnt = 0
  tex_used = set()
  mat_cnt = {}
  world_bb = [1e18, 1e18, 1e18, -1e18, -1e18, -1e18]
  ent_total = 0
  ents = bpy.data.collections.get('ENTITIES')
  ent_total = len(ents.all_objects) if ents else 0

  meta = {'_meta': {'blend': out, 'built': time.strftime('%Y-%m-%dT%H:%M:%S'),
                    'objects': len(objs), 'entities': ent_total,
                    'fields': 'n,h,c,tid,hid,tag,p,bb,t,nt'}}
  with open(jl_path, 'w', encoding='utf-8') as f:
    f.write(json.dumps(meta, ensure_ascii=False) + '\n')
    for i, ob in enumerate(objs):
      cat, tid, hidden = obj_class(ob)
      cls_cnt[cat] = cls_cnt.get(cat, 0) + 1
      if hidden:
        hidden_cnt += 1
      rec = {'n': ob.name, 'c': cat}
      hx = ob.get('hash')
      if hx:
        rec['h'] = hx
      if tid:
        rec['tid'] = tid
      if hidden:
        rec['hid'] = 1
      tag = ob.get('hide_tag')
      if tag:
        rec['tag'] = tag
      rec['p'] = [r2(ob.location.x), r2(ob.location.y), r2(ob.location.z)]
      bb = bbox_world(ob)
      if bb:
        rec['bb'] = [r2(v) for v in bb]
        world_bb[0] = min(world_bb[0], bb[0]); world_bb[1] = min(world_bb[1], bb[1])
        world_bb[2] = min(world_bb[2], bb[2]); world_bb[3] = max(world_bb[3], bb[3])
        world_bb[4] = max(world_bb[4], bb[4]); world_bb[5] = max(world_bb[5], bb[5])
      if ob.type == 'MESH' and ob.data is not None:
        tl, fb = mesh_tex(ob.data, names, cache)
        for m in ob.data.materials:
          if m is not None:
            mat_cnt[m.name] = mat_cnt.get(m.name, 0) + 1
        if tl:
          rec['t'] = list(tl)
          tex_used.update(tl)
        if fb:
          rec['nt'] = 1
          ntex_cnt += 1
      f.write(json.dumps(rec, ensure_ascii=False) + '\n')
      if (i + 1) % 20000 == 0:
        print('[mf] 已写 %d / %d（%.0fs）' % (i + 1, len(objs), time.time() - t0))

  veg_left = 0
  veg_miss = 0
  # 2026-10-29：这两段原本在 Blender 里扫 `collection.all_objects`（每次访问都重算），
  # 14.7 万对象实测卡住 **20~35 分钟**（jsonl 早已写完）。改成：jsonl 写完就交给
  # `manifest_from_jsonl.py` 用同一份数据、同一套口径反算（0.5 秒），
  # 只有它不可用时才退回下面的现场统计。
  try:
    import manifest_from_jsonl as _MF
    _MF.main(['--jsonl', jl_path])
    s = json.load(open(js_path, encoding='utf-8'))
    print('[mf] 对象清单 %s（%.1f MB，%.0fs）' % (
      jl_path, os.path.getsize(jl_path) / 1e6, time.time() - t0))
    print('[mf] 汇总 %s（由 manifest_from_jsonl 反算）' % js_path)
    print('[mf] ENTITIES %d / 分类 %d/%d %s / 隐藏 %d（地形 %d、植被 %d、占位 %d）/ '
          '待隐藏未隐藏 %d / 贴图用 %d / 无 albedo %d'
          % (s.get('entities', 0), s.get('classes_n', 0), 12,
             ','.join(s.get('classes', {})), s.get('hidden', 0),
             s.get('hidden_terrain', 0), s.get('veg_hidden', 0), s.get('parked_hidden', 0),
             s.get('veg_should_delete', 0), s.get('textures_used', 0),
             s.get('no_albedo_objects', 0)))
    return s
  except Exception as _e:
    print('[mf] manifest_from_jsonl 不可用（%s），退回内置汇总（会很慢）' % _e)

  for o in (ents.all_objects if ents else []):
    for c in o.users_collection:
      if c.name.startswith('veg|'):
        veg_left += 1
        break

  # 「应删未删」：按 strip_vegetation 的正则重扫一遍 ENTITIES，正常应为 0
  veg_miss = 0
  for o in (ents.all_objects if ents else []):
    if SHOULD_DEL.search(o.name.split('.')[0].lower()):
      veg_miss += 1

  cats = sorted(k for k in cls_cnt if k in CLASSES)
  size_gb = os.path.getsize(out) / 1e9 if os.path.exists(out) else 0.0
  verdict = (ent_total > 0 and len(cats) >= 10 and veg_miss == 0)
  summary = {
    'blend': out,
    'blend_size_gb': round(size_gb, 2),
    'built': time.strftime('%Y-%m-%dT%H:%M:%S'),
    'objects_file': os.path.basename(jl_path),
    'objects': len(objs),
    'entities': ent_total,
    'classes': {k: cls_cnt[k] for k in cats},
    'classes_n': len(cats),
    'classes_expected': 12,
    'hidden': hidden_cnt,
    'hidden_terrain': cls_cnt.get('hidden_terrain', 0),
    'veg_hidden': cls_cnt.get('veg_hidden', 0),
    'parked_hidden': cls_cnt.get('parked_hidden', 0),
    'veg_left': veg_left,
    'veg_should_delete': veg_miss,
    'materials': len(mat_cnt),
    'textures_used': len(tex_used),
    'no_albedo_objects': ntex_cnt,
    'world_bbox': [r2(v) for v in world_bb],
    'verdict': 'PASS' if verdict else 'CHECK',
  }
  with open(js_path, 'w', encoding='utf-8') as f:
    json.dump(summary, f, ensure_ascii=False, indent=1)
  with open(os.path.join(d, 'manifest.json'), 'w', encoding='utf-8') as f:
    json.dump(summary, f, ensure_ascii=False, indent=1)

  print('[mf] 对象清单 %s（%.1f MB，%.0fs）' % (
    jl_path, os.path.getsize(jl_path) / 1e6, time.time() - t0))
  print('[mf] 汇总 %s' % js_path)
  print('[mf] ENTITIES %d / 分类 %d/%d %s / 隐藏 %d（地形 %d、植被 %d）/ 待隐藏未隐藏 %d / 贴图用 %d / 无 albedo %d'
        % (ent_total, len(cats), 12, ','.join(cats), hidden_cnt,
           cls_cnt.get('hidden_terrain', 0), cls_cnt.get('veg_hidden', 0), veg_miss,
           len(tex_used), ntex_cnt))
  return summary


if __name__ == '__main__':
  main()
