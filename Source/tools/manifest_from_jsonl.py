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
# 🔴 类表唯一一份在 class_registry.py（此前这里写死 13 类，新增 stone 后漏算 744 个对象）
import sys as _sys
if os.path.join(ROOT, 'tools') not in _sys.path:
    _sys.path.insert(0, os.path.join(ROOT, 'tools'))
from class_registry import CLASSES, DEFAULT_HIDDEN     # noqa: E402

try:
    # 🔴 唯一一份植被规则在 veg_rules.py（2026-10-30 修：这里原来 import
    #    `strip_vegetation.VEG`，而那个模块并不导出 VEG → 每次都静默落进下面的
    #    兜底正则，跟构建链用的 `is_veg`（带盆栽/墙的排除）不是同一套口径）。
    from veg_rules import is_veg as SHOULD_DEL
except Exception:
    def SHOULD_DEL(_n):
        return False


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
    veg_miss = 0            # 默认隐藏类里**还露着**的对象数（判据见下）
    veg_name_outside = 0    # 名字像植被但归了别的类（信息项，不算错）
    hidc = {}               # 每个类里已隐藏的对象数
    n = 0
    nrm_obj = 0
    orm_obj = 0
    nrm_used = set()
    orm_used = set()
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
                hidc[c] = hidc.get(c, 0) + 1
            if r.get('nt'):
                ntex += 1
            for t in r.get('t') or ():
                tex_used.add(t)
            # 2026-10-30：法线 / 材质(高光) —— 旧 jsonl 没有这两个字段，读到就是 0
            tn = r.get('tn')
            if tn:
                nrm_obj += 1
                nrm_used.update(tn)
            tm = r.get('tm')
            if tm:
                orm_obj += 1
                orm_used.update(tm)
            b = r.get('bb')
            if b:
                world[0] = min(world[0], b[0]); world[1] = min(world[1], b[1])
                world[2] = min(world[2], b[2]); world[3] = max(world[3], b[3])
                world[4] = max(world[4], b[4]); world[5] = max(world[5], b[5])
            if c == 'veg':
                veg_left += 1
            # 名字像植被、但归了别的类（`p_debris_nbd_docks_weed1` 是码头杂物、
            # `smb_bridge_01_ivy` 是带常春藤的桥）—— **信息项**，不算错。
            if not r.get('hid') and SHOULD_DEL(str(r.get('n', '')).split('.')[0].lower()):
                veg_name_outside += 1

    cats = sorted(k for k in cls if k in CLASSES)
    ent_total = int(meta.get('entities') or 0)
    blend = a.blend or meta.get('blend') or ''
    size_gb = round(os.path.getsize(blend) / 1e9, 2) if blend and os.path.exists(blend) else 0.0
    # 「应藏未藏」的真正判据：**默认隐藏类里还有没有露着的对象**。
    # 旧判据是"名字像植被却没归 veg 类"，会把 `_docks_weed`（杂物）、`_bridge_ivy`（桥）
    # 当成错误 → v17 虚报 271 个。2026-10-30 改成本口径。
    veg_miss = sum(max(0, cls.get(k, 0) - hidc.get(k, 0)) for k in DEFAULT_HIDDEN)
    verdict = (ent_total > 0 and len(cats) == len(CLASSES) and veg_miss == 0)
    summary = {
        'blend': blend,
        'blend_size_gb': size_gb,
        'built': meta.get('built') or time.strftime('%Y-%m-%dT%H:%M:%S'),
        'objects_file': os.path.basename(jl),
        'objects': n,
        'entities': ent_total,
        'classes': {k: cls[k] for k in cats},
        'classes_n': len(cats),
        'classes_expected': len(CLASSES),
        'hidden': hidden,
        # 2026-10-29 起"隐藏"= 整类默认隐藏，不再有独立垃圾桶集合：
        # 这三个数直接取类大小，口径与面板一致。
        'hidden_terrain': cls.get('terrain_cell', 0),
        'veg_hidden': cls.get('veg', 0),
        'parked_hidden': 0,
        'lod_hidden': cls.get('lod', 0),
        'veg_left': veg_left,
        'veg_should_delete': veg_miss,
        'veg_name_outside': veg_name_outside,
        'materials': None,
        'textures_used': len(tex_used),
        'no_albedo_objects': ntex,
        'with_normal_objects': nrm_obj,
        'with_orm_objects': orm_obj,
        'normal_textures_used': len(nrm_used),
        'orm_textures_used': len(orm_used),
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
    print('ENTITIES %d / 类 %d/%d / 默认隐藏类未藏 %d（名字像植被但归别类 %d，信息项）/ '
          '隐藏 %d（地形 %d、植被 %d、占位 %d）/ 贴图用 %d / 无 albedo %d → %s'
          % (ent_total, len(cats), len(CLASSES), veg_miss, veg_name_outside,
             hidden, summary['hidden_terrain'],
             summary['veg_hidden'], summary['parked_hidden'],
             len(tex_used), ntex, summary['verdict']))
    print('TMAPS 带法线对象 %d（%d 张图）/ 带高光(ORM)对象 %d（%d 张图）'
          % (nrm_obj, len(nrm_used), orm_obj, len(orm_used)))
    print('[mf2] 汇总 %s（%.1fs，源 %s）' % (js, time.time() - t0, os.path.basename(jl)))


if __name__ == '__main__':
    main()
