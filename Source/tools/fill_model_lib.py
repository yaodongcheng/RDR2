"""按区域包补全无损模型库（lib_native）。

流程：解一个包 → 只处理"分区实例引用到、且还没入库"的 ydr/yft →
      无损写进 lib_native → 立刻删原始资源（峰值磁盘只多一个包）。

可反复执行，已入库的 hash 自动跳过。

用法：
  uv run python tools/fill_model_lib.py --max-minutes 40
  uv run python tools/fill_model_lib.py --only-area          # 只跑 area 包（建筑）
"""
import os
import re
import sys
import json
import time
import glob
import shutil
import argparse

ROOT = r'D:/BrainMaker/大镖客2解包分析'
sys.path.insert(0, os.path.join(ROOT, 'tools'))

import dump_model_lib as D  # noqa: E402

GAME = r'H:/EPICGAMES/RedDeadRedemption2'
RP = os.path.join(ROOT, 'tools/rdr2rpf/bin/Release/net9.0/rdr2rpf.exe')
LIB = D.OUT
TILES = os.path.join(ROOT, 'export/world/continent/tiles')
TMP = os.path.join(ROOT, 'work/fill_lib')
STATE = os.path.join(ROOT, 'work/fill_lib_state.json')

BAD = ('_slod', 'audioproxy', 'vfx_', 'lights_holder', '_shad', 'audioemitter',
       'helper', '_em00', '_proxy', '_collision', '_lod', 'lod_combine')


def joaat(s):
    h = 0
    for c in s.lower().encode():
        h = (h + c) & 0xffffffff
        h = h + (h << 10) & 0xffffffff
        h ^= h >> 6
    h = (h + (h << 3)) & 0xffffffff
    h ^= h >> 11
    h = (h + (h << 15)) & 0xffffffff
    return h


def packs(only_area, with_terrain=False):
    out = {}
    for f in sorted(glob.glob(os.path.join(ROOT, 'work/terrain/list_levels_*.txt'))):
        m = re.search(r'list_levels_(\d)\.txt$', f)
        if not m:
            continue
        lv = os.path.join(GAME, 'levels_%s.rpf' % m.group(1))
        for line in open(f, encoding='utf-8', errors='ignore'):
            mm = re.match(r'\s+(\d+)\s+res=\S+\s+comp=\S+\s+(\S.*)$', line)
            if not mm:
                continue
            p = mm.group(2).strip()
            if only_area:
                ok = '/area/' in p
            elif with_terrain:
                ok = ('/area/' in p or '/props/' in p or '/interiors/' in p
                      or '/terrain/' in p or '/destruction/' in p)
            else:
                ok = ('/area/' in p or '/props/' in p or '/interiors/' in p)
            if ok:
                out[p] = lv
    return out


def needed():
    need = set()
    for f in glob.glob(os.path.join(TILES, '*.json')):
        for e in json.load(open(f, encoding='utf-8')):
            need.add(e[0])
    return need


def extract(levels, path, dest):
    import subprocess
    os.makedirs(dest, exist_ok=True)
    subprocess.run([RP, 'extract', levels, dest, path], capture_output=True)
    for r in glob.glob(os.path.join(dest, '**', '*.rpf'), recursive=True):
        d = r[:-4] + '_x'
        os.makedirs(d, exist_ok=True)
        subprocess.run([RP, 'extract', r, d, ''], capture_output=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--max-minutes', type=float, default=0)
    ap.add_argument('--only-area', action='store_true')
    ap.add_argument('--with-terrain', action='store_true')
    ap.add_argument('--maxs', type=int, default=512)
    a = ap.parse_args()

    idx_path = os.path.join(LIB, 'index.json')
    lib = json.load(open(idx_path, encoding='utf-8')) if os.path.exists(idx_path) else {'models': {}, 'tex': []}
    done = {int(k, 16) for k in lib['models']}
    need = needed()
    print('已入库 %d / 需要 %d（缺 %d）' % (len(done), len(need), len(need - done)))

    tex = D.Tex(LIB, a.maxs)
    tex.by_name = {t['n'].lower(): t['id'] for t in lib['tex']}
    tex.meta = lib['tex']

    allp = packs(a.only_area, getattr(a, 'with_terrain', False))
    allp = {k: v for k, v in allp.items() if 'lod_combine' not in k}
    state = json.load(open(STATE, encoding='utf-8')) if os.path.exists(STATE) else {'done': []}
    done_packs = set(state['done'])
    todo = [p for p in sorted(allp) if p not in done_packs]
    print('待处理包 %d' % len(todo))

    t0 = time.time()
    n = 0
    added = 0
    for path in todo:
        if a.max_minutes and (time.time() - t0) / 60 > a.max_minutes:
            print('到时间上限')
            break
        work = os.path.join(TMP, 'p')
        shutil.rmtree(work, ignore_errors=True)
        extract(allp[path], path, work)

        files = {}
        for f in glob.glob(os.path.join(work, '**', '*.ydr'), recursive=True) + \
                 glob.glob(os.path.join(work, '**', '*.yft'), recursive=True):
            b = os.path.splitext(os.path.basename(f))[0]
            if any(x in b.lower() for x in BAD):
                continue
            h = int(b, 16) if re.match(r'^0x[0-9a-fA-F]{1,8}$', b) else joaat(b)
            if h in done or h not in need:
                continue
            files[h] = f
        if not files:
            done_packs.add(path)
            shutil.rmtree(work, ignore_errors=True)
            n += 1
            if n % 20 == 0:
                print('[%d] 空包累计 %d，用时 %.0f 分' % (n, len(done_packs), (time.time() - t0) / 60))
            continue

        ytd_dirs = sorted({os.path.dirname(f) for f in glob.glob(os.path.join(work, '**', '*.ytd'), recursive=True)})
        import export_sdn_gltf as EX
        tex.tl = EX.TexLib(ytd_dirs + [os.path.join(ROOT, 'work/lib_gtxd/txd')], a.maxs)

        got = 0
        for h, fp in files.items():
            M = D.load_any(fp)
            if not M:
                continue
            e = D.write_model(M, h, LIB, tex)
            if not e:
                continue
            lib['models'][hex(h)] = {k: e[k] for k in ('f', 'b', 's')}
            done.add(h)
            got += 1
        added += got
        done_packs.add(path)
        n += 1
        shutil.rmtree(work, ignore_errors=True)
        print('[%d] %-50s +%3d  累计 %d  %.0f 分' %
              (n, path.split('/area/')[-1], got, len(done), (time.time() - t0) / 60))

        lib['tex'] = tex.meta
        if n % 3 == 0:
            json.dump(lib, open(idx_path, 'w'), separators=(',', ':'))
            json.dump({'done': sorted(done_packs)}, open(STATE, 'w'))

    lib['tex'] = tex.meta
    json.dump(lib, open(idx_path, 'w'), separators=(',', ':'))
    json.dump({'done': sorted(done_packs)}, open(STATE, 'w'))
    sz = sum(os.path.getsize(os.path.join(dp, f)) for dp, _, fs in os.walk(LIB) for f in fs)
    print('\n+%d 模型；库 %d 模型 / %d 贴图 / %.2f GB；用时 %.1f 分' %
          (added, len(done), len(tex.meta), sz / 1e9, (time.time() - t0) / 60))


if __name__ == '__main__':
    main()
