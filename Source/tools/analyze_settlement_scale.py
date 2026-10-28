"""实测 46 个据点的"微缩模型"输入数据 —— 规格表与建模预算的唯一依据。

数据源（全部本地已有，不联网）
  export/levels/world/town_data/*.js   全世界 182 303 条唯一实体实例（含四元数/缩放/本地 AABB）
      window.RDR2_TOWNS["<code>"] = [[hash, x,y,z, qx,qy,qz,qw, sx,sy,sz, minx,miny,minz, maxx,maxy,maxz], ...]
      sdn.js 只放了少量核心件，其它落在 _misc.js —— 所以必须"全量并集去重"，不能只读 <code>.js
  deliverable/handoff/model_manifest.csv
      hash,name,in_lib,mdl,tris,verts,size_x,size_y,size_z,tex_ids,tex_names,instances
  deliverable/handoff/settlements_world_v2.csv
      code,name_zh,...,world_x,world_y,size_w_m,size_d_m

输出
  deliverable/handoff/settlement_scale.csv    每据点一行（实测，供人看）
  deliverable/handoff/settlement_scale.json   同上 + 地标候选 + 预算建议（供建模脚本吃）

分类口径（写死，避免每次重新吵）
  building : 模型名以 new_/val_/cor_/sdn_/old_/roa_/agu_/ann_/... 开头，且不是 debris/veg/water
             —— 实测 new_* 是建筑件（bank / mansion / jail / church…），p_* 是道具
  prop     : p_* 等，只在"地标候选"里给船/火车/水塔这类有辨识度的留位置
  raw_tris : manifest 三角面 × 出现次数，**不减面、不含 LOD 判断**
"""
import os
import re
import csv
import json
import math
import glob
from collections import defaultdict, Counter

ROOT = r'D:/BrainMaker/大镖客2解包分析'
TOWN_DATA = os.path.join(ROOT, 'export/levels/world/town_data')
LEDGER = os.path.join(ROOT, 'deliverable/handoff/model_ledger.csv')
SETTLE = os.path.join(ROOT, 'deliverable/handoff/settlements_world_v2.csv')
OUT_CSV = os.path.join(ROOT, 'deliverable/handoff/settlement_scale.csv')
OUT_JSON = os.path.join(ROOT, 'deliverable/handoff/settlement_scale.json')

PREFIX = re.compile(r'=\s*(\[.*\]);?\s*$', re.S)

# 建筑构件名首缀（实测 new_* 占建筑绝大多数；val_/cor_/sdn_/old_ 是这些据点的专用件）
BLD_PREFIX = (
    'new_', 'val_', 'cor_', 'sdn_', 'old_', 'roa_', 'agu_', 'ann_', 'arm_',
    'bla_', 'bra_', 'cal_', 'eme_', 'fom_', 'han_', 'mfr_', 'rho_', 'sis_',
    'str_', 'tum_', 'van_', 'wap_', 'but_', 'lag_', 'ora_', 'dew_', 'bee_',
    'rid_', 'cle_', 'lak_', 'col_', 'sha_', 'gua_', 'wal_', 'pro_', 'dow_',
    'man_', 'che_', 'hso_', 'abe_', 'roc_', 'lon_', 'sod_', 'gap_', 'mic_',
    'twi_', 'rat_', 'sis_',
)
# 名字里带这些的即使前缀对也不是"房子"（火车残骸 / 植被 / 水域 / 碰撞 / 远景）
BLD_BAD = ('debris', '_veg', 'veg_', 'water', 'collision', '_slod', '_lod',
           'audioproxy', 'occlusion', 'helper', 'vfx_', 'decal_', '_strm',
           'terrain', 'ground', '_shadow', 'light_', 'leaves', 'tree', 'bush',
           '__hd_', '_hd_0', 'p_12__', 'rock_', '_rock', 'weed', 'grass',
           'decal', 'kudzu', 'cable', 'glue', 'detail', '_dtl', '_dec',
           'roaddetail', '_trail', '_track', '_int', '_far', '_script',
           'vertex', '_vw', 'fence', 'hitching', 'post_', 'rail_')
# 这些前缀是道具 / 植被 / 车 / 远景，永远不是"房子"
NOT_BLD_PREFIX = ('p_', 's_', 'w_', 'v_', 'crp_', 'su_', 'rdr_', 'meta_',
                  'j_', 'dak_', 'veg_', 'amb_', 'prop_')
