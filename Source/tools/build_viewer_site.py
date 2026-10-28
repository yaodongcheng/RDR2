#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""构建「RDR2 解包成果总览」查看器的数据与文档页。

输出：
  export/viewer/site.json          统一数据（任务/武器/道具/NPC/据点/过场/文档/图集）
  export/viewer/docs/*.html        Markdown 文档的渲染页
"""
import csv
import html
import json
import os
import re
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W = lambda *p: os.path.join(ROOT, *p)
OUT = W('export/viewer')
DOCS_OUT = os.path.join(OUT, 'docs')


# ---------------------------------------------------------------- markdown
def md_inline(s):
    s = html.escape(s)
    s = re.sub(r'`([^`]+)`', r'<code>\1</code>', s)
    s = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', s)
    s = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2" target="_blank" rel="noopener">\1</a>', s)
    return s


def render_md(text, title):
    lines = text.split('\n')
    out = []
    toc = []
    i = 0
    in_code = False
    code_buf = []
    list_buf = []
    table_buf = []

    def flush_list():
        if list_buf:
            out.append('<ul>' + ''.join('<li>%s</li>' % md_inline(x) for x in list_buf) + '</ul>')
            list_buf.clear()

    def flush_table():
        if not table_buf:
            return
        rows = [r for r in table_buf if not re.match(r'^\s*\|[\s:\-|]+\|\s*$', r)]
        cells = [[c.strip() for c in r.strip().strip('|').split('|')] for r in rows]
        if cells:
            out.append('<table><thead><tr>' + ''.join('<th>%s</th>' % md_inline(c) for c in cells[0]) + '</tr></thead><tbody>')
            for r in cells[1:]:
                out.append('<tr>' + ''.join('<td>%s</td>' % md_inline(c) for c in r) + '</tr>')
            out.append('</tbody></table>')
        table_buf.clear()

    while i < len(lines):
        ln = lines[i]
        if ln.strip().startswith('```'):
            if in_code:
                out.append('<pre><code>' + html.escape('\n'.join(code_buf)) + '</code></pre>')
                code_buf = []
                in_code = False
            else:
                flush_list(); flush_table()
                in_code = True
            i += 1
            continue
        if in_code:
            code_buf.append(ln)
            i += 1
            continue
        if ln.startswith('|') and '|' in ln[1:]:
            flush_list()
            table_buf.append(ln)
            i += 1
            continue
        else:
            flush_table()
        m = re.match(r'^(#{1,6})\s+(.*)$', ln)
        if m:
            flush_list()
            lvl = len(m.group(1))
            txt = m.group(2).strip()
            hid = 'h%d-%d' % (lvl, len(toc))
            toc.append((lvl, txt, hid))
            out.append('<h%d id="%s">%s</h%d>' % (lvl, hid, md_inline(txt), lvl))
            i += 1
            continue
        if re.match(r'^\s*[-*]\s+', ln):
            list_buf.append(re.sub(r'^\s*[-*]\s+', '', ln))
            i += 1
            continue
        if re.match(r'^\s*\d+\.\s+', ln):
            list_buf.append(re.sub(r'^\s*\d+\.\s+', '', ln))
            i += 1
            continue
        if ln.strip().startswith('>'):
            flush_list()
            out.append('<blockquote>%s</blockquote>' % md_inline(ln.strip().lstrip('>').strip()))
            i += 1
            continue
        if re.match(r'^\s*---+\s*$', ln):
            flush_list(); out.append('<hr>'); i += 1; continue
        if not ln.strip():
            flush_list(); i += 1; continue
        flush_list()
        out.append('<p>%s</p>' % md_inline(ln))
        i += 1
    flush_list(); flush_table()
    if in_code:
        out.append('<pre><code>' + html.escape('\n'.join(code_buf)) + '</code></pre>')

    nav = ''.join('<a class="toc-l%d" href="#%s">%s</a>' % (lvl, hid, html.escape(t)) for lvl, t, hid in toc if lvl <= 3)
    page = """<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<title>{title}</title><meta name="viewport" content="width=device-width,initial-scale=1">
<style>
body{{margin:0;background:#f6f7f9;color:#1f2430;font:15px/1.8 "Microsoft YaHei",system-ui,sans-serif}}
.wrap{{display:flex;max-width:1180px;margin:0 auto;gap:28px;padding:28px 20px}}
nav{{position:sticky;top:20px;align-self:flex-start;width:240px;flex:0 0 240px;background:#fff;border:1px solid #e3e6ec;border-radius:10px;padding:14px;max-height:calc(100vh - 40px);overflow:auto}}
nav b{{display:block;margin-bottom:8px;color:#5b6475;font-size:12px;letter-spacing:.5px}}
nav a{{display:block;color:#3b4a63;text-decoration:none;font-size:13px;padding:3px 0;border-left:2px solid transparent;padding-left:8px}}
nav a:hover{{color:#1e5fd0}} nav .toc-l3{{padding-left:20px;color:#6b7585}} nav .toc-l1{{font-weight:600;color:#18202e}}
article{{flex:1;min-width:0;background:#fff;border:1px solid #e3e6ec;border-radius:10px;padding:32px 38px}}
h1{{font-size:26px;margin:0 0 18px}} h2{{font-size:21px;margin:30px 0 12px;padding-bottom:6px;border-bottom:1px solid #eef0f4}}
h3{{font-size:17px;margin:22px 0 8px}} p{{margin:10px 0}} ul{{margin:8px 0 8px 22px}} li{{margin:4px 0}}
code{{background:#f1f3f7;padding:1px 5px;border-radius:4px;font-size:13px}}
pre{{background:#11151c;color:#dce3ef;padding:14px 16px;border-radius:8px;overflow:auto;font-size:12.5px;line-height:1.6}}
pre code{{background:none;padding:0;color:inherit}}
table{{border-collapse:collapse;width:100%;margin:14px 0;font-size:13.5px}}
th,td{{border:1px solid #e3e6ec;padding:7px 10px;text-align:left;vertical-align:top}}
th{{background:#f3f5f9}} tr:nth-child(even) td{{background:#fbfcfe}}
blockquote{{margin:12px 0;padding:8px 14px;border-left:3px solid #b9c6dc;background:#f7f9fc;color:#45526a}}
hr{{border:0;border-top:1px solid #e8ebf1;margin:24px 0}}
a{{color:#1e5fd0}}
@media(max-width:900px){{nav{{display:none}} article{{padding:20px}}}}
</style></head><body><div class="wrap"><nav><b>目录</b>{nav}</nav><article>{body}</article></div></body></html>"""
    return page.format(title=html.escape(title), nav=nav or '（无标题目录）', body='\n'.join(out))


def build_docs():
    os.makedirs(DOCS_OUT, exist_ok=True)
    docs = []
    skip = {'交接历史.md'}
    for fn in sorted(os.listdir(ROOT)):
        if not fn.endswith('.md') or fn in skip:
            continue
        p = os.path.join(ROOT, fn)
        if not os.path.isfile(p):
            continue
        text = open(p, encoding='utf-8', errors='ignore').read()
        m = re.search(r'^#\s+(.+)$', text, re.M)
        title = m.group(1).strip() if m else fn
        slug = re.sub(r'[^\w\u4e00-\u9fff]+', '-', fn[:-3]).strip('-')[:80]
        out = os.path.join(DOCS_OUT, slug + '.html')
        open(out, 'w', encoding='utf-8').write(render_md(text, title))
        docs.append({'file': fn, 'title': title, 'slug': slug,
                     'size': len(text.encode('utf-8')), 'lines': text.count('\n') + 1,
                     'headings': len(re.findall(r'^##\s', text, re.M))})
    docs.sort(key=lambda d: -d['lines'])
    return docs


# ---------------------------------------------------------------- data
def read_csv(path):
    with open(path, encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))


def main():
    data = json.load(open(W('export/viewer/data.json'), encoding='utf-8'))
    sett = json.load(open(W('export/levels/world/settlements_bannerlord.json'), encoding='utf-8'))
    factions = sett['factions']
    settlements = sett['settlements']

    npcs = read_csv(W('export/npc/index.csv'))
    for n in npcs:
        n['glb'] = '../npc/' + n['glb'].replace('\\', '/')

    cutscene_clips = json.load(open(W('work/story/cutscene_clip_stats.json'), encoding='utf-8'))
    cs_cast = {r['cutscene_pkg']: r for r in read_csv(W('export/levels/world/cutscene_cast.csv'))}
    cutscenes = []
    for pkg, st in sorted(cutscene_clips.items()):
        row = cs_cast.get(pkg, {})
        cutscenes.append({'pkg': pkg, 'clips': st['clips'],
                          'missions': row.get('mission_ids', ''),
                          'cast_count': int(row.get('cast_count') or 0)})

    sched = json.load(open(W('export/levels/world/mission_schedule.json'), encoding='utf-8')) if os.path.exists(W('export/levels/world/mission_schedule.json')) else {}

    docs = build_docs()

    site = {
        'meta': {
            'built_at': time.strftime('%Y-%m-%d %H:%M'),
            'missions': len(data['missions']),
            'main_missions': sum(1 for m in data['missions'] if m.get('chapter')),
            'settlements': len(settlements),
            'factions': len(factions),
            'npcs': len(npcs),
            'weapons': len(data['weapons']),
            'items': len(data['items']),
            'cutscenes': len(cutscenes),
            'dialogue_lines': sum(m.get('dialogue_lines', 0) for m in data['missions']),
            'docs': len(docs),
            'scripted_missions': sum(1 for m in data['missions'] if m.get('script_file')),
            'objective_count': sum(len(m.get('script_objectives') or []) for m in data['missions']),
            'schedule_spawns': sum(len(v['spawns']) for v in sched.values()),
            'schedule_tasks': sum(sum(v['task_counts'].values()) for v in sched.values()),
            'schedule_anims': sum(v['anim_calls'] for v in sched.values()),
            'schedule_stages': sum(len(v['stages']) for v in sched.values()),
        },
        'weapons': data['weapons'],
        'items': data['items'],
        'missions': data['missions'],
        'unmatched_dialogue': data['unmatched_dialogue'],
        'factions': factions,
        'settlements': settlements,
        'npcs': npcs,
        'cutscenes': cutscenes,
        'docs': docs,
        'galleries': {
            'world': [
                {'src': '../levels/world/world_map_848.png', 'title': '大地图（848×848 网格）'},
                {'src': '../levels/world/settlements_map.png', 'title': '43 个据点分布'},
                {'src': '../levels/world/faction_map.png', 'title': '8 势力归属 + 村庄依附'},
            ],
            'sdn': [
                {'src': '../levels/world/blender/preview/01_overview.png', 'title': '圣丹尼斯 · 全景'},
                {'src': '../levels/world/blender/preview/02_street.png', 'title': '街道'},
                {'src': '../levels/world/blender/preview/03_market.png', 'title': '市场'},
                {'src': '../levels/world/blender/preview/04_cathedral.png', 'title': '教堂'},
                {'src': '../levels/world/blender/preview/05_harbor.png', 'title': '港口'},
                {'src': '../levels/world/blender/preview/06_trolley.png', 'title': '电车'},
                {'src': '../levels/world/blender/preview/07_block.png', 'title': '街区'},
                {'src': '../levels/world/blender/preview/08_train.png', 'title': '火车'},
            ],
        },
        'links': [
            {'title': '大地图交互查看器', 'src': '../levels/world/world_map.html', 'desc': '848² 地形 + 据点 + 瓦片'},
            {'title': '地形网格查看器', 'src': '../levels/terrain/terrain.html', 'desc': '高程网格 / 地形切片'},
            {'title': '圣丹尼斯整城报告', 'src': '../levels/world/blender/sdn_report.html', 'desc': '23,159 对象 / 62.77M 顶点'},
            {'title': 'NPC 模型查看器', 'src': '../npc/index.html', 'desc': '408 个角色 GLB'},
            {'title': 'NPC 动画查看器', 'src': '../npc/anim.html', 'desc': '骨骼动画预览'},
            {'title': '瓦伦丁整城（贴图）', 'src': '../levels/town/valentine_real.html', 'desc': '76 MB · 首次加载较慢'},
            {'title': '骨骼 / 动画实验台', 'src': '../skeleton_runtime/rdr2_actions.html', 'desc': '动作与骨架对照'},
        ],
        'data_files': [
            {'name': 'missions_story.csv', 'src': '../levels/world/missions_story.csv', 'desc': '270 条任务：标题/简介/cast/挑战'},
            {'name': 'missions.csv', 'src': '../levels/world/missions.csv', 'desc': '270 条任务定义（原始）'},
            {'name': 'mission_objectives.csv', 'src': '../levels/world/mission_objectives.csv', 'desc': '目标 + 失败条件'},
            {'name': 'mission_scripts.csv', 'src': '../levels/world/mission_scripts.csv', 'desc': '脚本文件 / 行数 / 目标数'},
            {'name': 'mission_steps.csv', 'src': '../levels/world/mission_steps.csv', 'desc': '逐步骤拆解（43 任务 / 215 步）'},
            {'name': 'mission_schedule.csv', 'src': '../levels/world/mission_schedule.csv', 'desc': '调度画像（生成点 / 行为）'},
            {'name': 'mission_dialogues.csv', 'src': '../levels/world/mission_dialogues.csv', 'desc': '对白按步骤归属（1,378 组 / 6,224 行）'},
            {'name': 'mission_events.csv', 'src': '../levels/world/mission_events.csv', 'desc': '微步骤事件流（4,725 条 TASK/CREATE/演出）'},
            {'name': 'mission_challenges.csv', 'src': '../levels/world/mission_challenges.csv', 'desc': '308 条任务挑战'},
            {'name': 'mission_cast.csv', 'src': '../levels/world/mission_cast.csv', 'desc': '任务 → 出场角色'},
            {'name': 'cutscene_cast.csv', 'src': '../levels/world/cutscene_cast.csv', 'desc': '181 过场包 → 角色'},
            {'name': 'actor_coverage.csv', 'src': '../levels/world/actor_coverage.csv', 'desc': '角色出场统计'},
            {'name': 'settlements_bannerlord.csv', 'src': '../levels/world/settlements_bannerlord.csv', 'desc': '43 据点'},
            {'name': 'npc_roster.csv', 'src': '../levels/world/npc_roster.csv', 'desc': '142 具名角色'},
            {'name': 'service_npcs.csv', 'src': '../levels/world/service_npcs.csv', 'desc': '75 条服务语音库'},
            {'name': 'weapon_models.csv', 'src': '../levels/world/weapon_models.csv', 'desc': '武器模型清单'},
            {'name': 'item_models.csv', 'src': '../levels/world/item_models.csv', 'desc': '道具模型清单'},
            {'name': 'CWeaponInfo.csv', 'src': '../levels/world/CWeaponInfo.csv', 'desc': '142 条武器 schema'},
            {'name': 'satchel_items.csv', 'src': '../levels/world/satchel_items.csv', 'desc': '3,636 条背包物品'},
        ],
    }
    json.dump(site, open(W('export/viewer/site.json'), 'w', encoding='utf-8'), ensure_ascii=False)
    print('site.json:', len(site['missions']), 'missions,', len(site['npcs']), 'npcs,',
          len(site['settlements']), 'settlements,', len(docs), 'docs')


if __name__ == '__main__':
    main()
