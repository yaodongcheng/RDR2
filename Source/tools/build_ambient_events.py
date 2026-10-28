#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
路上随机遭遇（`beat_*`）结构化。

背景
----
RDR2 的"随机"分两层：
  · 任务层   —— `rcm_*` / 章节脚本，已有 mission_* 全套数据；
  · 遭遇层   —— `beat_*`（119 个），玩家在野外走着触发的事件（抢劫/抛锚马车/伏击/绞刑…），
                此前**完全没结构化**（`export/story/beats_index.csv` 只覆盖任务脚本，不含 beat_*）。

本脚本把 `raw/script_full/1491.50/beat_*.c` 变成一张可消费的事件表：
  事件 id / 生成什么（模型）/ 用了哪些行为 / 有没有目标与目标文案 / 演出量 / 场地坐标。

输出
----
export/levels/world/ambient_events.json
export/levels/world/ambient_events.csv

用法
----
uv run python tools/build_ambient_events.py
"""
import csv
import json
import os
import re
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "raw", "script_full", "1491.50")
W = os.path.join(ROOT, "export", "levels", "world")
sys.path.insert(0, os.path.join(ROOT, "tools"))

SPAWN_RX = re.compile(r"(PED|VEHICLE|OBJECT)::(CREATE_[A-Z_0-9]+)\s*\(")
TASK_RX = re.compile(r"TASK::(TASK_[A-Z_0-9]+)\s*\(")
UILOG_RX = re.compile(r"UILOG::(_UILOG_[A-Z_0-9]+)\s*\(")
ANIM_RX = re.compile(r"ANIMSCENE::([A-Z_0-9]+)\s*\(")
KEY_RX = re.compile(r'"([A-Z][A-Z0-9_]{3,40})"')
# 场景点 / 战斗 / 载具 这类"事件性质"的强信号
SCENARIO_RX = re.compile(r'"(PROP_[A-Z0-9_]+|P_[A-Z0-9_]+|WORLD_HUMAN_[A-Z0-9_]+)"')

# 复用任务调度器那份中文行为词表（64 条），再补若干
from build_mission_schedule import TASK_ZH as _BASE_TASK_ZH  # noqa: E402

TASK_ZH = dict(_BASE_TASK_ZH)
TASK_ZH.update({
    "TASK_WANDER_STANDARD": "闲逛",
    "TASK_LOOK_AT_ENTITY": "注视目标",
    "TASK_MOUNT_ANIMAL": "上马",
    "TASK_DISMOUNT": "下马",
    "TASK_VEHICLE_DRIVE_TO_COORD": "开车前往",
    "TASK_VEHICLE_DRIVE_WANDER": "开车游走",
    "TASK_GO_TO_COORD_ANY_MEANS": "赶往坐标",
    "TASK_ENTER_VEHICLE": "上车",
    "TASK_LEAVE_VEHICLE": "下车",
    "TASK_STAND_GUARD": "站岗",
    "TASK_START_SCENARIO_IN_PLACE": "原地场景交互",
    "TASK_FOLLOW_TO_OFFSET_OF_ENTITY": "跟随目标",
    "TASK_CHAT_TO_PED": "与人交谈",
    "TASK_CUFF_PED": "铐住",
    "TASK_ARREST_PED": "逮捕",
    "TASK_HOGTIE_PED": "绑人",
    "TASK_PUT_PED_DIRECTLY_INTO_MELEE": "进入近战",
    "TASK_COMBAT_PED": "与目标交战",
    "TASK_GO_TO_ENTITY": "走向实体",
})

TASK_ZH_LEGACY = {
    "TASK_SMART_FLEE_PED": "逃离",
    "TASK_AGGRESSIVE": "攻击",
    "TASK_GOTO_ENTITY": "走向目标",
    "TASK_FOLLOW_NAV_MESH_TO_COORD": "走位",
    "TASK_AIM_GUN_AT_ENTITY": "举枪瞄准",
    "TASK_SHOOT_AT_COORD": "射击",
    "TASK_ENTER_COVER": "进掩体",
    "TASK_USE_SCENARIO_POINT": "场景点交互",
    "TASK_PLAY_ANIM": "播动画",
    "TASK_TURN_PED_TO_FACE_ENTITY": "转身面对",
    "TASK_WARP_PED_INTO_VEHICLE": "塞进载具",
    "TASK_VEHICLE_PARK": "停车",
    "TASK_HANDS_UP": "举手",
    "TASK_KNOCKED_OUT": "被打晕",
    "TASK_CARRIABLE": "可搬运",
}


def main():
    files = sorted(f for f in os.listdir(SRC) if f.startswith("beat_") and f.endswith(".c"))
    print(f"beat_* 脚本: {len(files)}")

    # 复用坐标提取器产出的结果
    coord = {}
    cp = os.path.join(W, "mission_coords.csv")
    if os.path.exists(cp):
        with open(cp, encoding="utf-8-sig") as fh:
            for r in csv.DictReader(fh):
                coord[r["script"]] = r

    events = {}
    rows = []
    for fn in files:
        s = open(os.path.join(SRC, fn), encoding="utf-8", errors="replace").read()
        eid = fn[:-2]

        spawns = []
        for m in SPAWN_RX.finditer(s):
            line = s.count("\n", 0, m.start())
            kind = m.group(2).replace("CREATE_", "").lower()
            near = s[max(0, m.start() - 400):m.start() + 400]
            models = [x for x in KEY_RX.findall(near)
                      if not x.startswith(("INPUT_", "WEAPON_", "COLOR_", "BLIP_"))][:3]
            spawns.append({"line": line + 1, "kind": kind, "models": models})

        counts = Counter(x["kind"] for x in spawns)
        models = sorted({m for x in spawns for m in x["models"]})

        tasks = Counter(m.group(1) for m in TASK_RX.finditer(s))
        anims = len(ANIM_RX.findall(s))
        uilog = len(UILOG_RX.findall(s))
        scen = len(SCENARIO_RX.findall(s))

        # 场地坐标（有就用）
        loc = None
        cr = coord.get(fn)
        if cr and cr.get("has_own_coords") == "True":
            loc = {
                "world": [float(cr["primary_x"]), float(cr["primary_y"]), float(cr["primary_z"])],
                "spread_m": [float(cr["spread_x_m"]), float(cr["spread_y_m"])],
                "nearest_settlement": cr["nearest_settlement"],
                "nearest_dist_m": float(cr["nearest_dist_m"]),
            }

        # 粗分类：只按「行为调用 + 生成物」的强信号判，不做全文子串匹配
        tags = []
        if (tasks.get("TASK_SMART_FLEE_PED") or tasks.get("TASK_AGGRESSIVE")
                or tasks.get("TASK_AIM_GUN_AT_ENTITY") or tasks.get("TASK_SHOOT_AT_COORD")):
            tags.append("敌对")
        if tasks.get("TASK_HANDS_UP"):
            tags.append("投降/劫持")
        if tasks.get("TASK_KNOCKED_OUT"):
            tags.append("击倒")
        if counts.get("vehicle"):
            tags.append("载具")
        blob = " ".join(models).upper()
        if any(k in blob for k in ("CORPSE", "DEAD", "BODY")):
            tags.append("尸体")
        if any(k in blob for k in ("WAGON", "CART", "COACH", "STAGECOACH", "BUGGY")):
            tags.append("马车")
        if any(k in blob for k in ("ANIMAL", "HORSE", "WOLF", "BEAR", "DEER", "DOG")):
            tags.append("动物")
        if not tags:
            tags.append("其它")

        # 复杂度评分（给搬运排序用）：行为数 + 生成数 + 演出量
        complexity = (sum(tasks.values()) / 20.0) + len(spawns) + (anims / 40.0)

        ev = {
            "id": eid,
            "script": fn,
            "size_kb": round(os.path.getsize(os.path.join(SRC, fn)) / 1024, 1),
            "spawn": {"count": len(spawns), "counts": dict(counts), "models": models[:20]},
            "tasks": {"total": sum(tasks.values()),
                      "top": [{"task": k, "zh": TASK_ZH.get(k, k), "n": v}
                              for k, v in tasks.most_common(6)]},
            "anim_scene_calls": anims,
            "uilog_calls": uilog,
            "scenario_tokens": scen,
            "tags": tags,
            "complexity": round(complexity, 1),
            "has_objectives": uilog > 0,
            "location": loc,
        }
        events[eid] = ev
        rows.append({
            "id": eid,
            "tags": "/".join(tags),
            "spawn_ped": counts.get("ped", 0),
            "spawn_object": counts.get("object", 0),
            "spawn_vehicle": counts.get("vehicle", 0),
            "models": len(models),
            "tasks": sum(tasks.values()),
            "complexity": round(complexity, 1),
            "top_task": (tasks.most_common(1)[0][0] if tasks else ""),
            "anim": anims,
            "has_objectives": uilog > 0,
            "has_coords": bool(loc),
            "nearest": (loc or {}).get("nearest_settlement", ""),
        })

    rows.sort(key=lambda r: -r["complexity"])
    os.makedirs(W, exist_ok=True)
    with open(os.path.join(W, "ambient_events.json"), "w", encoding="utf-8") as fh:
        json.dump(events, fh, ensure_ascii=False, indent=1)
    with open(os.path.join(W, "ambient_events.csv"), "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    tagc = Counter(t for e in events.values() for t in e["tags"])
    print(f"产出 {len(events)} 个遭遇 -> export/levels/world/ambient_events.json")
    print(f"  有目标提示 {sum(1 for e in events.values() if e['has_objectives'])} 个")
    print(f"  有场地坐标 {sum(1 for e in events.values() if e['location'])} 个")
    print(f"  会出人（ped）{sum(1 for e in events.values() if e['spawn']['counts'].get('ped'))} 个")
    print("\n标签分布:")
    for t, n in tagc.most_common():
        print(f"  {n:4d}  {t}")
    print("\n=== 最重的 10 个遭遇（生成 + 行为最多）===")
    for r in rows[:10]:
        print(f"  {r['id']:26s} ped={r['spawn_ped']:2d} veh={r['spawn_vehicle']:2d} "
              f"obj={r['spawn_object']:2d} task={r['tasks']:3d} anim={r['anim']:3d} "
              f"cx={r['complexity']:5.1f} {r['tags']:14s} {r['nearest']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
