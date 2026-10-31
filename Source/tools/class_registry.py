# -*- coding: utf-8 -*-
"""分类注册表 —— **唯一一份**类名表 + 默认隐藏表（不依赖 bpy，谁都能 import）。

## 为什么有这个文件（2026-10-30）

新增 `stone` 类时，`classify_entities` 里加了规则、也设了默认隐藏，但
`write_manifest` / `manifest_from_jsonl` / `report_manifest` 三处各自硬编码了
一份 13 类元组，没人跟着改。后果（v17 实测）：

    清单 classes 13 项合计 183,288，而 entities = 184,032
    → 744 个对象（正好是 stone 类）从类表里凭空消失，
      且 `classes_expected: 13` 还显示"对"，没人看得出来。

照 `veg_rules.py` 的先例把类表收成一份：谁要类名都从这里 import，
加类只改这一处 + `classify_entities.RULES` 加一条规则。

    from class_registry import CLASSES, DEFAULT_HIDDEN
"""

# 类名（key）。顺序只影响报告里的打印次序；真正的分类优先级看
# `classify_entities.RULES` 的书写顺序，不看这里。
CLASSES = (
    'lod', 'terrain_cell', 'underground', 'watertile', 'placeholder',
    'rail', 'struct', 'decal', 'veg', 'stone', 'rock',
    'veh', 'bldg', 'part', 'junk', 'prop', 'unknown',
)

# 默认隐藏的类：构建时把「数据层开关 + 视层眼睛」都设成隐藏，对象仍留在类里。
DEFAULT_HIDDEN = ('lod', 'terrain_cell', 'underground', 'watertile', 'placeholder', 'veg', 'stone')
