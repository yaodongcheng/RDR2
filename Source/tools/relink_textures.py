"""给已入库但缺贴图的模型重新匹配贴图（复用 dump_model_lib.write_model，格式安全）。

场景：`dump_model_lib` 入库时 TexLib 里没有对应 ytd，tex_id 被写成 -1，模型渲染成纯灰。
后来补进了 ytd（如 props 包），用本脚本回填。

用法：
  uv run python tools/relink_textures.py raw/_scratch/props_ydr --txd raw/_scratch/props_txd

只处理：hash 已在库、且当前**所有**子网格 tex_id < 0 的模型。
新贴图 id 从现有条数之后开始，不会覆盖旧图。
"""
import os
import sys
import json
import glob
import argparse

ROOT = r'D:/BrainMaker/大镖客2解包分析'
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import export_sdn_gltf as EX            # noqa: E402
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
    """与 dump_model_lib.Tex 同契约；新 id 从现有条数之后开始。"""

    def __init__(self, lib, dirs, texmeta, maxs=512):
        self.tl = EX.TexLib(dirs, maxs)
        self.dir = os.path.join(lib, 'tex')
        os.makedirs(self.dir, exist_ok=True)
        self.meta = list(texmeta)
        self.idx = {t['n'].lower(): t['id'] for t in texmeta if t.get('n')}
        self._next = len(texmeta)

    def get(self, name, hint_ytd=None):
        if not name:
            return -1
        k = name.lower()
        if k in self.idx:
            return self.idx[k]
        try:
            img, _ = self.tl.get(name, hint_ytd)
        except Exception:
            img = None
        if img is None:
            self.idx[k] = -1
            return -1
        tid = self._next
        self._next += 1
        fn = '%04d.png' % tid
        img.save(os.path.join(self.dir, fn))
        self.meta.append({'id': tid, 'n': name, 'f': 'tex/' + fn})
        self.idx[k] = tid
        return tid


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('ydr_dir')
    ap.add_argument('--txd', action='append', default=[])
    ap.add_argument('--lib', default=os.path.join(ROOT, 'assets/lib_native'))
    a = ap.parse_args()

    lib = a.lib
    idxp = os.path.join(lib, 'index.json')
    idx = json.load(open(idxp, encoding='utf-8'))
    models, texmeta = idx['models'], idx['tex']

    dirs = [os.path.join(ROOT, 'work/lib_gtxd/txd')] + a.txd + [a.ydr_dir]
    tex = Tex(lib, dirs, texmeta, 512)
    print('TexLib 索引 %d，已有贴图 %d' % (len(tex.tl.idx), len(texmeta)))
    start = tex._next

    files = sorted(glob.glob(os.path.join(a.ydr_dir, '**', '*.ydr'), recursive=True))
    print('ydr', len(files))
    fixed = 0
    for f in files:
        nm = os.path.basename(f).rsplit('.', 1)[0].replace('+hidr', '')
        h = joaat(nm)
        key = hex(h)
        m = models.get(key)
        if not m:
            continue
        if any(t >= 0 for t, _, _ in m['s']):
            continue
        try:
            M = EX.load_model(f)
        except Exception:
            continue
        if not M or not M.get('geoms'):
            continue
        try:
            r = write_model(M, h, lib, tex)
        except Exception as e:
            print('  [fail]', nm, e)
            continue
        if not r:
            continue
        if not any(t >= 0 for t, _, _ in r['s']):
            continue          # 还是没图，跳过（别覆盖原条目）
        models[key] = r
        fixed += 1
        print('  + %-30s %d 子网格' % (nm, len(r['s'])))

    idx['tex'] = tex.meta
    json.dump(idx, open(idxp, 'w', encoding='utf-8'), separators=(',', ':'))
    print('回填 %d 个模型，新增贴图 %d 张' % (fixed, tex._next - start))


if __name__ == '__main__':
    main()
