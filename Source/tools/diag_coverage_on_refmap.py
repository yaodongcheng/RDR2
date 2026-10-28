"""把「我方地形覆盖」叠到官方地图上，用来判断哪些陆地/城镇我们没有地形。

产物：work/verify/coverage_on_refmap.png
用法：uv run python tools/diag_coverage_on_refmap.py
"""
import os
import json

import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None
ROOT = r'D:/BrainMaker/大镖客2解包分析'
X0, YM1, SCALE = -7684.0, 4100.0, 14.5
REF = os.path.join(ROOT, '地图下载/大陆地图_缩略.jpg')
OUT = os.path.join(ROOT, 'work/verify/coverage_on_refmap.png')
W = 1800                                   # 输出宽度


def main():
    R = json.load(open(os.path.join(ROOT, '地图下载/配准结果.json')))
    a, c, tx, ty = R['a'], R['c'], R['tx'], R['ty']

    ref = Image.open(REF).convert('RGB')
    ow = W
    oh = int(round(ref.size[1] * ow / ref.size[0]))
    ref = ref.resize((ow, oh), Image.LANCZOS)
    # 1400-scale map px -> 大图 px
    k = ow / 1400.0

    mask = np.asarray(Image.open(os.path.join(ROOT, 'export/world/world_ground_mask.png')).convert('L'))
    mh, mw = mask.shape

    # 对每个输出像素反算 u,v（很慢，改成正算：遍历我们的 mask 像素 -> 官方 px）
    ov = np.asarray(ref, dtype=np.float32).copy()
    step = 1
    # mask 像素 -> world -> uv -> ref px
    ys, xs = np.mgrid[0:mh:step, 0:mw:step]
    wx = X0 + (xs + 0.5) * 12296.0 / mw
    wy = YM1 - (ys + 0.5) * 12296.0 / mh
    u = (wx - X0) / SCALE
    v = (YM1 - wy) / SCALE
    mx = (a * u - c * v + tx) * k
    my = (c * u + a * v + ty) * k
    mi = np.clip(np.round(mx).astype(np.int32), 0, ow - 1)
    mj = np.clip(np.round(my).astype(np.int32), 0, oh - 1)
    valid = (mask > 10)
    # green where we have terrain
    for ch, val in ((0, 0.45), (1, 1.0), (2, 0.45)):
        sel = valid
        ov[mj[sel], mi[sel], ch] = ov[mj[sel], mi[sel], ch] * 0.45 + 255 * val * 0.55

    Image.fromarray(ov.astype(np.uint8)).save(OUT)
    print('→', OUT, ow, oh)


if __name__ == '__main__':
    main()
