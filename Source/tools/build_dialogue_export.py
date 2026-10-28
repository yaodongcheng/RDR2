# -*- coding: utf-8 -*-
"""按任务/音频库导出剧本对白（只保留真中文台词，过滤 yldb 二进制噪声）。"""
import os, re, csv

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W = lambda *p: os.path.join(ROOT, *p)
CJK = lambda s: any("\u4e00" <= ch <= "\u9fff" for ch in s)


def clean(s):
    s = re.sub(r"~sl:[0-9]+:[0-9]+~", "", s)
    s = s.replace("~z~", "").replace("~n~", chr(10))
    s = re.sub(r"~INPUT_[A-Z0-9_]+~", "[按键]", s)
    return s.strip()


def main():
    txt = open(W("export/story/dialogue_chinesesimp.txt"), encoding="utf-8", errors="ignore").read()
    blocks = re.split(r"\n### ", txt)
    banks = {}
    for b in blocks[1:]:
        head = b.split("\n", 1)[0]
        m = re.match(r"(.+?\.yldb)\s+\((\d+) 条\)", head)
        if not m:
            continue
        fn = m.group(1)
        raw = [l.split("\t", 2)[2] for l in b.split("\n")[1:] if l.count("\t") >= 2]
        banks[fn] = [clean(x) for x in raw if CJK(x)]

    missions = list(csv.DictReader(open(W("export/levels/world/missions.csv"), encoding="utf-8-sig")))
    by_id = {m["mission_id"].upper(): m for m in missions}

    out_dir = W("export/story/mission_dialogue")
    un_dir = os.path.join(out_dir, "_unmatched")
    os.makedirs(un_dir, exist_ok=True)
    index = []

    for fn, lines in sorted(banks.items()):
        low = fn.lower()
        if not low.endswith("aud.yldb"):
            continue
        code = fn[:-8]
        mid = None
        if code.upper() in by_id:
            mid = code.upper()
        else:
            for k in by_id:
                kk = k[1:] if k.startswith("R") else k
                if (kk.lower().startswith(code.lower()) or code.lower().startswith(kk.lower())
                        or k.lower().startswith(code.lower())):
                    mid = k
                    break

        cjk = len(lines)
        if mid is None:
            path = os.path.join(un_dir, code + ".txt")
            with open(path, "a", encoding="utf-8") as f:
                f.write("# bank: " + fn + "\n")
                for l in lines:
                    f.write(l + "\n")
                f.write("\n")
            index.append({"mission_id": code.upper(), "category": "UNMATCHED_AUD",
                          "audio_bank": fn, "lines": cjk, "cjk_lines": cjk})
            continue

        m = by_id[mid]
        path = os.path.join(out_dir, mid + ".txt")
        with open(path, "a", encoding="utf-8") as f:
            f.write("# " + m["mission_id"] + " | " + m["category"] + " | bank: " + fn + "\n")
            for l in lines:
                f.write(l + "\n")
            f.write("\n")
        index.append({"mission_id": mid, "category": m["category"], "audio_bank": fn,
                      "lines": cjk, "cjk_lines": cjk})

    with open(W("export/levels/world/mission_dialogue_index.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["mission_id", "category", "audio_bank", "lines", "cjk_lines"])
        w.writeheader(); w.writerows(index)

    main_cats = {"CHAPTER_1", "CHAPTER_2", "CHAPTER_3", "CHAPTER_4", "CHAPTER_5",
                 "CHAPTER_6", "CHAPTER_7", "CHAPTER_8"}
    side_cats = {"RANDOM_CHARACTER", "RANDOM_STORY_CHARACTER", "BOUNTY_HUNTING"}
    matched = {x["mission_id"] for x in index if x["category"] != "UNMATCHED_AUD"}
    main_all = [m for m in missions if m["category"] in main_cats]
    side_all = [m for m in missions if m["category"] in side_cats]

    print("audio banks", len(index), "matched", len(matched), "unmatched", len(index) - len(matched))
    print("clean lines", sum(x["lines"] for x in index))
    print("main with dialogue", sum(1 for m in main_all if m["mission_id"] in matched), "/", len(main_all))
    print("side with dialogue", sum(1 for m in side_all if m["mission_id"] in matched), "/", len(side_all))


if __name__ == "__main__":
    main()
