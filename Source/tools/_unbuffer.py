# -*- coding: utf-8 -*-
"""把 Blender 内嵌 Python 的 stdout/stderr 改成行缓冲 —— 否则 `-b` 模式下日志是
全缓冲，构建跑到一半日志还是空白的（心跳看不到进度，AGENTS.md §2 明确禁止）。

用法（必须放在 -P 之前，Blender 按命令行顺序执行）：

    blender -b --python tools/_unbuffer.py -P tools/blender_continent.py -- --out ...
"""
import sys

for _s in (sys.stdout, sys.stderr):
  try:
    _s.reconfigure(line_buffering=True, write_through=True)
  except Exception:
    pass
