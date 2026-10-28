#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""从 .ymt 对话资产里解出「每一句的说话人」。

原理（2026-10-23 实测确认）
  1. 每个 `.ymt` 里有一张 **actor 表**：若干 16 字节条目
         { u32 nameHash, u32 actorId, u32 nameHash, u32 offset }
     `nameHash` = joaat(角色名)（实测：dutch / susan / hosea / abigail / swanson / arthur / charles_smith）
  2. 每个 `.ymt` 里还有一块 **逐句记录**（步长 56 字节），第 i 条对应第 i 句，
     其中 **+24 处的 u32 = actorId**（实测与录屏字幕吻合：CABIN 第2-5句=susan、第31句=dutch）。
  3. 台词键/语音上下文从字符串块按顺序取得（WNT1_HWAA ↔ WNT1_INT_CABIN_1）。

输出
  export/story/conversation_actors.json   {对话名: [{n, line_key, ctx, actor_id, actor}]}
  export/story/conversation_actors.csv
  export/story/conversation_actors_stats.json
"""
import argparse
import glob
import json
import os
import re
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
from parse_pso import parse  # noqa: E402
from yldb_keys import joaat  # noqa: E402

SRC = os.path.join(ROOT, 'raw', 'conversations', 'out')
STORY = os.path.join(ROOT, 'export', 'story')
NAMES = os.path.join(ROOT, 'tools', 'rdr2rpf', 'src', 'names.txt')

LINE_RE = re.compile(r'^([A-Z0-9]+(?:[A-Z0-9_]*?))_(\d{1,3})$')
NAME_MAP = None


def name_map():
    global NAME_MAP
    if NAME_MAP is None:
        NAME_MAP = {}
        names = []
        for l in open(NAMES, encoding='utf-8', errors='ignore'):
            n = l.strip()
            if n:
                names.append(n)
                NAME_MAP.setdefault(joaat(n), n)
        # 变体：cs_<name> / player_<name> / p_<name>（对话里的 actor 常用这些形式）
        for n in names:
            low = n.lower()
            if low.startswith(('cs_', 'player_', 'p_')):
                continue
            for pre in ('cs_', 'player_', 'p_'):
                NAME_MAP.setdefault(joaat(pre + low), n)
    return NAME_MAP


def build_hash_names(files, nm):
    """跨文件补全：同一 actor 的 h1/h2 若有一边能反查成名字，另一边也认作同名。"""
    pairs = []
    for f in files:
        try:
            info, sec = parse(f)
        except Exception:
            continue
        data = sec.get('PSIN')
        if not data:
            continue
        for b in info.get('pmap', {}).get('entries', []):
            off, ln = b['offset'], b['length']
            if ln < 16 or ln % 16:
                continue
            for i in range(ln // 16):
                o = off + i * 16
                if o + 16 > len(data):
                    break
                h1, aid, h2, _ = struct.unpack_from('>IIII', data, o)
                if h1 and h2:
                    pairs.append((h1, h2))
    resolved = {h: n for h, n in nm.items()}
    for _ in range(4):
        changed = 0
        for h1, h2 in pairs:
            n = resolved.get(h1) or resolved.get(h2)
            if n:
                if h1 not in resolved:
                    resolved[h1] = n; changed += 1
                if h2 not in resolved:
                    resolved[h2] = n; changed += 1
        if not changed:
            break
    return resolved


def read_actor_table(data, blocks, nm):
    """在块里找 actor 表：16 字节条目且 nameHash 能反查成名字"""
    best = None
    for b in blocks:
        off, ln = b['offset'], b['length']
        if ln < 16 or ln % 16:
            continue
        tab = {}
        resolved = 0
        equal = 0
        for i in range(ln // 16):
            o = off + i * 16
            if o + 16 > len(data):
                break
            h1, aid, h2, _ = struct.unpack_from('>IIII', data, o)
            if not (0 <= aid < 4096):
                continue
            name = nm.get(h1) or nm.get(h2)
            if name:
                resolved += 1
            if h1 == h2:
                equal += 1
            tab[aid] = name          # 名字可能为 None，但 id 仍要收进来
        if equal == 0 and resolved == 0:
            continue                  # 不像 actor 表
        # 优先「能反查出名字最多」的表；同分时取条目多的
        if (resolved, len(tab)) > (best[0], len(best[1])) if best else True:
            best = (resolved, tab)
    return best[1] if best else {}


def read_lines(data, blocks, n_lines, actors):
    """找逐句记录块：长度 = 句数 × 步长，且某一列全是已知 actor id。

    在所有可行列里，优先选「能对上名字最多」的那一列（避免选到语义错误的列）。
    actors: {id: name|None}
    """
    best = None  # (resolved, covered, stride, ids)
    for stride in (56, 64, 48, 40, 72, 80, 32, 24, 16, 88, 96):
        for b in blocks:
            off, ln = b['offset'], b['length']
            if stride * n_lines != ln:
                continue
            for col in range(0, stride - 3, 4):
                ids = []
                ok = True
                for i in range(n_lines):
                    o = off + i * stride + col
                    if o + 4 > len(data):
                        ok = False
                        break
                    v = struct.unpack_from('>I', data, o)[0]
                    if v not in actors:
                        ok = False
                        break
                    ids.append(v)
                if not ok:
                    continue
                resolved = sum(1 for v in ids if actors.get(v))
                distinct = len(set(ids))
                ratio = round(resolved / max(len(ids), 1), 2)
                # 优先：名字命中率 → 说话人有多样性（排除"整列同一默认值"的错列）→ 命中数
                score = (ratio, 1 if (distinct > 1 or n_lines == 1) else 0, resolved, distinct)
                if best is None or score > best[0]:
                    best = (score, stride, ids)
    if best:
        return best[1], best[2]
    return None, None


def read_lines_general(data, blocks, n_cands, actors):
    """通用搜索：块长度能整除出接近句数的条数即可（不限固定步长）"""
    best = None
    for b in blocks:
        off, ln = b['offset'], b['length']
        for stride in range(8, 161, 4):
            if ln % stride:
                continue
            cnt = ln // stride
            if cnt not in n_cands:
                continue
            for col in range(0, stride - 3, 4):
                ids = []
                ok = True
                for i in range(cnt):
                    o = off + i * stride + col
                    if o + 4 > len(data):
                        ok = False
                        break
                    v = struct.unpack_from('>I', data, o)[0]
                    if v not in actors:
                        ok = False
                        break
                    ids.append(v)
                if not ok:
                    continue
                resolved = sum(1 for v in ids if actors.get(v))
                distinct = len(set(ids))
                ratio = round(resolved / max(len(ids), 1), 2)
                score = (ratio, 1 if (distinct > 1 or cnt == 1) else 0, resolved, distinct)
                if best is None or score > best[0]:
                    best = (score, stride, ids)
    if best:
        return best[1], best[2]
    return None, None


def parse_file(path, nm):
    info, sec = parse(path)
    data = sec.get('PSIN')
    if not data:
        return None
    blocks = info.get('pmap', {}).get('entries', [])
    # 字符串块：成对出现 context / line_key
    toks = []
    for b in blocks:
        off, ln = b['offset'], b['length']
        seg = data[off:off + ln]
        for m in re.finditer(rb'[A-Z0-9_]{3,48}\x00', seg):
            toks.append(m.group()[:-1].decode())
    pairs = []
    i = 0
    while i < len(toks) - 1:
        a, b = toks[i], toks[i + 1]
        if LINE_RE.match(b) and not LINE_RE.match(a):
            pairs.append((a, b))
            i += 2
        else:
            i += 1
    if not pairs:
        return None
    conv = None
    ordered = []
    seen_keys = set()
    for ctx, lk in pairs:
        m = LINE_RE.match(lk)
        c, n = m.group(1), int(m.group(2))
        conv = conv or c
        if lk in seen_keys:          # 同一句在字符串块里可能出现两次
            continue
        seen_keys.add(lk)
        ordered.append({'n': n, 'line_key': lk, 'ctx': ctx})
    lines = {x['n']: x for x in ordered}
    max_n = max((x['n'] for x in ordered), default=0)
    n_lines = max(max_n, len(ordered))   # 句号可能有空洞（缺字幕），记录数按最大值算
    actors = read_actor_table(data, blocks, nm)
    if not actors:
        return None
    stride, ids = None, None
    cands = (n_lines, max_n, max_n + 1, len(ordered), max_n + 2, max_n - 1)
    for cand in cands:
        if cand <= 0:
            continue
        stride, ids = read_lines(data, blocks, cand, actors)
        if ids:
            n_lines = cand
            break
    if not ids:
        stride, ids = read_lines_general(data, blocks, set(c for c in cands if c > 0), actors)
    out = []
    by_number = (ids is not None) and (n_lines == max_n)
    for idx, x in enumerate(ordered):
        if not ids:
            aid = None
        elif by_number:
            aid = ids[x['n'] - 1] if 0 <= x['n'] - 1 < len(ids) else None
        else:
            aid = ids[idx] if idx < len(ids) else None
        out.append({'n': x['n'], 'line_key': x['line_key'], 'ctx': x['ctx'],
                    'actor_id': aid, 'actor': actors.get(aid) if aid is not None else None})
    return {'conversation': conv, 'actors': actors, 'stride': stride, 'lines': out}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--limit', type=int, default=0)
    args = ap.parse_args()
    nm = name_map()
    print(f'names.txt -> {len(nm)} 个哈希')
    out = {}
    rows = []
    ok = 0
    no_actor = 0
    for f in sorted(glob.glob(os.path.join(SRC, '*.ymt'))):
        r = parse_file(f, nm)
        if not r:
            no_actor += 1
            continue
        conv = r['conversation']
        out[conv] = {'file': os.path.basename(f)[:-4],
                     'actors': {str(k): v for k, v in r['actors'].items()},
                     'lines': r['lines']}
        for ln in r['lines']:
            rows.append([conv, ln['n'], ln['line_key'], ln['ctx'],
                         ln['actor_id'], ln['actor'] or '', os.path.basename(f)[:-4]])
        ok += 1
        if args.limit and ok >= args.limit:
            break
    json.dump(out, open(os.path.join(STORY, 'conversation_actors.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=0)
    import csv
    with open(os.path.join(STORY, 'conversation_actors.csv'), 'w', newline='',
              encoding='utf-8-sig') as fh:
        w = csv.writer(fh)
        w.writerow(['conversation', 'line_no', 'line_key', 'speech_context', 'actor_id', 'actor', 'ymt'])
        w.writerows(rows)
    named = sum(1 for r in rows if r[5])
    stats = {'ymt_total': len(glob.glob(os.path.join(SRC, '*.ymt'))),
             'conversations_parsed': ok, 'skipped': no_actor,
             'lines': len(rows), 'lines_with_actor_name': named,
             'coverage': round(named / max(len(rows), 1) * 100, 1)}
    json.dump(stats, open(os.path.join(STORY, 'conversation_actors_stats.json'), 'w',
                          encoding='utf-8'), ensure_ascii=False, indent=1)
    print(stats)


if __name__ == '__main__':
    main()
