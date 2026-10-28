# -*- coding: utf-8 -*-
"""UI 页：纹理画廊 + 界面/控件/布局清单。

输入：
  export/levels/world/ui_textures.csv        （extract_ui_textures.py）
  raw/ui/list/{frontend,generic,minimap,widgets,screens}.txt  （rdr2rpf list 结果）
  raw/ui/layout/data/ui/**                   （HUD 布局 XML / 配色 / 字体表）
输出：
  export/ui/data.json
  export/ui/index.html
"""
import os
import csv
import re
import json

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "export/ui")
LISTS = os.path.join(ROOT, "raw/ui/list")
LAYOUT = os.path.join(ROOT, "raw/ui/layout")

# 界面/控件清单里常见前缀的中文（按需补，不硬套）
Z = {
    "pause": "暂停菜单", "sidemenus": "侧边菜单", "hud": "HUD",
    "shops": "商店", "player_menu": "玩家菜单", "mp": "线上",
    "log": "日志", "crafting": "制作", "quick_select": "快捷选择",
    "wheels": "轮盘", "weapon_wheels": "武器轮盘", "scoreboard": "记分板",
    "sticky_feeds": "滚动消息", "generic": "通用", "list_items": "列表项",
}


def parse_list(path, kind):
    rows = []
    if not os.path.exists(path):
        return rows
    for ln in open(path, encoding="utf-8", errors="replace"):
        m = re.match(r"\s+(\d+)\s+res=\d+\s+comp=\w+\s+(.+?)\s*$", ln)
        if not m:
            continue
        size, name = int(m.group(1)), m.group(2)
        ext = name.rsplit(".", 1)[-1].lower()
        rows.append(dict(kind=kind, name=name, base=os.path.splitext(os.path.basename(name))[0],
                         ext=ext, bytes=size,
                         path_parts=name.split("/")[:-1]))
    return rows


def main():
    tex = list(csv.DictReader(open(os.path.join(ROOT, "export/levels/world/ui_textures.csv"),
                                  encoding="utf-8-sig")))
    texrows = [dict(dict=t["dict"], dict_zh=t["dict_zh"], name=t["name"],
                    w=int(t["w"] or 0), h=int(t["h"] or 0), fmt=t["fmt"],
                    png=t["png"].replace("export/", "../", 1),
                    status=t["status"])
               for t in tex if t["status"] == "ok"]

    # 字典汇总
    dicts = {}
    for t in texrows:
        d = dicts.setdefault(t["dict"], dict(dict=t["dict"], zh=t["dict_zh"], n=0))
        d["n"] += 1
    dicts = sorted(dicts.values(), key=lambda x: -x["n"])

    screens = parse_list(os.path.join(LISTS, "screens.txt"), "界面 screen")
    widgets = parse_list(os.path.join(LISTS, "widgets.txt"), "控件 widget")
    movies = (parse_list(os.path.join(LISTS, "frontend.txt"), "Scaleform 影片")
              + parse_list(os.path.join(LISTS, "generic.txt"), "Scaleform 影片")
              + parse_list(os.path.join(LISTS, "minimap.txt"), "Scaleform 影片"))
    for r in screens:
        r["zh"] = " / ".join(Z.get(p, p) for p in r["path_parts"]) or "根目录"

    layouts = []
    lroot = os.path.join(LAYOUT, "data/ui")
    for dirpath, _dn, fns in os.walk(lroot):
        for f in fns:
            full = os.path.join(dirpath, f)
            rel = os.path.relpath(full, lroot).replace("\\", "/")
            layouts.append(dict(rel=rel, bytes=os.path.getsize(full),
                                ext=os.path.splitext(f)[1].lower()))

    data = dict(dicts=dicts, textures=texrows, screens=screens, widgets=widgets,
                movies=movies, layouts=sorted(layouts, key=lambda x: x["rel"]),
                stats=dict(tex=len(texrows), dicts=len(dicts),
                           screens=len(screens), widgets=len(widgets),
                           movies=len(movies), layouts=len(layouts)))
    os.makedirs(OUT, exist_ok=True)
    json.dump(data, open(os.path.join(OUT, "data.json"), "w", encoding="utf-8"),
              ensure_ascii=False)
    print(data["stats"])


if __name__ == "__main__":
    main()
