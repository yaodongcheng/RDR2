# -*- coding: utf-8 -*-
"""不打开 Blender，直接从 `manifest_<name>.jsonl` 反算汇总，写 `manifest_<name>.json` + `manifest.json`。

## 为什么需要

`write_manifest.py` 在主循环之后还有两段"再扫一遍 ENTITIES"的收尾
（数植被残留、数应删未删）。在 14.7 万对象的场景里 `collection.all_objects` 每次访问都重算，
实测会卡 **20~35 分钟**（2026-10-29 两次构建都卡在这里），而 jsonl 其实早就写完了。

本工具用同一份 jsonl、同一套口径把汇总算出来（字段与 `write_manifest` 的 summary 对齐），
**秒级完成**，所以"清单已写、汇总卡住"时直接用它收尾。

    python tools/manifest_from_jsonl.py --blend <continent_v9.blend>
    python tools/manifest_from_jsonl.py --jsonl <manifest_continent_v9.jsonl>
"""
import os
import re
import json
import time
import argparse

ROOT = r'D:/BrainMaker/大镖客2解包分析'
D = os.path.join(ROOT, 'deliverable/blender/continent')
CLASSES = ('lod', 'terrain_cell', 'rail', 'struct', 'decal', 'veg', 'rock', 'veh', 'bldg', 'part',
           'junk', 'prop', 'unknown')

try:
    import sys
    sys.path.insert(0, os.path.join(ROOT, 'tools'))
    from strip_vegetation import VEG as SHOULD_DEL     # 与构建链同一个正则
except Exception:
    SHOULD_DEL = re.compile(
        r'(^|/)(p_tree|p_bush|p_shrub|p_grass|p_plant|p_fern|p_cactus|p_palm|p_reed|p_lily|p_ivy|p_vine)'
        r'|rdr_bush|_tree_|_bush_|_shrub|_fern_|_grass_|_cactus', re.I)


def r2(v):
    return round(float(v), 2)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--blend', default='')
    ap.add_argument('--jsonl', default='')
    a = ap.parse_args(argv)

    if a.jsonl:
        jl = a.jsonl
    else:
        blend = a.blend or os.path.join(D, 'continent_v9.blend')
        base = os.path.splitext(os.path.basename(blend))[0]
        jl = os.path.join(os.path.dirname(blend), 'manifest_%s.jsonl' % base)
    if not os.path.exists(jl):
        raise SystemExit('找不到 %s' % jl)

    t0 = time.time()
    cls = {}
    hidden = 0
    ntex = 0
    tex_used = set()
    world = [1e18, 1e18, 1e18, -1e18, -1e18, -1e18]
    veg_left = 0
    veg_miss = 0
    n = 0
    meta = {}
    with open(jl, encoding='utf-8') as f:
        meta = json.loads(f.readline()).get('_meta', {})
        for line in f:
            r = json.loads(line)
            n += 1
            c = r.get('c')
            cls[c] = cls.get(c, 0) + 1
            if r.get('hid'):
                hidden += 1
            if r.get('nt'):
                ntex += 1
            for t in r.get('t') or ():
                tex_used.add(t)
            b = r.get('bb')
            if b:
                world[0] = min(world[0], b[0]); world[1] = min(world[1], b[1])
                world[2] = min(world[2], b[2]); world[3] = max(world[3], b[3])
                world[4] = max(world[4], b[4]); world[5] = max(world[5], b[5])
            if c == 'veg':
                veg_left += 1
            # 「应删未删」只看**还露在 ENTITIES 里**的对象：收进 HIDDEN_VEG 的本来就没删
            # （最高原则 §6.1：植被默认隐藏不删），不能算成漏删。
            if not r.get('hid') and SHOULD_DEL.search(str(r.get('n', '')).split('.')[0].lower()):
                veg_miss += 1

    cats = sorted(k for k in cls if k in CLASSES)
    ent_total = int(meta.get('entities') or 0)
    blend = a.blend or meta.get('blend') or ''
    size_gb = round(os.path.getsize(blend) / 1e9, 2) if blend and os.path.exists(blend) else 0.0
    verdict = (ent_total > 0 and len(cats) >= 10 and veg_miss == 0)
    summary = {
        'blend': blend,
        'blend_size_gb': size_gb,
        'built': meta.get('built') or time.strftime('%Y-%m-%dT%H:%M:%S'),
        'objects_file': os.path.basename(jl),
        'objects': n,
        'entities': ent_total,
        'classes': {k: cls[k] for k in cats},
        'classes_n': len(cats),
        'classes_expected': 13,
        'hidden': hidden,
        # 2026-10-29 起"隐藏"= 整类默认隐藏，不再有独立垃圾桶集合：
        # 这三个数直接取类大小，口径与面板一致。
        'hidden_terrain': cls.get('terrain_cell', 0),
        'veg_hidden': cls.get('veg', 0),
        'parked_hidden': 0,
        'lod_hidden': cls.get('lod', 0),
        'veg_left': veg_left,
        'veg_should_delete': veg_miss,
        'materials': None,
        'textures_used': len(tex_used),
        'no_albedo_objects': ntex,
        'world_bbox': [r2(v) for v in world],
        'verdict': 'PASS' if verdict else 'CHECK',
        'note': '由 manifest jsonl 反算（tools/manifest_from_jsonl.py；'
                'write_manifest 的收尾两遍扫描在 14.7 万对象上要 20~35 分钟）',
    }
    d = os.path.dirname(jl)
    base = os.path.splitext(os.path.basename(jl))[0].replace('manifest_', '')
    js = os.path.join(d, 'manifest_%s.json' % base)
    json.dump(summary, open(js, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    json.dump(summary, open(os.path.join(d, 'manifest.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print('ENTITIES %d / 13 类 %d/13 / 植被 %d / 隐藏 %d（地形 %d、植被 %d、占位 %d）/ '
          '待隐藏未隐藏 %d / 贴图用 %d / 无 albedo %d → %s'
          % (ent_total, len(cats), veg_left, hidden, summary['hidden_terrain'],
             summary['veg_hidden'], summary['parked_hidden'], veg_miss,
             len(tex_used), ntex, summary['verdict']))
    print('[mf2] 汇总 %s（%.1fs，源 %s）' % (js, time.time() - t0, os.path.basename(jl)))


if __name__ == '__main__':
    main()
