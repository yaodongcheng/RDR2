# -*- coding: utf-8 -*-
"""组装 HTML 查看器的数据：武器 / 道具 / 任务 / 对白。"""
import os, csv, json, shutil, re
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W = lambda *p: os.path.join(ROOT, *p)
VIEW = W("export/viewer")


WEAPON_ZH = [
    ("w_revolver_cattleman", "牛仔左轮手枪"), ("w_revolver_doubleaction", "双动式左轮手枪"),
    ("w_revolver_schofield", "斯科菲尔德左轮手枪"), ("w_revolver_navy", "海军左轮手枪"),
    ("w_revolver_lemat", "勒马特左轮手枪"), ("w_pistol_volcanic", "火山手枪"),
    ("w_pistol_mauser", "毛瑟手枪"), ("w_pistol_semiauto", "半自动手枪"),
    ("w_rifle_springfield", "斯普林菲尔德步枪"), ("w_rifle_boltaction", "栓动步枪"),
    ("w_rifle_rollingblock", "滚轮闭锁式步枪"), ("w_rifle_carcano", "卡尔卡诺步枪"),
    ("w_rifle_varmint", "狐鼠步枪"), ("w_rifle_elephant", "大象步枪"),
    ("w_repeater_carbine", "卡宾连发步枪"), ("w_repeater_lancaster", "兰卡斯特连发步枪"),
    ("w_repeater_litchfield", "利奇菲尔德连发步枪"), ("w_shotgun_doublebarrel", "双管霰弹枪"),
    ("w_shotgun_sawedoff", "短管霰弹枪"), ("w_shotgun_pump", "泵动式霰弹枪"),
    ("w_shotgun_semiauto", "半自动霰弹枪"), ("w_shotgun_repeating", "连发霰弹枪"),
    ("w_bow_improved", "改良弓"), ("w_bow", "弓"), ("w_lasso", "套索"),
    ("w_fishingrod", "钓鱼竿"), ("w_melee_knife", "猎刀"), ("w_melee_machete", "砍刀"),
    ("w_melee_hatchet", "短柄斧"), ("w_melee_tomahawk", "战斧"), ("w_melee_cleaver", "切肉刀"),
    ("w_melee_hammer", "锤子"), ("w_melee_torch", "火把"),
    ("w_rifle_binoculars", "望远镜"), ("w_binoculars", "望远镜"), ("w_camerabox", "相机"),
    ("w_electricfielddetector", "电场探测器"), ("w_stick_dynamite", "炸药"),
    ("w_sp_bowarrow_arrow_smallgame", "小型猎物箭"), ("w_sp_bowarrow_dynamite", "炸药箭"),
    ("w_sp_bowarrow_fire", "火焰箭"), ("w_sp_bowarrow_charles", "查尔斯之箭"),
    ("w_sp_bowarrow", "箭"), ("w_rifle_scopeinner", "瞄准镜"),
    ("w_melee_lasso", "套索"), ("w_melee_fishingpole", "钓鱼竿"),
    ("w_melee_brassknuckles", "指虎"), ("w_melee_brokensword", "断剑"),
    ("w_throwable_dynamite", "炸药"), ("w_throwable_molotov", "燃烧瓶"),
    ("w_throwable_throwingknife", "飞刀"), ("w_throwable_tomahawk", "投掷战斧"),
]
ATTACH = re.compile(r"_(grip|sight|clip|wrap|inner|slod|scope|strap|barrel|stock|cylinder|hammer|trigger|lever|bolt|magazine|engraving|carving|tint|pal|eg)\d*$", re.I)
ITEM_WORDS = {
    "alligator":"短吻鳄","aligato":"短吻鳄","pronghorn":"叉角羚","bighorn":"大角羊","ram":"公羊",
    "deer":"鹿","elk":"麋鹿","moose":"驼鹿","rabbit":"兔子","squirrel":"松鼠","beaver":"河狸",
    "badger":"獾","fox":"狐狸","wolf":"狼","coyote":"郊狼","boar":"野猪","pig":"猪","cow":"牛",
    "bull":"公牛","sheep":"羊","goat":"山羊","chicken":"鸡","turkey":"火鸡","duck":"鸭",
    "goose":"鹅","fish":"鱼","trout":"鳟鱼","salmon":"鲑鱼","catfish":"鲶鱼","crab":"蟹",
    "turtle":"龟","snake":"蛇","frog":"蛙","bird":"鸟","eagle":"鹰","hawk":"鹰","owl":"猫头鹰",
    "crow":"乌鸦","feather":"羽毛","egg":"蛋","meat":"肉","fur":"皮毛","hide":"兽皮","horn":"角",
    "antler":"鹿角","claw":"爪","tooth":"牙齿","bone":"骨头","skull":"头骨","head":"头",
    "heart":"心","liver":"肝","tail":"尾巴","pelt":"皮毛","skin":"皮","tuft":"一撮毛",
    "herb":"草药","plant":"植物","flower":"花","root":"根","leaf":"叶","berry":"浆果",
    "mushroom":"蘑菇","ginseng":"人参","yarrow":"蓍草","tobacco":"烟草","sage":"鼠尾草",
    "thyme":"百里香","mint":"薄荷","orchid":"兰花","bacon":"培根","cabbage":"卷心菜",
    "bean":"豆","corn":"玉米","apple":"苹果","pear":"梨","peach":"桃","cherry":"樱桃",
    "grape":"葡萄","melon":"瓜","pumpkin":"南瓜","potato":"土豆","carrot":"胡萝卜",
    "onion":"洋葱","tomato":"番茄","bread":"面包","cheese":"奶酪","butter":"黄油",
    "milk":"牛奶","honey":"蜂蜜","sugar":"糖","salt":"盐","pepper":"胡椒","coffee":"咖啡",
    "tea":"茶","whiskey":"威士忌","beer":"啤酒","wine":"葡萄酒","rum":"朗姆酒","gin":"杜松子酒",
    "brandy":"白兰地","water":"水","stew":"炖菜","soup":"汤","pie":"派","cake":"蛋糕",
    "biscuit":"饼干","chocolate":"巧克力","coin":"硬币","key":"钥匙","letter":"信件",
    "note":"便条","map":"地图","photo":"照片","book":"书","newspaper":"报纸","document":"文件",
    "pamphlet":"小册子","card":"卡片","ring":"戒指","necklace":"项链","bracelet":"手链",
    "earring":"耳环","watch":"怀表","mirror":"镜子","comb":"梳子","brush":"刷子","soap":"肥皂",
    "candle":"蜡烛","bottle":"瓶子","jar":"罐子","box":"盒子","chest":"箱子","bag":"袋子",
    "satchel":"背包","holster":"枪套","belt":"腰带","buckle":"带扣","hat":"帽子","boot":"靴子",
    "glove":"手套","scarf":"围巾","coat":"外套","shirt":"衬衫","pants":"裤子","dress":"裙子",
    "jewelry":"珠宝","gem":"宝石","pearl":"珍珠","gold":"金","silver":"银","tusk":"象牙",
    "knife":"刀","axe":"斧","hammer":"锤","shovel":"铲","pickaxe":"镐","saw":"锯","rope":"绳",
    "lantern":"提灯","torch":"火把","fishingrod":"钓竿","bait":"鱼饵","trap":"陷阱",
    "arrow":"箭","bundle":"束","bullet":"子弹","gunpowder":"火药","dynamite":"炸药",
    "molotov":"燃烧瓶","spoon":"勺子","bowl":"碗","plate":"盘子","cup":"杯子","fork":"叉子",
}


