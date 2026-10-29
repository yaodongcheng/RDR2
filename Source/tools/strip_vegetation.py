# -*- coding: utf-8 -*-
"""植被处理：**默认隐藏**（不删），可选删除。

## 为什么默认隐藏

最高原则 6.1「禁擅自剔除网格体」：植被也是数据。9,676 个植被对象隐藏起来视口一样不画，
但随时能在 N 面板切回来；删了就得靠重建或重新实例化恢复。
（旧的 `--mode delete` 保留，给"必须压内存/压体积"的场合用：9,676 对象 + 孤立网格能省约 1~2 GB。）

## 用法

    # 默认：移到 HIDDEN_VEG 集合并关闭可见性（视口+渲染）
    blender -b deliverable/blender/continent/continent_v6.blend -P tools/strip_vegetation.py -- --out <out.blend>

    # 真删（旧行为）
    blender -b <blend> -P tools/strip_vegetation.py -- --mode delete --out <out.blend> [--dry]

判定：按 names.txt 反查模型名，**用 `tools/veg_rules.py` 里唯一一份规则**
（树/灌木/草/蕨/仙人掌/棕榈/芦苇/睡莲/藤蔓/常春藤/weed/brush/palmetto/tumbleweed）。
盆栽 `p_pot_*`、花艺 `flowerarng*`、装饰 `p_cs_*` 是**道具**，不算植被、不隐藏。
只处理 `ENTITIES` 集合里的对象，**不动 LIB / 室内 / Terrain / Water**。
"""
import bpy
import os
import re
import sys
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# 🔴 植被判定只有一份：`veg_rules.py`（classify_entities 也用同一份）。
#    2026-10-29 之前这里自带宽窄两套，导致"分类为植被但不隐藏"的 1,247 个对象，
#    面板里出现两个都叫「植被」的集合。
from veg_rules import is_veg

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NAMES = os.path.join(ROOT, 'tools/rdr2rpf/bin/Release/net9.0/names.txt')


def argv():
    a = sys.argv
    return a[a.index('--') + 1:] if '--' in a else []


def joaat(s):
    h = 0
    for c in s.lower().encode():
        h = (h + c) & 0xFFFFFFFF
        h = (h + (h << 10)) & 0xFFFFFFFF
        h ^= h >> 6
    h = (h + (h << 3)) & 0xFFFFFFFF
    h ^= h >> 11
    return (h + (h << 15)) & 0xFFFFFFFF


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default='')
    ap.add_argument('--dry', action='store_true')
    ap.add_argument('--mode', default='hide', choices=['hide', 'delete'],
                    help='hide（默认）= 移到隐藏集合，不丢数据；delete = 真删')
    ap.add_argument('--col', default='HIDDEN_VEG', help='hide 模式的集合名')
    a = ap.parse_args(argv())

    names = {}
    with open(NAMES, encoding='latin1', errors='ignore') as f:
        for l in f:
            n = l.strip()
            if n:
                names.setdefault(joaat(n), n.lower())

    ent = bpy.data.collections.get('ENTITIES')
    if ent is None:
        raise SystemExit('没有 ENTITIES 集合')
    victims = []
    for o in ent.all_objects:      # 分类后对象在 ENTITIES/<类>|<地块> 子集合里，必须用 all_objects
        hx_s = o.get('hash')
        n = ''
        if hx_s:
            try:
                n = names.get(int(hx_s, 16), '')
            except Exception:
                n = ''
        if not n:                       # 没有 hash 属性（旧产物）：退回按对象名本身判定
            n = o.name.split('.')[0].lower()
        if n and is_veg(n):
            victims.append(o)
    print('[veg] ENTITIES %d 个对象，其中植被 %d 个' % (len(ent.all_objects), len(victims)))

    if a.dry:
        print('[veg] dry-run，不动。样例：', [o.name for o in victims[:8]])
        return

    if a.mode == 'hide':
        # 2026-10-29 规范：**不搬对象**。植被已经是分类里的一类（C_veg_植被），
        # 隐藏 = 给这个类设"默认不显示"，对象仍留在类里，N 面板切回来就看得到。
        ent = bpy.data.collections.get('ENTITIES')
        hits = [c for c in ent.children if c.name.startswith('C_veg_')] if ent else []
        if not hits:
            print('[veg] 没找到 C_veg_* 分类集合 —— 先跑 classify_entities.py --apply')
            return
        if all(c.hide_viewport for c in hits):
            print('[veg] 植被已经是隐藏状态，跳过（省一次 7 GB 存盘）')
            return
        n = 0
        for c in hits:
            c.hide_viewport = True
            c.hide_render = True
            n += len(c.all_objects)
        print('[veg] 「植被」%d 个 → 整类默认隐藏（仍在类里，未删未搬）' % n)
        out = a.out or bpy.data.filepath
        bpy.ops.wm.save_as_mainfile(filepath=out)
        print('[veg] saved %s (%.2f GB)' % (out, os.path.getsize(out) / 1e9))
        return

    # delete：旧行为——只删对象，不动共享网格（LIB 里被别处引用的网格留着）
    used_meshes = {o.data.name for o in victims if o.type == 'MESH'}
    for o in victims:
        bpy.data.objects.remove(o, do_unlink=True)
    left = len(ent.all_objects)
    print('[veg] 已删除 %d 个；ENTITIES 剩 %d；场景对象 %d' % (len(victims), left, len(bpy.data.objects)))

    # 顺手清掉只被植被用到的孤立网格（省内存；LIB 里被别处引用的不动）
    if used_meshes:
        orphan = 0
        for me in list(bpy.data.meshes):
            if me.name in used_meshes and me.users == 0:
                bpy.data.meshes.remove(me)
                orphan += 1
        print('[veg] 清理孤立网格 %d 个' % orphan)

    out = a.out or bpy.data.filepath
    bpy.ops.wm.save_as_mainfile(filepath=out)
    print('[veg] saved %s (%.2f GB)' % (out, os.path.getsize(out) / 1e9))


if __name__ == '__main__':
    main()
