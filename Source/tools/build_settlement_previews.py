"""全据点 3D 预览批处理：按圣丹尼斯的同一套管线，逐镇抽包 → 导出 glTF → 写清单。

和 `export_sdn_gltf.py` 的关系：
  本脚本只负责"准备数据 + 调参数 + 收口清单"，真正的几何/材质导出仍走圣丹尼斯那个导出器
  （同样的 ydr+yft、法线、albedo 白名单、同位置去重规则）。

关键工程决策（来自 Valentine 试点）：
  · **全局道具库只抽一次**：`work/sdn/props` + `work/sdn/props2`（2 145 个道具）
    接到每个镇，实体覆盖率 6% → 72%；不按镇重复抽。
  · 贴图用该镇的 `gtxd_<town>.rpf` + 全局 `work/sdn/gtxd/txd`。
  · 半径按据点档位：城市 equiv/2+80、村庄 equiv/2+60、小屋 100~160。
  · 预览用 `--maxs 256`（512² 太占体积）；正式出场景时改 512。

用法：
  uv run python tools/build_settlement_previews.py --only rho,bla
  uv run python tools/build_settlement_previews.py --all
  uv run python tools/build_settlement_previews.py --all --skip-extract   # 只重导出
"""
import os
import re
import sys
import json
import glob
import time
import shutil
import argparse
import subprocess

ROOT = r'D:/BrainMaker/大镖客2解包分析'
GAME = r'H:/EPICGAMES/RedDeadRedemption2'
RP = os.path.join(ROOT, 'tools/rdr2rpf/bin/Release/net9.0/rdr2rpf.exe')
WORK = os.path.join(ROOT, 'work/towns')
OUT = os.path.join(ROOT, 'export/previews')
sys.path.insert(0, os.path.join(ROOT, 'tools'))

import plan_town  # noqa: E402

SKIP_PACK = ('_vfx', '_lod_combine', '_collision', 'audioproxy', '_decals')


def build_index():
    """levels_N.rpf 的完整条目表 → {path: (levels_file, size)}"""
    idx = {}
    for f in sorted(glob.glob(os.path.join(ROOT, 'work/terrain/list_levels_*.txt'))):
        m = re.search(r'list_levels_(\d)\.txt$', f)
        if not m:
            continue
        lv = os.path.join(GAME, 'levels_%s.rpf' % m.group(1))
        for line in open(f, encoding='utf-8', errors='ignore'):
            mm = re.match(r'\s+(\d+)\s+res=\S+\s+comp=\S+\s+(\S.*)$', line)
            if mm:
                idx[mm.group(2).strip()] = (lv, int(mm.group(1)))
    return idx


def run(cmd, log=None):
    t = time.time()
    p = subprocess.run(cmd, capture_output=True, text=True, errors='ignore')
    dt = time.time() - t
    if log:
        with open(log, 'a', encoding='utf-8') as f:
            f.write('$ %s\n%s\n%s\n' % (' '.join(cmd), p.stdout[-2000:], p.stderr[-2000:]))
    return p.returncode, p.stdout + p.stderr, dt


def extract_entry(levels, path, dest):
    os.makedirs(dest, exist_ok=True)
    rc, out, dt = run([RP, 'extract', levels, dest, path])
    # 抽出来的是 <name>.rpf，再展开
    base = os.path.basename(path)
    got = os.path.join(dest, os.path.dirname(path).replace('levels/rdr3/', '').replace('levels/', ''), base)
    if not os.path.exists(got):
        cand = glob.glob(os.path.join(dest, '**', base), recursive=True)
        got = cand[0] if cand else None
    if got and got.endswith('.rpf'):
        sub = dest + '_x'
        os.makedirs(sub, exist_ok=True)
        run([RP, 'extract', got, sub, ''])
        return sub
    return dest


