# -*- coding: utf-8 -*-
"""按**名字**重建 `assets/lib_native/tex` 表：`id = 名字排序下标`，`tex/<id>.png` 由 ytd 按名字解出。

## 为什么

旧表的 `id` 是历史残留（复用过、重排过），`id ↔ 名字 ↔ 文件内容` 会错位，
于是出现"草坪上贴了一扇门"。新表让 **id 完全由名字决定**：

- 名字集合来自**源模型自己声明的贴图名**（`work/needed_tex_names.json`）；
- `id = 该名字在排序后的下标`（同一批名字 → 同一批 id，可复现）；
- 图片从 `work/tex_name_index.json` 指到的 `.ytd` 里解（`decode_one`），统一缩到 ≤512；
- 解不出来的名字**不占 id**（`s` 里写 -1）→ 宁可没贴图，也不贴错（最高原则 §6.3）。

## 用法

    python tools/tex_table_rebuild.py --dry     # 只看能解多少张
    python tools/tex_table_rebuild.py           # 真写（先备份 index.json）
"""
import os
import sys
import json
import time
import shutil
import argparse
from collections import OrderedDict

ROOT = r'D:/BrainMaker/大镖客2解包分析'
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import rdr2_ytd as T
from ytd_to_png import decode_one
from PIL import Image

LIB = os.path.join(ROOT, 'assets/lib_native')
INDEX = os.path.join(LIB, 'index.json')
TEXIDX = os.path.join(ROOT, 'work/tex_name_index.json')
NEEDED = os.path.join(ROOT, 'work/needed_tex_names.json')
IDS = os.path.join(ROOT, 'work/tex_name_ids.json')
EPOCH = time.strftime('%Y%m%d')
MAXS = 512
CACHE_FILES = 12


class FileCache:
    def __init__(self, n=CACHE_FILES):
        self.n = n
        self.d = OrderedDict()

    def get(self, path):
        if path in self.d:
            self.d.move_to_end(path)
            return self.d[path]
        with open(path, 'rb') as f:
            b = f.read()
        self.d[path] = b
        if len(self.d) > self.n:
            self.d.popitem(last=False)
        return b


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry', action='store_true')
    ap.add_argument('--limit', type=int, default=0)
    a = ap.parse_args()

    need = json.load(open(NEEDED, encoding='utf-8'))
    texidx = json.load(open(TEXIDX, encoding='utf-8'))
    names = sorted(set(need['have']))
    print('[tb] 需要贴图 %d 个名字；ytd 索引 %d 个名字' % (len(names), len(texidx)))
    if a.limit:
        names = names[:a.limit]

    d = json.load(open(INDEX, encoding='utf-8'))
    texdir = os.path.join(LIB, 'tex')
    os.makedirs(texdir, exist_ok=True)

    cache = FileCache()
    ok = 0
    fail = []
    tex = []
    t0 = time.time()
    for i, nm in enumerate(names):
        e = texidx.get(nm)
        if not e:
            fail.append((nm, 'no-index'))
            continue
        fp = os.path.join(ROOT, e['f'])
        try:
            data = cache.get(fp)
            blob = data[16 + e['sys'] + e['gfx']:]
            blob = blob[:max(4096, e['w'] * e['h'] * 4)]
            im, fmt = decode_one(blob, e['w'], e['h'], e['fmt'])
        except Exception as ex:
            fail.append((nm, 'decode:%s' % ex))
            continue
        if im is None:
            fail.append((nm, 'decode-none'))
            continue
        if max(im.size) > MAXS:
            im = im.resize((MAXS, MAXS), Image.LANCZOS)
        if im.mode not in ('RGB', 'RGBA'):
            im = im.convert('RGB')
        tid = len(tex)
        if not a.dry:
            im.save(os.path.join(texdir, '%05d.png' % tid), 'PNG', optimize=False)
        tex.append({'id': tid, 'n': nm, 'f': 'tex/%05d.png' % tid})
        ok += 1
        if (i + 1) % 2000 == 0:
            print('[tb] %d/%d 解码成功 %d，失败 %d（%.0fs）'
                  % (i + 1, len(names), ok, len(fail), time.time() - t0))

    print('[tb] 解码成功 %d / 失败 %d（%.1f%% 覆盖率，%.0fs）'
          % (ok, len(fail), 100.0 * ok / max(1, len(names)), time.time() - t0))
    if a.dry:
        print('[tb] dry-run，未写盘')
        return

    bak = os.path.join(LIB, 'index_before_textable_%s.json' % time.strftime('%Y%m%d_%H%M'))
    if not os.path.exists(bak):
        shutil.copy2(INDEX, bak)
        print('[tb] 备份 %s' % os.path.basename(bak))

    d['tex'] = tex
    d['tex_epoch'] = EPOCH
    json.dump(d, open(INDEX, 'w', encoding='utf-8'), separators=(',', ':'))
    ids = {'__epoch__': EPOCH}
    ids.update({t['n']: t['id'] for t in tex})
    json.dump(ids, open(IDS, 'w', encoding='utf-8'), separators=(',', ':'))
    print('[tb] 写入 %s：贴图 %d 条 / epoch %s' % (os.path.basename(INDEX), len(tex), EPOCH))
    print('[tb] 名字→id %s' % IDS)
    if fail:
        json.dump([{'n': n, 'why': w} for n, w in fail],
                  open(os.path.join(ROOT, 'work/tex_decode_fail.json'), 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()
