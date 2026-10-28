# -*- coding: utf-8 -*-
"""把 `assets/lib_native/tex/` 里**磁盘上有、index 没登记**的贴图补登记进 `tex` 表。

## 为什么会有孤儿贴图

`.mdl` 子网格只存 **tid**（整数），不存名字（最高原则 §6.4 的老坑）。
`dump_model_lib` 重跑过几次、贴图表被某次运行用更小的池覆盖过，于是：

| 实测（2026-10-29） | 数 |
|---|---|
| `tex/` 目录里的 PNG | **7,074** |
| `index.json` 的 `tex` 表 | **5,292**（id 0..5291） |
| 孤儿（磁盘有、表里没有） | **1,782**（id 5292..7073） |
| 引用越界 tid 的子网格 | 71,951 / 221,494（**32.5%**） |
| 其中「本来一张 albedo 都没有」的模型 | **20,858 个 / 场景 23,099 个实例** |

## 为什么 id 可信（不是猜）

那 1,782 张的**文件名就是 tid**，与 `.mdl` 里的 tid 来自同一代贴图池；
随机抽有源 `.ydr` 的模型做像素比对（解出真实贴图名 → 池里取图 → 与 `tex/<tid>.png` 逐像素比），
**一致率 5/5**。因此按 id 绑定是"找回原绑定"，不是 fuzzy 匹配（§6.3 没被违反）。

## 做法

- 只**追加**条目：`{id, n: 'tex<id>', f: 'tex/<id>.png', x: 1}`（`x:1` = 孤儿标记，
  名字是 id 派生、不是游戏原名）；
- 已有条目一个字节都不动（贴图 id 顺序不能变，动了就串号）；
- 先备份 `index_before_orphantex_<时间>.json`（已存在则不覆盖）。

    python tools/register_orphan_textures.py --dry
    python tools/register_orphan_textures.py
    # 之后必须让已存盘 blend 重挂材质：
    #   blender -b <blend> -P tools/postprocess_continent.py -- --relink --manifest-only
"""
import os
import re
import json
import time
import shutil
import argparse

ROOT = r'D:/BrainMaker/大镖客2解包分析'
LIB = os.path.join(ROOT, 'assets/lib_native')
INDEX = os.path.join(LIB, 'index.json')
TEXDIR = os.path.join(LIB, 'tex')
REPORT = os.path.join(ROOT, 'work/orphan_tex_report.json')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry', action='store_true')
    a = ap.parse_args()

    idx = json.load(open(INDEX, encoding='utf-8'))
    models, tex = idx['models'], idx.get('tex', [])
    have = {t['id'] for t in tex}
    print('[tex] 现有贴图 %d 条（id 0..%d）' % (len(tex), max(have) if have else -1))

    disk = {}
    for f in os.listdir(TEXDIR):
        if not f.lower().endswith('.png'):
            continue
        base = os.path.splitext(f)[0]
        if base.isdigit():
            disk[int(base)] = f
    print('[tex] 磁盘 PNG %d 张' % len(disk))

    orphans = sorted(i for i in disk if i not in have)
    print('[tex] 孤儿 %d 张（id %s..%s）'
          % (len(orphans), orphans[0] if orphans else '-', orphans[-1] if orphans else '-'))

    # 能救回多少模型（只是统计，不改库）
    ntex = len(tex)
    top = max(orphans) + 1 if orphans else ntex
    gain_models = gain_subs = 0
    for hx, e in models.items():
        s = e.get('s') or []
        a0 = sum(1 for t, _v, _i in s if 0 <= t < ntex)
        a1 = sum(1 for t, _v, _i in s if 0 <= t < top)
        if a0 == 0 and a1:
            gain_models += 1
            gain_subs += a1
    print('[tex] 登记后：%d 个模型从"全无 albedo"变成有（补 %d 个子网格）'
          % (gain_models, gain_subs))

    if not orphans:
        print('[tex] 没有孤儿，什么都不做')
        return
    if a.dry:
        print('[tex] dry-run，未写盘')
        return

    bak = os.path.join(LIB, 'index_before_orphantex_%s.json' % time.strftime('%Y%m%d_%H%M'))
    if not os.path.exists(bak):
        shutil.copy2(INDEX, bak)
        print('[tex] 已备份 %s' % os.path.basename(bak))

    for i in orphans:
        tex.append({'id': i, 'n': 'tex%04d' % i, 'f': 'tex/%s' % disk[i], 'x': 1})
    tex.sort(key=lambda t: t['id'])
    json.dump(dict(models=models, tex=tex), open(INDEX, 'w', encoding='utf-8'),
              separators=(',', ':'))
    print('[tex] 写入 %s：贴图 %d 条（+%d）'
          % (INDEX, len(tex), len(orphans)))
    json.dump(dict(orphans=len(orphans), id_min=orphans[0], id_max=orphans[-1],
                   gain_models=gain_models, gain_subs=gain_subs,
                   note='名字是 id 派生（tex<id>），游戏原名已随旧 tex 表丢失'),
              open(REPORT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('[tex] 报告 %s' % REPORT)


if __name__ == '__main__':
    main()
