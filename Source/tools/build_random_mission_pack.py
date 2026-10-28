#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
把 RDR2 的「随机任务 / 陌生人任务 / 赏金 / 物品请求」打包成骑砍2 可直接消费的数据。

输入
----
export/levels/world/missions_story.csv     270 个任务的中文名/描述/出场角色/对白量
export/levels/world/mission_objectives.csv 目标与失败条件（中文）
export/levels/world/mission_dialogues.json 对白（分步骤）
export/levels/world/mission_schedule.json  生成表（spawn 模型名 / 任务指令统计）
export/levels/world/mission_coords.csv     场地坐标（tools/extract_mission_coords.py 产出）
export/world/bannerlord/camp_scenes.json   野外网格 + 据点锚定场景（坐标换算权威参数）
deliverable/handoff/settlements_world_v2.csv

输出
----
export/world/bannerlord/random_missions.json  每任务一条，含：
    id / category / 中文标题描述 / 目标 / 对白量 / 出场角色
    location: { world, campaign_uv, tile_scene, scene_local, nearest, source }
    port: { tier, template_only, blockers[] }
export/world/bannerlord/random_missions.csv   同上拍平，便于人读
export/world/bannerlord/random_missions_index.json  分类计数 + 分级计数

用法
----
uv run python tools/build_random_mission_pack.py
"""
import csv
import json
import math
import os
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W = os.path.join(ROOT, "export", "levels", "world")
BL = os.path.join(ROOT, "export", "world", "bannerlord")

RANDOM_CATS = ["RANDOM_CHARACTER", "RANDOM_STORY_CHARACTER", "BOUNTY_HUNTING",
               "ITEM_REQUEST", "ENDLESS_SUMMER"]

# 搬运难度分级：T1 最轻 → T4 最重
TIER = {
    "ITEM_REQUEST": (1, "物品请求：只要『谁要什么 / 交付给谁 / 回报』三段，骑砍2 用对话+物品即可闭合"),
    "BOUNTY_HUNTING": (2, "赏金：骑砍2 原生有一模一样的『通缉—追捕—交人』骨架，只换皮"),
    "RANDOM_CHARACTER": (3, "陌生人小剧本：一个场景 1~3 步，需要场景 + 少量演出"),
    "ENDLESS_SUMMER": (3, "尾声随机任务：同陌生人，但绑主线角色"),
    "RANDOM_STORY_CHARACTER": (4, "剧情型随机任务：多幕演出 + 过场，成本最高，建议最后做"),
}


def load_csv(path, enc="utf-8-sig"):
    with open(path, encoding=enc) as fh:
        return list(csv.DictReader(fh))


def load_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def main():
    scenes = load_json(os.path.join(BL, "camp_scenes.json"))
    camp = scenes["campaign"]
    M = camp["m_per_unit"]
    OX, OY = camp["origin_world"]
    GX, GY = scenes["grid_origin"]
    SW = scenes["scene_size_m"]
    NX, NY = scenes["grid"]
    anchors = {a["code"]: a for a in scenes.get("anchors", [])}

    story = {r["id"]: r for r in load_csv(os.path.join(W, "missions_story.csv"))}
    objs = defaultdict(list)
    for r in load_csv(os.path.join(W, "mission_objectives.csv")):
        objs[r["mission_id"]].append({"kind": r["kind"], "type": r["type"], "seq": r["seq"], "text": r["text"]})
    dlg = load_json(os.path.join(W, "mission_dialogues.json"))
    sched = load_json(os.path.join(W, "mission_schedule.json"))
    coords = {r["mission_id"]: r for r in load_csv(os.path.join(W, "mission_coords.csv")) if r["mission_id"]}
    settlements = load_csv(os.path.join(ROOT, "deliverable", "handoff", "settlements_world_v2.csv"))

    def world_to_campaign(x, y):
        return round((x - OX) / M, 2), round((OY - y) / M, 2)

    def resolve_tile(x, y):
        i = max(0, min(NX - 1, int(math.floor((x - GX) / SW))))
        j = max(0, min(NY - 1, int(math.floor((GY - y) / SW))))
        cx = GX + (i + 0.5) * SW
        cy = GY - (j + 0.5) * SW
        return f"wild{int(SW)}_{i:02d}_{j:02d}", round(x - cx, 1), round(y - cy, 1), [i, j]

    def anchor_hit(x, y):
        for code, a in anchors.items():
            b = a["bbox"]
            if b[0] <= x <= b[2] and b[1] <= y <= b[3]:
                return a
        return None

    def nearest_settlement(x, y):
        best, bd = None, 1e18
        for s in settlements:
            if not s.get("world_x"):
                continue
            d = math.hypot(x - float(s["world_x"]), y - float(s["world_y"]))
            if d < bd:
                best, bd = s, d
        return best, bd

    out, rows = {}, []
    tier_count = Counter()
    cat_count = Counter()

    for mid, st in story.items():
        cat = st["category"]
        if cat not in RANDOM_CATS:
            continue
        tier, tier_note = TIER[cat]
        cat_count[cat] += 1
        tier_count[tier] += 1

        objectives = objs.get(mid, [])
        d = dlg.get(mid) or {}
        steps = d.get("steps") or {}
        n_dlg_steps = len(steps)
        n_lines = 0
        for arr in steps.values():
            for item in arr:
                n_lines += len(item.get("lines") or [])
        n_lines += sum(len(x.get("lines") or []) for x in (d.get("unassigned") or []))

        sc = sched.get(mid) or {}
        spawns = sc.get("spawns") or []
        models = sorted({m for s in spawns for m in (s.get("models") or [])})

        # ---- 标题/描述兜底 ----
        # 8 个任务的 label 不在已解包的语言库里（RBT03/12/21、REHEC1/2 等），
        # 直接显示 ID 很难看，这里给一个诚实的中文兜底名，并在 port.blockers 里标注。
        title = (st["title_zh"] or "").strip()
        desc = (st["desc_zh"] or "").strip()
        name_fallback = False
        if len(title) < 2:
            name_fallback = True
            base = "无名通缉犯" if cat == "BOUNTY_HUNTING" else "无名旅人"
            title = f"{base}（{mid}）"
        if not desc:
            desc = ("布告上只有一张潦草的画像和一个价码，名字被雨水泡花了。"
                    if cat == "BOUNTY_HUNTING"
                    else "这个人身上有故事，但你还不知道从哪问起。")
            name_fallback = True

        # ---- 落位 ----
        loc = None
        cr = coords.get(mid)
        blockers = []
        if cr and cr.get("has_own_coords") == "True":
            x, y = float(cr["primary_x"]), float(cr["primary_y"])
            u, v = world_to_campaign(x, y)
            a = anchor_hit(x, y)
            if a:
                loc = {"world": [x, y, float(cr["primary_z"])], "campaign_uv": [u, v],
                       "site_scene": a["id"], "site_zh": a["zh"], "kind": "settlement_anchor"}
            else:
                sid, sx, sy, ij = resolve_tile(x, y)
                loc = {"world": [x, y, float(cr["primary_z"])], "campaign_uv": [u, v],
                       "tile_scene": sid, "scene_local": [sx, sy], "tile_ij": ij,
                       "kind": "wilderness_tile"}
            loc["source"] = "script_const"
            loc["nearest_settlement"] = {"code": cr["nearest_code"], "zh": cr["nearest_settlement"],
                                         "dist_m": float(cr["nearest_dist_m"])}
            loc["own_point_count"] = int(cr["n_own_points"])
        else:
            # 模板化：脚本里没有专属坐标 —— 用据点代锚点，标明需要人工/数据表落位
            ns, nd = nearest_settlement(0, 0)  # 占位，下面按 category 处理
            blockers.append("坐标：脚本为模板化，场地由运行时数据表选点，需在骑砍2 侧按据点二次分配")
            loc = {"world": None, "campaign_uv": None, "kind": "unplaced",
                   "source": "template", "note": "按 category 在骑砍2 侧选点（见方案文档 §4）"}

        # 章节/前置
        ent = {
            "id": mid,
            "category": cat,
            "title_zh": title,
            "desc_zh": desc,
            "cast_count": int(st["cast_count"] or 0),
            "cast": [c for c in (st["cast"] or "").split(";") if c][:12],
            "objectives": objectives,
            "dialogue": {"lines": n_lines or int(st["dialogue_lines"] or 0),
                         "steps_with_dialogue": n_dlg_steps,
                         "bank": st["dialogue_bank"]},
            "beats": {"cutscene_clips": int(st["cutscene_clips"] or 0)},
            "spawn": {"count": len(spawns), "models": models[:24],
                      "counts": sc.get("spawn_counts") or {},
                      "task_top": list((sc.get("task_counts") or {}).items())[:6]},
            "location": loc,
            "port": {"tier": tier, "tier_note": tier_note,
                     "template_only": not (cr and cr.get("has_own_coords") == "True"),
                     "name_fallback": name_fallback,
                     "blockers": blockers + (["文案：原 label 未在已解包语言库中，标题/描述为兜底文本"]
                                             if name_fallback else [])},
        }
        out[mid] = ent
        rows.append({
            "id": mid, "category": cat, "tier": tier,
            "title_zh": st["title_zh"],
            "objectives": len(objectives),
            "dialogue_lines": ent["dialogue"]["lines"],
            "spawn_models": len(models),
            "cast": ent["cast_count"],
            "loc_kind": loc["kind"],
            "campaign_u": (loc.get("campaign_uv") or ["", ""])[0],
            "campaign_v": (loc.get("campaign_uv") or ["", ""])[1],
            "scene": loc.get("tile_scene") or loc.get("site_scene") or "",
            "nearest": (loc.get("nearest_settlement") or {}).get("zh", ""),
            "template_only": ent["port"]["template_only"],
        })

    rows.sort(key=lambda r: (r["tier"], r["category"], r["id"]))
    os.makedirs(BL, exist_ok=True)
    with open(os.path.join(BL, "random_missions.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    with open(os.path.join(BL, "random_missions.csv"), "w", encoding="utf-8-sig", newline="") as fh:
        wr = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        wr.writeheader()
        wr.writerows(rows)

    idx = {
        "total": len(out),
        "by_category": dict(cat_count),
        "by_tier": {str(k): v for k, v in sorted(tier_count.items())},
        "with_own_coords": sum(1 for e in out.values() if not e["port"]["template_only"]),
        "tier_meaning": {str(k): v[1] for k, v in TIER.items()},
        "coord_source": "tools/extract_mission_coords.py（脚本常量，剔除跨脚本共享锚点）",
        "campaign_formula": camp["desc"],
        "note": "campaign_uv 由 export/world/bannerlord/camp_scenes.json 的 campaign 参数换算；"
                "不要用 Rdr2CampBehavior.cs 里的 ORIGIN_X/ORIGIN_Y_NORTH（与数据差 852 m）",
    }
    with open(os.path.join(BL, "random_missions_index.json"), "w", encoding="utf-8") as fh:
        json.dump(idx, fh, ensure_ascii=False, indent=1)

    print(f"打包 {len(out)} 个随机/支线任务 -> export/world/bannerlord/random_missions.json")
    print("\n按 category:")
    for c, n in cat_count.most_common():
        print(f"  {n:4d}  {c:24s} T{TIER[c][0]}")
    print("\n按难度档:")
    for t, n in sorted(tier_count.items()):
        print(f"  T{t}  {n:4d}  {TIER[[k for k,v in TIER.items() if v[0]==t][0]][1][:52]}")
    print(f"\n有脚本专属坐标: {idx['with_own_coords']} / {len(out)}")
    print("\n=== T1/T2 首批候选（最省力）===")
    for r in rows:
        if r["tier"] <= 2:
            print(f"  T{r['tier']} {r['id']:7s} {r['title_zh'][:24]:26s} 目标{r['objectives']:>2d} "
                  f"对白{r['dialogue_lines']:>4d} 生成{r['spawn_models']:>2d} {r['loc_kind']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
