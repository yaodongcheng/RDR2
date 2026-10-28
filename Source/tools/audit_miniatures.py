"""微缩模型验收：按《沙盒大地图·据点微缩模型规格》里那 6 条不合格标准逐条判定。

跟 build_miniatures.py 的区别
  build 是"生成"，这个只"验"：读已落盘的 glb / png / audit.csv，不改任何东西。
  外包交付后跑这一条就行。

用法
  uv run python tools/audit_miniatures.py           # 全部
  uv run python tools/audit_miniatures.py --code sdn
"""
import os
import csv
import json
import struct
import argparse
import hashlib

import numpy as np
from PIL import Image

ROOT = r'D:/BrainMaker/大镖客2解包分析'
MI = os.path.join(ROOT, 'deliverable/miniatures')
MODELS = os.path.join(MI, 'models')
TEX = os.path.join(MI, 'tex')
AUDIT = os.path.join(MI, 'audit.csv')
SCALE = os.path.join(ROOT, 'deliverable/handoff/settlement_scale.json')

TIER_CAP = {'town': 260000, 'castle': 130000, 'village': 90000,
            'camp': 70000, 'poi': 70000, 'hideout': 70000}


def read_glb(path):
    d = open(path, 'rb').read()
    magic, ver, total = struct.unpack('<III', d[:12])
    if magic != 0x46546C67:
        raise ValueError('not glb')
    ln, _ = struct.unpack('<II', d[12:20])
    js = json.loads(d[20:20 + ln])
    binoff = 20 + ln + 8
    acc = js['accessors']
    prim = js['meshes'][0]['primitives']
    n_draw = len(prim)
    idx_acc = prim[0].get('indices', 0)
    n_tri = acc[idx_acc]['count'] // 3
    pos = acc[prim[0]['attributes']['POSITION']]
    return js, n_tri, n_draw, pos['min'], pos['max']


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--code', default='')
    args = ap.parse_args()

    scale = {r['code']: r for r in json.load(open(SCALE, encoding='utf-8'))}
    rows = list(csv.DictReader(open(AUDIT, encoding='utf-8-sig')))
    if args.code:
        rows = [r for r in rows if r['code'] == args.code]

    tex_hash = {}
    fails = []
    print(f"{'code':8}{'面数':>8}{'上限':>8}{'尺寸 m':>14}{'缩放':>8}  判定")
    print('-' * 78)
    for r in rows:
        code = r['code']
        glb = os.path.join(MODELS, code + '.glb')
        png = os.path.join(TEX, code + '.png')
        errs = []
        if not os.path.exists(glb):
            errs.append('缺 glb')

        js = n_tri = n_draw = None
        dims = (0, 0, 0)
        if os.path.exists(glb):
            js, n_tri, n_draw, pmin, pmax = read_glb(glb)
            dims = tuple(pmax[i] - pmin[i] for i in range(3))
            cap = TIER_CAP.get(r['btype'], 8000)
            if n_tri > cap:
                errs.append(f'超面数上限 {n_tri}>{cap}')
            if n_draw != 1:
                errs.append(f'draw call {n_draw}≠1')
            if dims[1] < 0.12:
                errs.append('高度 <0.12 m（像白板）')
            # 尺寸比例核对（放大点跳过）
            boost = float(r['scale_boost'])
            if boost <= 1.02:
                sx = scale[code]
                want_x = sx['size_w'] / 29.0
                # v3 取景裁到"建成区"，可以比官方占地小；只查"有没有超出官方框 15%"
                if dims[0] > want_x * 1.20:
                    errs.append(f'X 超出官方占地 {dims[0]:.2f} > {want_x:.2f}')
            attrs = js['meshes'][0]['primitives'][0]['attributes']
            has_tex = bool(js['materials'][0].get('pbrMetallicRoughness', {}).get('baseColorTexture'))
            has_col = 'COLOR_0' in attrs
            if not (has_tex or has_col):
                errs.append('既没贴图也没顶点色')

        if os.path.exists(png):
            im = Image.open(png).convert('RGB')
            a = np.asarray(im, dtype=np.float32)
            if a.std() < 8:
                errs.append(f'贴图近似纯色 std={a.std():.1f}')
            if im.size[0] < 512:
                errs.append(f'贴图 <512（{im.size[0]}）')
            h = hashlib.md5(open(png, 'rb').read()).hexdigest()
            if h in tex_hash:
                errs.append(f'贴图与 {tex_hash[h]} 完全相同')
            else:
                tex_hash[h] = code

        verdict = 'OK' if not errs else 'FAIL: ' + '; '.join(errs)
        if errs:
            fails.append((code, errs))
        print(f"{code:8}{n_tri or 0:8,}{TIER_CAP.get(r['btype'], 8000):8,}"
              f"{dims[0]:6.1f}x{dims[2]:5.1f}x{dims[1]:4.2f}  "
              f"{float(r['scale_boost']):7.2f}  {verdict}")

    print()
    if fails:
        print(f'❌ {len(fails)} / {len(rows)} 不合格')
        raise SystemExit(1)
    print(f'✅ {len(rows)} 个全部通过（面数 / 单 draw / 单贴图 / 尺寸 / 贴图非纯色）')


if __name__ == '__main__':
    main()
