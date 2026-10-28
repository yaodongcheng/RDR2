#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
把随机任务的中文台词库（`raw/story/lang/chinesesimp/<bank>.yldb`）提取成结构化对白。

为什么单独做
------------
`export/levels/world/mission_dialogues.json` 只覆盖 38 个任务（多为章节任务），
随机任务（赏金/陌生人）的台词在**独立的 yldb 库**里，没被并进去。
本轮实测：150 个随机任务里 **35 个**有中文台词库（13 个赏金任务全有）。

清洗规则
--------
RDR2 字幕带富文本标记，这里统一去掉：
  `~z~`          台词开始标记
  `~sl:a:b~`     时间轴（保留正文）
  `~n~`          换行 → 空格
  `~INPUT_XXX~`  按键提示 → 保留可读部分（如 `~INPUT_JUMP~` → 「跳跃」）

输出
----
export/levels/world/random_dialogue.json
    { mission_id: { bank, lines: [ {t, text} ], n } }
export/levels/world/random_dialogue.csv
    mission_id, idx, t, text

用法
----
uv run python tools/build_random_dialogue.py
"""
import csv
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from yldb_dump import strings_of  # noqa: E402

LANG = os.path.join(ROOT, "raw", "story", "lang", "chinesesimp")
W = os.path.join(ROOT, "export", "levels", "world")
CJK = re.compile(r"[\u4e00-\u9fff]")

RANDOM_CATS = ("RANDOM_CHARACTER", "RANDOM_STORY_CHARACTER", "BOUNTY_HUNTING",
               "ITEM_REQUEST", "ENDLESS_SUMMER")

# 常见按键提示的可读化（其余直接去掉提示文本）
INPUT_ZH = {
    "JUMP": "跳跃", "ATTACK": "攻击", "AIM": "瞄准", "INTERACT": "互动",
    "COVER": "掩体", "RELOAD": "装弹", "MELEE": "近战", "DEADEYE": "死神之眼",
    "HORSE_SPUR": "催马", "WHISTLE": "吹哨", "LANTERN": "提灯",
}


def clean(s):
    """去 RDR2 富文本标记。"""
    s = re.sub(r"~sl:[\d.]+:[\d.]+~", "", s)
    s = re.sub(r"~INPUT_([A-Z_0-9]+)~", lambda m: "「" + INPUT_ZH.get(m.group(1), m.group(1)) + "」", s)
    s = s.replace("~z~", "").replace("~n~", " ").replace("~z", "")
    s = re.sub(r"~[a-z]{1,3}~", "", s)
    s = re.sub(r"\s{2,}", " ", s).strip()
    return s


def main():
    story = list(csv.DictReader(open(os.path.join(W, "missions_story.csv"), encoding="utf-8-sig")))
    have = set(os.listdir(LANG))

    out, rows = {}, []
    for r in story:
        if r["category"] not in RANDOM_CATS:
            continue
        bank = (r["dialogue_bank"] or "").strip()
        if not bank or bank not in have:
            continue
        raw = strings_of(os.path.join(LANG, bank))
        items = []
        for it in raw:
            # strings_of 返回 (key, text) 或纯字符串，两种都兜住
            if isinstance(it, (tuple, list)) and len(it) == 2:
                k, t = it
            else:
                k, t = None, str(it)
            if not isinstance(t, str) or not CJK.search(t):
                continue
            txt = clean(t)
            if len(txt) < 2:
                continue
            items.append({"t": k, "text": txt})
        if not items:
            continue
        out[r["id"]] = {"bank": bank, "n": len(items), "lines": items}
        for i, x in enumerate(items):
            rows.append({"mission_id": r["id"], "idx": i, "t": x["t"] or "", "text": x["text"]})

    os.makedirs(W, exist_ok=True)
    with open(os.path.join(W, "random_dialogue.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    with open(os.path.join(W, "random_dialogue.csv"), "w", encoding="utf-8-sig", newline="") as fh:
        wr = csv.DictWriter(fh, fieldnames=["mission_id", "idx", "t", "text"])
        wr.writeheader()
        wr.writerows(rows)

    print(f"提取 {len(out)} 个随机任务的台词，共 {sum(v['n'] for v in out.values())} 行")
    by = {}
    for r in story:
        if r["id"] in out:
            by[r["category"]] = by.get(r["category"], 0) + 1
    for k, v in sorted(by.items(), key=lambda x: -x[1]):
        print(f"  {v:3d}  {k}")
    print("\n抽样：")
    for mid in list(out)[:2]:
        print(f"  [{mid}] {out[mid]['bank']} {out[mid]['n']} 行")
        for x in out[mid]["lines"][:3]:
            print("     -", x["text"][:60])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
