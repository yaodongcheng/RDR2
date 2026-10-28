"""把全部 gtxd 包的 ytd 抽到一个公共贴图池（贴图按名字兜底用）。

产物：work/lib_gtxd/txd/*.ytd
用法：uv run python tools/extract_gtxd_pool.py
"""
import os, re, glob, shutil, subprocess, time
ROOT = r'D:/BrainMaker/大镖客2解包分析'
GAME = r'H:/EPICGAMES/RedDeadRedemption2'
RP = os.path.join(ROOT, 'tools/rdr2rpf/bin/Release/net9.0/rdr2rpf.exe')
OUT = os.path.join(ROOT, 'work/lib_gtxd/txd')
TMP = os.path.join(ROOT, 'work/lib_gtxd/tmp')

def main():
    os.makedirs(OUT, exist_ok=True)
    idx = {}
    for f in sorted(glob.glob(os.path.join(ROOT, 'work/terrain/list_levels_*.txt'))):
        m = re.search(r'list_levels_(\d)\.txt$', f)
        if not m: continue
        lv = os.path.join(GAME, 'levels_%s.rpf' % m.group(1))
        for line in open(f, encoding='utf-8', errors='ignore'):
            mm = re.match(r'\s+(\d+)\s+res=\S+\s+comp=\S+\s+(\S.*)$', line)
            if mm and '/gtxd/' in mm.group(2):
                idx[mm.group(2).strip()] = lv
    print('gtxd 包', len(idx))
    t0 = time.time()
    for i, (path, lv) in enumerate(sorted(idx.items()), 1):
        shutil.rmtree(TMP, ignore_errors=True)
        os.makedirs(TMP, exist_ok=True)
        subprocess.run([RP, 'extract', lv, TMP, path], capture_output=True)
        for r in glob.glob(os.path.join(TMP, '**', '*.rpf'), recursive=True):
            d = r[:-4] + '_x'
            os.makedirs(d, exist_ok=True)
            subprocess.run([RP, 'extract', r, d, ''], capture_output=True)
        n = 0
        for f in glob.glob(os.path.join(TMP, '**', '*.ytd'), recursive=True):
            dst = os.path.join(OUT, os.path.basename(f))
            if not os.path.exists(dst):
                shutil.copy2(f, dst); n += 1
        print('[%2d/%d] %-46s +%3d  (%.1f 分)' % (i, len(idx), path.split('/gtxd/')[-1], n, (time.time()-t0)/60))
        shutil.rmtree(TMP, ignore_errors=True)
    print('池中 ytd', len(os.listdir(OUT)))

if __name__ == '__main__':
    main()
