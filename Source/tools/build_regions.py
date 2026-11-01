# -*- coding: utf-8 -*-
"""批量生成区域裁剪 blend（规格 = docs/TODO.md「★ 下一步」§4）。

    python tools/build_regions.py --dry-run          # 只打印计划
    python tools/build_regions.py                    # 跳过 status=done
    python tools/build_regions.py --only 20,18       # 只跑指定编号（已 done 的也跑）
    python tools/build_regions.py --force            # 全部重跑

每块：构建（blender_continent --full）→ 清单归位到 regions_support\\<编号>_<tile>\\ →
`_check_region.py` 对账 → 更新 region_list.csv 的 status。**任何一块 FAIL 立即停止**。

一次只跑一个 Blender；启动前若检测到已有 Blender 进程，直接退出（AGENTS：禁止并跑）。
"""
import argparse
import csv
import datetime
import os
import shutil
import subprocess
import sys
import time

ROOT = r'D:/BrainMaker/大镖客2解包分析'
TOOLS = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.dirname(TOOLS)
REGIONS = os.path.join(ROOT, 'deliverable/blender/regions')
SUPPORT = os.path.join(ROOT, 'deliverable/blender/regions_support')
LIST_CSV = os.path.join(SUPPORT, 'region_list.csv')
CORR = os.path.join(SUPPORT, 'region_corrections.csv')
LIB = os.path.join(ROOT, 'assets/lib_native')
LOGDIR = r'D:/BrainMaker/大镖客2解包分析/_logs'
RUNCMD = os.path.join(TOOLS, 'run.cmd')
UNBUF = os.path.join(TOOLS, '_unbuffer.py')
CONTINENT = os.path.join(TOOLS, 'blender_continent.py')
CHECK = os.path.join(TOOLS, '_check_region.py')
DEFAULT_BLENDER = r'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe'
DRIVER_LOG = os.path.join(LOGDIR, 'build_regions.log')
FIELDS = ['number', 'tile', 'blend', 'visible', 'status']


