# -*- coding: utf-8 -*-
"""向后兼容转出口 —— **规则真身已移到 `class_rules.py`**。

保留这个文件是为了让既有 import（blender_tour / write_manifest /
manifest_from_jsonl / report_manifest / classify_entities）不用改路径。
新代码请直接 `from class_rules import ...`；这里不再定义任何规则值。
"""
from class_rules import (  # noqa: F401
    CLASSES, DEFAULT_HIDDEN, TECHNICAL, ROAD, RUIN,
    RULES, LEFTOVER, ALL_CLASSES,
    classify_name, apply_hard_rules, load_corrections, apply_corrections,
)
