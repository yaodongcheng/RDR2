"""从原始烘图生成"有地表数据"掩码（1 px/m），给 Blender 切掉图幅外的空白区。"""
import os, numpy as np
from PIL import Image
ROOT = r'D:/BrainMaker/大镖客2解包分析'
src = os.path.join(ROOT, 'export/world/world_ground_1p0.png')
out = os.path.join(ROOT, 'export/world/world_ground_mask.png')
g = np.asarray(Image.open(src).convert('RGB'))
m = (g.max(axis=2) > 10).astype(np.uint8) * 255
Image.fromarray(m).save(out)
print('→', out, 'valid %.1f%%' % (100.0 * (m > 0).mean()))
