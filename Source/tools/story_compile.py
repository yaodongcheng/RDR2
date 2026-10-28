#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""RDR2 剧本编译器 v2 —— 把反编译脚本编成「可读、可落地的关卡片段表」。

为什么重写
  v1 想找"唯一的总状态机"，但 RDR2 主线脚本是**嵌套状态机**：
    外层阶段机  ->  beat 运行器  ->  beat 函数（switch(func_xxx(cParam0)) 的 case 0..N）
  beat 函数的 case 序号就是**播放顺序**（每个 case 末尾用 func_135(cParam0, N) 推进）。
  所以正确做法是：把含本任务内容的 beat 函数找出来，按 case 序号线性展开。

输入
  raw/script_full/1491.50/*.c              RDR3-Decompiled-Scripts build 1491.50（1639 个）
  raw/story/lang/chinesesimp/<id>.yldb     任务文本（目标中文）
  raw/story/lang/chinesesimp/<id>aud.yldb  任务对白（<组>_<序号> 中文）

输出
  export/story/beats/<ID>.json
  export/story/beats/<ID>.md（可读剧本）
"""
import argparse
import json
import os
import re
import sys
from collections import OrderedDict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(ROOT, 'raw', 'script_full', '1491.50')
LANG = os.path.join(ROOT, 'raw', 'story', 'lang', 'chinesesimp')
OUT = os.path.join(ROOT, 'export', 'story', 'beats')

sys.path.insert(0, os.path.join(ROOT, 'tools'))
from yldb_keys import Yldb  # noqa: E402

FUNC_DEF = re.compile(
    r'^(?:void|int|float|bool|char\*|char|Vector3|var|struct<[^>]*>|unsigned int)'
    r'(?:\s*/\*[^*]*\*/)?\s+(func_\d+)\s*\(')
CALL_FUNC = re.compile(r'\b(func_\d+)\s*\(')
CASE_LBL = re.compile(r'^\s*case\s+(-?\d+)\s*:')
GXT = re.compile(r'"([^"]+)"\s*/\*\s*GXT:\s*([^*]*?)\s*\*/')
STR = re.compile(r'"([^"\\]{2,80})"')
ANIM_PL = re.compile(r'"((?:pl_|script@)[A-Za-z0-9_@\.]+)"')
NEXT_SET = re.compile(r'func_\d+\(\s*(?:cParam0|uParam0)\s*,\s*(-?\d+)\s*\)\s*;')
STATE_SET = re.compile(r'->f_\d+\s*=\s*-?\d+\s*;')
CONST_ASSIGN = re.compile(r'^\s*(\w+)\s*=\s*(-?\d+)\s*;')
TABLE_CALL_VAR = re.compile(r'(func_\d+)\(\s*(\w+)\s*\)')
CALL_TABLE = re.compile(r'(func_\d+)\(\s*(?:cParam0|uParam0)\s*,\s*(-?\d+)\s*\)')
HASH_MODEL = re.compile(r'joaat\("([A-Z]_[A-Z]_[A-Z0-9_]+)"\)|"([A-Z]_[A-Z]_[A-Z0-9_]+)"')


def clean(t):
    if not t:
        return ''
    t = re.sub(r'~[^~]{0,120}~', '', t)      # ~z~ ~o~ ~sl:0.0:1.9~ ~INPUT_XXX[PromptId=..]~ 等
    t = t.replace('\\n', ' ').replace('\\"', '"')
    return re.sub(r'\s+', ' ', t).strip()


class TextBank:
    def __init__(self):
        self._c = {}

    def y(self, name):
        if name not in self._c:
            p = os.path.join(LANG, name)
            self._c[name] = Yldb(p) if os.path.exists(p) else None
        return self._c[name]

    def text(self, bank, key):
        y = self.y(bank)
        if y is None:
            return None
        v = y.get(key)
        if not v or v in ('<miss>', '<null>'):
            return None
        return clean(v)

    def has(self, bank, key):
        return self.text(bank, key) is not None


def sanitize(lines):
    """去掉字符串字面量与注释，只留代码骨架（否则字符串里的 {} 会打乱括号配对）。"""
    out = []
    in_block = False
    for ln in lines:
        buf = []
        i = 0
        n = len(ln)
        while i < n:
            if in_block:
                j = ln.find('*/', i)
                if j < 0:
                    i = n
                    break
                in_block = False
                i = j + 2
                continue
            c = ln[i]
            if c == '/' and i + 1 < n and ln[i + 1] == '*':
                in_block = True
                i += 2
                continue
            if c == '/' and i + 1 < n and ln[i + 1] == '/':
                break
            if c == '"':
                i += 1
                while i < n:
                    if ln[i] == chr(92):
                        i += 2
                        continue
                    if ln[i] == '"':
                        i += 1
                        break
                    i += 1
                buf.append('""')
                continue
            buf.append(c)
            i += 1
        out.append(''.join(buf))
    return out


class Script:
    def __init__(self, path):
        self.path = path
        self.name = os.path.basename(path)
        with open(path, encoding='utf-8', errors='ignore') as f:
            self.lines = f.read().split('\n')
        self.code = sanitize(self.lines)
        self.funcs = self._parse()

    def _parse(self):
        funcs = OrderedDict()
        n = len(self.lines)
        i = 0
        while i < n:
            m = FUNC_DEF.match(self.lines[i])
            if not m:
                i += 1
                continue
            j = i
            while j < n and '{' not in self.code[j]:
                j += 1
            depth = 0
            k = j
            while k < n:
                depth += self.code[k].count('{') - self.code[k].count('}')
                if depth <= 0 and k > j:
                    break
                k += 1
            funcs[m.group(1)] = (j, k)
            i = k + 1
        return funcs

    def body(self, fn):
        a, b = self.funcs.get(fn, (0, -1))
        return self.lines[a:b + 1]

    def cases(self, fn):
        """按第一层 case 切块 -> [(case号, 行列表, 起始行号)]"""
        body = self.body(fn)
        out = []
        stack = 0
        base = None
        cur = None
        start = 0
        code = self.code[self.funcs[fn][0]:self.funcs[fn][1] + 1]
        for off, ln in enumerate(body):
            m = CASE_LBL.match(ln)
            if m and (base is None or stack == base):
                if base is None:
                    base = stack
                if cur is not None:
                    out.append(cur)
                cur = (int(m.group(1)), [], self.funcs[fn][0] + off)
            if cur is not None:
                cur[1].append(ln)
            cl = code[off] if off < len(code) else ''
            stack += cl.count('{') - cl.count('}')
        if cur is not None:
            out.append(cur)
        return out


def build_callers(s: Script):
    callers = {}
    for fn in s.funcs:
        body = s.body(fn)
        for off, ln in enumerate(body):
            for m in CALL_FUNC.finditer(ln):
                g = m.group(1)
                if g != fn and g in s.funcs:
                    callers.setdefault(g, []).append((fn, s.funcs[fn][0] + off))
    return callers


def case_of(s: Script, fn, lineno):
    """lineno 落在 fn 的哪个 case 里"""
    for num, lines, start in s.cases(fn):
        if start <= lineno <= start + len(lines):
            return num
    return None


def flow_rank(s: Script, fn, callers, depth=0, seen=None):
    """按调用层级 + 外层 case 序号给 beat 函数排序（越小越早）"""
    seen = seen or set()
    if fn in seen or depth > 6:
        return (999999,)
    seen = seen | {fn}
    cs = callers.get(fn)
    if not cs:
        return (999999, s.funcs[fn][0])
    best = None
    for cfn, lineno in cs:
        cnum = case_of(s, cfn, lineno)
        key = flow_rank(s, cfn, callers, depth + 1, seen) + (cnum if cnum is not None else 99999,)
        if best is None or key < best:
            best = key
    return best


class Extractor:
    def __init__(self, script: Script, tid: str, tb: TextBank, aud_bank=None):
        self.s = script
        self.tid = tid
        self.tb = tb
        self.bank_txt = f'{tid.lower()}.yldb'
        self.bank_aud = aud_bank or f'{tid.lower()}aud.yldb'
        self._conv = {}
        self._tables = {}

    # ---------------- 对白 ----------------
    def conv_lines(self, group):
        if group in self._conv:
            return self._conv[group]
        lines = []
        for i in range(1, 81):
            zh = self.tb.text(self.bank_aud, f'{group}_{i}')
            if zh is None:
                zh = self.tb.text(self.bank_aud, f'{group}_{i:02d}')
            if zh:
                lines.append({'n': i, 'zh': zh})
        self._conv[group] = lines
        return lines

    def is_conv(self, key):
        if not re.fullmatch(r'[A-Z0-9]{2,}(?:_[A-Z0-9]{1,}){0,4}', key):
            return False
        lines = self.conv_lines(key)
        return len(lines) > 0

    def func_at(self, line):
        best = None
        for fn, (a, b) in self.s.funcs.items():
            if a <= line <= b:
                if best is None or (b - a) < (self.s.funcs[best][1] - self.s.funcs[best][0]):
                    best = fn
        return best or '(top)'

    def table_of(self, fn):
        """index -> 对话键 的查表函数（case N: sVar0.f_0 = \"KEY\";）"""
        if fn in self._tables:
            return self._tables[fn]
        body = self.s.body(fn)
        m = {}
        if body and 'switch' in chr(10).join(body[:8]):
            cur = None
            for ln in body:
                cm = CASE_LBL.match(ln)
                if cm:
                    cur = int(cm.group(1))
                    continue
                if cur is None:
                    continue
                sm = re.search(r'=\s*"([A-Z0-9_]{4,})"', ln)
                if sm and cur not in m:
                    m[cur] = sm.group(1)
        self._tables[fn] = m or None
        return self._tables[fn]

    # ---------------- 单行 ----------------
    def line_events(self, ln, no):
        ev = []
        for m in GXT.finditer(ln):
            key, en = m.group(1), clean(m.group(2))
            kind = classify(key)
            zh = self.tb.text(self.bank_txt, key) or self.tb.text(self.bank_aud, key)
            if kind == 'text' and not zh:
                continue                     # 记
            ev.append({'t': kind, 'key': key, 'zh': zh or '', 'en': en, 'line': no})
        for m in ANIM_PL.finditer(ln):
            ev.append({'t': 'animscene', 'name': m.group(1), 'line': no})
        if 'CREATE_PED(' in ln or 'CREATE_VEHICLE(' in ln or 'CREATE_OBJECT(' in ln:
            what = 'ped' if 'CREATE_PED(' in ln else ('vehicle' if 'CREATE_VEHICLE(' in ln else 'object')
            m = HASH_MODEL.search(ln)
            ev.append({'t': 'spawn', 'what': what,
                       'model': (m.group(1) or m.group(2)) if m else '',
                       'line': no})
        for m in STR.finditer(ln):
            k = m.group(1)
            if self.is_conv(k):
                ev.append({'t': 'conv', 'group': k, 'line': no,
                           'lines': len(self.conv_lines(k))})
        # 间接触发：func_table(cParam0, 42) → 查表拿到对白组
        for m in CALL_TABLE.finditer(ln):
            tab = self.table_of(m.group(1))
            if not tab:
                continue
            key = tab.get(int(m.group(2)))
            if key and self.is_conv(key):
                ev.append({'t': 'conv', 'group': key, 'line': no,
                           'lines': len(self.conv_lines(key)), 'via': 'table'})
        return ev

    def func_events(self, fn, depth=0, stack=()):
        """函数内事件（含一层被调函数展开，用于 wrapper）。"""
        if fn in stack or depth > 2 or fn not in self.s.funcs:
            return []
        body = self.s.body(fn)
        base = self.s.funcs[fn][0]
        ev = []
        for off, ln in enumerate(body):
            ev.extend(self.line_events(ln, base + off))
        if not any(e['t'] in ('conv', 'objective') for e in ev):
            for ln in body:
                for m in CALL_FUNC.finditer(ln):
                    g = m.group(1)
                    if g != fn:
                        ev.extend(self.func_events(g, depth + 1, stack + (fn,)))
        return dedupe(ev)

    # ---------------- 整个任务 ----------------
    def relevant(self, fn):
        body = self.s.body(fn)
        return any(self.is_conv(k) for ln in body for k in STR.findall(ln)) or \
               any(self.tb.text(self.bank_txt, k) for ln in body
                   for k in [m.group(1) for m in GXT.finditer(ln)])

    def compile(self):
        seqs = []
        for fn in self.s.funcs:
            body_txt = "\n".join(self.s.body(fn))
            # beat 函数一定拿 cParam0（任务结构体）；纯文本查表函数是 switch(iParam0){return "KEY"}
            if 'cParam0' not in body_txt:
                continue
            cs = self.s.cases(fn)
            if len(cs) < 2:
                continue
            n_next = sum(1 for c in cs if any(NEXT_SET.search(l) or STATE_SET.search(l) for l in c[1]))
            if n_next < 1:
                continue
            # 演出场景表（pl_/script@ 一大堆、且几乎没有对白）不是 beat 机
            n_anim = sum(len(ANIM_PL.findall(l)) for c in cs for l in c[1])
            if n_anim > 15:
                n_conv = sum(1 for c in cs for l in c[1] for m in STR.finditer(l)
                             if self.is_conv(m.group(1)))
                if n_conv < 3:
                    continue
            cases = []
            hit = False
            for num, lines, start in cs:
                ev = []
                nested = []
                nxt = None
                consts = {}
                for off, ln in enumerate(lines):
                    ev.extend(self.line_events(ln, start + off))
                    ca = CONST_ASSIGN.match(ln)
                    if ca:
                        consts[ca.group(1)] = int(ca.group(2))
                    for m in TABLE_CALL_VAR.finditer(ln):
                        tab = self.table_of(m.group(1))
                        v = consts.get(m.group(2))
                        if tab and v in tab:
                            key = tab[v]
                            if self.is_conv(key):
                                ev.append({'t': 'conv', 'group': key, 'line': start + off,
                                           'lines': len(self.conv_lines(key)), 'via': 'table-var'})
                    for m in CALL_FUNC.finditer(ln):
                        g = m.group(1)
                        if g in self.s.funcs and g not in nested and self.s.cases(g) and len(self.s.cases(g)) >= 2 and self.relevant(g):
                            nested.append(g)
                    if NEXT_SET.search(ln) or STATE_SET.search(ln):
                        m = NEXT_SET.search(ln)
                        nxt = int(m.group(1)) if m else -1
                ev = dedupe(ev)
                if any(e['t'] in ('conv', 'objective') for e in ev):
                    hit = True
                cases.append({'case': num, 'line': start, 'next': nxt,
                              'events': ev, 'nested': nested})
            if not hit:
                continue
            seqs.append({'func': fn, 'line': self.s.funcs[fn][0], 'cases': cases})
        if not seqs:
            # 兜底：没有可识别 beat 机 → 按「所属函数」分块（每个函数通常就是一个 beat），
            # 块内按行序、块间按函数起始行排序。仍不是严格时序，但比一坨平铺强。
            groups = OrderedDict()
            for off, ln in enumerate(self.s.lines):
                ev = self.line_events(ln, off + 1)
                if not ev:
                    continue
                fn = self.func_at(off + 1)
                groups.setdefault(fn, []).append((off + 1, ev))
            seqs = []
            for fn, items in sorted(groups.items(), key=lambda kv: self.s.funcs.get(kv[0], (0, 0))[0]):
                ev = []
                for _, e in sorted(items):
                    ev.extend(e)
                ev = dedupe(ev)
                if not any(x['t'] in ('conv', 'objective') for x in ev):
                    continue
                seqs.append({'func': fn, 'line': self.s.funcs.get(fn, (0, 0))[0], 'rank': (0,),
                             'cases': [{'case': 0, 'line': 0, 'next': None,
                                        'events': ev, 'nested': []}]})
            if not seqs:
                ev = []
                for off, ln in enumerate(self.s.lines):
                    ev.extend(self.line_events(ln, off + 1))
                seqs = [{'func': '(file_scan)', 'line': 0, 'rank': (0,),
                         'cases': [{'case': 0, 'line': 0, 'next': None,
                                    'events': dedupe(ev), 'nested': []}]}]
            callers = {}
        else:
            callers = build_callers(self.s)
        for sq in seqs:
            if sq['func'] in ('(file_scan)', '(top)'):
                sq['rank'] = (0,)
            else:
                sq['rank'] = flow_rank(self.s, sq['func'], callers)
        seqs.sort(key=lambda x: x['rank'])
        # 嵌套展开：cases 里 nested 的 beat 函数，直接内联到该 case 下
        for s in seqs:
            for c in s['cases']:
                sub = []
                for g in c['nested']:
                    if any(x['func'] == g for x in seqs) and g != s['func']:
                        sub.append(g)
                c['nested'] = sub
        # 兜底：整脚本扫一遍，把没进 beat 的对白组也收进来（标 loose，不参与时序）
        loose = OrderedDict()
        for off, ln in enumerate(self.s.lines):
            for m in STR.finditer(ln):
                k = m.group(1)
                if self.is_conv(k):
                    loose.setdefault(k, off + 1)
        convs = OrderedDict()
        for s in seqs:
            for c in s['cases']:
                for e in c['events']:
                    if e['t'] == 'conv':
                        convs.setdefault(e['group'], self.conv_lines(e['group']))
        loose_only = OrderedDict((k, self.conv_lines(k)) for k in loose if k not in convs)
        for k, v in loose_only.items():
            convs[k] = v
        return {'id': self.tid, 'script': self.s.name, 'sequences': seqs,
                'conversations': convs,
                'loose': {k: loose[k] for k in loose_only},
                'stats': {'sequences': len(seqs),
                          'beats': sum(len(s['cases']) for s in seqs),
                          'conversations': len(convs),
                          'dialogue_lines': sum(len(v) for v in convs.values()),
                          'objectives': sum(1 for s in seqs for c in s['cases']
                                            for e in c['events'] if e['t'] == 'objective'),
                          'loose_conversations': len(loose_only),
                          'loose_lines': sum(len(v) for v in loose_only.values()),
                          'structure': ('file' if (len(seqs) == 1 and seqs[0]['func'] == '(file_scan)')
                                        else ('cases' if any(len(x['cases']) > 1 for x in seqs)
                                              else 'functions'))}}


def classify(key):
    k = key.upper()
    if '_OBJ' in k or 'OBJECTIVE' in k:
        return 'objective'
    if 'FAIL' in k:
        return 'fail'
    if 'HELP' in k or '_TIP' in k:
        return 'help'
    return 'text'


def dedupe(ev):
    seen, out = set(), []
    for e in ev:
        k = (e['t'], e.get('key') or e.get('group') or e.get('name') or e.get('model'))
        if k in seen:
            continue
        seen.add(k)
        out.append(e)
    return out


# --------------------------------------------------------------------------- #
def build_map(ids, cache=os.path.join(ROOT, 'export/story/script_map.json')):
    """一次扫全部脚本，统计每个「文本键前缀」出现次数，再给每个任务挑最优脚本。"""
    import collections
    if os.path.exists(cache):
        try:
            m = json.load(open(cache, encoding='utf-8'))
            if all(i in m for i in ids):
                return {k: tuple(v) for k, v in m.items() if k in ids}
        except Exception:
            pass
    pref = re.compile(r'"([A-Z0-9]{3,20})_[A-Z0-9_]+"')
    per_file = {}
    for f in os.listdir(SRC_DIR):
        if not f.endswith('.c'):
            continue
        try:
            txt = open(os.path.join(SRC_DIR, f), encoding='utf-8', errors='ignore').read()
        except OSError:
            continue
        per_file[f] = collections.Counter(pref.findall(txt))
    mapping = {}
    for tid in ids:
        best, best_n = None, 0
        for f, c in per_file.items():
            n = c.get(tid, 0)
            if n > best_n:
                best, best_n = f, n
        if best:
            mapping[tid] = (best, best_n)
    os.makedirs(os.path.dirname(cache), exist_ok=True)
    json.dump(mapping, open(cache, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    return mapping


def render_md(d):
    L = [f'# {d.get("title_zh")} `{d["id"]}` — {d.get("title_en")}', '']
    L.append(f'> 章：{d.get("chapter_name")}　类别：{d.get("category")}　脚本：`{d["script"]}`')
    L.append(f'> 片段序列 {d["stats"]["sequences"]}　beat {d["stats"]["beats"]}　'
             f'对白组 {d["stats"]["conversations"]}（{d["stats"]["dialogue_lines"]} 行）　目标 {d["stats"]["objectives"]}')
    L.append('')
    for s in d['sequences']:
        L.append(f'## 序列 `{s["func"]}`（源文件行 {s["line"]}）')
        for c in s['cases']:
            ev = c['events']
            if not any(e['t'] in ('objective', 'conv') for e in ev):
                continue
            L.append(f'\n### case {c["case"]}' + (f' → 下一 case {c["next"]}' if c['next'] is not None else ''))
            for e in ev:
                if e['t'] == 'objective':
                    L.append(f'- 🎯 **{e["zh"]}**')
                elif e['t'] == 'animscene':
                    L.append(f'- 🎬 `{e["name"]}`')
                elif e['t'] == 'spawn':
                    L.append(f'- 👤 生成 {e["what"]} `{e["model"]}`')
            groups = [e['group'] for e in ev if e['t'] == 'conv']
            for g in groups:
                L.append(f'- 💬 `{g}`')
                for ln in d['conversations'][g]:
                    L.append(f'  - {ln["zh"]}')
    return '\n'.join(L)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--id', action='append')
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--out', default=OUT)
    ap.add_argument('--no-md', action='store_true')
    args = ap.parse_args()

    meta = json.load(open(os.path.join(ROOT, 'export/levels/world/missions_story.json'), encoding='utf-8'))
    import csv as _csv
    banks = {}
    _idx = os.path.join(ROOT, 'export/levels/world/mission_dialogue_index.csv')
    if os.path.exists(_idx):
        for row in _csv.DictReader(open(_idx, encoding='utf-8-sig')):
            banks[row['mission_id']] = row['audio_bank']
    objs = {}
    _op = os.path.join(ROOT, 'export/levels/world/mission_objectives.json')
    if os.path.exists(_op):
        _raw = json.load(open(_op, encoding='utf-8'))
        for mid, v in _raw.items():
            objs[mid] = {'objectives': v.get('objective', []), 'fails': v.get('fail', [])}
    tb = TextBank()
    ids = args.id or [r['id'] for r in meta]
    mapping = build_map(ids)
    os.makedirs(args.out, exist_ok=True)
    done = 0
    rows = []
    _scripts = {}
    for r in meta:
        tid = r['id']
        if args.id and tid not in args.id:
            continue
        if tid not in mapping or mapping[tid][1] < 3:
            continue
        if mapping[tid][0] not in _scripts:
            _scripts[mapping[tid][0]] = Script(os.path.join(SRC_DIR, mapping[tid][0]))
        sc = _scripts[mapping[tid][0]]
        ex = Extractor(sc, tid, tb, banks.get(tid))
        d = ex.compile()
        d['objectives_all'] = objs.get(tid, {})
        d.update({'title_zh': r.get('title_zh'), 'title_en': r.get('title_en'),
                  'chapter': r.get('chapter'), 'chapter_name': r.get('chapter_name'),
                  'category': r.get('category'), 'cast': r.get('cast', []),
                  'map_score': mapping[tid][1]})
        d['stats']['fallback'] = any(s['func'] == '(file_scan)' for s in d['sequences'])
        with open(os.path.join(args.out, f'{tid}.json'), 'w', encoding='utf-8') as f:
            json.dump(d, f, ensure_ascii=False, indent=1)
        if not args.no_md:
            with open(os.path.join(args.out, f'{tid}.md'), 'w', encoding='utf-8') as f:
                f.write(render_md(d))
        st = d['stats']
        rows.append({'id': tid, 'script': mapping[tid][0], **st})
        print(f'{tid:12s} {mapping[tid][0]:30s} seq={st["sequences"]:3d} beat={st["beats"]:4d} '
              f'conv={st["conversations"]:3d} lines={st["dialogue_lines"]:5d} obj={st["objectives"]:4d}')
        done += 1
        if args.limit and done >= args.limit:
            break
    print(f'\n== {done} -> {args.out}')
    if rows:
        import csv
        with open(os.path.join(ROOT, 'export/story/beats_index.csv'), 'w', newline='', encoding='utf-8-sig') as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)


if __name__ == '__main__':
    main()