def town_radius(s):
    eq = s.get('equiv_m') or max(s.get('size_w', 200), s.get('size_d', 200))
    cat = s.get('category', '')
    if s['code'] == 'sdn':
        return 620
    if cat == '大城市':
        return max(400, eq / 2 + 80)
    if cat in ('城堡',):
        return max(320, eq / 2 + 80)
    if cat in ('村庄',):
        return max(240, eq / 2 + 70)
    if cat in ('藏身处',):
        return max(220, eq / 2 + 70)
    return max(140, eq / 2 + 50)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--only', default='')
    ap.add_argument('--all', action='store_true')
    ap.add_argument('--skip-extract', action='store_true')
    ap.add_argument('--maxs', type=int, default=256)
    ap.add_argument('--min-verts', type=int, default=0)
    a = ap.parse_args()

    st = json.load(open(os.path.join(ROOT, 'export/levels/world/settlements.json'),
                        encoding='utf-8'))['settlements']
    want = {x.strip() for x in a.only.split(',') if x.strip()}
    todo = [s for s in st if (a.all or s['code'] in want)]
    if not todo:
        print('没有选中据点（用 --all 或 --only a,b）')
        return

    idx = build_index()
    print('索引 %d 条' % len(idx))
    os.makedirs(WORK, exist_ok=True)
    os.makedirs(OUT, exist_ok=True)
    manifest_path = os.path.join(OUT, 'index.json')
    manifest = json.load(open(manifest_path, encoding='utf-8')) if os.path.exists(manifest_path) else {'items': []}
    by_code = {x['code']: x for x in manifest['items']}

    box = plan_town.tile_bboxes()
    log = os.path.join(WORK, 'batch.log')

    for n, s in enumerate(todo, 1):
        code, name = s['code'], s['name_zh']
        cx, cy = s['cx'], s['cy']
        r = town_radius(s)
        t0 = time.time()
        adir, _tile = plan_town.area_dir_for(cx, cy, box)
        print('[%d/%d] %s %s  (%.0f,%.0f) r=%.0f  area=%s' %
              (n, len(todo), code, name, cx, cy, r, adir))
        if not adir:
            print('   ! 找不到 area 目录，跳过')
            continue

        tdir = os.path.join(WORK, code)
        models = os.path.join(tdir, 'models')
        gtxd = os.path.join(tdir, 'gtxd/txd')

        if not a.skip_extract:
            # 1) 该镇的 area 包（按 code 前缀）
            # 先在**全地图**按 code 前缀找（实测 Tumbleweed/Armadillo 的包在 rstu_96_99，
            # 而不是 plan_town 推出的 rstu_03_06 —— 只按 area 目录找会漏掉整座城）
            packs = [p for p in idx
                     if p.startswith('levels/rdr3/area/')
                     and os.path.basename(p).startswith(code + '_')
                     and not any(k in p for k in SKIP_PACK)]
            if not packs:
                packs = [p for p in idx if '/area/%s/' % adir in p
                         and os.path.basename(p).startswith(code + '_')
                         and not any(k in p for k in SKIP_PACK)]
            # 有些地名的包前缀不是 3 位 code，用更宽的匹配兜底
            if len(packs) < 2:
                alt = s['name_en'].split()[0].lower()[:5]
                packs = [p for p in idx if '/area/' in p
                         and os.path.basename(p).startswith(alt)
                         and not any(k in p for k in SKIP_PACK)]
            print('   area 包 %d 个' % len(packs))
            os.makedirs(models, exist_ok=True)
            for p in packs:
                lv, size = idx[p]
                sub = extract_entry(lv, p, os.path.join(tdir, 'tmp'))
                for f in glob.glob(os.path.join(sub, '**', '*.ydr'), recursive=True) + \
                         glob.glob(os.path.join(sub, '**', '*.yft'), recursive=True):
                    shutil.copy2(f, models)

            # 2) 该镇 gtxd（贴图）
            gname = None
            for p in idx:
                b = os.path.basename(p)
                if p.startswith('levels/rdr3/gtxd/') and b.startswith('gtxd_'):
                    key = b[5:-4]
                    if key and (key.startswith(code) or key.startswith(s['name_en'].split()[0].lower()[:5])):
                        gname = p
                        break
            if gname:
                print('   gtxd: %s' % os.path.basename(gname))
                lv, _ = idx[gname]
                sub = extract_entry(lv, gname, os.path.join(tdir, 'gtxd'))
                os.makedirs(gtxd, exist_ok=True)
                for f in glob.glob(os.path.join(sub, '**', '*.ytd'), recursive=True):
                    shutil.copy2(f, gtxd)

        # 3) 导出 glTF
        outdir = os.path.join(OUT, code)
        # 兼容已有的 work/<code>/models（圣丹尼斯的建筑包不叫 sdn_*，早期是从 zone 抽的）
        legacy = os.path.join(ROOT, 'work', code, 'models')
        ydr_dirs = [models] + ([legacy] if os.path.isdir(legacy) and legacy != models else [])
        ydr_dirs += [os.path.join(ROOT, 'work/sdn/props'),
                     os.path.join(ROOT, 'work/sdn/props2')]
        ydr = ','.join([d for d in ydr_dirs if os.path.isdir(d)])
        ytd = ','.join([gtxd, os.path.join(ROOT, 'work/sdn/gtxd/txd'),
                        os.path.join(ROOT, 'export/models')])
        cmd = [sys.executable, os.path.join(ROOT, 'tools/export_sdn_gltf.py'),
               '--cx', str(cx), '--cy', str(cy), '--r', str(r),
               '--ydr', ydr, '--ytd', ytd, '--chunk', '160',
               '--maxs', str(a.maxs), '--out', outdir]
        rc, outp, dt = run(cmd, log)
        if rc != 0:
            print('   ! 导出失败：', outp[-400:])
            continue
        # 写块清单（预览页按清单加载）
        tdir2 = os.path.join(outdir, 'tiles')
        if os.path.isdir(tdir2):
            files = sorted(os.path.basename(f) for f in glob.glob(os.path.join(tdir2, '*.gltf')))
            json.dump({'files': files}, open(os.path.join(tdir2, 'tiles.json'), 'w'))

        m = re.search(r'实例 (\d+) 个.*模型 (\d+) 个', outp)
        miss = re.search(r'缺 (\d+) 张', outp)
        size = sum(os.path.getsize(f) for f in glob.glob(os.path.join(outdir, '**', '*'), recursive=True)
                   if os.path.isfile(f))
        ent = dict(code=code, name=s['name_en'], zh=name, category=s.get('category'),
                   cx=cx, cy=cy, r=r, u=s.get('u'), v=s.get('v'),
                   instances=int(m.group(1)) if m else None,
                   models=int(m.group(2)) if m else None,
                   miss_tex=int(miss.group(1)) if miss else None,
                   bytes=size, seconds=round(dt, 1), dir='previews/%s' % code)
        by_code[code] = ent
        print('   -> %d 实例 / %d 模型 / %.1f MB / %.0fs' %
              (ent['instances'] or 0, ent['models'] or 0, size / 1e6, dt))
        manifest['items'] = sorted(by_code.values(), key=lambda x: -x['bytes'])
        json.dump(manifest, open(manifest_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    manifest['items'] = sorted(by_code.values(), key=lambda x: (x['category'] or '', -x['bytes']))
    manifest['count'] = len(manifest['items'])
    json.dump(manifest, open(manifest_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('清单 -> %s（%d 个）' % (manifest_path, manifest['count']))


if __name__ == '__main__':
    main()
