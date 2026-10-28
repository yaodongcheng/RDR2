#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
补全「任务 id → 脚本文件」映射。

现有 `mission_scripts.json` 只覆盖 194 个任务，150 个随机任务里 61 个没映射上，
但脚本其实就在 `raw/script_full/1491.50/`（例：`RABI22` → `rcm_abigail22.c`）。

做法（只接受可验证的匹配，不硬凑）
--------------------------------
1. 已有映射且文件存在 → 直接沿用，标记 source=existing；
2. 否则在未被占用的脚本里找候选，**必须同时满足**三条才算数：
     · 脚本名去掉 `rcm_/bh_/bounty_` 前缀后，以任务 id 的数字后缀结尾；
     · 脚本名包含任务 id 字母部分（去掉开头 R）的前 3 位；
     · **内容可验证**：脚本里出现 `<MID>_` 或 `<去R前缀>_` 的字面量。
   三条缺一不可 —— 宁可标 missing，也不硬凑（早期版本靠"数字相同"乱配，
   把 `CONSUMABLE_MEAL_CAMP_STEW_DAILY_1` 配到 `cv_cc_am_cnf_01.c`，属于造假）。
3. 通过验证 → source=verified；否则 source=missing（script 留空）。

输出
----
export/levels/world/mission_scripts_plus.json
    { id: {script, source, score} }

用法
----
uv run python tools/recover_mission_scripts.py
"""
import csv
import difflib
import json
import os
import re
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "raw", "script_full", "1491.50")
W = os.path.join(ROOT, "export", "levels", "world")

PREFIX = re.compile(r"^(rcm_|bh_|bounty_|oddjob_|beat_|act_)")


def norm(s):
    return re.sub(r"[^a-z0-9]", "", s.lower())


def split_id(mid):
    m = re.match(r"^([A-Z]+)(\d+)([A-Z]?)$", mid)
    if m:
        return m.group(1), m.group(2)
    m = re.match(r"^([A-Z]+)(\d+)$", mid)
    if m:
        return m.group(1), m.group(2)
    return mid.rstrip("0123456789"), "".join(c for c in mid if c.isdigit())


def main():
    story = {r["id"]: r for r in csv.DictReader(open(os.path.join(W, "missions_story.csv"), encoding="utf-8-sig"))}
    old = json.load(open(os.path.join(W, "mission_scripts.json"), encoding="utf-8"))
    files = {f for f in os.listdir(SRC) if f.endswith(".c")}

    used = set()
    out = {}
    for mid, d in old.items():
        s = (d.get("script") or "").strip()
        if s and s in files:
            out[mid] = {"script": s, "source": "existing", "score": 99}
            used.add(s)

    stems = {f: norm(PREFIX.sub("", f[:-2])) for f in files}

    # RECIPE 不是任务（是营地炖菜配方），根本没有脚本，不参与匹配
    skip = {m for m, r in story.items() if r["category"] == "RECIPE"}

    def content_verified(path, mid):
        try:
            t = open(path, encoding="utf-8", errors="replace").read()
        except OSError:
            return False
        tags = {mid + "_"}
        if mid.startswith("R"):
            tags.add(mid[1:] + "_")
        return any(tag in t for tag in tags)

    missing = [m for m in story if m not in out and m not in skip]
    recovered = 0
    for mid in missing:
        letters, digits = split_id(mid)
        key = norm(letters)[1:] if letters.startswith("R") else norm(letters)  # RABI22 → abi
        best, bs = None, 0
        for f, st in stems.items():
            if f in used:
                continue
            if not digits or not st.endswith(digits):
                continue
            if not (key[:3] and key[:3] in st):
                continue
            if not content_verified(os.path.join(SRC, f), mid):
                continue
            score = 5 + difflib.SequenceMatcher(None, key, st).find_longest_match(0, len(key), 0, len(st)).size
            if score > bs:
                best, bs = f, score
        if best:
            out[mid] = {"script": best, "source": "verified", "score": bs}
            used.add(best)
            recovered += 1
        else:
            out[mid] = {"script": "", "source": "missing", "score": 0}

    with open(os.path.join(W, "mission_scripts_plus.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)

    cats = ("RANDOM_CHARACTER", "RANDOM_STORY_CHARACTER", "BOUNTY_HUNTING",
            "ITEM_REQUEST", "ENDLESS_SUMMER")
    rnd = [m for m, r in story.items() if r["category"] in cats]
    ok_rnd = sum(1 for m in rnd if out.get(m, {}).get("script"))
    print(f"总任务 {len(story)}：有脚本 {sum(1 for v in out.values() if v['script'])}"
          f"（沿用 {sum(1 for v in out.values() if v['source']=='existing')}，"
          f"内容验证后新补 {recovered}）")
    print(f"150 个随机任务：有脚本 {ok_rnd}")
    print("\n新补样本：")
    n = 0
    for mid, v in out.items():
        if v["source"] == "verified" and n < 12:
            print(f"  {mid:8s} -> {v['script']:36s} score={v['score']}  {story[mid]['title_zh'][:16]}")
            n += 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