def log(msg):
    line = '[%s] %s' % (datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S'), msg)
    print(line, flush=True)
    os.makedirs(LOGDIR, exist_ok=True)
    with open(DRIVER_LOG, 'a', encoding='utf-8') as f:
        f.write(line + '\n')


def read_list():
    with open(LIST_CSV, encoding='utf-8', newline='') as f:
        return list(csv.DictReader(f))


def write_list(rows):
    tmp = LIST_CSV + '.tmp'
    with open(tmp, 'w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, lineterminator='\n')
        w.writeheader()
        w.writerows(rows)
    os.replace(tmp, LIST_CSV)


def blender_pids():
    """当前在跑的 Blender 进程（用 tasklist；进程名大小写不敏感）。"""
    try:
        out = subprocess.run(['tasklist', '/FO', 'CSV', '/NH'],
                             capture_output=True, text=True, errors='replace').stdout
    except Exception:
        return []
    pids = []
    for line in out.splitlines():
        cols = [c.strip('"') for c in line.split('","')]
        if cols and cols[0].lower().startswith('blender'):
            try:
                pids.append(int(cols[1]))
            except Exception:
                pass
    return pids


def run_build(num, tile, out, step, blender, timeout):
    logpath = os.path.join(LOGDIR, 'region_%s.log' % num)
    cmd = ('tools\\run.cmd "%s" "%s" -b --python "%s" -P "%s" -- '
           '--out "%s" --lib "%s" --only-tile %s --step %s --rails --full --no-water '
           '--corrections "%s"'
           % (logpath, blender, UNBUF, CONTINENT, out, LIB, tile, step, CORR))
    log('[%s] build cmd: %s' % (num, cmd))
    t0 = time.time()
    p = subprocess.Popen(cmd, cwd=SRC, shell=True)
    try:
        rc = p.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        log('[%s] TIMEOUT %ds -> taskkill /T' % (num, timeout))
        subprocess.run(['taskkill', '/F', '/T', '/PID', str(p.pid)],
                       capture_output=True)
        try:
            p.wait(timeout=60)
        except Exception:
            pass
        return False, 'timeout'
    dt = int(time.time() - t0)
    log('[%s] build rc=%d (%ds)' % (num, rc, dt))
    if rc != 0:
        return False, 'build rc=%d（日志 %s）' % (rc, logpath)
    if not os.path.exists(out):
        return False, 'build 结束但 blend 不存在'
    return True, 'build %ds' % dt


def move_manifests(num, tile):
    """构建写在 regions/ 旁边的清单 → regions_support/<编号>_<tile>/。"""
    stem = '%s_%s' % (num, tile)
    destdir = os.path.join(SUPPORT, stem)
    os.makedirs(destdir, exist_ok=True)
    moved = []
    for name in ('manifest_%s.jsonl' % stem, 'manifest_%s.json' % stem, 'manifest.json'):
        src = os.path.join(REGIONS, name)
        if not os.path.exists(src):
            if name.startswith('manifest_%s.jsonl' % stem):
                return None, '缺少 %s' % name
            continue
        shutil.move(src, os.path.join(destdir, name))
        moved.append(name)
    return os.path.join(destdir, 'manifest_%s.jsonl' % stem), 'moved %d' % len(moved)


def check_region(tile, audit):
    # `--allow-stale-underground`：v23 有一批对象包围盒是局部坐标（矩阵未求值）→ 埋深误判。
    # 区域侧用当前代码是可信的一方；大陆最终重跑之后要改成严检（去掉这个开关）。
    p = subprocess.run([sys.executable, CHECK, '--tile', tile, '--audit', audit,
                        '--allow-stale-underground'],
                       cwd=SRC, capture_output=True, text=True,
                       encoding='utf-8', errors='replace')
    out = (p.stdout or '') + (p.stderr or '')
    for line in out.strip().splitlines():
        log('    ' + line)
    return p.returncode == 0, out.strip().splitlines()[-1] if out.strip() else ''


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--only', default='', help='只跑这些编号，逗号分隔（已 done 的也跑）')
    ap.add_argument('--force', action='store_true', help='忽略 status=done，全部重跑')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--step', default='8', help='地形步长（米），默认 8')
    ap.add_argument('--timeout', type=int, default=3600, help='单块构建超时（秒），默认 3600')
    ap.add_argument('--blender', default=DEFAULT_BLENDER)
    ap.add_argument('--allow-concurrent', action='store_true',
                    help='允许已有 Blender 在跑（默认拒绝，AGENTS 禁止并跑）')
    a = ap.parse_args()

    for p, what in ((LIST_CSV, 'region_list.csv'), (CORR, 'region_corrections.csv'),
                    (LIB, 'lib_native'), (a.blender, 'blender.exe')):
        if not os.path.exists(p):
            log('ERROR 找不到 %s：%s' % (what, p))
            return 2

    rows = read_list()
    only = set(x.strip() for x in a.only.split(',') if x.strip())
    todo = []
    for r in rows:
        num = (r.get('number') or '').strip()
        if not num:
            continue
        if only:
            if num in only:
                todo.append(r)
        elif a.force or (r.get('status') or '').strip() != 'done':
            todo.append(r)

    log('===== build_regions start：待跑 %d 块 (%s) ====='
        % (len(todo), ','.join('%s:%s' % (r['number'], r['tile']) for r in todo) or '无'))
    if not todo:
        log('没有待跑的区域。')
        return 0
    if a.dry_run:
        for r in todo:
            out = os.path.join(REGIONS, '%s_%s.blend' % (r['number'], r['tile']))
            log('[dry] #%s %s -> %s' % (r['number'], r['tile'], out))
        return 0

    pids = blender_pids()
    if pids and not a.allow_concurrent:
        log('ERROR 检测到 Blender 正在运行（PID %s）。先关掉再跑（AGENTS：禁止并跑）。'
            % ','.join(map(str, pids)))
        return 3

    os.makedirs(REGIONS, exist_ok=True)
    os.makedirs(LOGDIR, exist_ok=True)
    failed = 0
    t_all = time.time()
    for i, r in enumerate(todo, 1):
        num = (r.get('number') or '').strip()
        tile = (r.get('tile') or '').strip()
        out = os.path.join(REGIONS, '%s_%s.blend' % (num, tile))
        log('[%s] (%d/%d) 开始 %s' % (num, i, len(todo), tile))
        ok, msg = run_build(num, tile, out, a.step, a.blender, a.timeout)
        if not ok:
            r['status'] = 'failed'
            write_list(rows)
            log('[%s] FAILED：%s（批量停止）' % (num, msg))
            failed = 1
            break
        audit, mmsg = move_manifests(num, tile)
        if not audit:
            r['status'] = 'failed'
            write_list(rows)
            log('[%s] FAILED：清单归位失败（%s）（批量停止）' % (num, mmsg))
            failed = 1
            break
        log('[%s] %s，对账 %s' % (num, mmsg, audit))
        ok, last = check_region(tile, audit)
        if not ok:
            r['status'] = 'failed'
            write_list(rows)
            log('[%s] FAILED：%s（批量停止）' % (num, last or '对账失败'))
            failed = 1
            break
        r['status'] = 'done'
        write_list(rows)
        log('[%s] -> done' % num)

    log('===== build_regions end：%s，总耗时 %d 分钟 ====='
        % ('FAILED' if failed else '全部完成', int((time.time() - t_all) / 60)))
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
