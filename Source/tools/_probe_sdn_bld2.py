"""临时探针：统计 sdn 范围内建筑实例前缀分布 / 面数总量。"""
import os, importlib.util, collections
HERE = os.path.dirname(os.path.abspath(__file__))
_s = importlib.util.spec_from_file_location('bmr', os.path.join(HERE, 'build_miniatures_real.py'))
BMR = importlib.util.module_from_spec(_s); _s.loader.exec_module(BMR)

ledger = BMR.load_ledger()
insts = BMR.load_instances()
s = [x for x in BMR.load_settlements() if x['code'] == 'sdn'][0]
hw, hd = s['w'] / 2, s['d'] / 2
sel = [e for e in insts if abs(e[1] - s['x']) <= hw and abs(e[2] - s['y']) <= hd]
bld = [e for e in sel if (ledger.get(e[0]) and BMR.is_building(ledger[e[0]]['name'], ledger[e[0]]['sz'], ledger[e[0]]['tris'], ledger[e[0]]['sx'], ledger[e[0]]['sy']))]
pref = collections.Counter()
tot = 0
for e in bld:
    m = ledger[e[0]]
    pref[m['name'].split('_')[0]] += 1
    tot += m['tris']
print('buildings', len(bld), 'sum tris(raw)', tot)
for k, v in pref.most_common(30):
    print(f'  {k:12} {v}')
names = sorted(set(ledger[e[0]]['name'] for e in bld))
print('unique names', len(names))
print(names[:20])
print([n for n in names if n.startswith('sd_')][:25])
