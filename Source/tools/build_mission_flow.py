#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
把任务脚本还原成「真实执行时间轴」。

不发明任何东西
--------------
本脚本只做一件事：**按反编译源码的行号顺序**，把脚本里真实存在的调用抽出来排成时间轴：
    · 对话：脚本里的对话组标签（如 `RBT14_GREET_A`）→ 字幕库按 `组名_1/2/3…` 取**真实中文台词**
    · 目标：`mission_objectives.csv` 里已解出的目标 / 失败条件（真实文案）
    · 生成：`CREATE_PED/OBJECT/VEHICLE` 调用点 + 附近的模型名
    · 行为：`TASK_*` 调用点（带中文）
    · 演出：`ANIMSCENE` / `TASK_PLAY_ANIM` 调用点

每条事件都带 **源码行号**，可以回到 `raw/script_full/1491.50/<script>` 逐行核对。
不生成任何数值（成功率/荣誉/时间都不编）。

输出
----
export/levels/world/mission_flow.json   按任务：phases → beats
export/levels/world/mission_flow.csv    拍平，便于统计

用法
----
uv run python tools/build_mission_flow.py [--all]
    --all  除 150 个随机任务外，把 270 个任务全跑（章节任务也还原）
"""
import argparse
import csv
import json
import os
import re
import sys
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from yldb_keys import Yldb                     # noqa: E402
from build_mission_schedule import TASK_ZH as BASE_TASK_ZH   # noqa: E402

SRC = os.path.join(ROOT, "raw", "script_full", "1491.50")
LANG = os.path.join(ROOT, "raw", "story", "lang", "chinesesimp")
W = os.path.join(ROOT, "export", "levels", "world")

RANDOM_CATS = ("RANDOM_CHARACTER", "RANDOM_STORY_CHARACTER", "BOUNTY_HUNTING",
               "ITEM_REQUEST", "ENDLESS_SUMMER")

# 函数定义行
FN_DEF = re.compile(r"^(?:void|int|float|bool|char|vector3|var|struct<[^>]*>)\s+(func_\d+)\s*\(")
# 生成调用
SPAWN = re.compile(r"(PED|OBJECT|VEHICLE)::(CREATE_[A-Z_0-9]+)\s*\(")
# 行为调用
TASK = re.compile(r"TASK::(TASK_[A-Z_0-9]+)\s*\(")
# 演出：只认"创建/加载/播放"动画场景，查询类（IS_/DOES_/GET_/WAS_…）不算演出
ANIM = re.compile(r"ANIMSCENE::(_CREATE_ANIM_SCENE)\s*\(")

# 纯状态类行为：不构成"这一步在干什么"，会让时间轴只剩噪音
NOISE_TASKS = {
    "TASK_CLEAR_LOOK_AT", "TASK_STAND_STILL", "TASK_TURN_PED_TO_FACE_ENTITY",
    "TASK_LOOK_AT_ENTITY", "TASK_WANDER_STANDARD", "TASK_ACHIEVE_HEADING",
    "TASK_LOOK_AT_COORD", "TASK_SET_BLOCKING_OF_NON_TEMPORARY_EVENTS",
}
# 字符串字面量
LIT = re.compile(r'"([A-Za-z][A-Za-z0-9_]{3,80})"')

TASK_ZH = dict(BASE_TASK_ZH)
TASK_ZH.update({
    "TASK_WANDER_STANDARD": "闲逛", "TASK_LOOK_AT_ENTITY": "注视目标",
    "TASK_MOUNT_ANIMAL": "上马", "TASK_GO_TO_ENTITY": "走向目标",
    "TASK_COMBAT_PED": "与目标交战", "TASK_HOGTIE_PED": "绑人",
    "TASK_CUFF_PED": "铐住", "TASK_ARREST_PED": "逮捕",
    "TASK_PUT_PED_DIRECTLY_INTO_MELEE": "进入近战",
})

CLEAN = re.compile(r"~[A-Za-z_]+[^~]*~")


def clean(s):
    return re.sub(r"\s{2,}", " ", CLEAN.sub("", str(s))).strip()


def fn_index(lines):
    out = []
    for i, l in enumerate(lines):
        m = FN_DEF.match(l)
        if m:
            out.append((i, m.group(1)))
    return out


def fn_at(idx, line):
    cur = "?"
    for i, n in idx:
        if i <= line:
            cur = n
        else:
            break
    return cur


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true", help="跑全部 270 个任务")
    args = ap.parse_args()

    story = {r["id"]: r for r in csv.DictReader(open(os.path.join(W, "missions_story.csv"), encoding="utf-8-sig"))}
    # 优先用"补全 + 内容验证"过的映射（tools/recover_mission_scripts.py）
    sp = os.path.join(W, "mission_scripts_plus.json")
    scripts = json.load(open(sp, encoding="utf-8")) if os.path.exists(sp)         else json.load(open(os.path.join(W, "mission_scripts.json"), encoding="utf-8"))

    objs = defaultdict(list)
    for r in csv.DictReader(open(os.path.join(W, "mission_objectives.csv"), encoding="utf-8-sig")):
        objs[r["mission_id"]].append(r)

    glob = Yldb(os.path.join(LANG, "global.yldb"))
    banks = {}
    bank_files = set(os.listdir(LANG))

    want = [mid for mid, st in story.items()
            if args.all or st["category"] in RANDOM_CATS]

    out, rows = {}, []
    stat = Counter()

    for mid in want:
        st = story[mid]
        script = (scripts.get(mid) or {}).get("script") or ""
        if not script or not os.path.exists(os.path.join(SRC, script)):
            continue
        path = os.path.join(SRC, script)
        text = open(path, encoding="utf-8", errors="replace").read()
        lines = text.split("\n")
        idx = fn_index(lines)

        bank_name = (st.get("dialogue_bank") or "").strip()
        bank = None
        if bank_name and bank_name in bank_files:
            if bank_name not in banks:
                banks[bank_name] = Yldb(os.path.join(LANG, bank_name))
            bank = banks[bank_name]

        beats = []

        # ---------- 1) 对话组 ----------
        seen_group = set()
        if bank:
            for m in LIT.finditer(text):
                g = m.group(1)
                if g in seen_group:
                    continue
                # 不做前缀过滤：RDR2 的对话组命名并不统一
                #（RABI22→RABI22_* / RODDF1→RODDF_*、RODF1_* / RCKPT1→CKPT3_*、CKPTB_*），
                # 而字幕库本身是**该任务专属**的，直接拿脚本里的标签去查这个库即可。
                if not g.isupper() or "_" not in g:
                    continue
                got = []
                for i in range(1, 40):
                    v = bank.get(f"{g}_{i}")
                    if v is None:
                        if i == 1:
                            break
                        continue
                    t = clean(v)
                    if t:
                        got.append(t)
                if not got:
                    continue
                seen_group.add(g)
                line = text.count("\n", 0, m.start())
                beats.append({
                    "kind": "dialogue", "line": line + 1,
                    "fn": fn_at(idx, line), "group": g, "lines": got,
                })

        # ---------- 2) 生成 ----------
        for m in SPAWN.finditer(text):
            line = text.count("\n", 0, m.start())
            near = text[max(0, m.start() - 500):m.start() + 500]
            models = [x for x in LIT.findall(near)
                      if not x.startswith(("INPUT_", "COLOR_", "BLIP_", "WEAPON_", mid))
                      and not x.islower()][:3]
            beats.append({
                "kind": "spawn", "line": line + 1, "fn": fn_at(idx, line),
                "what": m.group(2).replace("CREATE_", "").lower(), "models": models,
            })

        # ---------- 3) 行为（同类合并，保留首个行号） ----------
        task_first = {}
        for m in TASK.finditer(text):
            t = m.group(1)
            if t in task_first or t in NOISE_TASKS:
                continue
            line = text.count("\n", 0, m.start())
            task_first[t] = {
                "kind": "task", "line": line + 1, "fn": fn_at(idx, line),
                "task": t, "zh": TASK_ZH.get(t, ""),
            }
        beats.extend(task_first.values())

        # ---------- 4) 演出 ----------
        for m in ANIM.finditer(text):
            line = text.count("\n", 0, m.start())
            # 场景名在变量里：往回找 StringCopy(&sVarN, "场景名")
            arg = text[m.end():m.end() + 90]
            name = ""
            vm = re.match(r"\s*&\(?([A-Za-z_][A-Za-z0-9_]*)", arg)
            if vm:
                var = re.escape(vm.group(1))
                back = text[max(0, m.start() - 4000):m.start()]
                sm = re.findall(rf'StringCopy\(&{var}\s*,\s*"([^"]+)"', back)
                if sm:
                    name = sm[-1]
            beats.append({"kind": "anim", "line": line + 1, "fn": fn_at(idx, line),
                          "what": name or "脚本动画场景"})

        beats.sort(key=lambda b: b["line"])

        # ---------- 5) 按函数分组 = 阶段 ----------
        beats = [b for b in beats
                 if b["kind"] != "task" or b.get("task") not in NOISE_TASKS]
        phases = []
        cur = None
        for b in beats:
            if cur is None or cur["fn"] != b["fn"]:
                cur = {"fn": b["fn"], "line": b["line"], "beats": []}
                phases.append(cur)
            cur["beats"].append(b)

        # ---------- 6) 目标 / 失败条件（真实文案） ----------
        objectives, fails = [], []
        for r in sorted(objs.get(mid, []), key=lambda x: int(x["seq"] or 0)):
            item = {"text": r["text"], "seq": r["seq"], "type": r["type"]}
            (fails if r["type"] == "fail" else objectives).append(item)

        # 丢掉空阶段
        phases = [p for p in phases if p["beats"]]

        # ---------- 7) 赏金金额（原文提取） ----------
        bounty = None
        mm = re.search(r"\$(\d+)", st.get("desc_zh") or "")
        if mm:
            bounty = int(mm.group(1))

        n_dlg = sum(len(b["lines"]) for b in beats if b["kind"] == "dialogue")
        n_grp = sum(1 for b in beats if b["kind"] == "dialogue")
        n_spawn = sum(1 for b in beats if b["kind"] == "spawn")
        n_task = sum(1 for b in beats if b["kind"] == "task")

        out[mid] = {
            "id": mid,
            "category": st["category"],
            "title_zh": st.get("title_zh") or "",
            "desc_zh": st.get("desc_zh") or "",
            "script": script,
            "bank": bank_name,
            "bounty_usd": bounty,
            "objectives": objectives,
            "fail_conditions": fails,
            "cast": [c for c in (st.get("cast") or "").split(";")
                     if c and not re.match(r"^(cs_|[a-z]|z_)", c)],
            "phases": phases,
            "stats": {
                "phases": len(phases),
                "dialogue_groups": n_grp,
                "dialogue_lines": n_dlg,
                "spawns": n_spawn,
                "distinct_tasks": n_task,
                "source_lines": len(lines),
            },
        }
        if n_grp:
            stat["with_dialogue"] += 1
        if n_spawn:
            stat["with_spawn"] += 1
        if objectives:
            stat["with_objectives"] += 1
        stat["total"] += 1

        rows.append({
            "id": mid, "category": st["category"],
            "title_zh": st.get("title_zh") or "",
            "script": script,
            "phases": len(phases), "dialogue_groups": n_grp, "dialogue_lines": n_dlg,
            "spawns": n_spawn, "tasks": n_task,
            "objectives": len(objectives), "fails": len(fails),
            "bounty_usd": bounty if bounty is not None else "",
        })

    rows.sort(key=lambda r: (-r["dialogue_lines"], r["id"]))
    os.makedirs(W, exist_ok=True)
    with open(os.path.join(W, "mission_flow.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    if rows:
        with open(os.path.join(W, "mission_flow.csv"), "w", encoding="utf-8-sig", newline="") as fh:
            wr = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            wr.writeheader()
            wr.writerows(rows)

    print(f"还原 {len(out)} 个任务 -> export/levels/world/mission_flow.json")
    print(f"  有真实台词: {stat['with_dialogue']}")
    print(f"  有生成记录: {stat['with_spawn']}")
    print(f"  有目标文案: {stat['with_objectives']}")
    print("\n台词量 Top 10:")
    for r in rows[:10]:
        print(f"  {r['id']:8s} {r['title_zh'][:14]:16s} 组{r['dialogue_groups']:3d} "
              f"句{r['dialogue_lines']:4d} 生成{r['spawns']:3d} 阶段{r['phases']:3d}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
