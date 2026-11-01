# -*- coding: utf-8 -*-
"""把 `assets/lib_native/tex/` 的 PNG **按当前源 ytd 重新解一遍**（内容对齐 + 修长宽比）。

## 为什么要它（2026-11-01 实测）

区域 #20 的 `new_pie_03_dockmed3` 在 Material Preview 里整块发黑，查到根因**不是**材质节点：

| 来源 | `nbx_wall_woodplank_11long_rotted_ab` 的 RGB 均值 |
|---|---|
| 池子里的 `tex/03858.png`（2026-10-29 写） | **0.034**（其实是这张图的 alpha 遮罩被当成了颜色） |
| 现在从 `work/all_packs/gtxd_saintdenis/new_pie_g+hi.ytd` 重解 | **0.253**（真正的木板色） |

即池子里有一部分老 PNG 与源对不上（alpha 通道对、RGB 不对）。同一个 bug 还连带
**非方形贴图被拉成正方形**（旧代码 `im.resize((MAXS, MAXS))`，1024×512 的墙板被纵向拉长一倍）。

本工具只做一件事：**逐个贴图表项重解 → 和现有 PNG 比对 → 不一样才覆盖**（同名同路径，
`tex id` 不变，`.mdl` / `index.json` 一个字节都不用改）。

    python tools/refresh_tex_pool.py --dry            # 只统计会变多少张
    python tools/refresh_tex_pool.py --jobs 12        # 真刷

判定口径：把两张图都缩到 32×32 比平均绝对差；`> 0.02` 或尺寸不同 → 重写。
"""
import argparse
import json
import os
import sys
import time
import multiprocessing as mp

ROOT = r'D:/BrainMaker/大镖客2解包分析'
TOOLS = os.path.join(ROOT, 'tools')
LIB = os.path.join(ROOT, 'assets/lib_native')
INDEX = os.path.join(LIB, 'index.json')
TEXIDX = os.path.join(ROOT, 'work/tex_name_index.json')
PAL = os.path.join(ROOT, 'work/paltex')

sys.path.insert(0, TOOLS)

FLIP_G_ROLES = ('nm', 'nm2')
ALPHA_ROLES = ('l1', 'ct', 'dt', 'pl')
CMP_SIZE = 32
DIFF_EPS = 0.02


def _fit(im, maxs):
    """等比缩放（**颜色与 alpha 分开缩**，否则 PIL 12 会按 alpha 预乘把 RGB 乘黑）。"""
    from ytd_to_png import resize_max
    return resize_max(im, maxs)


def _source_image(name, role, maxs, texidx):
    """→ PIL.Image（已缩放、已翻 G）或 None"""
    import numpy as np
    from PIL import Image
    from ytd_to_png import decode_one
    if role == 'pl':
        p = os.path.join(PAL, name + '.png')
        if not os.path.exists(p):
            return None
        im = Image.open(p).convert('RGBA')
    else:
        e = texidx.get((name or '').lower())
        if not e:
            return None
        fp = os.path.join(ROOT, e['f'].replace('/', os.sep))
        if not os.path.exists(fp):
            return None
        with open(fp, 'rb') as f:
            data = f.read()
        blob = data[16 + e.get('sys', 0) + e.get('gfx', 0):]
        blob = blob[:max(4096, e.get('w', 0) * e.get('h', 0) * 4)]
        im, _fmt = decode_one(blob, e.get('w', 0), e.get('h', 0), e.get('fmt', 0))
        if im is None:
            return None
        im = im.convert('RGBA')
    im = _fit(im, maxs)
    if role in ALPHA_ROLES:
        out = im.convert('RGBA')
    else:
        out = im.convert('RGB')
    if role in FLIP_G_ROLES:
        a = np.asarray(out, dtype=np.uint8).copy()
        a[:, :, 1] = 255 - a[:, :, 1]
        out = Image.fromarray(a, 'RGB')
    return out


def _job(item):
    """(name, role, rel, maxs, texidx_path, dry) → (rel, status, note)"""
    name, role, rel, maxs, idxpath, dry = item
    try:
        import numpy as np
        from PIL import Image
        texidx = _JOB_IDX
        dst = os.path.join(LIB, rel)
        new = _source_image(name, role, maxs, texidx)
        if new is None:
            return rel, 'skip', 'no-source'
        old_size = None
        old = None
        if os.path.exists(dst):
            try:
                old = Image.open(dst).convert('RGBA')
                old_size = old.size
            except Exception:
                old = None
        if old is not None and old_size == new.size:
            a = np.asarray(old.convert('RGB').resize((CMP_SIZE, CMP_SIZE), Image.BILINEAR),
                           np.float32) / 255
            b = np.asarray(new.convert('RGB').resize((CMP_SIZE, CMP_SIZE), Image.BILINEAR),
                           np.float32) / 255
            if float(np.abs(a - b).mean()) <= DIFF_EPS:
                return rel, 'same', ''
        if dry:
            return rel, 'would-change', ('size %s→%s' % (old_size, new.size))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        new.save(dst, 'PNG', optimize=False)
        return rel, 'changed', ('size %s→%s' % (old_size, new.size))
    except Exception as ex:
        return rel, 'error', '%s: %s' % (type(ex).__name__, ex)


_JOB_IDX = None


def _init(idxpath):
    global _JOB_IDX
    _JOB_IDX = json.load(open(idxpath, encoding='utf-8'))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--maxs', type=int, default=512)
    ap.add_argument('--jobs', type=int, default=max(4, (os.cpu_count() or 8) - 4))
    ap.add_argument('--dry', action='store_true')
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--roles', default='',
                    help='只刷这些角色（逗号分隔：ab,nm,ma,l1,ct,dt,nm2,ma2,pl）；空 = 全部')
    a = ap.parse_args()

    idx = json.load(open(INDEX, encoding='utf-8'))
    texidx = json.load(open(TEXIDX, encoding='utf-8'))
    roles = set(x.strip() for x in a.roles.split(',') if x.strip())
    items = []
    for t in idx['tex']:
        role = t.get('role') or 'ab'
        if roles and role not in roles:
            continue
        if not t.get('n') or not t.get('f'):
            continue
        items.append((t['n'], role, t['f'], a.maxs, TEXIDX, a.dry))
    if a.limit:
        items = items[:a.limit]
    print('[refresh] 待处理 %d 张（dry=%s, maxs=%d）' % (len(items), a.dry, a.maxs))

    stat = {}
    t0 = time.time()
    done = 0
    examples = []
    with mp.Pool(a.jobs, initializer=_init, initargs=(TEXIDX,)) as pool:
        for rel, st, note in pool.imap_unordered(_job, items, chunksize=16):
            stat[st] = stat.get(st, 0) + 1
            if st in ('changed', 'would-change') and len(examples) < 12:
                examples.append((rel, note))
            done += 1
            if done % 2000 == 0:
                el = time.time() - t0
                print('[refresh] %d/%d  %.0f/s  剩 ~%.0f 分  %s'
                      % (done, len(items), done / el, (len(items) - done) / max(1e-9, done / el) / 60,
                         stat), flush=True)
    print('[refresh] 完成：%s，用时 %.1f 分' % (stat, (time.time() - t0) / 60))
    for rel, note in examples:
        print('   %-28s %s' % (rel, note))
    if a.dry:
        print('[refresh] dry-run，没有写盘')


if __name__ == '__main__':
    mp.freeze_support()
    main()