# 有辨识度、值得保留的道具（船 / 火车 / 水塔 / 井架）
KEEP_PROP = ('ship', 'boat', 'train', 'watertower', 'tank', 'derrick', 'crane',
             'windmill', 'church', 'station', 'bridge', 'tower')


def load_manifest():
    """全量台账：lib_native 52 539 个网格的 bbox + 三角面 + 名字。"""
    d = {}
    with open(LEDGER, encoding='utf-8-sig') as f:
        for r in csv.DictReader(f):
            try:
                h = int(r['hash'], 16)
            except ValueError:
                continue
            d[h] = {
                'name': r['name'],
                'tris': int(r['tris'] or 0),
                'verts': int(r['verts'] or 0),
                'sx': float(r['sx'] or 0),
                'sy': float(r['sy'] or 0),
                'sz': float(r['sz'] or 0),
            }
    return d


def load_settlements():
    rows = []
    with open(SETTLE, encoding='utf-8-sig') as f:
        for r in csv.DictReader(f):
            if not r['code']:
                continue
            r['world_x'] = float(r['world_x'])
            r['world_y'] = float(r['world_y'])
            r['size_w_m'] = float(r['size_w_m'])
            r['size_d_m'] = float(r['size_d_m'])
            rows.append(r)
    return rows


def load_all_instances():
    """全量并集去重：(hash, x, y, z) 四舍五入到 0.1 m。"""
    uni = {}
    for p in glob.glob(os.path.join(TOWN_DATA, '*.js')):
        txt = open(p, encoding='utf-8', errors='replace').read()
        m = PREFIX.search(txt)
        if not m:
            continue
        try:
            arr = json.loads(m.group(1))
        except json.JSONDecodeError:
            continue
        for e in arr:
            k = (e[0], round(e[1], 1), round(e[2], 1), round(e[3], 1))
            if k not in uni:
                uni[k] = e
    return list(uni.values())


def is_building(name, sz=None, tris=None):
    """房子判定：名字干净 + 前缀不是道具 + 够高。
    不再依赖固定前缀表 —— 各据点建筑前缀五花八门（rho_station / val_01_trainstn_ext /
    new_com_02_bank / 干脆无名），用"高度 + 前缀排除"更稳。"""
    n = name.lower()
    if any(b in n for b in BLD_BAD):
        return False
    if n.startswith(NOT_BLD_PREFIX):
        return False
    if sz is not None and sz < 2.5:
        return False
    if tris is not None and tris < 40:
        return False
    return True


def is_keep_prop(name):
    n = name.lower()
    return n.startswith('p_') and any(k in n for k in KEEP_PROP)


def raster_footprint(insts, man, cell=1.0, key=None):
    """所有实例世界 AABB 投影到 XY 的并集面积（1 m 栅格）。key 可只统计建筑。"""
    cells = set()
    for it in insts:
        m = man.get(it[0])
        if key and (not m or not key(m)):
            continue
        minx, miny, maxx, maxy = it[11], it[12], it[14], it[15]
        if maxx <= minx or maxy <= miny:
            continue
        x0, x1 = int(math.floor(it[1] + minx)), int(math.ceil(it[1] + maxx))
        y0, y1 = int(math.floor(it[2] + miny)), int(math.ceil(it[2] + maxy))
        for gx in range(x0, x1):
            for gy in range(y0, y1):
                cells.add((gx, gy))
    return len(cells) * cell * cell


