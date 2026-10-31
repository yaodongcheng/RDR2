# -*- coding: utf-8 -*-
"""分类规则自检：合法性 + 纠错冗余 + 用例回归。

    python tools/_check_rules.py [--corrections <csv>] [--cases tools/rules_cases.csv]

判据（任一 FAIL 即退出码 1）：
  1. CLASSES 无重复；DEFAULT_HIDDEN ⊆ CLASSES；RULES/LEFTOVER 的 key 都在 CLASSES；
  2. 纠错清单 target_class 合法；
  3. 纠错冗余：某条纠错在 v23 全量名字上**一次都没改变分类** → 已被规则覆盖，应删除/转正；
  4. 用例表：名字（+可选贴图）跑「classify_name → apply_corrections → apply_hard_rules」得到期望类。
"""
import argparse
import collections
import csv
import json
import os
import sys

ROOT = r'D:/BrainMaker/大镖客2解包分析'
CORR = os.path.join(ROOT, 'deliverable/blender/regions_support/region_corrections.csv')
V23 = os.path.join(ROOT, 'deliverable/blender/continent/manifest_continent_v23.jsonl')
CASES = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'rules_cases.csv')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from class_rules import (  # noqa: E402
    CLASSES, DEFAULT_HIDDEN, RULES, LEFTOVER, TECHNICAL,
    classify_name, apply_corrections, apply_hard_rules, load_corrections,
)


def check_defs():
    bad = []
    if len(set(CLASSES)) != len(CLASSES):
        bad.append('CLASSES 有重复')
    for k in DEFAULT_HIDDEN:
        if k not in CLASSES:
            bad.append('DEFAULT_HIDDEN 含未知类 %s' % k)
    for key, _, _ in RULES:
        if key not in CLASSES:
            bad.append('RULES 含未知类 %s' % key)
    for key, _ in LEFTOVER:
        if key not in CLASSES:
            bad.append('LEFTOVER 含未知类 %s' % key)
    return bad


def model_textures(h, cache, idx):
    if h in cache:
        return cache[h]
    if not idx:
        try:
            idx.update(json.load(open(os.path.join(ROOT, 'assets/lib_native/index.json'), encoding='utf-8')))
        except Exception:
            idx['models'] = {}
            idx['tex'] = []
    out = []
    e = (idx.get('models') or {}).get(h)
    if e:
        tex = idx.get('tex') or []
        for s in (e.get('s') or []):
            tid = s[0]
            if isinstance(tid, int) and 0 <= tid < len(tex):
                out.append(tex[tid].get('n') or '')
    cache[h] = out
    return out


def check_corrections(corr):
    bad = []
    hits = collections.Counter()
    cache, idx = {}, {}
    for line in open(V23, encoding='utf-8'):
        o = json.loads(line)
        if '_meta' in o:
            continue
        nm = o.get('n') or ''
        k0 = classify_name(nm)
        txs = list(o.get('t') or []) + model_textures(o.get('h'), cache, idx)
        for rx, trx, tgt, cid, reason in corr:
            hit = bool(rx and nm and rx.search(nm))
            if not hit and trx is not None:
                hit = any(trx.search(t) for t in txs if t)
            if hit:
                hits[cid] += 1
                if k0 not in TECHNICAL and k0 != tgt:
                    hits[cid + '_changed'] += 1
    for rx, trx, tgt, cid, reason in corr:
        if tgt not in CLASSES:
            bad.append('纠错 #%s target_class=%s 不在 CLASSES' % (cid, tgt))
        if hits[cid] == 0:
            bad.append('纠错 #%s 在 v23 全量里命中 0 个（冗余/已覆盖，建议删除）' % cid)
    for rx, trx, tgt, cid, reason in corr:
        print('  #%-3s 命中 %6d  改变 %6d  -> %s' %
              (cid, hits[cid], hits[cid + '_changed'], tgt))
    return bad


def check_cases(corr):
    bad = []
    n = 0
    with open(CASES, encoding='utf-8-sig', newline='') as f:
        for row in csv.DictReader(f):
            name = (row.get('name') or '').strip()
            if not name:
                continue
            n += 1
            exp = (row.get('expected') or '').strip()
            tex = [t for t in (row.get('textures') or '').split('|') if t]
            k = classify_name(name)
            k = apply_corrections(k, name, tex, corr, verbose=False)
            k = apply_hard_rules(k, name)
            if k != exp:
                bad.append('用例 %s：期望 %s，实际 %s（%s）' %
                           (name, exp, k, row.get('note') or ''))
    print('  用例 %d 条' % n)
    return bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--corrections', default=CORR)
    ap.add_argument('--cases', default=CASES)
    a = ap.parse_args()
    corr = load_corrections(a.corrections)
    bad = []
    bad += check_defs()
    bad += check_corrections(corr)
    bad += check_cases(corr)
    if bad:
        print('[rules] FAIL')
        for x in bad:
            print('   ', x)
        raise SystemExit(1)
    print('[rules] PASS')


if __name__ == '__main__':
    main()