def norm_base(stem):
    s = re.sub(r"\+hi$", "", stem)
    s = re.sub(r"_hi$", "", s)
    s = re.sub(r"x$", "", s)
    s = re.sub(r"\d+x?$", "", s)
    s = re.sub(r"_\d+$", "", s)
    return s


def weapon_zh(stem):
    for k, v in WEAPON_ZH:
        if stem.startswith(k):
            return v
    return stem


def weapon_cat(stem):
    if "revolver" in stem: return "左轮手枪"
    if "pistol" in stem: return "手枪"
    if "repeater" in stem: return "连发步枪"
    if "shotgun" in stem: return "霰弹枪"
    if "sniper" in stem: return "狙击枪"
    if "binocular" in stem or "scope" in stem or "camera" in stem or "electric" in stem: return "工具"
    if "bowarrow" in stem: return "箭/弹药"
    if "rifle" in stem: return "步枪"
    if "bow" in stem: return "弓"
    if "lasso" in stem: return "套索"
    if "fishing" in stem: return "钓竿"
    if "melee" in stem: return "近战"
    if "throw" in stem or "dynamite" in stem or "molotov" in stem: return "投掷物"
    return "工具"


ITEM_ZH = [
    ("alligato", "短吻鳄牙齿"), ("alligatorpelt", "短吻鳄皮毛"), ("bearskin", "熊皮"),
    ("beartuftsfur", "熊毛皮"), ("beefstew", "炖牛肉"), ("bacon_cabbage", "培根卷心菜"),
    ("arrowbundle", "箭束"), ("pirateskey", "海盗钥匙"), ("corpsenecklace", "尸体项链"),
    ("gunpowder", "火药"), ("dynamite", "炸药"), ("molotov", "燃烧瓶"), ("cheese", "奶酪"),
    ("bread", "面包"), ("meat", "肉"), ("fish", "鱼"), ("herb", "草药"), ("tonic", "补药"),
    ("bottle", "瓶子"), ("card", "卡片"), ("horn", "角"), ("feather", "羽毛"), ("egg", "蛋"),
    ("apple", "苹果"), ("corn", "玉米"), ("bean", "豆"), ("coffee", "咖啡"),
    ("whiskey", "威士忌"), ("beer", "啤酒"), ("wine", "葡萄酒"), ("medicine", "药"),
    ("bandage", "绷带"), ("ring", "戒指"), ("watch", "怀表"), ("buckle", "带扣"),
    ("comb", "梳子"), ("mirror", "镜子"), ("brush", "刷子"), ("soap", "肥皂"),
    ("candle", "蜡烛"), ("book", "书"), ("newspaper", "报纸"), ("map", "地图"),
    ("photo", "照片"), ("cigar", "雪茄"), ("cigarette", "香烟"), ("pipe", "烟斗"),
    ("tobacco", "烟草"), ("pamphlet", "小册子"), ("document", "文件"), ("note", "便条"),
    ("pronghorn", "叉角羚皮毛"), ("bighorn", "大角羊角"), ("rabbit", "兔子"),
    ("squirrel", "松鼠"), ("beaver", "河狸皮"), ("badger", "獾皮"), ("fox", "狐狸皮"),
    ("wolf", "狼皮"), ("deer", "鹿皮"), ("elk", "麋鹿皮"), ("moose", "驼鹿皮"),
    ("boar", "野猪皮"), ("cow", "牛皮"), ("sheep", "羊皮"), ("coin", "硬币"),
]
KEEP_PKG = {"p_valuable", "p_food", "p_drink", "p_plant", "int_doctor_office",
            "s_pickups", "s_cards"}


