# -*- coding: utf-8 -*-
"""批量生成 58 张场景 blend（两层口径）。

    python tools/build_scenes.py --dry-run              # 只打印计划
    python tools/build_scenes.py                       # 跳过已完成（--resume 默认开）
    python tools/build_scenes.py --only sdn,bla         # 只跑指定场景
    python tools/build_scenes.py --force                # 全部重跑

每张：`blender_continent.py --scene <id> --full` → 场景地形（deliverable/terrain）
     → 装配实体（活动区高清 / 活动区外只 lod）→ 分类 → 两层裁剪 + 平移 → manifest + 报告。

验收（每张自动做）：
  · 日志里没有 Traceback；
  · 产物 blend 存在；
  · manifest 里所有实体的世界包围盒都落在**远景范围**内（0 个超界）。

一次只跑一个 Blender；启动前若已有 Blender 在跑，直接退出（AGENTS：禁止并跑）。
状态写 `scene_build_status.csv`（与 blend 同目录）。
"""
import argparse
import collections
import csv
import datetime
import json
import os
import re
import subprocess
import sys
import time

ROOT = r'D:/BrainMaker/大镖客2解包分析'
TOOLS = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.dirname(TOOLS)
# 后面 `import export_scene_terrain_maps` 等在同目录；显式补进 sys.path，
# 免得从别的 cwd 用绝对路径调用时脚本目录没进搜索路径（实测会报 No module named）。
if TOOLS not in sys.path:
    sys.path.insert(0, TOOLS)
LIB = os.path.join(ROOT, 'assets/lib_native')
CORR = os.path.join(ROOT, 'deliverable/blender/regions_support/region_corrections.csv')
CSV_IN = os.path.join(SRC, 'docs', '世界与地编', 'scene_list.csv')
LOGDIR = os.path.join(ROOT, '_logs')
OUTDIR = os.path.join(ROOT, 'deliverable/blender/scenes')
STATUS_CSV = os.path.join(OUTDIR, 'scene_build_status.csv')
RUNCMD = os.path.join(TOOLS, 'run.cmd')
UNBUF = os.path.join(TOOLS, '_unbuffer.py')
CONTINENT = os.path.join(TOOLS, 'blender_continent.py')
DEFAULT_BLENDER = r'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe'
DRIVER_LOG = os.path.join(LOGDIR, 'build_scenes.log')
FIELDS = ['id', 'kind', 'name', 'activity', 'far', 'status', 'seconds', 'objects', 'ring',
          'rooms', 'blend_mb', 'note']


def log(msg):
    line = '[%s] %s' % (datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S'), msg)
    print(line, flush=True)
    os.makedirs(LOGDIR, exist_ok=True)
    with open(DRIVER_LOG, 'a', encoding='utf-8') as f:
        f.write(line + '\n')


def read_scenes():
    rows = []
    with open(CSV_IN, encoding='utf-8-sig', newline='') as f:
        for r in csv.DictReader(f):
            sid = (r.get('id') or '').strip()
            aw = (r.get('活动区宽_m') or '').strip()
            if not sid or not aw:
                continue            # 瓜玛：尺寸待定，先不跑
            rows.append({
                'id': sid, 'kind': r.get('kind') or '', 'name': r.get('name') or '',
                'x': float(r['x']), 'y': float(r['y']),
                'aw': float(r['活动区宽_m']), 'ah': float(r['活动区高_m']),
                'w': float(r['每边外扩_m']),
                'fw': float(r['远景宽_m']), 'fh': float(r['远景高_m']),
            })
    return rows


def read_status():
    if not os.path.exists(STATUS_CSV):
        return {}
    with open(STATUS_CSV, encoding='utf-8', newline='') as f:
        return {r['id']: r for r in csv.DictReader(f)}


def write_status(rows):
    os.makedirs(OUTDIR, exist_ok=True)
    tmp = STATUS_CSV + '.tmp'
    with open(tmp, 'w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, lineterminator='\n')
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, '') for k in FIELDS})
    os.replace(tmp, STATUS_CSV)


def blender_pids():
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


