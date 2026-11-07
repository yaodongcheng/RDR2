# -*- coding: utf-8 -*-
"""场景远景框 ↔ 地图边界：**唯一实现**（纯 Python，不依赖 Blender）。

2026-11-07 用户裁定："远景框要考虑地图边界" —— 超出官方地图画面区的部分是在建没有画面/没有地形
数据的地方，应该裁掉。裁剪结果**必须**被三处共用，否则构建和验收会用两个框：
  ① `scene_trim.load_scene()`（地形 + 裁剪 + 摆放都吃它）
  ② `build_scenes.read_scenes()`（构建后的「0 超界」验收）
  ③ 预览页 `regions_viewer.html`（只负责画出来，不裁剪）

规则：夹进 `docs/世界与地编/scene_extent.json` 的 `map` 框 → 再**向外**取 128 的整数倍
（地形按 128 节点切）→ 并保证活动区 P 完整（代价是最多多出 128 m）。
"""
import json
import math
import os

SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXTENT_JSON = os.path.join(SRC, 'docs', '世界与地编', 'scene_extent.json')
Q = 128.0
_CACHE = None


def map_extent():
    """地图画面区 `[x0, y0, x1, y1]`；读不到返回 None（不裁剪，保持旧行为）。"""
    global _CACHE
    if _CACHE is None:
        try:
            _CACHE = json.load(open(EXTENT_JSON, encoding='utf-8')).get('map') or ()
        except Exception:
            _CACHE = ()
    return _CACHE or None


def clamp_scene_to_map(sc, verbose=True):
    """把 `sc` 的远景框夹进地图边界；返回**新的** dict（不改原对象）。"""
    ext = map_extent()
    if not ext or len(ext) < 4:
        return sc
    x, y, fw, fh = float(sc['x']), float(sc['y']), float(sc['fw']), float(sc['fh'])
    L, R, B, T = x - fw / 2, x + fw / 2, y - fh / 2, y + fh / 2
    if not (L < ext[0] or B < ext[1] or R > ext[2] or T > ext[3]):
        return sc
    # 默认**向内**取 128 的整数倍（裁剪就是要变小）；只有活动区 P 会被切到时才向外扩。
    L = math.ceil(max(L, ext[0]) / Q) * Q
    B = math.ceil(max(B, ext[1]) / Q) * Q
    R = math.floor(min(R, ext[2]) / Q) * Q
    T = math.floor(min(T, ext[3]) / Q) * Q
    p = sc.get('p')
    if p:
        L = min(L, math.floor(float(p[0]) / Q) * Q)
        B = min(B, math.floor(float(p[1]) / Q) * Q)
        R = max(R, math.ceil(float(p[2]) / Q) * Q)
        T = max(T, math.ceil(float(p[3]) / Q) * Q)
    out = dict(sc)
    out.update({'x': (L + R) / 2, 'y': (B + T) / 2, 'fw': R - L, 'fh': T - B})
    if verbose:
        print('[scene] %s 远景框按地图边界裁剪：%.0fx%.0f → %.0fx%.0f'
              % (sc.get('id', '?'), fw, fh, R - L, T - B))
    return out