def item_zh(stem):
    low = stem.lower()
    for k, v in ITEM_ZH:
        if k in low:
            return v
    return None


def main():
    os.makedirs(VIEW, exist_ok=True)

    # 武器
    wmeta = {}
    for r in csv.DictReader(open(W("export/levels/world/weapon_models.csv"), encoding="utf-8-sig")):
        stem = os.path.splitext(os.path.basename(r["file"]))[0]
        wmeta[stem] = r["category"]
    weapons = []
    seen = {}
    for fn in sorted(os.listdir(W("export/viewer/models/weapons"))):
        if not fn.endswith(".gltf"):
            continue
        stem = fn[:-5]
        stem0 = re.sub(r"_hi$", "", stem)
        if ATTACH.search(stem0) or "engraving" in stem0 or "sight_rear" in stem0:
            continue
        base = norm_base(stem0)
        if base in seen:
            seen[base]["variants"] += 1
            continue
        row = {"id": stem, "name": weapon_zh(base), "category": weapon_cat(base),
               "gltf": "models/weapons/" + fn, "variants": 1}
        seen[base] = row
        weapons.append(row)

    # 道具
    imeta = {}
    for r in csv.DictReader(open(W("export/levels/world/item_models.csv"), encoding="utf-8-sig")):
        stem = os.path.splitext(os.path.basename(r["file"]))[0]
        imeta[stem] = (r["package"], r["category"])
    items = []
    for fn in sorted(os.listdir(W("export/viewer/models/items"))):
        if not fn.endswith(".gltf"):
            continue
        stem = fn[:-5]
        pkg, cat = imeta.get(stem, ("", "其他"))
        if pkg not in KEEP_PKG:
            continue
        zh = item_zh(stem)
        items.append({"id": stem, "name": zh or (cat + " · " + stem), "category": cat,
                      "package": pkg, "gltf": "models/items/" + fn})

    # 任务
    missions = {r["mission_id"]: dict(r) for r in
                csv.DictReader(open(W("export/levels/world/missions.csv"), encoding="utf-8-sig"))}
    cast = {r["mission_id"]: r for r in
            csv.DictReader(open(W("export/levels/world/mission_cast.csv"), encoding="utf-8-sig"))}
    dlg = defaultdict(lambda: {"lines": 0, "banks": []})
    for r in csv.DictReader(open(W("export/levels/world/mission_dialogue_index.csv"), encoding="utf-8-sig")):
        if r["category"] == "UNMATCHED_AUD":
            continue
        dlg[r["mission_id"]]["lines"] += int(r["lines"])
        dlg[r["mission_id"]]["banks"].append(r["audio_bank"])
    mrows = []
    for mid, m in missions.items():
        c = cast.get(mid, {})
        mrows.append({
            "id": mid, "category": m["category"], "type": m["mission_type"],
            "cast_count": int(c.get("cast_count") or 0),
            "cast": [x for x in (c.get("cast") or "").split(";") if x],
            "cutscene": c.get("cutscene_pkgs", ""),
            "dialogue_lines": dlg[mid]["lines"],
            "dialogue_banks": dlg[mid]["banks"],
        })
    mrows.sort(key=lambda x: (x["category"], x["id"]))
    goals = list(csv.DictReader(open(W("export/levels/world/goals_sp_missions.csv"), encoding="utf-8-sig")))

    # 对白文件
    ddir = W("export/viewer/dialogue")
    os.makedirs(ddir, exist_ok=True)
    for fn in os.listdir(W("export/story/mission_dialogue")):
        if fn.endswith(".txt"):
            shutil.copy2(W("export/story/mission_dialogue", fn), os.path.join(ddir, fn))
    udir = W("export/viewer/dialogue_unmatched")
    os.makedirs(udir, exist_ok=True)
    for fn in os.listdir(W("export/story/mission_dialogue/_unmatched")):
        if fn.endswith(".txt"):
            shutil.copy2(W("export/story/mission_dialogue/_unmatched", fn), os.path.join(udir, fn))

    data = {
        "weapons": weapons,
        "items": items,
        "missions": mrows,
        "goals": goals,
        "unmatched_dialogue": sorted(f[:-4] for f in os.listdir(udir) if f.endswith(".txt")),
    }
    json.dump(data, open(W("export/viewer/data.json"), "w", encoding="utf-8"), ensure_ascii=False)
    print("weapons", len(weapons), "items", len(items), "missions", len(mrows),
          "goals", len(goals), "unmatched banks", len(data["unmatched_dialogue"]))


if __name__ == "__main__":
    main()
