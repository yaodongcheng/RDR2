"""临时探针：统计 sdn 范围内建筑实例数量/命名情况。"""
import os, sys, importlib.util, collections
HERE = os.path.dirname(os.path.abspath(__file__))
_s = importlib.util.spec_from_file_location('bmr', os.path.join(HERE, 'build_miniatures_real.py'))
BMR = importlib.util.module_from_spec(_s); _s.loader.exec_module(BMR)

ledger = BMR.load_ledger()
insts = BMR.load_instances()
s = [x for x in BMR.load_settlements() if x['code'] == 'sdn'][0]
print('settlement', s)
hw, hd = s['w'] / 2, s['d'] / 2
sel = [e for e in insts if abs(e[1] - s['x']) <= hw and abs(e[2] - s['y']) <= hd]
print('instances in box', len(sel))
bld = [e for e in sel if (ledger.get(e[0]) and BMR.is_building(ledger[e[0]]['name'], ledger[e[0]]['sz'], ledger[e[0]]['tris'], ledger[e[0]]['sx'], ledger[e[0]]['sy']))]
print('buildings', len(bld))
print('unique hashes', len(set(e[0] for e in bld)))
c = collections.Counter()
for e in bld:
    m = ledger[e[0]]
    print(f"  {m['name'][:48]:50} x={e[1]:8.1f} y={e[2]:8.1f} z={e[3]:7.1f} sz={m['sz']:6.1f} tris={m['tris']:7d} sc=({e[8]:.2f},{e[9]:.2f},{e[10]:.2f})")
