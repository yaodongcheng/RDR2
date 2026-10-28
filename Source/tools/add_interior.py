"""把室内 ydr 批量转进 lib_native（RMDL1 + 贴图 + index.json）。

室内模型（`roc_hse_int_*` / `roc_sev_*` / 家具）不在大陆的 area 包里，
而在 `levels/rdr3/interiors/<name>_int.rpf`。本脚本补这条线。

用法：
  uv run python tools/add_interior.py <ydr_dir> [--lib ...]

前置：ydr 对应的 .ytd 必须已经在 TexLib 的搜索目录里
（本脚本默认会先用 `work/lib_gtxd/txd`，所以先 `cp *.ytd` 进去，或让 <ydr_dir> 自己含 ytd）。

产物：写入 lib_native/<hh>/<hash>.mdl + tex/<id>.png，并合并 index.json。
已入库的 hash 自动跳过。
"""
import os
import sys
import json
import glob
import argparse

ROOT = r'D:/BrainMaker/大镖客2解包分析'
sys.path.insert(0, os.path.join(ROOT, 'tools'))

import export_sdn_gltf as EX          # noqa: E402
from dump_model_lib import write_model  # noqa: E402


def joaat(s):
    h = 0
    for c in s.lower().encode():
        h = (h + c) & 0xffffffff
        h = (h + (h << 10)) & 0xffffffff
        h ^= h >> 6
    h = (h + (h << 3)) & 0xffffffff
    h ^= h >> 11
    h = (h + (h << 15)) & 0xffffffff
    return h


class Tex:
    """和 dump_model_lib.Tex 同契约，但允许传入额外 ytd 目录。"""

    def __init__(self, lib, dirs, maxs=512):
        self.tl = EX.TexLib(dirs, maxs)
        self.dir = os.path.join(lib, 'tex')
        os.makedirs(self.dir, exist_ok=True)
        self.idx = {}
        self.meta = []

    def get(self, name, hint_ytd=None):
        if not name:
            return -1
        key = name.lower()
        if key in self.idx:
            return self.idx[key]
        try:
            img, _ = self.tl.get(name, hint_ytd)
        except Exception:
            img = None
        if img is None:
            self.idx[key] = -1
            return -1
        tid = getattr(self, '_next', len(self.meta))
        self._next = tid + 1
        fn = '%04d.png' % tid
        img.save(os.path.join(self.dir, fn))
        self.meta.append({'id': tid, 'n': name, 'f': 'tex/' + fn})
        self.idx[key] = tid
        return tid


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('ydr_dir')
    ap.add_argument('--lib', default=os.path.join(ROOT, 'assets/lib_native'))
    ap.add_argument('--maxs', type=int, default=512)
    a = ap.parse_args()

    lib = a.lib
    idxp = os.path.join(lib, 'index.json')
    idx = json.load(open(idxp, encoding='utf-8'))
    models, texmeta = idx['models'], idx['tex']

    dirs = [os.path.join(ROOT, 'work/lib_gtxd/txd'),
            os.path.join(ROOT, 'work/sdn/gtxd/txd'),
            os.path.join(ROOT, 'export/models'),
            a.ydr_dir]

    tex = Tex(lib, dirs, a.maxs)
    # 已入库的贴图沿用 id（新贴图 id 从现有条数之后开始，绝不覆盖）
    for t in texmeta:
        tex.idx.setdefault(t['n'].lower(), t['id'])
    tex.meta = list(texmeta)          # 先装入已有索引
    tex._next = len(texmeta)

    files = sorted(glob.glob(os.path.join(a.ydr_dir, '**', '*.ydr'), recursive=True))
    print('ydr:', len(files))
    done = skip = fail = 0
    for f in files:
        name = os.path.basename(f).rsplit('.', 1)[0]
        if name.endswith('+hidr'):
            name = name[:-5]
        h = joaat(name)
        k = hex(h)
        if k in models:
            skip += 1
            continue
        try:
            M = EX.load_model(f)
        except Exception as e:
            print('  [load fail]', os.path.basename(f), e)
            fail += 1
            continue
        if not M:
            fail += 1
            continue
        try:
            r = write_model(M, h, lib, tex)
        except Exception as e:
            print('  [write fail]', os.path.basename(f), e)
            fail += 1
            continue
        if not r:
            fail += 1
            continue
        models[k] = r
        done += 1
        print('  + %-34s tris=%-6d %s' % (name, sum(i // 3 for _, v, i in r['s']), k))

    idx['models'] = models
    idx['tex'] = tex.meta   # 已是 旧 + 新增 的完整列表
    json.dump(idx, open(idxp, 'w', encoding='utf-8'), separators=(',', ':'))
    print('入库 %d，跳过(已有) %d，失败 %d；库内模型 %d 个' % (done, skip, fail, len(models)))


if __name__ == '__main__':
    main()
