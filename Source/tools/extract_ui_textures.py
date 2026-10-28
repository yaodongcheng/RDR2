# -*- coding: utf-8 -*-
"""游戏 UI 资源导出：`textures/ui_textures.rpf`（16 个 .ytd / 1 848 张纹理）→ PNG + 清单 + 画廊。

## 覆盖了什么
`ui_textures.rpf` 是 RDR2 唯一一个 UI 纹理字典包，16 个 .ytd 各自是一类界面：

| .ytd | 内容 |
|---|---|
| `blips` | **地图/雷达图标**（NPC、商店、任务、动物…321 张） |
| `inventory_items` | **背包/商器物图标**（803 张） |
| `satchel_textures` | 背包界面（326 张） |
| `menu_textures` | **菜单九宫格/滚动条/按钮底**（63 张） |
| `multiwheel_weapons` | **武器轮盘图标**（64 张） |
| `swatches_gunsmith` | 枪匠木料/金属配色票（107 张） |
| `shaving_menu` | 理发界面（50 张） |
| `generic_textures` | 通用底图/网格（41 张） |
| `itemtype_textures` | 物品类型徽标（28 张） |
| `minigames_hud` | 小游戏 HUD（20 张） |
| `honor_display` / `scoreboard` / `scoretimer` / `feeds` / `document_textures` / `credits` | 荣誉条 / 记分板 / 计时 / 消息条 / 文档（通缉令等）/ 片尾 |

## 两种 .ytd 布局
内联条目（步长 0xB0）与**指针数组**两种，见 `rdr2_ytd.Ytd.textures_any()`。
后者正是 `blips / menu_textures / inventory_items / satchel_textures / honor_display /
shaving_menu / swatches_gunsmith` 这 7 个字典（此前一律解出 0 张）的原因。

用法：
  uv run python tools/extract_ui_textures.py [--max 512]
产出：
  export/ui/textures/<字典>/<纹理名>.png
  export/levels/world/ui_textures.csv
"""
import os
import csv
import sys
import argparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import rdr2_ytd as Y            # noqa: E402
from PIL import Image           # noqa: E402
import ytd_to_png as TP         # noqa: E402

SRC = os.path.join(ROOT, "raw/ui/out")
# 补充：scaleform 包里自带的 .ytd（HUD 准星 / 小地图 / 暂停菜单底 / 全屏警告 / 按键提示…）
EXTRA_DIRS = [
    ("sf_generic", os.path.join(ROOT, "raw/ui/sf_out/scaleform_generic")),
    ("sf_minimap", os.path.join(ROOT, "raw/ui/sf_out/scaleform_minimap")),
    ("sf_frontend", os.path.join(ROOT, "raw/ui/sf_out/scaleform_frontend")),
]
DST = os.path.join(ROOT, "export/ui/textures")
CSV_OUT = os.path.join(ROOT, "export/levels/world/ui_textures.csv")

ZH = {
    "sf_generic_hud_reticle": "HUD 准星（3D 命中）",
    "sf_generic_hudmanager": "HUD 管理器图集",
    "sf_generic_pausemenu_assets": "暂停菜单图集",
    "sf_minimap_minimap_v2": "小地图图集 v2",
    "sf_minimap_button_prompts": "按键提示图集",
    "sf_minimap_clik_shared_components": "通用组件图集",
    "sf_minimap_fullscreenalert": "全屏警告",
    "sf_minimap_gun_barrel": "枪管（HUD）",
    "blips": "地图/雷达图标",
    "inventory_items": "背包与商器物图标",
    "satchel_textures": "背包界面",
    "menu_textures": "菜单底图/滚动条",
    "multiwheel_weapons": "武器轮盘图标",
    "swatches_gunsmith": "枪匠配色票",
    "shaving_menu": "理发界面",
    "generic_textures": "通用底图/网格",
    "itemtype_textures": "物品类型徽标",
    "minigames_hud": "小游戏 HUD",
    "honor_display": "荣誉/声望条",
    "scoreboard_textures": "记分板",
    "scoretimer_textures": "计时器",
    "feeds": "消息条",
    "document_textures": "文档（通缉令等）",
    "credits": "片尾",
}


def safe(s):
    return ''.join(c if c.isalnum() or c in '_-.' else '_' for c in s)[:90]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max", type=int, default=512, help="超过该边长的纹理等比缩小")
    a = ap.parse_args()

    jobs = [(ytd[:-4], os.path.join(SRC, ytd))
            for ytd in sorted(os.listdir(SRC)) if ytd.endswith(".ytd")]
    for tag, d in EXTRA_DIRS:
        if not os.path.isdir(d):
            continue
        for f in sorted(os.listdir(d)):
            if f.endswith(".ytd"):
                jobs.append((f"{tag}_{f[:-4]}", os.path.join(d, f)))

    rows = []
    for dic, src in jobs:
        y = Y.Ytd(open(src, 'rb').read())
        texs = y.textures_any()
        outdir = os.path.join(DST, dic)
        os.makedirs(outdir, exist_ok=True)
        seen = {}
        ok = 0
        for t in texs:
            nm = safe(t['name'] or f"tex{t['idx']:03d}")
            if nm in seen:
                seen[nm] += 1
                nm = f"{nm}_{seen[nm]}"
            else:
                seen[nm] = 0
            blob = y.gfx[t['gfx_off']:]
            im, fmt_name = TP.decode_one(blob, t['w'], t['h'], t['fmt'])
            status = "ok"
            if im is None:
                status = f"decode_fail:{fmt_name}"
            else:
                try:
                    if max(im.size) > a.max:
                        r = a.max / max(im.size)
                        im = im.resize((max(1, int(im.width * r)), max(1, int(im.height * r))),
                                       Image.LANCZOS)
                except Exception:
                    pass
                im.save(os.path.join(outdir, nm + ".png"))
                ok += 1
            rows.append(dict(dict=dic, dict_zh=ZH.get(dic, dic), name=t['name'],
                             w=t['w'], h=t['h'], fmt=f"0x{(t['fmt'] >> 24) & 0xFF:02X}",
                             fmt_name=fmt_name, png=f"export/ui/textures/{dic}/{nm}.png",
                             status=status))
        print(f"{dic:28s} {len(texs):5d} tex  ok={ok}", flush=True)

    os.makedirs(os.path.dirname(CSV_OUT), exist_ok=True)
    with open(CSV_OUT, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print("rows", len(rows), "->", CSV_OUT)


if __name__ == "__main__":
    main()
