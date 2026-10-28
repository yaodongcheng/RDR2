#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""批量渲染 AVG 立绘（透明底半身像），数据来自 build_avg_main.py 的 chars 表。

一个 handle 一张 PNG：export/avg/portraits/<handle>.png
同时写 export/avg/data/portraits.json（handle → 中文名 / 模型 / 文件 / 像素尺寸）

渲染本身交给 tools/render_portrait.py（Blender Cycles，一张约 3 s）。
"""
import json
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding='utf-8')

ROOT = r'D:/BrainMaker/大镖客2解包分析'
Npc = os.path.join(ROOT, 'export/npc')
OUT = os.path.join(ROOT, 'export/avg/portraits')
BLENDER = r'C:/Program Files/Blender Foundation/Blender 5.2/blender.exe'
SCRIPT = os.path.join(ROOT, 'tools/render_portrait.py')


def glb_for(model):
    if model == 'player_zero':
        p = os.path.join(Npc, 'player/player_zero/player_zero.glb')
        return p if os.path.exists(p) else None
    if model.startswith('cs_'):
        p = os.path.join(Npc, 'cs', model, model + '.glb')
        return p if os.path.exists(p) else None
    if model.startswith('generic_'):
        p = os.path.join(Npc, 'generic', model, model + '.glb')
        return p if os.path.exists(p) else None
    return None


def main():
    data = json.load(open(os.path.join(ROOT, 'export/levels/world/avg_main.json'), encoding='utf-8'))
    chars = data['chars']
    os.makedirs(OUT, exist_ok=True)
    manifest = {}
    ok = miss = fail = 0
    for handle, meta in sorted(chars.items()):
        model = meta.get('model')
        glb = glb_for(model)
        rec = {'zh': meta.get('zh'), 'model': model, 'glb': None, 'file': None, 'ok': False}
        if not glb:
            rec['error'] = 'no-model'
            manifest[handle] = rec
            miss += 1
            continue
        rec['glb'] = os.path.relpath(glb, ROOT).replace('\\', '/')
        out = os.path.join(OUT, handle + '.png')
        cmd = [BLENDER, '-b', '--python', SCRIPT, '--', glb, out,
               '--samples', '14', '--res', '700x920']
        r = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore')
        if os.path.exists(out) and os.path.getsize(out) > 3000:
            rec['ok'] = True
            rec['file'] = 'portraits/' + handle + '.png'
            rec['zh'] = meta.get('zh')
            ok += 1
        else:
            rec['error'] = (r.stdout or '')[-400:] + (r.stderr or '')[-400:]
            fail += 1
        manifest[handle] = rec
        print('  %-22s %-26s %s' % (handle, rec.get('zh'), 'OK' if rec['ok'] else 'FAIL'))
    json.dump({'generated': data['generated'], 'chars': manifest},
              open(os.path.join(ROOT, 'export/avg/data/portraits.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print('\nok=%d  no-model=%d  fail=%d  共 %d' % (ok, miss, fail, len(chars)))


if __name__ == '__main__':
    main()
