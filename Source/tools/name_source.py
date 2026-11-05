# -*- coding: utf-8 -*-
"""names.txt 的**唯一读取入口**：原表 + 从 `*_children` 反推的父名补充。

## 为什么要有这个模块（2026-11-05）

`names.txt`（rdr2rpf 的生成物）里有大量 `<X>_children`，却**没有父名 `<X>`**：

    有：val_02_slod_children
    无：val_02_slod

世界里的街区 LOD 实例引用的正是父名 → joaat 查不到名字 → 对象被命名成 `e_<hash>`
→ `classify_name` 判成 `unknown`（再被纠错清单误判成 veg）→ 进不了远景分组。
结果：**每座城的远景都偏稀**（瓦伦丁最明显）。

实测（2026-11-05）：

| 项 | 数量 |
|---|---:|
| `*_children` 条目 | 10,621 |
| 父名不在 names.txt | 9,615 |
| 其中在世界里有实例 | 9,037 |
| ├ **有模型**（改名即可修复，全图城镇街区 LOD） | **158** |
| └ 无模型（几何只在 `_children.ydd`，多为地形 SLOD） | 8,879 |

## 规则

- `X_children` → `X`；**只补原表没有的**，不覆盖原表（原表优先）。
- 不改 `names.txt` 本身 —— 那是生成物，下次生成会覆盖（生成物禁止手改）。

## 用法

    from name_source import load_names, load_names_lower, iter_names,
                            parent_names, joaat

    names = load_names()               # {joaat: 原名}
    names = load_names_lower()         # {joaat: 小写名}（分类/比对用）
    for n in iter_names(): ...         # 原表 + 补充，逐条
"""
import os

ROOT = r'D:/BrainMaker/大镖客2解包分析'
NAMES = os.path.join(ROOT, 'tools/rdr2rpf/bin/Release/net9.0/names.txt')

_CACHE = None


def joaat(s):
    h = 0
    for c in s.lower().encode():
        h = (h + c) & 0xFFFFFFFF
        h = (h + (h << 10)) & 0xFFFFFFFF
        h ^= h >> 6
    h = (h + (h << 3)) & 0xFFFFFFFF
    h ^= h >> 11
    return (h + (h << 15)) & 0xFFFFFFFF


def _read(path):
    try:
        with open(path, encoding='latin1', errors='ignore') as f:
            return [ln.strip() for ln in f if ln.strip() and not ln.lstrip().startswith('#')]
    except OSError:
        return []


def parent_names(names=None):
    """`X_children` → `X`（只返回原表里没有的父名，按首次出现顺序去重）。"""
    if names is None:
        names = _read(NAMES)
    have = {n.lower() for n in names}
    seen = set()
    out = []
    for n in names:
        if not n.lower().endswith('_children'):
            continue
        p = n[:-len('_children')]
        pl = p.lower()
        if not p or pl in have or pl in seen:
            continue
        seen.add(pl)
        out.append(p)
    return out


def iter_names(path=NAMES):
    """逐条产出：原表 → 补充父名。"""
    global _CACHE
    if path == NAMES and _CACHE is not None:
        for n in _CACHE:
            yield n
        return
    names = _read(path)
    extra = parent_names(names)
    for n in names:
        yield n
    for p in extra:
        yield p
    if path == NAMES:
        _CACHE = names + extra


def load_names(path=NAMES):
    """{joaat: 原名}（原表优先；补充只填缺）。"""
    d = {}
    for n in iter_names(path):
        d.setdefault(joaat(n), n)
    return d


def load_names_lower(path=NAMES):
    """{joaat: 小写名}（`classify_entities` / `scene_interiors` 用这套口径）。"""
    d = {}
    for n in iter_names(path):
        d.setdefault(joaat(n), n.lower())
    return d
