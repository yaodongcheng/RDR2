"""为一堆 `.ytd` 建立"纹理条目名 → (文件, 条目下标)"索引。

RDR2 的 `.ytd` 是**多纹理字典**（`cs_dutch_ms1_merge.ytd` 内有 32 张纹理）。
模型 shader 里写的是**贴图条目名**（如 `CS_Dutch_MS1_Holster_Belt_001_c0_000_ab`），
必须先在 `.ytd` 集合里按条目名反查，才能拿到像素。

用法:
  uv run python tools/rdr2_tex_index.py --dir <ytd目录> [--dir ...] --out <index.json>
"""
import os
import sys
import json
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rdr2_ytd as T   # noqa: E402


def index_dirs(dirs, verbose=False):
    idx = {}
    files = []
    for d in dirs:
        if not os.path.isdir(d):
            continue
        for root, _dd, fs in os.walk(d):
            for f in fs:
                if f.lower().endswith('.ytd'):
                    files.append(os.path.join(root, f))
    files.sort()
    for i, p in enumerate(files):
        try:
            raw = open(p, 'rb').read()
            y = T.Ytd(raw)
            texs = y.textures()
        except Exception as e:
            if verbose:
                print('  ERR', p, e)
            continue
        for t in texs:
            nm = (t.get('name') or '').lower()
            if not nm:
                continue
            # 同一名字出现在多个 ytd 时，优先不带 +hi 的（节省内存）
            cur = idx.get(nm)
            if cur is None or ('+hi' in os.path.basename(cur[0]) and '+hi' not in os.path.basename(p)):
                idx[nm] = [p, t['idx']]
        if verbose and i % 200 == 0:
            print(f'  {i}/{len(files)} {os.path.basename(p)}')
    return idx, files


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dir', action='append', default=[])
    ap.add_argument('--out', required=True)
    ap.add_argument('--verbose', action='store_true')
    a = ap.parse_args()
    idx, files = index_dirs(a.dir, a.verbose)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    json.dump({'index': idx, 'files': len(files)}, open(a.out, 'w'), separators=(',', ':'))
    print(f'ytd files={len(files)}  texture entries={len(idx)}  -> {a.out}')


if __name__ == '__main__':
    main()
