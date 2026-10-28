#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""给 AVG 出「2D 背景」：用真实的 3D 据点场景，在固定机位渲染成 16:9 JPG。

为什么是"渲染"而不是"画"
------------------------
项目里没有游戏原画的 2D 背景（那是引擎实时渲染的）。要规避"真实空间分镜"
又不想凭空编造地点，最稳的做法是：**用已经解包并装配好的真实场景**，
在真实坐标处按几个固定机位出图，作为 AVG 的静态背景层。

数据来源
--------
  export/levels/world/settlements.json  据点中心 cx/cy/cz + 半径
  export/previews/<code>/tiles/         每据点已烘焙的 glTF
  export/previews/index.html?shot=N     我加的固定取景参数（4 个方位角）
  tools/bgshot.mjs                      headless Chrome 截图（JPEG q90）

输出
----
  export/avg/bg/<code>_<n>.jpg
  export/avg/data/bg.json   {code: {zh, shots:[{file, cam, tgt}]}}
"""
import json
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding='utf-8')

ROOT = r'D:/BrainMaker/大镖客2解包分析'
EXP = os.path.join(ROOT, 'export')
OUT = os.path.join(EXP, 'avg/bg')
BASE = 'http://127.0.0.1:8799'
NODE = 'node'
SHOTJS = os.path.join(ROOT, 'tools/bgshot.mjs')
W, H = 1600, 900
ANGLES = [0, 2]          # previews 的 shot 0/1/2/3 → 这里取 0 与 2（约差 170°）
EXTRA_ANGLES = [1, 3]    # 两个角度都空时再补拍
K, HH = 0.50, 0.17       # 取景：画面宽 ≈ 据点直径的 1.1 倍、机位压低到接近人眼（街区级，不是鸟瞰）
FOV = 45
FORCE = os.environ.get('AVG_BG_FORCE') == '1'   # 改了取景参数就强制重渲
MIN_TRIS = 25000         # 低于这个面数说明该据点没烘出建筑（只有零星道具）→ 用替身
# 没烘出建筑 / 没有 tiles 的据点 → 用它所在章节的主场景顶替
PROXY = {'adl': 'col', 'wal': 'bla', 'sod': 'pro', 'wap': 'but', 'che': 'sdn',
         'man': 'van', 'hso': 'val', 'abe': 'mfr', 'lon': 'rho'}


def valid(path):
    """几乎纯色（方差极小）的图等于没拍到东西，不能当背景。"""
    try:
        from PIL import Image, ImageStat
    except Exception:
        return os.path.getsize(path) > 20000
    try:
        im = Image.open(path).convert('RGB').resize((160, 90))
        sd = sum(ImageStat.Stat(im).stddev) / 3.0
        return sd >= 8.0
    except Exception:
        return False


def run(url, out, wait_ms=1400, timeout=160):
    cmd = [NODE, SHOTJS, url, out, str(wait_ms), str(W), str(H), str(timeout)]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore')
    info = {}
    for line in (r.stdout or '').splitlines():
        line = line.strip()
        if line.startswith('{'):
            try:
                info = json.loads(line)
            except Exception:
                pass
    return info


def main():
    data = json.load(open(os.path.join(EXP, 'levels/world/avg_main.json'), encoding='utf-8'))
    st = {s['code']: s for s in
          json.load(open(os.path.join(EXP, 'levels/world/settlements.json'), encoding='utf-8'))['settlements']}
    used = sorted({m['location']['settlement'] for m in data['missions']
                   if m.get('location') and m['location'].get('settlement')})
    os.makedirs(OUT, exist_ok=True)

    manifest = {}
    okc = 0
    for code in used:
        s = st.get(code)
        if not s:
            print('  MISS meta', code)
            continue
        rec = {'zh': s['name_zh'], 'en': s.get('name_en'), 'radius': s.get('size_w'),
               'proxy': None, 'shots': []}
        for n in ANGLES + EXTRA_ANGLES:
            if rec['shots'] and n in EXTRA_ANGLES:
                break                         # 已经有可用图就不再补角度
            fn = '%s_%d.jpg' % (code, n)
            out = os.path.join(OUT, fn)
            # 已有且过检的图直接复用（重跑时省掉 9 分钟）
            if not FORCE and os.path.exists(out) and valid(out) and n in ANGLES:
                rec['shots'].append({'file': 'bg/' + fn, 'shot': n, 'cached': True})
                print('  %-8s %-14s shot%d 复用' % (code, s['name_zh'], n))
                continue
            url = ('%s/previews/index.html?code=%s&hud=0&fov=%s&shot=%d&k=%s&h=%s'
                   % (BASE, code, FOV, n, K, HH))
            info = run(url, out, 1400)
            if os.path.exists(out) and valid(out):
                rec['shots'].append({'file': 'bg/' + fn, 'shot': n,
                                     'cam': info.get('cam'), 'tgt': info.get('tgt'),
                                     'tris': info.get('tris')})
                print('  %-8s %-14s shot%d OK  tris=%-8s %s KB' %
                      (code, s['name_zh'], n, info.get('tris'), os.path.getsize(out) // 1024))
            else:
                if os.path.exists(out):
                    os.remove(out)            # 空白图不留在产物里，免得被误用
                print('  %-8s %-14s shot%d 空/失败 phase=%s' %
                      (code, s['name_zh'], n, info.get('phase')))
        tris = max([x.get('tris') or 0 for x in rec['shots']] or [0])
        if rec['shots'] and tris and tris < MIN_TRIS:
            px = PROXY.get(code)
            if px:
                rec['proxy'] = px
                print('      → 面数 %s 太低，标 proxy=%s' % (tris, px))
        if not rec['shots']:
            px = PROXY.get(code)
            rec['proxy'] = px
            print('      → 无可用图，proxy=%s' % px)
        manifest[code] = rec
        if rec['shots'] and not rec['proxy']:
            okc += 1

    json.dump({'generated': data['generated'], 'size': [W, H], 'locations': manifest},
              open(os.path.join(EXP, 'avg/data/bg.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print('\n据点 %d / 直接用真实场景 %d，图 %d 张' %
          (len(used), okc, sum(len(v['shots']) for v in manifest.values())))
    print('走替身(proxy)的：', [k for k, v in manifest.items() if v.get('proxy')])


if __name__ == '__main__':
    main()
