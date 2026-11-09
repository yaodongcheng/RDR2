# -*- coding: utf-8 -*-
"""给 RDR2 场景切到「彩图完全覆盖」：设 vista 参数 + 把所有地形层颜色刷成纯白。

为什么刷白：shader 里 blend_type=1 是 albedo = 层颜色 × 彩图；
层颜色 = plain_white(1.0) 时结果就是彩图本身（织丰同款，1.2.12 实机验证过）。

用法：
  python patch_rdr2_terrain_colormap.py --scene Main_map --colormap rdr2_map_colormap_TEST --dry-run
  python patch_rdr2_terrain_colormap.py --scene Main_map --colormap rdr2_map_colormap_TEST
  python patch_rdr2_terrain_colormap.py --scene Main_map --restore
"""
import argparse
import io
import os
import re
import sys

MODULES = r"H:\SteamLibrary\steamapps\common\Mount & Blade II Bannerlord\Modules"
SCENES = {
    "Main_map": os.path.join(MODULES, "RDR2", "SceneObj", "Main_map", "scene.xscene"),
    "rdr2_sanit_denis": os.path.join(MODULES, "RDR2", "SceneObj", "rdr2_sanit_denis", "scene.xscene"),
}
WANT_ATTRS = {
    "vista_tileset": "none",
    "vista_diffuse_name": None,          # 由 --colormap 填
    "vista_diffuse_blend_type": "1",     # 1 = multiply（彩图 × 层颜色）
    "vista_diffuse_blend_amount": "1.000",
    "vista_layer_detail_distance": "10000.000",
    "vista_albedo_multiplier": "0.670",
    "colormap_detail_level": "-1",
}
TEX_RE = re.compile(r'(<texture\s+type="(diffusemap|normalmap|specularmap|areamap|splattingmap|displacementmap)"\s+name=")([^"]*)(")')


def set_attr(tag, key, value):
    if re.search(r'\b%s="[^"]*"' % re.escape(key), tag):
        return re.sub(r'\b%s="[^"]*"' % re.escape(key), '%s="%s"' % (key, value), tag)
    return tag[:-1].rstrip() + ' %s="%s">' % (key, value)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True, choices=sorted(SCENES))
    ap.add_argument("--colormap", default=None)
    ap.add_argument("--water-level", default=None)
    ap.add_argument("--min-height", default=None)
    ap.add_argument("--max-height", default=None)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--restore", action="store_true")
    args = ap.parse_args()
    if not args.restore and not args.colormap:
        raise SystemExit("need --colormap (or --restore)")

    path = SCENES[args.scene]
    bak = path + ".colormap_bak"
    if args.restore:
        if not os.path.isfile(bak):
            raise SystemExit("no backup: " + bak)
        with open(bak, "rb") as f:
            data = f.read()
        with open(path, "wb") as f:
            f.write(data)
        print("restored", path, "from", bak)
        return

    with open(path, "rb") as f:
        txt = f.read().decode("utf-8")
    if not os.path.isfile(bak):
        with open(bak, "wb") as f:
            f.write(txt.encode("utf-8"))
        print("backup ->", bak)

    m = re.search(r"<terrain\b[^>]*>", txt)
    if not m:
        raise SystemExit("no <terrain> tag")
    tag = m.group(0)
    for k, v in WANT_ATTRS.items():
        tag = set_attr(tag, k, args.colormap if k == "vista_diffuse_name" else v)
    if args.min_height is not None:
        tag = set_attr(tag, "min_height", args.min_height)
    if args.max_height is not None:
        tag = set_attr(tag, "max_height", args.max_height)
    out = txt[:m.start()] + tag + txt[m.end():]
    print("terrain tag ->", tag)

    if args.water_level is not None:
        out, n = re.subn(r'(<property\s+name="water_level"\s+value=")[^"]*(")',
                         r'\g<1>' + args.water_level + r'\g<2>', out)
        print("water_level replaced:", n)

    # 只改 <layers> 段里的贴图
    ls = out.find("<layers", m.start())
    le = out.find("</layers>", ls)
    if ls < 0 or le < 0:
        raise SystemExit("no <layers> block")
    block = out[ls:le]
    changed = {}

    def repl(mm):
        typ, name = mm.group(2), mm.group(3)
        if typ == "diffusemap":
            new = "plain_white"
        else:
            new = "none"
        if new != name:
            changed[typ] = changed.get(typ, 0) + 1
        return mm.group(1) + new + mm.group(4)

    block2 = TEX_RE.sub(repl, block)
    out = out[:ls] + block2 + out[le:]
    print("textures changed:", changed if changed else "(none)")

    if args.dry_run:
        print("dry-run: not written")
        return
    with open(path, "wb") as f:
        f.write(out.encode("utf-8"))
    print("wrote", path)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
