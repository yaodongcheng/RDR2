"""对比：preview tile 里的实体 z 与大陆高度图 z，判断两者是否同一套高程基准。"""
import json, os, glob
import numpy as np

ROOT = r'D:/BrainMaker/大镖客2解包分析'
meta = json.load(open(os.path.join(ROOT, 'deliverable/heightmap/continent_height_meta.json'), encoding='utf-8'))
hm = meta['heightmap']
zmin, zmax = hm['zmin'], hm['zmax']
raw = np.fromfile(os.path.join(ROOT, 'deliverable/heightmap/continent_height_r16.raw'), dtype='<u2')
z = zmin + raw.astype(np.float32) / 65535.0 * (zmax - zmin)
z = z.reshape(hm['h'], hm['w'])
x0, y1 = meta['x0'], meta['y1']

def at(x, y):
    c = int(round((x - x0) / 4)); r = int(round((y1 - y) / 4))
    c = max(0, min(hm['w'] - 1, c)); r = max(0, min(hm['h'] - 1, r))
    return float(z[r, c])

idx = json.load(open(os.path.join(ROOT, 'export/previews/index.json'), encoding='utf-8'))['items']
for code in ('val', 'twi', 'bla', 'sdn', 'ann', 'rho'):
    it = [i for i in idx if i['code'] == code][0]
    zs = []
    for f in glob.glob(os.path.join(ROOT, f'export/previews/{code}/tiles/*.gltf'))[:6]:
        j = json.load(open(f, encoding='utf-8'))
        for n in j['nodes']:
            if 'mesh' in n and 'translation' in n:
                zs.append(n['translation'][2])
    if not zs:
        print(code, 'no nodes'); continue
    zs = np.array(zs)
    print(f"{code:5} cx={it['cx']:8.1f} cy={it['cy']:8.1f} | hmap={at(it['cx'], it['cy']):8.1f} "
          f"| tiles z: min={zs.min():8.1f} p05={np.percentile(zs,5):8.1f} med={np.median(zs):8.1f}")
