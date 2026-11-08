# -*- coding: utf-8 -*-
"""导出角色与武器/道具到交付包（第一版：原始 GLB / glTF 原样）。

产物：
  deliverable/characters/            角色 GLB（414 个，贴图内嵌）+ index.csv/README
  deliverable/weapons/               45 把武器 glTF + bin + textures + weapon_assembly.csv
  deliverable/items/                 916 件道具 glTF + bin + textures
  deliverable/manifests/characters_export.csv
  deliverable/manifests/weapons_export.csv
  deliverable/manifests/items_export.csv

说明：
  · 角色 GLB 已确认全部内嵌贴图（images[].uri = None），不需要额外贴图目录；
  · 武器/道具的 glTF 用相对 `textures/...`，整目录拷过去即可；
  · 武器 glTF 是**拼装后的展示模型**，`weapon_assembly.csv` 记录主体/部件，供骑行2侧重组参考；
  · 这是原始资产第一版，不绑骨架、不转格式。
"""
import csv
import io
import json
import os
import shutil

RDR2 = r'D:/BrainMaker/大镖客2解包分析'
D = os.path.join(RDR2, 'deliverable')
M = os.path.join(D, 'manifests')
NPC = os.path.join(RDR2, 'export/npc')
VIEWER = os.path.join(RDR2, 'export/viewer')
ASSEMBLY = os.path.join(RDR2, 'export/levels/world/weapon_assembly.csv')


def rows(p):
    return list(csv.DictReader(io.open(p, encoding='utf-8-sig')))


def main():
    os.makedirs(M, exist_ok=True)

    # ---------- 角色 ----------
    out_c = os.path.join(D, 'characters')
    shutil.copytree(NPC, out_c, dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns('*.png', '*.html', 'verify'))
    crows = []
    for r in rows(os.path.join(NPC, 'index.csv')):
        glb = (r.get('glb') or '').split('?')[0]
        src = os.path.join(NPC, glb.replace('/', os.sep))
        dst = os.path.join(out_c, glb.replace('/', os.sep))
        if not os.path.exists(src):
            continue
        crows.append([r.get('rank'), r.get('tier'), r.get('cn_name'), r.get('name'),
                      r.get('category'), glb, 'characters/' + glb,
                      os.path.getsize(dst), r.get('parts'), r.get('verts'),
                      r.get('tris'), r.get('textures'), r.get('sources')])
    with io.open(os.path.join(M, 'characters_export.csv'), 'w',
                 encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f)
        w.writerow(['rank', 'tier', 'cn_name', 'name', 'category', 'glb', 'dest',
                    'bytes', 'parts', 'verts', 'tris', 'textures', 'sources'])
        w.writerows(crows)

    # ---------- 武器 / 道具 ----------
    data = json.load(io.open(os.path.join(VIEWER, 'data.json'), encoding='utf-8'))
    asm = {}
    if os.path.exists(ASSEMBLY):
        for r in rows(ASSEMBLY):
            asm[r.get('base') or ''] = (r.get('parts') or '', r.get('part_count') or '')

    wout = os.path.join(D, 'weapons')
    iout = os.path.join(D, 'items')
    shutil.copytree(os.path.join(VIEWER, 'models/weapons'),
                    os.path.join(wout, 'models/weapons'), dirs_exist_ok=True)
    shutil.copytree(os.path.join(VIEWER, 'models/items'),
                    os.path.join(iout, 'models/items'), dirs_exist_ok=True)
    if os.path.exists(ASSEMBLY):
        shutil.copy2(ASSEMBLY, os.path.join(wout, 'weapon_assembly.csv'))

    wrows = []
    for x in data.get('weapons') or []:
        gltf = x.get('gltf') or ''
        src = os.path.join(VIEWER, gltf.replace('/', os.sep))
        if not os.path.exists(src):
            continue
        parts, pc = asm.get(x.get('id') or '', ('', ''))
        wrows.append([x.get('id'), x.get('name'), x.get('category'), gltf,
                      'weapons/' + gltf, os.path.getsize(src), x.get('variants'),
                      x.get('id'), parts, pc])
    with io.open(os.path.join(M, 'weapons_export.csv'), 'w',
                 encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f)
        w.writerow(['id', 'name', 'category', 'gltf', 'dest', 'bytes', 'variants',
                    'assembly_base', 'assembly_parts', 'part_count'])
        w.writerows(wrows)

    irows = []
    for x in data.get('items') or []:
        gltf = x.get('gltf') or ''
        src = os.path.join(VIEWER, gltf.replace('/', os.sep))
        if not os.path.exists(src):
            continue
        irows.append([x.get('id'), x.get('name'), x.get('category'), x.get('package'),
                      gltf, 'items/' + gltf, os.path.getsize(src)])
    with io.open(os.path.join(M, 'items_export.csv'), 'w',
                 encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f)
        w.writerow(['id', 'name', 'category', 'package', 'gltf', 'dest', 'bytes'])
        w.writerows(irows)

    print('characters %d / weapons %d / items %d' % (len(crows), len(wrows), len(irows)))


if __name__ == '__main__':
    main()
