#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""过场动画反拆解：录屏 → 镜头表 / 字幕对白 / 任务归属 / 查看器

适用：把一段「主线录屏」（带字幕，最好字幕自带说话人）反拆成结构化数据。
不是重新解包资产，而是**从画面+字幕还原演出信息**：
  - 每个镜头（硬切点、时长、关键帧）
  - 过场 / 操作 分类（RDR2 过场有黑边 letterbox）
  - 每句台词（起止时间、OCR 文本、说话人前缀）
  - 与已解包剧本（beats）交叉匹配：任务 / 对话组 / 句号 / 官方说话人
  - 汇总：覆盖了哪些任务、哪些台词是资产里没有的（反拆出来的新增信息）

用法
  uv run python tools/decompose_cutscene.py --stage scan      # 低分辨率扫描（1~2 分钟）
  uv run python tools/decompose_cutscene.py --stage shots     # 镜头表 + 关键帧
  uv run python tools/decompose_cutscene.py --stage subs      # 字幕 OCR（10~20 分钟）
  uv run python tools/decompose_cutscene.py --stage match     # 与剧本对齐
  uv run python tools/decompose_cutscene.py --stage export    # 数据 + 页面
  uv run python tools/decompose_cutscene.py --stage all

输入
  录屏/*.mp4（默认取目录里最大的 mp4），可用 --video 指定
输出
  raw/cutscene/      中间产物（scan.npz / shots.json / subs.json / matched.json / thumbs/）
  export/cutscene/   交付物（index.html / dialogue.json+csv / shots.json+csv / summary.json）
"""
import argparse
import csv
import glob
import json
import os
import re
import subprocess
import sys
import time
from collections import Counter, defaultdict

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'export', 'cutscene')
STORY = os.path.join(ROOT, 'export', 'story')
BEATS = os.path.join(STORY, 'beats')
RAW_CUT = os.path.join(ROOT, 'raw', 'cutscene')

# 当前正在处理的视频（set_ctx 切换；多段录屏各自有独立中间产物）
CUR = dict(slug='_', video=None)
WORK = RAW_CUT
BAND = ''
THUMBS = ''
SHOTS_IMG = os.path.join(OUT, 'shots')


def slug_of(path):
    base = os.path.splitext(os.path.basename(path))[0]
    s = re.sub(r'[^A-Za-z0-9\u4e00-\u9fff-]+', '_', base).strip('_')
    return s[:40] or 'video'


def set_ctx(video):
    """切换当前视频：中间产物 raw/cutscene/<slug>/，缩略图 export/cutscene/shots/<slug>/"""
    global WORK, BAND, THUMBS, SHOTS_IMG
    slug = slug_of(video)
    WORK = os.path.join(RAW_CUT, slug)
    BAND = os.path.join(WORK, 'band')
    THUMBS = os.path.join(WORK, 'thumbs')
    SHOTS_IMG = os.path.join(OUT, 'shots', slug)
    CUR.update(slug=slug, video=video)
    for d in (WORK, BAND, THUMBS, SHOTS_IMG):
        os.makedirs(d, exist_ok=True)
    return CUR

FFMPEG = os.environ.get('FFMPEG') or ''
if not FFMPEG:
    _c = os.path.join(os.environ.get('USERPROFILE', ''),
                      'AppData/Roaming/com.brainmaker.client/cowork-updates/ffmpeg-binary/ffmpeg.exe')
    FFMPEG = _c if os.path.exists(_c) else 'ffmpeg'

SCAN_FPS = 10
SCAN_W, SCAN_H = 320, 180
BAND_FPS = 2
BAND_REL = (0.62, 0.96)            # 字幕竖条（占画面高度比例；stage_scan 会自动校准）


def log(*a):
    print(*a, flush=True)


def pick_video(explicit=None):
    if explicit:
        return explicit if os.path.isabs(explicit) else os.path.join(ROOT, explicit)
    cands = []
    for pat in ('录屏/*.mp4', 'raw/capture/*.mp4'):
        cands += glob.glob(os.path.join(ROOT, pat))
    if not cands:
        raise SystemExit('找不到录屏（录屏/*.mp4）')
    return max(cands, key=os.path.getsize)


def probe(video):
    p = subprocess.run([FFMPEG, '-hide_banner', '-i', video], capture_output=True, text=True,
                       errors='ignore')
    txt = p.stderr
    dur = 0.0
    m = re.search(r'Duration: (\d+):(\d+):(\d+\.\d+)', txt)
    if m:
        dur = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
    w = h = 0
    m = re.search(r'Video:.*?(\d{2,5})x(\d{2,5})', txt)
    if m:
        w, h = int(m.group(1)), int(m.group(2))
    fps = 0.0
    m = re.search(r'(\d+(?:\.\d+)?) fps', txt)
    if m:
        fps = float(m.group(1))
    return dict(duration=round(dur, 2), width=w, height=h, fps=fps, path=video)


# ---------------------------------------------------------------- scan
def stage_scan(video):
    """低分辨率流式扫描，把「每帧的特征」存下来（后续切点/场景判定都从这里算，不用重复解码）

    存什么
      gray40w  40x24 灰度（uint8）    —— 结构差
      hist3d   8x8x8 RGB 直方图（uint8 0~255）—— 颜色分布差（对运镜平移不敏感）
      topb/botb 上下黑边行数          —— 过场黑边判定
    """
    os.makedirs(WORK, exist_ok=True)
    info = probe(video)
    log('scan', info)
    cmd = [FFMPEG, '-hide_banner', '-loglevel', 'error', '-i', video,
           '-vf', f'fps={SCAN_FPS},scale={SCAN_W}:{SCAN_H}', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-']
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, bufsize=10 ** 8)
    fs = SCAN_W * SCAN_H * 3
    ts, topb, botb, brights = [], [], [], []
    grays, hists = [], []
    prof = np.zeros(SCAN_H, np.int32)      # 每行被判为「白字」的帧数
    idx = 0
    gw, gh = SCAN_W // 3, SCAN_H // 3          # 106x60（够算边缘/相关，又不至于太大）
    while True:
        buf = p.stdout.read(fs)
        if len(buf) < fs:
            break
        fr = np.frombuffer(buf, np.uint8).reshape(SCAN_H, SCAN_W, 3)
        g = fr.mean(axis=2)
        rowmean = g.mean(axis=1)
        black = rowmean < 6.0
        tb = 0
        while tb < SCAN_H and black[tb]:
            tb += 1
        bb = 0
        while bb < SCAN_H and black[SCAN_H - 1 - bb]:
            bb += 1
        grays.append(g[::3, ::3][:gh, :gw].astype(np.uint8))
        # 字幕带探测：只看画面中部（躲开左下小地图、右下弹药），统计「白字行」
        mid = g[:, int(SCAN_W * 0.14):int(SCAN_W * 0.86)]
        wrows = (mid > 200).sum(axis=1)
        sel = (wrows >= 3) & (wrows <= 90)
        prof[sel] += 1
        q = (fr.astype(np.uint16) >> 5).astype(np.int32)          # 0..7
        flat = (q[:, :, 0] * 64 + q[:, :, 1] * 8 + q[:, :, 2]).ravel()
        h = np.bincount(flat, minlength=512).astype(np.float32)
        h = h / max(1.0, h.sum())
        hists.append((h * 255).astype(np.uint8))
        ts.append(idx / SCAN_FPS)
        topb.append(tb)
        botb.append(bb)
        brights.append(float(g.mean()))
        idx += 1
        if idx % 4000 == 0:
            log('  frames', idx)
    p.stdout.close()
    p.wait()
    # ---- 自动定字幕带：取「白字行」的 3%~97% 分位，再上下留白 ----
    thr = max(2, int(idx * 0.005))          # 短片段字幕少，阈值按帧数比例给（0.5%）
    rows = np.where(prof >= thr)[0]
    if len(rows) >= 4:
        y0 = int(np.percentile(rows, 3)) - 6
        y1 = int(np.percentile(rows, 97)) + 6
        y0 = max(0, min(y0, SCAN_H - 20))
        y1 = max(y0 + 12, min(SCAN_H, y1))
        info['band_rel'] = [round(y0 / SCAN_H, 4), round(y1 / SCAN_H, 4)]
        info['band_rows'] = [int(y0), int(y1)]
        info['band_source'] = 'auto'
        log('字幕带自动定位: %.2f~%.2f 片高 (扫描分辨率 %d~%d 行)' % (
            info['band_rel'][0], info['band_rel'][1], y0, y1))
    else:
        info['band_rel'] = list(BAND_REL)
        info['band_source'] = 'fallback'
        log('字幕带未探测到，用兜底比例', info['band_rel'])
    np.savez_compressed(os.path.join(WORK, 'scan.npz'),
                        ts=np.array(ts, np.float32), topb=np.array(topb, np.int16),
                        botb=np.array(botb, np.int16), bright=np.array(brights, np.float32),
                        gray=np.array(grays), hist=np.array(hists), info=json.dumps(info))
    log('frames', idx, 'dur', idx / SCAN_FPS)
    return info


# ---------------------------------------------------------------- shots
def frame_metrics(z):
    """从扫描特征算逐帧差（分块向量化，避免一次性 float64 大数组）

    返回
      gdiff  灰度平均绝对差（对硬切敏感，但对运镜也敏感）
      gNCC   灰度归一化互相关（切镜时骤降到 0.1~0.3，运镜一般 >0.5）★主判据
      hdiff  8³ 颜色直方图卡方（切到不同布景才大）
    """
    gray = z['gray']
    hist = z['hist'].astype(np.float32)
    n = len(gray)
    gdiff = np.zeros(n, np.float32)
    gncc = np.ones(n, np.float32)
    hdiff = np.zeros(n, np.float32)
    block = 2000
    for s in range(0, n, block):
        e = min(n, s + block)
        a = gray[s:e].reshape(e - s, -1).astype(np.float32)
        p = gray[max(0, s - 1):max(1, e - 1)]
        if len(p) != e - s:
            p = gray[s:e].reshape(e - s, -1).astype(np.float32)
            p = np.vstack([p[:1], p[:-1]])
        else:
            p = p.reshape(e - s, -1).astype(np.float32)
        gdiff[s:e] = np.abs(a - p).mean(axis=1)
        na, np_ = a.mean(axis=1), p.mean(axis=1)
        sa = a @ np.ones(1) if False else (a * a).sum(axis=1)
        sp = (p * p).sum(axis=1)
        sab = (a * p).sum(axis=1)
        m = a.shape[1]
        den = np.sqrt(np.maximum(sa - m * na * na, 1e-6) * np.maximum(sp - m * np_ * np_, 1e-6))
        gncc[s:e] = (sab - m * na * np_) / den
        h = hist[s:e]
        hp = hist[max(0, s - 1):max(1, e - 1)]
        if len(hp) != e - s:
            hp = np.vstack([h[:1], h[:-1]])
        mm = (h + hp) / 2 + 1e-3
        hdiff[s:e] = (((h - hp) ** 2 / mm).sum(axis=1) / 2)
    gdiff[0] = gncc[0] = hdiff[0] = 0.0
    gncc[0] = 1.0
    gncc = np.clip(gncc, -1, 1)
    return gdiff, gncc, hdiff


def detect_cuts(gdiff, gncc, hdiff, ts):
    """切点判定

    在人工核对过的窗口上标定（21:56/21:58 硬切、22:06 暗景硬切、23:13–23:33 骑马运镜误报）：
      硬切    gNCC 掉到 0.0~0.3；**运镜**虽然 gdiff 可以到 19，但 gNCC 仍在 0.82~0.9
      大跳变  gdiff>=18 且 gNCC<0.6（过场进出、闪白、黑场）
      低置信  gNCC<0.5 且颜色也变（hd>=4）：暗景切镜常落在这里，单独标记
    只保留局部极大（score 最大）并保证 0.5 s 间隔。
    """
    n = len(gdiff)
    score = (1.0 - gncc) * 10 + gdiff * 0.3 + hdiff * 0.15
    conf = {}
    for i in range(1, n - 1):
        hard = gncc[i] < 0.32 and gdiff[i] >= 1.5
        big = gdiff[i] >= 18.0 and gncc[i] < 0.6
        soft = gncc[i] < 0.5 and hdiff[i] >= 4.0 and gdiff[i] >= 3.0
        if not (hard or big or soft):
            continue
        if score[i] < score[i - 1] or score[i] < score[i + 1]:
            continue
        conf[i] = 'high' if (hard or big) else 'low'
    idx = sorted(conf)
    keep = []
    for i in idx:
        if keep and ts[i] - ts[keep[-1]] < 0.5:
            if score[i] > score[keep[-1]]:
                keep[-1] = i
            continue
        keep.append(i)
    return keep, score, conf


def stage_shots():
    z = np.load(os.path.join(WORK, 'scan.npz'), allow_pickle=True)
    ts = z['ts']
    topb = z['topb']
    botb = z['botb']
    bright = z['bright']
    hist = z['hist'].astype(np.float32)
    info = json.loads(str(z['info']))
    gdiff, gncc, hdiff = frame_metrics(z)
    lb_min = max(3, int(round(SCAN_H * 0.025)))
    lb = (topb >= lb_min) & (botb >= lb_min)
    cuts, score, conf = detect_cuts(gdiff, gncc, hdiff, ts)
    np.save(os.path.join(WORK, 'metrics.npy'),
            np.stack([ts, gdiff, gncc, hdiff, score], axis=1).astype(np.float32))
    bounds = [0] + list(cuts) + [len(ts)]
    shots = []
    for k in range(len(bounds) - 1):
        a, b = bounds[k], bounds[k + 1]
        if b - a < 2:
            continue
        seg_lb = lb[a:b]
        shots.append(dict(
            id=len(shots) + 1,
            t0=round(float(ts[a]), 2),
            t1=round(float(ts[b - 1]) + 1.0 / SCAN_FPS, 2),
            cinematic=bool(seg_lb.mean() >= 0.5),
            bar_top=int(np.median(topb[a:b])),
            bar_bot=int(np.median(botb[a:b])),
            bright=round(float(bright[a:b].mean()), 1),
            motion=round(float(gdiff[a:b].mean()), 2),
            cut_conf=conf.get(a, 'start'),
            hist=[round(float(x), 4) for x in hist[a:b].mean(axis=0)],
        ))
    shots[0]['t0'] = 0.0
    shots[-1]['t1'] = info['duration']
    for s in shots:
        s['dur'] = round(s['t1'] - s['t0'], 2)
    # 场景归并：相邻且色彩接近的镜头合并成「场」
    scene_id = 1
    for i, s in enumerate(shots):
        s['scene'] = scene_id
        if i + 1 < len(shots):
            a = np.array(s['hist'])
            b = np.array(shots[i + 1]['hist'])
            if float(np.abs(a - b).sum()) / 255.0 >= 0.25:
                scene_id += 1
    # 过场段落：连续 cinematic 镜头（间隔 < 6 s 视为同一段）
    seg_id = 0
    prev_end = None
    for s in shots:
        if s['cinematic']:
            if prev_end is None or s['t0'] - prev_end > 6.0:
                seg_id += 1
            s['cutscene'] = seg_id
            prev_end = s['t1']
        else:
            s['cutscene'] = None
            prev_end = None
    json.dump(dict(info=info, shots=shots), open(os.path.join(WORK, 'shots.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    cine = [s for s in shots if s['cinematic']]
    log(f'shots {len(shots)}  cuts {len(cuts)}  cinematic {len(cine)}  cutscene-segments {seg_id}  '
        f'cine-time {sum(s["dur"] for s in cine)/60:.1f} min')
    if cine:
        log('shot dur median', round(float(np.median([s['dur'] for s in shots])), 2),
            '| cine median', round(float(np.median([s['dur'] for s in cine])), 2))
    return shots, info


# ---------------------------------------------------------------- thumbs + band
def stage_thumbs(video, shots):
    os.makedirs(THUMBS, exist_ok=True)
    os.makedirs(SHOTS_IMG, exist_ok=True)
    # 一次性抽 2 fps 缩略图，按镜头中点取最近的那张
    cmd = [FFMPEG, '-hide_banner', '-loglevel', 'error', '-y', '-i', video,
           '-vf', f'fps=2,scale=480:270', '-q:v', '6',
           os.path.join(THUMBS, 't_%05d.jpg')]
    subprocess.run(cmd, check=False)
    files = sorted(glob.glob(os.path.join(THUMBS, 't_*.jpg')))
    log('thumbs', len(files))
    from PIL import Image
    used = {}
    for s in shots:
        best, best_b = None, -1.0
        for frac in (0.35, 0.6, 0.85):
            mid = s['t0'] + (s['t1'] - s['t0']) * frac
            k = max(1, min(len(files), int(round(mid * 2))))
            if not files:
                continue
            src = files[k - 1]
            try:
                b = float(np.asarray(Image.open(src).convert('L')).mean())
            except Exception:
                continue
            if b > best_b and b > 6:            # 跳过黑场 / 淡入淡出的全黑帧
                best, best_b = src, b
        if best is None:
            mid = (s['t0'] + s['t1']) / 2
            k = max(1, min(len(files), int(round(mid * 2))))
            best = files[k - 1] if files else None
        if not best:
            continue
        name = f'shot_{s["id"]:04d}.jpg'
        dst = os.path.join(SHOTS_IMG, name)
        if not os.path.exists(dst):
            with open(best, 'rb') as fi, open(dst, 'wb') as fo:
                fo.write(fi.read())
        s['thumb'] = 'shots/%s/%s' % (CUR['slug'], name)
        s['thumb_bright'] = round(best_b, 1)
        used[s['id']] = best
    json.dump(dict(info=json.load(open(os.path.join(WORK, 'shots.json'), encoding='utf-8'))['info'],
                   shots=shots), open(os.path.join(WORK, 'shots.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)


def band_signature(path):
    """字幕条签名：画面中部的白字掩码，缩到 160x24（避开左下小地图 / 右下 HUD）"""
    from PIL import Image
    a = np.asarray(Image.open(path).convert('L'))
    h, w = a.shape
    sub = a[int(h * 0.28):int(h * 0.90), int(w * 0.12):int(w * 0.88)]
    m = sub > 165
    if int(m.sum()) < 40:
        return None
    img = Image.fromarray((m * 255).astype(np.uint8)).resize((160, 24), Image.BILINEAR)
    return np.asarray(img) > 110


def band_crop_for_ocr(path, scale=1.25):
    """裁出（可能的）多行字幕区域，放大后交给 OCR"""
    from PIL import Image
    im = Image.open(path)
    a = np.asarray(im.convert('L'))
    h, w = a.shape
    x0, x1 = int(w * 0.10), int(w * 0.90)
    y0, y1 = int(h * 0.20), int(h * 0.95)
    sub = a[y0:y1, x0:x1]
    m = sub > 150
    rows = np.where(m.sum(axis=1) >= 3)[0]
    if len(rows) == 0:
        return None
    # 找连续行带（一行字幕 = 一条）
    bands, i = [], 0
    while i < len(rows):
        j = i
        while j + 1 < len(rows) and rows[j + 1] - rows[j] <= 4:
            j += 1
        if rows[j] - rows[i] >= 7:
            bands.append((rows[i], rows[j]))
        i = j + 1
    if not bands:
        return None
    top = min(b[0] for b in bands) - 6
    bot = max(b[1] for b in bands) + 7
    cols = np.where(m[max(0, top):bot].any(axis=0))[0]
    if len(cols) == 0:
        return None
    cx0, cx1 = max(0, cols.min() - 8), min(sub.shape[1], cols.max() + 9)
    crop = im.crop((x0 + cx0, y0 + max(0, top), x0 + cx1, y0 + bot))
    cw, ch = crop.size
    return crop.resize((int(cw * scale), int(ch * scale)), Image.LANCZOS)


def stage_subs(force=False):
    """字幕条 → 分组 → OCR → 每句的起止时间与文本"""
    try:
        from rapidocr_onnxruntime import RapidOCR
    except Exception as e:
        raise SystemExit(f'需要 rapidocr_onnxruntime：uv pip install --system rapidocr_onnxruntime（{e}）')
    files = sorted(glob.glob(os.path.join(BAND, 'b_*.png')))
    if not files:
        raise SystemExit('没有字幕条帧，先跑 --stage band')
    cache_path = os.path.join(WORK, 'ocr_cache.json')
    cache = {}
    if os.path.exists(cache_path) and not force:
        cache = json.load(open(cache_path, encoding='utf-8'))
    log('band frames', len(files), 'cache', len(cache))

    sigs = []
    for k, f in enumerate(files):
        sigs.append(band_signature(f))
        if (k + 1) % 1000 == 0:
            log('  sig', k + 1)
    groups = []
    cur = None
    for k, c in enumerate(sigs):
        if c is None:
            if cur:
                groups.append(cur)
                cur = None
            continue
        if cur is None:
            cur = dict(a=k, b=k, cells=c)
            continue
        d = float((c != cur['cells']).sum()) / max(1, int((c | cur['cells']).sum()))
        if d > 0.15:
            groups.append(cur)
            cur = dict(a=k, b=k, cells=c)
        else:
            cur['b'] = k
            cur['cells'] = c
    if cur:
        groups.append(cur)
    # 合并过短组（淡入淡出的过渡帧），并丢弃 <0.5 s 的碎片
    merged = []
    for g in groups:
        if merged and (g['a'] - merged[-1]['b']) <= 1:
            merged[-1]['b'] = g['b']
        else:
            merged.append(dict(g))
    groups = [g for g in merged if (g['b'] - g['a']) >= 1]
    log('subtitle groups', len(groups))

    ocr = RapidOCR()

    def ocr_frame(idx):
        key = str(idx)
        if key in cache:
            return cache[key]
        p = files[idx]
        crop = band_crop_for_ocr(p)
        txt = ''
        if crop is not None:
            try:
                r, _ = ocr(np.asarray(crop)[:, :, ::-1])
            except Exception:
                r = None
            if r:
                r = sorted(r, key=lambda x: min(b[1] for b in x[0]))
                txt = ' '.join(x[1] for x in r)
        cache[key] = txt
        return txt

    def score(t):
        cjk = len(re.findall(r'[\u4e00-\u9fff]', t))
        return cjk * 2 + len(t) * 0.1 - (5 if not cjk and len(t) < 4 else 0)

    out = []
    for n, g in enumerate(groups):
        cand = []
        # 字幕有「逐字显示」的过程：取 0.45/0.75/0.95 三帧，挑信息量最大的一帧
        for frac in (0.45, 0.75, 0.95):
            idx = int(g['a'] + (g['b'] - g['a']) * frac)
            t = ocr_frame(idx)
            if t:
                cand.append((score(t), t, idx))
        if not cand:
            continue
        cand.sort(reverse=True)
        best = cand[0]
        out.append(dict(
            t0=round(g['a'] / BAND_FPS, 2),
            t1=round((g['b'] + 1) / BAND_FPS, 2),
            text=best[1].strip(),
            frame=best[2],
            alts=[c[1] for c in cand[1:]],
        ))
        if (n + 1) % 100 == 0:
            log(f'  ocr {n+1}/{len(groups)}  {out[-1]["text"][:30]}')
            json.dump(cache, open(cache_path, 'w', encoding='utf-8'), ensure_ascii=False)
    json.dump(cache, open(cache_path, 'w', encoding='utf-8'), ensure_ascii=False)
    json.dump(out, open(os.path.join(WORK, 'subs.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    log('subtitle lines', len(out))


def stage_band(video):
    """把字幕带单独抽成一串 PNG（位置来自 scan 的自动探测，与分辨率无关）"""
    os.makedirs(BAND, exist_ok=True)
    info = json.loads(str(np.load(os.path.join(WORK, 'scan.npz'), allow_pickle=True)['info']))
    H = info.get('height') or 720
    W = info.get('width') or 1280
    rel = info.get('band_rel') or list(BAND_REL)
    y0 = max(0, int(H * rel[0]))
    y1 = min(H, int(H * rel[1]))
    h = max(24, y1 - y0)
    log('band crop %dx%d+0+%d  (来源: %s)' % (
        W, h, y0, '逐片自动探测' if info.get('band_source') == 'auto' else '兜底比例'))
    cmd = [FFMPEG, '-hide_banner', '-loglevel', 'error', '-y', '-i', video,
           '-vf', 'fps=%d,crop=%d:%d:0:%d' % (BAND_FPS, W, h, y0), '-q:v', '4',
           os.path.join(BAND, 'b_%05d.png')]
    subprocess.run(cmd, check=False)
    files = glob.glob(os.path.join(BAND, 'b_*.png'))
    log('band frames', len(files))



# ---------------------------------------------------------------- match
CJK = r'\u4e00-\u9fff'


def norm_text(s):
    s = s.replace('…', '').replace('......', '')
    s = re.sub(r'[^\u4e00-\u9fffA-Za-z0-9]', '', s)
    return s.lower()


def split_speaker(raw):
    """从 OCR 串里分离「说话人前缀」——RDR2 的字幕是「名字：台词」，
    OCR 有时把名字读在句首、有时读在句尾（字幕切换的过渡帧）。

    返回 (名字, 台词, 位置) —— 位置是 'lead' / 'trail' / ''
    句尾的名字按经验属于**下一句**，不能当成这一句的说话人证据。
    """
    t = raw.strip()
    m = re.match(rf'^([{CJK}·]{{1,8}})\s*[:：]\s*(.*)$', t)
    if m and len(m.group(2)) >= 2:
        return m.group(1), m.group(2).strip(), 'lead'
    m = re.match(rf'^(.*?)\s*([{CJK}·]{{1,8}})\s*[:：]\s*$', t)
    if m and len(m.group(1)) >= 2:
        return m.group(2), m.group(1).strip(), 'trail'
    return '', t, ''


def load_corpus():
    entries = []
    ov_path = os.path.join(STORY, 'speaker_overrides.json')
    ov = json.load(open(ov_path, encoding='utf-8')) if os.path.exists(ov_path) else {}
    for f in sorted(glob.glob(os.path.join(BEATS, '*.json'))):
        b = json.load(open(f, encoding='utf-8'))
        mid = b['id']
        for g, lines in b.get('conversations', {}).items():
            for ln in lines:
                sp = (ov.get(mid, {}).get(g) or {}).get(str(ln['n']))
                if sp is None:
                    sp = (ov.get(mid, {}).get('*') or {}).get(str(ln['n']))
                entries.append(dict(mission=mid, title=b.get('title_zh'), chapter=b.get('chapter'),
                                    group=g, n=ln['n'], zh=ln['zh'], speaker=sp,
                                    norm=norm_text(ln['zh'])))
    return entries


def clean_markup(s):
    s = re.sub(r'~[a-zA-Z]{1,3}(:[^~]*)?~', '', s)
    s = s.replace('~', '').strip()
    return s


def load_bank_corpus():
    """第二语料：mission_dialogue/<任务>.txt（录进游戏音频库的全部台词，含过场里的
    非对话组台词；没有说话人，但能确定「属于哪个任务」）"""
    entries = []
    d = os.path.join(STORY, 'mission_dialogue')
    for f in sorted(glob.glob(os.path.join(d, '*.txt'))):
        mid = os.path.splitext(os.path.basename(f))[0]
        seen = set()
        n = 0
        try:
            raw = open(f, encoding='utf-8-sig', errors='ignore').read()
        except Exception:
            continue
        for line in raw.replace(chr(13), '').split(chr(10)):
            if not line.strip() or line.startswith('#'):
                continue
            t = clean_markup(line)
            if len(t) < 2 or t in seen:
                continue
            seen.add(t)
            n += 1
            entries.append(dict(mission=mid, title=None, chapter=None, group='BANK', n=n,
                                zh=t, speaker=None, norm=norm_text(t)))
    return entries


def load_objectives():
    entries = []
    for f in sorted(glob.glob(os.path.join(BEATS, '*.json'))):
        b = json.load(open(f, encoding='utf-8'))
        oa = b.get('objectives_all') or {}
        for kind in ('objectives', 'fails'):
            for i, t in enumerate(oa.get(kind) or []):
                t = clean_markup(str(t))
                if len(t) >= 3:
                    entries.append(dict(mission=b['id'], title=b.get('title_zh'), group=kind,
                                        kind=kind, n=i, zh=t, norm=norm_text(t)))
    return entries


def _similarity(nb, c):
    from difflib import SequenceMatcher
    if not nb or not c:
        return 0.0
    if nb == c:
        return 1.0
    short, long_ = (nb, c) if len(nb) <= len(c) else (c, nb)
    if len(short) >= 5 and short in long_:
        return 0.82 + 0.16 * (len(short) / len(long_))
    sm = SequenceMatcher(None, nb, c)
    r = sm.ratio()
    m = sm.find_longest_match(0, len(nb), 0, len(c))
    part = (2.0 * m.size) / max(1, len(nb) + len(c))
    return max(r, part * 0.95)


def build_index(entries):
    by_norm = defaultdict(list)
    by_len = defaultdict(list)
    for e in entries:
        by_norm[e['norm']].append(e)
        by_len[len(e['norm']) // 5].append(e)
    return by_norm, by_len


def _index_of(entries):
    by_norm = defaultdict(list)
    by_len = defaultdict(list)
    for e in entries:
        by_norm[e['norm']].append(e)
        by_len[len(e['norm']) // 5].append(e)
    return by_norm, by_len


def _cands(nb, idx, min_score):
    by_norm, by_len = idx
    found = [(1.0, e) for e in by_norm.get(nb, [])]
    if found:
        return found
    L = len(nb) // 5
    seen = set()
    for d in (-2, -1, 0, 1, 2):
        for e in by_len.get(L + d, []):
            if id(e) in seen:
                continue
            seen.add(id(e))
            sc = _similarity(nb, e['norm'])
            if sc >= min_score:
                found.append((sc, e))
    found.sort(key=lambda x: -x[0])
    return found


def assign(queries, entries_by_mission, windows, used_line, used_corpus,
           min_score=0.55, use_window=True):
    """一对一贪心分配

    queries: [(i, nb, t)]
    windows: {mission: (t_first, t_last)}  —— 只有在这段时间内才考虑该任务的台词，
             用来排除「好吧。」「谢谢你。」这类到处都有的短句串到别的任务
    """
    idx_cache = {}

    def idx_of(m):
        if m not in idx_cache:
            idx_cache[m] = _index_of(entries_by_mission[m])
        return idx_cache[m]

    all_idx = None
    pairs = []
    for i, nb, t in queries:
        if not nb or i in used_line:
            continue
        if use_window and windows:
            ms = [m for m, (a, b) in windows.items() if a - 120 <= t <= b + 120]
            if not ms:
                if all_idx is None:
                    all_idx = _index_of([e for v in entries_by_mission.values() for e in v])
                found = _cands(nb, all_idx, min_score)
            else:
                found = []
                for m in ms:
                    found += _cands(nb, idx_of(m), min_score)
                found.sort(key=lambda x: -x[0])
        else:
            if all_idx is None:
                all_idx = _index_of([e for v in entries_by_mission.values() for e in v])
            found = _cands(nb, all_idx, min_score)
        for sc, e in found[:4]:
            key = (e['mission'], e['group'], e['n'])
            if key in used_corpus:
                continue
            pairs.append((sc, i, e, key))
    pairs.sort(key=lambda x: -x[0])
    got = {}
    for sc, i, e, key in pairs:
        if sc < min_score:
            break
        if i in used_line or key in used_corpus:
            continue
        used_line.add(i)
        used_corpus.add(key)
        got[i] = (sc, e)
    return got


def group_by_mission(entries):
    d = defaultdict(list)
    for e in entries:
        d[e['mission']].append(e)
    return d



# 译名差异（游戏内字幕 vs 本地化表）：归一后再比对
NAME_ALIAS = {'艾比盖尔': '阿比盖尔', '阿比': '阿比盖尔', '哈维尔': '哈维尔',
              '约翰': '约翰', '比尔': '比尔', '蓝尼': '蓝尼', '莱尼': '蓝尼'}


def short_name(n):
    return (n or '').split('·')[0].strip()


def names_equal(a, b):
    """两个说话人是否是同一个人（容忍简称 / 译名差异 / 全名）"""
    sa, sb = short_name(a), short_name(b)
    if not sa or not sb:
        return None
    sa = NAME_ALIAS.get(sa, sa)
    sb = NAME_ALIAS.get(sb, sb)
    if sa == sb:
        return True
    return sa in sb or sb in sa


def resolve_speaker(prefix, cast):
    """把 OCR 出来的「名字：」对到角色表（OCR 常把「达奇」读成「表」）"""
    from difflib import SequenceMatcher
    if not prefix:
        return None, None
    p = prefix.strip(' ·:：')
    if not p:
        return None, None
    if p in cast:
        return p, 'ocr'
    best, best_r = None, 0.0
    for c in cast:
        short = c.split('·')[0]
        r = max(SequenceMatcher(None, p, c).ratio(), SequenceMatcher(None, p, short).ratio())
        if (p and (c.startswith(p) or short.startswith(p))) and len(p) >= 2:
            r = max(r, 0.8)
        if r > best_r:
            best, best_r = c, r
    if best and best_r >= 0.55:
        return best, 'ocr?(%.2f)' % best_r
    return None, None


def match_subs(subs, cast):
    corpus_a = group_by_mission(load_corpus())
    corpus_b = group_by_mission(load_bank_corpus())
    corpus_o = group_by_mission(load_objectives())

    bodies = []
    for s in subs:
        sp_ocr, body, pos = split_speaker(s['text'])
        bodies.append((sp_ocr, body, norm_text(body), pos))
    q = [(i, b[2], subs[i]['t0']) for i, b in enumerate(bodies)]

    used_line, used_corpus = set(), set()
    # 第 1 轮：只认高置信，建立「哪些任务在这段时间里」
    got1 = assign(q, corpus_a, {}, used_line, used_corpus, min_score=0.9, use_window=False)
    # 只让「反复出现」的任务定义时间窗（否则一句「谢谢你」会给别的主角任务开窗）
    cnt = defaultdict(int)
    for i, (sc, e) in got1.items():
        cnt[e['mission']] += 1
    valid = {m for m, c in cnt.items() if c >= 3}
    for i, (sc, e) in list(got1.items()):
        if e['mission'] not in valid:
            used_line.discard(i)
            used_corpus.discard((e['mission'], e['group'], e['n']))
            del got1[i]
    windows = {}
    for i, (sc, e) in got1.items():
        t = subs[i]['t0']
        a, b = windows.get(e['mission'], (t, t))
        windows[e['mission']] = (min(a, t), max(b, t))

    # 第 2 轮：在任务时间窗内补全（含音频库语料）
    got2 = assign(q, corpus_a, windows, used_line, used_corpus, min_score=0.6)
    got3 = assign(q, corpus_b, windows, used_line, used_corpus, min_score=0.66)
    got4 = assign(q, corpus_o, {}, used_line, used_corpus, min_score=0.7, use_window=False)

    # 句尾名字 → 归到下一句（字幕切换时名字先冒出来的典型现象）
    for i in range(len(bodies) - 1):
        sp_ocr, body, nb, pos = bodies[i]
        if pos == 'trail' and sp_ocr and not bodies[i + 1][0]:
            _, body2, nb2, _p2 = bodies[i + 1]
            bodies[i + 1] = (sp_ocr, body2, nb2, 'lead')

    out = []
    for i, s in enumerate(subs):
        sp_ocr, body, nb, pos = bodies[i]
        sp_name, sp_src = resolve_speaker(sp_ocr, cast)
        rec = dict(s, speaker_ocr=sp_ocr, body=body, nb=nb, speaker_pos=pos,
                   speaker_final=None, speaker_src=None, match=None, kind='unknown')
        hit = got1.get(i) or got2.get(i)
        if hit:
            sc, e = hit
            rec['match'] = dict(score=round(float(sc), 3), source='script', mission=e['mission'],
                                title=e['title'], chapter=e['chapter'], group=e['group'], n=e['n'],
                                zh=e['zh'], speaker=e['speaker'])
            rec['kind'] = 'dialogue'
            rec['speaker_final'] = e['speaker'] or sp_name
            rec['speaker_src'] = 'ymt(actor)' if e['speaker'] else (sp_src or None)
            # 画面字幕自带的「名字：」是**独立证据**，但要先过质量闸门：
            #   ① 名字在句首（句尾的名字属于下一句）② 名字是精确命中而非模糊 ③ 剧本匹配 >=0.9
            # 否则只记证据、不下结论（OCR 把「达奇」读成「表」这类噪声很多）
            strong = (pos == 'lead' and sp_src == 'ocr' and sc >= 0.9 and len(body) >= 5)
            rec['speaker_evidence'] = dict(screen=sp_name, pos=pos, strong=bool(strong))
            if e['speaker'] and sp_name and strong:
                rec['speaker_screen'] = sp_name
                rec['speaker_conflict'] = (names_equal(e['speaker'], sp_name) is False)
            else:
                rec['speaker_conflict'] = False
        elif i in got3:
            sc, e = got3[i]
            rec['match'] = dict(score=round(float(sc), 3), source='bank', mission=e['mission'],
                                title=None, chapter=None, group='BANK', n=e['n'], zh=e['zh'],
                                speaker=None)
            rec['kind'] = 'bank'
            rec['speaker_final'] = sp_name
            rec['speaker_src'] = sp_src
        elif i in got4:
            sc, e = got4[i]
            rec['match'] = dict(score=round(float(sc), 3), source='objective', mission=e['mission'],
                                title=e['title'], chapter=None, group=e['kind'], n=e['n'],
                                zh=e['zh'], speaker=None)
            rec['kind'] = 'objective'
        else:
            cjk = len(re.findall(rf'[{CJK}]', body))
            if cjk < 3:
                rec['kind'] = 'ui'
            elif s['t0'] < 170:
                rec['kind'] = 'narration'
            else:
                rec['kind'] = 'unmatched'
            rec['speaker_final'] = sp_name
            rec['speaker_src'] = sp_src
        out.append(rec)
    return out


def collect_cast():
    names = set()
    for f in sorted(glob.glob(os.path.join(BEATS, '*.json'))):
        b = json.load(open(f, encoding='utf-8'))
        for c in b.get('cast') or []:
            names.add(c)
    ov_path = os.path.join(STORY, 'speaker_overrides.json')
    if os.path.exists(ov_path):
        ov = json.load(open(ov_path, encoding='utf-8'))
        for mid, groups in ov.items():
            for g, lines in groups.items():
                for k, v in lines.items():
                    if v:
                        names.add(v)
    names.discard('未知角色')
    return names


def stage_match():
    subs = json.load(open(os.path.join(WORK, 'subs.json'), encoding='utf-8'))
    shots = json.load(open(os.path.join(WORK, 'shots.json'), encoding='utf-8'))['shots']
    rows = match_subs(subs, collect_cast())
    for r in rows:
        mid = (r['t0'] + r['t1']) / 2
        s = next((x for x in shots if x['t0'] <= mid < x['t1']), None)
        if s is None and shots:
            s = shots[-1]
        r['shot'] = s['id'] if s else None
        r['cinematic'] = bool(s and s['cinematic'])
        r['cutscene'] = s['cutscene'] if s else None
    json.dump(rows, open(os.path.join(WORK, 'matched.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    from collections import Counter
    c = Counter(r['kind'] for r in rows)
    log(f'subtitle lines {len(rows)}  ' + '  '.join(f'{k}={v}' for k, v in c.most_common()))
    sp = Counter(r['speaker_final'] for r in rows if r.get('speaker_final'))
    log('speakers:', dict(sp.most_common(12)))
    per = Counter(r['match']['mission'] for r in rows if r.get('match'))
    log('missions:', dict(per.most_common(8)))



# ---------------------------------------------------------------- export
KIND_ZH = {'dialogue': '剧本对白', 'bank': '音频库台词', 'objective': '任务目标',
           'narration': '旁白/章节', 'ui': '界面文本', 'unmatched': '未收录'}


def fmt_t(t):
    return '%02d:%05.2f' % (int(t) // 60, t % 60)


def build_summary(rows, shots, info):
    seg = {}
    for s in shots:
        if s.get('cutscene'):
            g = seg.setdefault(s['cutscene'], dict(id=s['cutscene'], t0=s['t0'], t1=s['t1'],
                                                   shots=0, lines=0, speakers=Counter()))
            g['t0'] = min(g['t0'], s['t0'])
            g['t1'] = max(g['t1'], s['t1'])
            g['shots'] += 1
    for r in rows:
        if r.get('cutscene') and r['cutscene'] in seg:
            g = seg[r['cutscene']]
            g['lines'] += 1
            if r.get('speaker_final'):
                g['speakers'][r['speaker_final']] += 1
    segments = []
    for g in sorted(seg.values(), key=lambda x: x['t0']):
        segments.append(dict(id=g['id'], t0=round(g['t0'], 2), t1=round(g['t1'], 2),
                             dur=round(g['t1'] - g['t0'], 2), shots=g['shots'], lines=g['lines'],
                             speakers=[k for k, _ in g['speakers'].most_common(8)]))
    cine = [s for s in shots if s['cinematic']]
    play = [s for s in shots if not s['cinematic']]
    corpus = load_corpus()
    per_mission = defaultdict(lambda: dict(total=0, seen=set()))
    for e in corpus:
        per_mission[e['mission']]['total'] += 1
    for r in rows:
        m = r.get('match')
        if m and m['source'] == 'script':
            per_mission[m['mission']]['seen'].add((m['group'], m['n']))
    mission_cov = []
    for mid, d in per_mission.items():
        if d['seen']:
            mission_cov.append(dict(mission=mid, total=d['total'], seen=len(d['seen']),
                                    pct=round(len(d['seen']) / max(1, d['total']) * 100, 1)))
    mission_cov.sort(key=lambda x: -x['seen'])
    cast = defaultdict(lambda: dict(lines=0, cine=0, first=None, last=None))
    for r in rows:
        sp = r.get('speaker_final')
        if not sp:
            continue
        c = cast[sp]
        c['lines'] += 1
        c['cine'] += 1 if r.get('cinematic') else 0
        c['first'] = r['t0'] if c['first'] is None else min(c['first'], r['t0'])
        c['last'] = r['t0'] if c['last'] is None else max(c['last'], r['t0'])
    cast_rows = [dict(name=k, **v) for k, v in sorted(cast.items(), key=lambda x: -x[1]['lines'])]
    missing = {}
    for mid, d in per_mission.items():
        if not d['seen']:
            continue
        miss = [dict(group=e['group'], n=e['n'], zh=e['zh'], speaker=e['speaker'])
                for e in corpus if e['mission'] == mid and (e['group'], e['n']) not in d['seen']]
        if miss:
            missing[mid] = miss
    kinds = Counter(r['kind'] for r in rows)
    return dict(
        video=info,
        generated=time.strftime('%Y-%m-%d %H:%M'),
        totals=dict(shots=len(shots), cuts=len(shots) - 1, cinematic_shots=len(cine),
                    gameplay_shots=len(play), cutscene_segments=len(segments),
                    cutscene_time=round(sum(s['dur'] for s in cine), 1),
                    gameplay_time=round(sum(s['dur'] for s in play), 1),
                    subtitle_lines=len(rows), kinds=dict(kinds)),
        pace=dict(cine_shot_median=round(float(np.median([s['dur'] for s in cine])), 2) if cine else 0,
                  gameplay_shot_median=round(float(np.median([s['dur'] for s in play])), 2) if play else 0,
                  cine_cuts_per_min=round(len(cine) / max(1e-6, sum(s['dur'] for s in cine) / 60), 1),
                  shortest=round(min([s['dur'] for s in shots]), 2),
                  longest=round(max([s['dur'] for s in shots]), 2)),
        segments=segments, missions=mission_cov, cast=cast_rows,
        missing_counts={k: len(v) for k, v in missing.items()},
        missing=missing,
    )


def load_one(video):
    """读单条视频的中间产物，打上 video 标记，并算出它自己的 summary"""
    set_ctx(video)
    rp = os.path.join(WORK, 'matched.json')
    sp = os.path.join(WORK, 'shots.json')
    if not (os.path.exists(rp) and os.path.exists(sp)):
        log('!! 跳过（缺少中间产物）', video)
        return None
    rows = json.load(open(rp, encoding='utf-8'))
    W = json.load(open(sp, encoding='utf-8'))
    shots, info = W['shots'], W['info']
    slug = CUR['slug']
    by_shot = defaultdict(list)
    for r in rows:
        r['video'] = slug
        if r.get('shot'):
            by_shot[r['shot']].append(r)
    for x in shots:
        x['video'] = slug
        x['lines'] = len(by_shot.get(x['id'], []))
        sps = Counter([y['speaker_final'] for y in by_shot.get(x['id'], []) if y.get('speaker_final')])
        x['speakers'] = [k for k, _ in sps.most_common(4)]
        x['first_line'] = next((y['body'] for y in by_shot.get(x['id'], [])), '')
    summ = build_summary(rows, shots, info)
    summ['slug'] = slug
    summ['src'] = 'videos/%s.mp4' % slug
    return dict(slug=slug, rows=rows, shots=shots, summary=summ, info=info)


def stage_export_all(videos):
    os.makedirs(OUT, exist_ok=True)
    vdir = os.path.join(OUT, 'videos')
    os.makedirs(vdir, exist_ok=True)
    packs = []
    for v in videos:
        pack = load_one(v)
        if not pack:
            continue
        dst = os.path.join(vdir, pack['slug'] + '.mp4')
        if not os.path.exists(dst):
            try:
                os.link(os.path.abspath(v), dst)
            except Exception:
                import shutil
                shutil.copy(os.path.abspath(v), dst)
        packs.append(pack)

    rows = [r for p_ in packs for r in p_['rows']]
    shots = [x for p_ in packs for x in p_['shots']]
    vid_meta = []
    for p_ in packs:
        sm = p_['summary']
        sm.pop('missing', None)          # 缺口明细单独放，避免页面体积过大
        vid_meta.append(dict(slug=p_['slug'], src='videos/%s.mp4' % p_['slug'],
                             info=p_['info'], summary=sm,
                             missing=p_['summary'].get('missing') or {}))

    merged = dict(generated=time.strftime('%Y-%m-%d %H:%M'), videos=vid_meta,
                  rows=rows, shots=shots)
    json.dump(merged, open(os.path.join(OUT, 'dialogue.json'), 'w', encoding='utf-8'),
              ensure_ascii=False)
    json.dump(dict(generated=merged['generated'], videos=vid_meta, shots=shots),
              open(os.path.join(OUT, 'shots.json'), 'w', encoding='utf-8'), ensure_ascii=False)
    json.dump(dict(generated=merged['generated'],
                   videos=[dict(slug=v['slug'], info=v['info'], summary=v['summary'],
                                missing_counts=v['summary'].get('missing_counts') or {})
                           for v in vid_meta]),
              open(os.path.join(OUT, 'summary.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)

    with open(os.path.join(OUT, 'dialogue.csv'), 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f)
        w.writerow(['视频', '序号', '起', '止', '时长', '镜头', '过场', '类型', '说话人', '说话人来源',
                    '识别文本', '任务', '任务名', '对话组', '句号', '剧本原文', '匹配置信度',
                    '匹配来源', '字幕名字', '名字冲突'])
        for i, r in enumerate(rows, 1):
            m = r.get('match') or {}
            w.writerow([r.get('video', ''), i, fmt_t(r['t0']), fmt_t(r['t1']),
                        round(r['t1'] - r['t0'], 2), r.get('shot'),
                        '过场' if r.get('cinematic') else '操作',
                        KIND_ZH.get(r['kind'], r['kind']), r.get('speaker_final') or '',
                        r.get('speaker_src') or '', r['text'], m.get('mission', ''),
                        m.get('title') or '', m.get('group', ''), m.get('n', ''),
                        m.get('zh', ''), m.get('score', ''), m.get('source', ''),
                        r.get('speaker_screen') or '',
                        '是' if r.get('speaker_conflict') else ''])
    with open(os.path.join(OUT, 'shots.csv'), 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f)
        w.writerow(['视频', '镜头', '场', '起', '止', '时长', '类型', '过场段', '台词数',
                    '说话人', '首句', '切点置信度', '缩略图'])
        for x in shots:
            w.writerow([x.get('video', ''), x['id'], x['scene'], fmt_t(x['t0']), fmt_t(x['t1']),
                        x['dur'], '过场' if x['cinematic'] else '操作', x.get('cutscene') or '',
                        x['lines'], '/'.join(x['speakers']), x['first_line'][:40],
                        x.get('cut_conf', ''), x.get('thumb', '')])

    build_html(merged)
    tot = dict(videos=len(packs),
               shots=sum(p_['summary']['totals']['shots'] for p_ in packs),
               subtitles=sum(p_['summary']['totals']['subtitle_lines'] for p_ in packs),
               dialogue=sum(p_['summary']['totals']['kinds'].get('dialogue', 0) for p_ in packs))
    log('export →', OUT, tot)
    for p_ in packs:
        t = p_['summary']['totals']
        log('  [%s] 镜头=%d 过场=%d 字幕=%d' % (p_['slug'], t['shots'], t['cinematic_shots'],
                                              t['subtitle_lines']))


def link_video(path):
    dst = os.path.join(OUT, 'source.mp4')
    if os.path.exists(dst):
        return
    try:
        os.link(path, dst)
    except Exception:
        import shutil
        shutil.copy(path, dst)


def build_html(merged):
    tpl = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cutscene_template.html')
    if not os.path.exists(tpl):
        log('!! 缺少模板 tools/cutscene_template.html，跳过页面')
        return
    t = open(tpl, encoding='utf-8').read()
    payload = json.dumps(merged, ensure_ascii=False).replace('</', '<\\/')
    open(os.path.join(OUT, 'index.html'), 'w', encoding='utf-8').write(t.replace('/*__DATA__*/', payload))
    log('page', os.path.join(OUT, 'index.html'))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--stage', default='all',
                    choices=['scan', 'shots', 'thumbs', 'band', 'subs', 'match', 'export', 'all'])
    ap.add_argument('--force', action='store_true', help='重跑 OCR（忽略缓存）')
    ap.add_argument('--video', default=None, nargs='*',
                    help='一个或多个录屏；省略则用 录屏/*.mp4 里最大的那条')
    ap.add_argument('--all-videos', action='store_true', help='录屏目录下所有 mp4 都跑一遍')
    args = ap.parse_args()

    os.makedirs(RAW_CUT, exist_ok=True)
    os.makedirs(OUT, exist_ok=True)

    if args.video:
        videos = [v if os.path.isabs(v) else os.path.join(ROOT, v) for v in args.video]
    elif args.all_videos:
        videos = sorted(glob.glob(os.path.join(ROOT, '录屏', '*.mp4')))
    elif args.stage == 'export':
        # 只做导出时，默认把「已经跑过 match 的所有录屏」都并进来，别漏掉之前处理的
        videos = []
        for d in sorted(glob.glob(os.path.join(RAW_CUT, '*'))):
            sj = os.path.join(d, 'shots.json')
            if os.path.isdir(d) and os.path.exists(sj) and os.path.exists(os.path.join(d, 'matched.json')):
                try:
                    videos.append(json.load(open(sj, encoding='utf-8'))['info']['path'])
                except Exception:
                    pass
        if not videos:
            videos = [pick_video(None)]
    else:
        videos = [pick_video(None)]

    log('待处理视频 %d 条' % len(videos))
    for v in videos:
        ctx = set_ctx(v)
        log('=' * 70)
        log('[%s] %s' % (ctx['slug'], v))
        if args.stage in ('scan', 'all'):
            stage_scan(v)
        if args.stage in ('shots', 'all'):
            shots, info = stage_shots()
        elif args.stage in ('thumbs', 'subs', 'match'):
            shots = json.load(open(os.path.join(WORK, 'shots.json'), encoding='utf-8'))['shots']
        else:
            shots = None
        if args.stage in ('thumbs', 'all'):
            stage_thumbs(v, shots)
        if args.stage in ('band', 'all'):
            stage_band(v)
        if args.stage in ('subs', 'all'):
            stage_subs(force=args.force)
        if args.stage in ('match', 'all'):
            stage_match()
    if args.stage in ('export', 'all'):
        stage_export_all(videos)


if __name__ == '__main__':
    main()