def run_build(sc, out, blender, timeout):
    logpath = os.path.join(LOGDIR, 'scene_%s.log' % sc['id'])
    cmd = ('tools\\run.cmd "%s" "%s" -b --python "%s" -P "%s" -- '
           '--out "%s" --lib "%s" --scene %s --rails --full --corrections "%s"'
           % (logpath, blender, UNBUF, CONTINENT, out, LIB, sc['id'], CORR))
    t0 = time.time()
    p = subprocess.Popen(cmd, cwd=SRC, shell=True)
    try:
        rc = p.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        log('[%s] TIMEOUT %ds -> taskkill /T' % (sc['id'], timeout))
        subprocess.run(['taskkill', '/F', '/T', '/PID', str(p.pid)], capture_output=True)
        try:
            p.wait(timeout=60)
        except Exception:
            pass
        return False, 'timeout', int(time.time() - t0)
    dt = int(time.time() - t0)
    if rc != 0:
        return False, 'rc=%d（日志 %s）' % (rc, logpath), dt
    if not os.path.exists(out):
        return False, 'blend 不存在', dt
    try:
        txt = open(logpath, encoding='utf-8', errors='replace').read()
    except Exception:
        txt = ''
    if 'Traceback' in txt:
        return False, '日志里有 Traceback（%s）' % logpath, dt
    return True, 'ok', dt


def scene_rooms(logpath):
    """从场景日志里抠出室内统计（`[int] 室内：N 个包 / M 个对象`）。没摆返回 '0/0'。"""
    try:
        txt = open(logpath, encoding='utf-8', errors='replace').read()
    except Exception:
        return '0/0'
    m = re.search(r'\[int\] 室内：(\d+) 个包 / (\d+) 个对象', txt)
    return '%s/%s' % (m.group(1), m.group(2)) if m else '0/0'


def scene_warns(logpath):
    """数场景日志里的 `[int][WARN]`（室内朝向未校验等）—— 有就必须在驱动日志里露头。"""
    try:
        txt = open(logpath, encoding='utf-8', errors='replace').read()
    except Exception:
        return 0
    return txt.count('[int][WARN]')


