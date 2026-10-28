"""渲染验证截图（带固定机位），用于"修前/修后"对比。

  blender -b <blend> -P tools/blender_shots_fix.py -- <outdir>
"""
import bpy
import sys
import os
import importlib.util
import math
from mathutils import Vector

ROOT = r'D:/BrainMaker/大镖客2解包分析'
spec = importlib.util.spec_from_file_location('bc', os.path.join(ROOT, 'tools/blender_continent.py'))
bc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bc)

argv = sys.argv
outdir = argv[argv.index('--') + 1] if '--' in argv else os.path.join(ROOT, 'work/verify/shots')
os.makedirs(outdir, exist_ok=True)

VIEWS = [
    ('overview', (0, -9000, 5200), (0, 0, 100), 32, None),
    ('top', (0, 0, 9000), (0, 0, 0), 32, 13000),
    ('ne_detail', (4600, -2600, 900), (3300, 1100, 60), 40, None),
    ('sw_detail', (-3000, -7000, 1400), (-5600, -6000, 120), 40, None),
    ('nw_detail', (-3000, 4500, 1600), (-5600, 2400, 200), 40, None),
]
sc = bpy.context.scene
sc.render.resolution_x, sc.render.resolution_y = 1600, 900
try:
    sc.render.engine = 'BLENDER_EEVEE'
except Exception:
    pass
sc.eevee.taa_render_samples = 16
sc.view_settings.view_transform = 'Standard'
sc.view_settings.exposure = -0.2

for name, loc, look, lens, ortho in VIEWS:
    cam = bc.add_cam(loc, look, lens, ortho)
    sc.camera = cam
    sc.render.filepath = os.path.join(outdir, name + '.png')
    bpy.ops.render.render(write_still=True)
    print('SHOT', name)
    bpy.data.objects.remove(cam, do_unlink=True)
print('DONE', outdir)