def main():
    man = load_manifest()
    settles = load_settlements()
    insts_all = load_all_instances()
    print(f'实例并集 {len(insts_all):,} 条 / manifest {len(man):,} 个模型')

    out = []
    for s in settles:
        code = s['code']
        cx, cy = s['world_x'], s['world_y']
        hw, hd = s['size_w_m'] / 2, s['size_d_m'] / 2
        # 取景盒外扩 25 m（规格里"取景外扩 ≤50 m"的下限），避免切掉最外一圈房子
        pad = min(25.0, 0.1 * max(hw, hd))
        sel = [e for e in insts_all
               if abs(e[1] - cx) <= hw + pad and abs(e[2] - cy) <= hd + pad]

        n_inst = len(sel)
        n_bld = 0
        raw_tris = 0
        bld_tris = 0
        miss = 0
        landmarks = []
        heights = []
        for e in sel:
            m = man.get(e[0])
            if not m:
                miss += 1
                continue
            raw_tris += m['tris']
            nm = m['name']
            if is_building(nm, m['sz'], m['tris']):
                n_bld += 1
                bld_tris += m['tris']
                heights.append(m['sz'])
                # 地标候选打分：占地 × 高度（教堂/银行/庄园/监狱这类自然排前）
                area = abs(m['sx'] * m['sy'])
                landmarks.append((area * max(m['sz'], 1.0), nm, round(m['sx'], 1),
                                  round(m['sy'], 1), round(m['sz'], 1), m['tris']))
            elif is_keep_prop(nm):
                area = abs(m['sx'] * m['sy'])
                landmarks.append((area * max(m['sz'], 1.0) * 0.6, nm, round(m['sx'], 1),
                                  round(m['sy'], 1), round(m['sz'], 1), m['tris']))

        foot_all = raster_footprint(sel, man)
        foot_bld = raster_footprint(
            sel, man, key=lambda m: is_building(m['name'], m['sz'], m['tris']))
        bbox = s['size_w_m'] * s['size_d_m']

        # 地标去重（同名只留一个），取前 3
        seen = set()
        land3 = []
        for sc, nm, sx, sy, sz, tr in sorted(landmarks, reverse=True):
            if nm in seen:
                continue
            seen.add(nm)
            land3.append({'name': nm, 'sx': sx, 'sy': sy, 'sz': sz, 'tris': tr})
            if len(land3) == 3:
                break

        out.append({
            'code': code,
            'name_zh': s['name_zh'],
            'name_en': s['name_en'],
            'btype': s['btype'],
            'faction': s['faction'],
            'world_x': cx,
            'world_y': cy,
            'size_w': s['size_w_m'],
            'size_d': s['size_d_m'],
            'bbox_m2': round(bbox, 1),
            'foot_all_m2': round(foot_all, 1),
            'foot_bld_m2': round(foot_bld, 1),
            'n_inst': n_inst,
            'n_bld': n_bld,
            'miss_model': miss,
            'raw_tris': raw_tris,
            'bld_tris': bld_tris,
            'max_h': round(max(heights), 1) if heights else 0,
            'density_per_ha': round(n_bld / bbox * 10000, 2) if bbox else 0,
            'landmarks': land3,
        })

    out.sort(key=lambda r: -r['bbox_m2'])

    with open(OUT_CSV, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['code', 'name_zh', 'name_en', 'btype', 'faction',
                    'world_x', 'world_y', 'size_w', 'size_d', 'bbox_m2',
                    'foot_all_m2', 'foot_bld_m2', 'n_inst', 'n_bld',
                    'miss_model', 'raw_tris', 'bld_tris', 'max_h',
                    'density_per_ha', 'landmark1', 'landmark2', 'landmark3'])
        for r in out:
            lm = [x['name'] for x in r['landmarks']] + ['', '', '']
            w.writerow([r['code'], r['name_zh'], r['name_en'], r['btype'], r['faction'],
                        r['world_x'], r['world_y'], r['size_w'], r['size_d'],
                        r['bbox_m2'], r['foot_all_m2'], r['foot_bld_m2'],
                        r['n_inst'], r['n_bld'], r['miss_model'], r['raw_tris'],
                        r['bld_tris'], r['max_h'], r['density_per_ha'],
                        lm[0], lm[1], lm[2]])
    with open(OUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)

    tot_inst = sum(r['n_inst'] for r in out)
    tot_tris = sum(r['raw_tris'] for r in out)
    tot_bld = sum(r['n_bld'] for r in out)
    tot_foot = sum(r['foot_bld_m2'] for r in out)
    print(f'据点 {len(out)} | 实例 {tot_inst:,} | 建筑 {tot_bld:,} '
          f'| 原始三角面 {tot_tris:,} | 建筑占地 {tot_foot:,.0f} m²')
    print()
    hdr = (f"{'code':7}{'类型':8}{'名字':13}{'设定占地 m':>13}{'建筑占地':>9}"
           f"{'实体':>7}{'建筑':>6}{'原始面':>11}{'最高':>6}{'建筑/ha':>8}  地标")
    print(hdr)
    print('-' * 120)
    for r in out:
        print(f"{r['code']:7}{r['btype']:8}{r['name_zh'][:11]:13}"
              f"{r['size_w']:5.0f}x{r['size_d']:<7.0f}{r['foot_bld_m2']:9.0f}"
              f"{r['n_inst']:7d}{r['n_bld']:6d}{r['raw_tris']:11,d}"
              f"{r['max_h']:6.1f}{r['density_per_ha']:8.1f}  "
              + ', '.join(x['name'] for x in r['landmarks']))


if __name__ == '__main__':
    main()
