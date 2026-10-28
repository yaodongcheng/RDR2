# -*- coding: utf-8 -*-
"""兵种（gameplay ped archetype）覆盖审计 + 页面数据。

## 结论先说（会被写进页面上）
- **兵种清单是全的**：`packs/base/data/metapeds/metapeds.rpf` 里 1 086 个 `*.ymt`，
  一个兵种一个文件，文件名就是 archetype 名（`s_m_m_pinlaw_01` / `a_m_m_*` / `g_m_m_*` …）。
- **模型不是全的**：只有 **过场角色**（`cs_*`，整只合并模型）导出了 282 个 GLB；
  真正的 gameplay 兵种是**部件池拼装**出来的——穿哪几件写在 `CPedModelInfo.PedComponentSetName`
  （`packs/base/data/metapeds.ymt`，PSIN）里，指向的部件集还没解出，
  所以 `s_m_m_pinlaw_01`（平克顿侦探）这类**没有可直接导出的整套模型**。
- `s_m_m_pinlaw_01` 的**骨骼偏移/表情/变体数据**是有的（18 KB ymt，55 根骨 + variations），
  缺的只是"穿哪几件衣服"。

输入：raw/npc/list_metapeds.txt（rdr2rpf list 结果）、deliverable/handoff/ped_archetypes.csv、
      export/npc/cs/*（已导出的过场 GLB）
输出：export/levels/world/ped_coverage.csv、export/units/data.json
"""
import os
import re
import csv
import json

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIST = os.path.join(ROOT, "raw/npc/list_metapeds.txt")
ARCH = os.path.join(ROOT, "deliverable/handoff/ped_archetypes.csv")
CSDIR = os.path.join(ROOT, "export/npc/cs")
OUT = os.path.join(ROOT, "export/units")

# 重点关注的兵种：用户明确提到的平克顿，加上几类常见"兵种"
FOCUS = {
    "s_m_m_pinlaw_01": dict(zh="平克顿侦探（Pinkerton 探员）",
                            note="用户点名要看的兵种；archetype 与骨骼数据都在，缺「穿哪几件」的部件集"),
    "cs_pinkertongoon": dict(zh="平克顿打手（过场）",
                             note="过场版：模型只有上半身（头 + 马甲 + 手），不是完整人物"),
    "s_m_m_ambientlawrural_01": dict(zh="乡村执法（治安官/副警长）", note=""),
    "s_m_m_dispatchlawrural_01": dict(zh="派警执法", note=""),
    "g_m_m_unicriminals_01": dict(zh="帮派罪犯（通用）", note=""),
    "a_m_m_unicorpse_01": dict(zh="通用尸体", note=""),
}


def parse_metapeds():
    rows = []
    for ln in open(LIST, encoding="utf-8", errors="replace"):
        m = re.match(r"\s+(\d+)\s+res=\d+\s+comp=\w+\s+(\S+\.ymt)\s*$", ln)
        if not m:
            continue
        rows.append((m.group(2)[:-4], int(m.group(1))))
    return rows


def main():
    arch = {r["name"].lower(): r for r in csv.DictReader(open(ARCH, encoding="utf-8-sig"))}
    cs_dirs = set(os.listdir(CSDIR)) if os.path.isdir(CSDIR) else set()

    rows = []
    for name, ymt_bytes in parse_metapeds():
        a = arch.get(name.lower(), {})
        # 过场版 GLB：cs_pinkertongoon -> cs_pinkertongoon_ms1
        cs = ""
        cands = [name, name + "_ms1"] + [d for d in cs_dirs if d.startswith(name + "_")]
        for cand in cands:
            if cand in cs_dirs:
                d = os.path.join(CSDIR, cand)
                g = [f for f in os.listdir(d) if f.endswith(".glb")]
                if g:
                    cs = f"../npc/cs/{cand}/{g[0]}"
                    break
        focus = FOCUS.get(name, {})
        kind = ("过场角色" if name.lower().startswith("cs_") else
                "动物" if name.lower().startswith("a_c_") else
                "兵种/人物")
        rows.append(dict(
            name=name,
            zh=focus.get("zh") or a.get("zh") or "",
            category=a.get("category") or ("过场角色" if kind == "过场角色" else
                                           "动物" if kind == "动物" else "兵种"),
            kind=kind,
            ymt_kb=round(ymt_bytes / 1024, 1),
            has_cutscene_glb="Y" if cs else "",
            glb=cs,
            has_gameplay_model="N",     # 配方未解 → 一律 N（不糊弄）
            focus="Y" if focus else "",
            note=focus.get("note", ""),
        ))

    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(ROOT, "export/levels/world/ped_coverage.csv"), "w",
              newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    from collections import Counter
    stat = Counter(r["kind"] for r in rows)
    data = dict(
        stats=dict(total=len(rows), cs=sum(1 for r in rows if r["has_cutscene_glb"]),
                   gameplay=0, animal=stat.get("动物", 0),
                   cs_role=stat.get("过场角色", 0), unit=stat.get("兵种/人物", 0)),
        rows=rows,
        renders=dict(
            pinkerton_full=[f"../npc/verify/pinkfull_{v}.png"
                            for v in ("front", "q34", "side")],
            pinkerton_full_glb="../npc/units/cs_pinkertongoon_full/cs_pinkertongoon_full.glb",
            pinkerton_cutscene=[f"../npc/verify/pinkerton_{v}.png"
                                for v in ("front", "q34", "side")],
            pool_sample=[f"../npc/verify/pool_sample_{v}.png"
                         for v in ("front", "q34")],
            pool_sample_glb="../npc/units/pool_sample_suit_male/pool_sample_suit_male.glb",
        ),
    )
    json.dump(data, open(os.path.join(OUT, "data.json"), "w", encoding="utf-8"),
              ensure_ascii=False)
    print(data["stats"])


if __name__ == "__main__":
    main()
