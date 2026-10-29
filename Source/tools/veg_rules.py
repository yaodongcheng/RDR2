# -*- coding: utf-8 -*-
"""植被判定 —— **全仓唯一一份正则**（分类与隐藏共用）。

## 为什么有这个文件（2026-10-29）

以前两处各写一套：
  · `classify_entities.py` 用**宽**规则 → 12,111 个对象算「植被类」
  · `strip_vegetation.py` 用**窄**规则 → 10,860 个被藏起来
结果 1,247 个对象「被判成植被、但没被藏」，面板里出现两个都叫「植被」的集合，
分不清区别。实测这 1,247 个里 573 个是 `p_pot_plant_*`（**盆栽**）、
还有一堆 `p_flowerarng*`（**花艺陈设**）—— 它们本来就该是 **prop 道具**，不是植被。

## 结论（规则本身）

- **算植被**：树 / 灌木 / 草 / 蕨 / 仙人掌 / 棕榈 / 芦苇 / 睡莲 / 藤蔓 / 常春藤 /
  杂草 `weed` / 灌丛 `brush` / `palmetto` / `tumbleweed`（不含 `_wall`，那是墙）。
- **不算植被（是道具）**：`p_pot_`（盆栽）、`flowerarng`（花艺）、`p_cs_`（装饰件）、
  `dressing`（陈设）。它们含 `plant`/`flower` 字样，但物理上是摆件。

两边 import 这里之后：**分类为 veg 的 = 会被隐藏的**，面板只剩一个「植被」。
"""

import re

# 算植被
VEG = re.compile(
    r'p_tree|_tree|bush|shrub|p_fern|_fern|p_grass|_grass|p_plant|_plant|cactus|p_palm|'
    r'p_reed|_reed|lily|'
    # `vine`/`ivy` 前面不能紧跟字母：旧写法把 `cal_privy_01`（厕所）分进了植被。
    # 用 `(?<![a-z])` 而不是 `\b`：`p_ivy_01` / `ragwort_vine` 里前面是下划线，
    # `\b` 不成立（下划线算单词字符），会把真的常春藤/藤蔓也漏掉。
    r'(?<![a-z])vine|(?<![a-z])ivy|foliage|weed|sapling|flower', re.I)

# 命中这些 = 是「长得像植物的道具」，不算植被（先判这个，再判 VEG）
VEG_EXCLUDE = re.compile(
    r'p_pot_|flowerarng|p_cs_|dressing|_pot_|planter', re.I)

# 边长 ≤ 这个的算「盆栽级小件」，即使命中 VEG 也归道具（兜底，防漏）
POT_MAX_M = 3.0


def is_veg(name):
    """按名字判植被：命中 VEG 且不命中 VEG_EXCLUDE。"""
    if not name:
        return False
    b = name.split('/')[-1]
    b = b.split('.')[0] if b.count('.') else b      # 去掉 Blender 的 .001 后缀
    if VEG_EXCLUDE.search(b):
        return False
    return bool(VEG.search(b))
