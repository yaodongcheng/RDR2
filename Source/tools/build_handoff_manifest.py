"""给下游（骑砍2 Agent / 任何引擎）生成机读交接清单。

产物 deliverable/handoff/
    model_manifest.csv        每个可加载模型的：hash / 名字 / .mdl 路径 / 三角面 / 尺寸 / 贴图 / 场景实例数
    settlements_world.csv     43 个据点的世界坐标（由 u,v 反算，含尺寸与所属势力）
    handoff_meta.json         坐标约定、版本、统计（给机器读）

用法：uv run python tools/build_handoff_manifest.py
"""
import os
import csv
import json
import glob

import numpy as np

ROOT = r'D:/BrainMaker/大镖客2解包分析'
LIB = os.path.join(ROOT, 'assets/lib_native')
IDX = os.path.join(LIB, 'index.json')
SCENE_MODELS = os.path.join(ROOT, 'export/world/continent/models.json')
TILES = os.path.join(ROOT, 'export/world/continent/tiles')
SETTLE = os.path.join(ROOT, 'export/levels/world/settlements_bannerlord.csv')
HM_META = os.path.join(ROOT, 'deliverable/heightmap/continent_height_meta.json')
W_META = os.path.join(ROOT, 'deliverable/terrain_weights/weights_meta.json')
OUT = os.path.join(ROOT, 'deliverable/handoff')

# settlements_bannerlord.csv 的 u/v 是 5000 宽缩略图坐标，配准变换：
#   world_x = -7684 + u*14.5 , world_y = 4100 - v*14.5
U2X, V2Y = 14.5, 14.5
X_OFF, Y_OFF = -7684.0, 4100.0


def main():
    os.makedirs(OUT, exist_ok=True)
    idx = json.load(open(IDX, encoding='utf-8'))
    M, T = idx['models'], idx['tex']
    tex_name = {t['id']: t['n'] for t in T}
    tex_file = {t['id']: t['f'] for t in T}
    scene = json.load(open(SCENE_MODELS, encoding='utf-8'))

    # 场景实例计数 + 名字（缺名时用 ydr 文件名兜底）
    cnt = {}
    for p in sorted(glob.glob(os.path.join(TILES, '*.json'))):
        for e in json.load(open(p)):
            cnt[e[0]] = cnt.get(e[0], 0) + 1

    rows = []
    for h, path in scene.items():
        name = os.path.basename(path).rsplit('.', 1)[0]
        m = M.get(h)
        if m:
            b = m['b']
            tris = sum(i // 3 for _, v, i in m['s'])
            verts = sum(v for _, v, _ in m['s'])
            tids = [t for t, _, _ in m['s']]
            rows.append([h, name, 1, m['f'], tris, verts,
                         round(b[3] - b[0], 3), round(b[4] - b[1], 3), round(b[5] - b[2], 3),
                         ';'.join(str(t) for t in tids if t >= 0),
                         ';'.join(tex_name.get(t, '') for t in tids if t >= 0),
                         cnt.get(int(h, 16), 0)])
        else:
            rows.append([h, name, 0, '', 0, 0, '', '', '', '', '', cnt.get(int(h, 16), 0)])

    rows.sort(key=lambda r: (-r[11], -r[4]))
    p = os.path.join(OUT, 'model_manifest.csv')
    with open(p, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.writer(f)
        w.writerow(['hash', 'name', 'in_lib', 'mdl', 'tris', 'verts',
                    'size_x', 'size_y', 'size_z', 'tex_ids', 'tex_names', 'instances'])
        w.writerows(rows)
    missing = sum(1 for r in rows if r[2] == 0)
    print('model_manifest.csv  %d 行（缺模型 %d）' % (len(rows), missing))

    # 据点世界坐标
    srows = []
    for r in csv.DictReader(open(SETTLE, encoding='utf-8-sig')):
        u, v = float(r['u']), float(r['v'])
        srows.append(dict(code=r['code'], name_zh=r['name_zh'], name_en=r['name_en'],
                          btype=r['btype'], faction=r['faction_zh'], owner=r['owner'],
                          bound_to=r['bound_to'],
                          world_x=round(X_OFF + u * U2X, 1),
                          world_y=round(Y_OFF - v * V2Y, 1),
                          size_w_m=float(r['size_w']), size_d_m=float(r['size_d']),
                          u=u, v=v))
    p2 = os.path.join(OUT, 'settlements_world.csv')
    with open(p2, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=list(srows[0]))
        w.writeheader()
        w.writerows(srows)
    print('settlements_world.csv  %d 个据点' % len(srows))

    hm = json.load(open(HM_META, encoding='utf-8'))
    wm = json.load(open(W_META, encoding='utf-8'))
    meta = dict(
        generated_from='tools/build_handoff_manifest.py',
        area=hm['x0'], area_end=[hm['x1'], hm['y1']], size_m=hm['size_m'], res_m=hm['res_m'],
        heightmap=dict(png='deliverable/heightmap/continent_height_4m.png',
                       raw='deliverable/heightmap/continent_height_r16.raw',
                       zmin=hm['heightmap']['zmin'], zmax=hm['heightmap']['zmax'],
                       formula=hm['heightmap']['z_formula'], row0='north'),
        weights=dict(dir='deliverable/terrain_weights', layers=[l['key'] for l in wm['layers']],
                     res_m=wm['res_m'], row0='north'),
        world_to_pixel='col = (x - x0)/4 ; row = (y1 - y)/4',
        pixel_to_world='x = x0 + col*4 ; y = y1 - row*4',
        ground_color=dict(base='export/world/world_ground_final_out.png', px=12296, res_m=1.0,
                          hi_detail='export/world/world_ground_2p0.png', hi_res_m=0.5,
                          hi_detail_note='0.5 m/px，但外延补丁区是空的（16.8% 近黑）'),
        instances='export/world/continent/tiles/*.json  字段 [hash,x,y,z,qx,qy,qz,qw,sxy,sz,cls]',
        model_lib='assets/lib_native  (index.json + <shard>/<hash>.mdl + tex/<id>.png)',
        counts=dict(scene_entities=182158, scene_archetypes=len(scene),
                    lib_models=len(M), lib_textures=len(T),
                    loadable_missing=missing),
        units='meter', up_axis='RDR2 世界 Z 向上；转换到目标引擎需按引擎 up 轴重映射（务必先做标定场景）')
    json.dump(meta, open(os.path.join(OUT, 'handoff_meta.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print('handoff_meta.json')


if __name__ == '__main__':
    main()