def verify_scene(sc, manifest):
    """0 超界 + 至少 1 个对象 → PASS。"""
    if not os.path.exists(manifest):
        return False, '缺 manifest', 0, 0
    fx0, fy0 = sc['x'] - sc['fw'] / 2, sc['y'] - sc['fh'] / 2
    fx1, fy1 = sc['x'] + sc['fw'] / 2, sc['y'] + sc['fh'] / 2
    n = ring = bad = 0
    with open(manifest, encoding='utf-8') as f:
        for line in f:
            r = json.loads(line)
            bb = r.get('bb')
            if not bb or (r.get('n') or '').startswith('Terrain'):
                continue
            n += 1
            if r.get('ring'):
                ring += 1
            if bb[0] < fx0 - 1 or bb[1] < fy0 - 1 or bb[3] > fx1 + 1 or bb[4] > fy1 + 1:
                bad += 1
    if n == 0:
        return False, '0 个对象', n, ring
    if bad:
        return False, '%d 个对象超出远景框' % bad, n, ring
    return True, 'ok', n, ring


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--only', default='', help='只跑这些 id，逗号分隔')
    ap.add_argument('--force', action='store_true', help='忽略已完成状态，全部重跑')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--timeout', type=int, default=2400, help='单张超时（秒），默认 2400')
    ap.add_argument('--blender', default=DEFAULT_BLENDER)
    ap.add_argument('--dir', default=OUTDIR, help='blend 输出目录')
    ap.add_argument('--allow-concurrent', action='store_true')
    a = ap.parse_args()

    for p, what in ((CSV_IN, 'scene_list.csv'), (CORR, 'region_corrections.csv'),
                    (LIB, 'lib_native'), (a.blender, 'blender.exe'), (RUNCMD, 'run.cmd')):
        if not os.path.exists(p):
            log('ERROR 找不到 %s：%s' % (what, p))
            return 2

    scenes = read_scenes()
    status = read_status()
    only = set(x.strip() for x in a.only.split(',') if x.strip())
    todo = []
    for sc in scenes:
        sid = sc['id']
        if only:
            if sid in only:
                todo.append(sc)
        elif a.force or (status.get(sid, {}).get('status') != 'done'):
            todo.append(sc)

    log('===== build_scenes start：待跑 %d 张 / 共 %d 张 =====' % (len(todo), len(scenes)))

    # 🔴 算法自检（2026-11-04）：地形采样口径（行偏移 -1 / 全局格点 / 最近邻）一旦回归，
    # 断崖处差 2~3 m 但平地上看不出来 —— 批量开跑前必须过 check_scene_terrain.py。
    chk = os.path.join(TOOLS, 'check_scene_terrain.py')
    if os.path.exists(chk):
        p = subprocess.run([sys.executable, chk], capture_output=True, text=True,
                           encoding='utf-8', errors='replace')
        for line in (p.stdout or '').strip().splitlines():
            log('    ' + line)
        if p.returncode != 0:
            log('ERROR 地形算法自检未过（tools/check_scene_terrain.py），先修算法再批量')
            return 4

    # 🔴 UV 的 V 约定闸门（2026-11-05）：RDR2 是左上原点、Blender 是左下原点。
    # 一旦有人把这行翻转删掉/翻反，全世界的文字与贴花都会上下颠倒，而木板砖墙看不出来
    # —— 和上面那条地形 UV 是同一类"自洽但错"的坑，所以**开跑前必须过**。
    uvc = os.path.join(TOOLS, 'check_uv_v_convention.py')
    if os.path.exists(uvc):
        p = subprocess.run([sys.executable, '-X', 'utf8', uvc], capture_output=True,
                           text=True, encoding='utf-8', errors='replace')
        for line in (p.stdout or '').strip().splitlines():
            if any(k in line for k in ('模型', '递减', '递增', 'PASS', 'FAIL')):
                log('    ' + line.strip())
        if p.returncode != 0:
            log('ERROR UV V 约定自检未过（tools/check_uv_v_convention.py），先修再批量')
            return 4

    # 🔴 MLO 实例查找唯一口径闸门（2026-11-06）：构建 / 审计 / 体检必须同一优先级
    #   （精确 → _main → _lod）。旧写法「先撞到谁算谁」会把 `val_bank_int_lod`（yaw −100°）
    #   当成银行实例 ⇒ 瓦伦丁室内转歪，而体检用正确优先级所以 PASS（假绿）。
    mlochk = os.path.join(TOOLS, '_check_mlo_lookup.py')
    if os.path.exists(mlochk):
        p = subprocess.run([sys.executable, '-X', 'utf8', mlochk], capture_output=True,
                           text=True, encoding='utf-8', errors='replace')
        for line in (p.stdout or '').strip().splitlines():
            log('    ' + line.strip())
        if p.returncode != 0:
            log('ERROR MLO 实例查找闸门未过（tools/_check_mlo_lookup.py），先修再批量')
            return 4

    if not todo:
        log('没有待跑的场景。')
        return 0
    if a.dry_run:
        for sc in todo:
            log('[dry] %-8s %-10s 活动区 %.0f 远景 %.0f×%.0f'
                % (sc['id'], sc['name'], sc['aw'], sc['fw'], sc['fh']))
        return 0

    pids = blender_pids()
    if pids and not a.allow_concurrent:
        log('ERROR 检测到 Blender 正在运行（PID %s）。先关掉再跑。' % ','.join(map(str, pids)))
        return 3

    # 分类开关/可见性的合成单测（Blender，约 3 s）。2026-11-04 接进闸门：
    # 这条测试因为"没人跑"烂了很久（SPECS 缺 terrain_lod/road，一跑就 assert 失败），
    # 而它管的正是启动器"面板说隐藏、画面还在"那类 bug（cat_show 子串匹配打错目标）。
    unit = os.path.join(TOOLS, '_check_tour_vis_unit.py')
    if os.path.exists(unit):
        ulog = os.path.join(LOGDIR, 'check_tour_vis_unit.log')
        subprocess.run('tools\\run.cmd "%s" "%s" -b --factory-startup -P "%s"'
                       % (ulog, a.blender, unit), cwd=SRC, shell=True)
        try:
            utxt = open(ulog, encoding='utf-8', errors='replace').read()
        except Exception:
            utxt = ''
        if '=== UNIT OK ===' not in utxt:
            log('ERROR 分类开关单测未过（tools/_check_tour_vis_unit.py），日志 %s' % ulog)
            return 4
        log('    分类开关单测 PASS（=== UNIT OK ===）')

    # 远景框裁剪单测（Blender，约 3 s）。2026-11-04 加：圣丹尼斯 cor_01_slod 漏裁，
    # 根因是 clip_to_rect 用错矩阵（matrix_world 未求值）+ bisect 的 clear 侧用反。
    clip = os.path.join(TOOLS, '_check_scene_trim_clip.py')
    if os.path.exists(clip):
        clog = os.path.join(LOGDIR, 'check_scene_trim_clip.log')
        subprocess.run('tools\\run.cmd "%s" "%s" -b --factory-startup -P "%s"'
                       % (clog, a.blender, clip), cwd=SRC, shell=True)
        try:
            ctxt = open(clog, encoding='utf-8', errors='replace').read()
        except Exception:
            ctxt = ''
        if '=== UNIT OK ===' not in ctxt:
            log('ERROR 远景框裁剪单测未过（tools/_check_scene_trim_clip.py），日志 %s' % clog)
            return 4
        log('    远景框裁剪单测 PASS（=== UNIT OK ===）')

    os.makedirs(a.dir, exist_ok=True)
    os.makedirs(LOGDIR, exist_ok=True)
    failed = 0
    t_all = time.time()
    for i, sc in enumerate(todo, 1):
        sid = sc['id']
        out = os.path.join(a.dir, '%s.blend' % sid)
        manifest = os.path.join(a.dir, 'manifest_%s.jsonl' % sid)
        log('[%s] (%d/%d) 开始：%s（活动区 %.0f / 远景 %.0f×%.0f）'
            % (sid, i, len(todo), sc['name'], sc['aw'], sc['fw'], sc['fh']))
        ok, msg, dt = run_build(sc, out, a.blender, a.timeout)
        row = {'id': sid, 'kind': sc['kind'], 'name': sc['name'],
               'activity': '%d' % sc['aw'], 'far': '%dx%d' % (sc['fw'], sc['fh']),
               'seconds': str(dt),
               'blend_mb': '%.1f' % (os.path.getsize(out) / 1e6) if os.path.exists(out) else '0'}
        if not ok:
            row['status'] = 'failed'; row['note'] = msg
            status[sid] = row; write_status([status[k] for k in sorted(status)])
            log('[%s] FAILED：%s（批量停止）' % (sid, msg))
            failed = 1
            break
        vok, vmsg, n, ring = verify_scene(sc, manifest)
        row.update({'objects': str(n), 'ring': str(ring),
                    'rooms': scene_rooms(os.path.join(LOGDIR, 'scene_%s.log' % sid)),
                    'note': vmsg})
        if not vok:
            row['status'] = 'failed'
            status[sid] = row; write_status([status[k] for k in sorted(status)])
            log('[%s] FAILED：验收 %s（批量停止）' % (sid, vmsg))
            failed = 1
            break
        # TODO-2：同步导出该场景的**高度图 + 材质 mask**（骑砍2 交付物）。
        # 采样口径与 blend 地形同一份实现（scene_terrain_core），自检不过 = 交付物不对。
        try:
            import export_scene_terrain_maps as _maps
            tm = _maps.export_scene(sid)
        except Exception as e:
            row['status'] = 'failed'; row['note'] = '地形图导出异常：%s' % e
            status[sid] = row; write_status([status[k] for k in sorted(status)])
            log('[%s] FAILED：地形图导出异常 %s（批量停止）' % (sid, e))
            failed = 1
            break
        if tm is None:
            log('[%s] 地形图跳过（该行没有远景尺寸）' % sid)
        else:
            ck = tm['check']
            log('[%s] 地形图 %s / %s（%d×%d，最大误差 %.3f m，%s）'
                % (sid, tm['height_png'], tm['mask_png'], tm['width'], tm['height'],
                   ck['max_err_m'], ck['status']))
            if ck['status'] != 'PASS':
                row['status'] = 'failed'; row['note'] = '地形图自检 FAIL'
                status[sid] = row; write_status([status[k] for k in sorted(status)])
                log('[%s] FAILED：地形图自检 FAIL（%s）（批量停止）' % (sid, ck))
                failed = 1
                break
        _w = scene_warns(os.path.join(LOGDIR, 'scene_%s.log' % sid))
        if _w:
            row['note'] = '%s / ⚠ 室内告警 %d' % (vmsg, _w)
            log('[%s] ⚠ 室内告警 %d 条（朝向未校验，见 _logs/scene_%s.log）' % (sid, _w, sid))
        row['status'] = 'done'
        status[sid] = row; write_status([status[k] for k in sorted(status)])
        log('[%s] -> done：%d 对象（远景 %d）/ %ds / %.1f MB'
            % (sid, n, ring, dt, float(row['blend_mb'])))

    log('===== build_scenes end：%s，总耗时 %.1f 分钟 ====='
        % ('FAILED' if failed else '全部完成', (time.time() - t_all) / 60))
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
