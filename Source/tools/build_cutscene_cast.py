# -*- coding: utf-8 -*-
"""从 181 个过场包里提取 clip 名中的角色 ID，构建「过场包 → 角色」和「任务 → 角色」映射。

输出：
  export/levels/world/cutscene_cast.csv     每个过场包的角色列表
  export/levels/world/mission_cast.csv      每个任务的角色列表（按 missions.meta）
  export/levels/world/actor_coverage.csv    每个角色出现在哪些包/任务
  export/levels/world/cast_stats.json
"""
import re, os, csv, json, collections
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W = lambda *p: os.path.join(ROOT, *p)

RX = re.compile(rb'(cs_[a-z0-9_]+?|player_(?:zero|three))_(?:face|dual)')


def load_actor_index():
    full = []
    for fn in ["work/npc/cs_prefixes.txt", "work/npc/cs_missing_prefixes.txt"]:
        for l in open(W(fn), encoding="utf-8"):
            l = l.strip()
            if l:
                full.append(l)
    base2full = collections.defaultdict(set)
    for f in full:
        base2full[f].add(f)
        base2full[re.sub(r"_(ms1|fs1)$", "", f)].add(f)
    base2full["player_zero"] = {"player_zero"}
    base2full["player_three"] = {"player_three"}
    return base2full


def main():
    base2full = load_actor_index()
    root_dir = W("work/story/cutscene_all/extracted")
    pkg_cast = {}
    for name in sorted(os.listdir(root_dir)):
        d = os.path.join(root_dir, name)
        if not os.path.isdir(d):
            continue
        actors = set()
        for r, _, files in os.walk(d):
            for fn in files:
                data = open(os.path.join(r, fn), "rb").read()
                for m in RX.finditer(data):
                    actors.add(m.group(1).decode("ascii"))
        pkg_cast[name.replace("cuts_", "")] = actors

    # 角色 base → 全名（多个候选时保留 base）
    ALIAS = {
        "cs_mrsadler": "cs_mrsadler_fs1",
        "cs_johnmarston": "player_three",
        "cs_abe": "cs_abe_ms1",
        "cs_hectorfellowes": "cs_hectorhollowes_ms1",
    }
    def resolve(a):
        if a in ALIAS:
            return ALIAS[a]
        cand = base2full.get(a)
        if cand and len(cand) == 1:
            return next(iter(cand))
        return a

    pkg_resolved = {p: sorted(resolve(a) for a in s) for p, s in pkg_cast.items()}

    # 任务
    root = ET.parse(W("work/meta/common/data/missions.meta")).getroot()
    missions = []
    for m in root.find("Missions"):
        missions.append({
            "mission_id": m.findtext("MissionId"),
            "category": m.findtext("Category"),
            "mission_type": m.findtext("MissionType"),
        })

    def match_pkgs(mid):
        key = (mid or "").lower()
        out = []
        for p in pkg_resolved:
            if key == p or key.startswith(p) or p.startswith(key):
                out.append(p)
        return out

    mission_rows = []
    for m in missions:
        ps = match_pkgs(m["mission_id"])
        cast = sorted(set(a for p in ps for a in pkg_resolved[p]))
        mission_rows.append({**m, "cutscene_pkgs": ";".join(ps),
                             "cast_count": len(cast), "cast": ";".join(cast)})

    with open(W("export/levels/world/mission_cast.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["mission_id", "category", "mission_type",
                                          "cutscene_pkgs", "cast_count", "cast"])
        w.writeheader(); w.writerows(mission_rows)

    # 包级
    prow = []
    for p in sorted(pkg_resolved):
        ms = [m["mission_id"] for m in missions if p in match_pkgs(m["mission_id"])]
        prow.append({"cutscene_pkg": p, "mission_ids": ";".join(ms),
                     "cast_count": len(pkg_resolved[p]), "cast": ";".join(pkg_resolved[p])})
    with open(W("export/levels/world/cutscene_cast.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["cutscene_pkg", "mission_ids", "cast_count", "cast"])
        w.writeheader(); w.writerows(prow)

    # 角色级
    roster = {r["id"]: r for r in csv.DictReader(open(W("export/levels/world/npc_roster.csv"), encoding="utf-8-sig"))}
    appear = collections.defaultdict(lambda: {"pkgs": set(), "missions": set(), "cats": set()})
    for m in mission_rows:
        for a in filter(None, m["cast"].split(";")):
            appear[a]["missions"].add(m["mission_id"])
            appear[a]["cats"].add(m["category"])
    for p, cast in pkg_resolved.items():
        for a in cast:
            appear[a]["pkgs"].add(p)

    arow = []
    for a, v in sorted(appear.items()):
        r = roster.get(a, {})
        arow.append({
            "actor_id": a, "name_zh": r.get("name_zh", ""), "faction": r.get("faction", ""),
            "in_roster": "Y" if a in roster else "N",
            "generic": "Y" if a.startswith(("cs_genstory", "cs_chainprisoner")) else "N",
            "pkg_count": len(v["pkgs"]), "mission_count": len(v["missions"]),
            "categories": ";".join(sorted(v["cats"])),
        })
    arow.sort(key=lambda r: (-r["mission_count"], r["actor_id"]))
    with open(W("export/levels/world/actor_coverage.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["actor_id", "name_zh", "faction", "in_roster",
                                          "generic", "pkg_count", "mission_count", "categories"])
        w.writeheader(); w.writerows(arow)

    # 统计
    main_cats = {"CHAPTER_1", "CHAPTER_2", "CHAPTER_3", "CHAPTER_4", "CHAPTER_5", "CHAPTER_6", "CHAPTER_7", "CHAPTER_8"}
    side_cats = {"RANDOM_CHARACTER", "RANDOM_STORY_CHARACTER", "BOUNTY_HUNTING"}
    stats = {
        "packages": len(pkg_resolved),
        "packages_with_cast": sum(1 for v in pkg_resolved.values() if v),
        "actors_total": len(appear),
        "actors_in_roster": sum(1 for r in arow if r["in_roster"] == "Y"),
        "actors_not_in_roster": sum(1 for r in arow if r["in_roster"] == "N"),
        "main_missions": sum(1 for m in mission_rows if m["category"] in main_cats),
        "main_with_cast": sum(1 for m in mission_rows if m["category"] in main_cats and m["cast_count"] > 0),
        "side_missions": sum(1 for m in mission_rows if m["category"] in side_cats),
        "side_with_cast": sum(1 for m in mission_rows if m["category"] in side_cats and m["cast_count"] > 0),
        "missions_without_pkg": sum(1 for m in mission_rows if not m["cutscene_pkgs"]),
    }
    json.dump(stats, open(W("export/levels/world/cast_stats.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(json.dumps(stats, ensure_ascii=False, indent=1))
    print("\nTop actors:")
    for r in arow[:20]:
        print(f'  {r["mission_count"]:>3} missions  {r["actor_id"]:<28} {r["name_zh"]:<10} {r["faction"]}')
    print("\nNot in roster (top 30):")
    for r in [x for x in arow if x["in_roster"] == "N"][:30]:
        print(f'  {r["mission_count"]:>3} missions  {r["actor_id"]:<28} {r["categories"]}')


if __name__ == "__main__":
    main()
