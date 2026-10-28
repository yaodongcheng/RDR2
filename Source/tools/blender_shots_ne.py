import bpy, sys, os, importlib.util
ROOT = r'D:/BrainMaker/大镖客2解包分析'
spec = importlib.util.spec_from_file_location('bc', os.path.join(ROOT, 'tools/blender_continent.py'))
bc = importlib.util.module_from_spec(spec); spec.loader.exec_module(bc)
argv = sys.argv
outdir = argv[argv.index('--') + 1]
os.makedirs(outdir, exist_ok=True)
VIEWS = [
    ('ne_from_sw', (1200, -3000, 2500), (3300, 1500, 150), 35, None),
    ('ne_top', (3400, 1000, 6000), (3400, 1000, 0), 35, 5200),
]
sc = bpy.context.scene
sc.render.resolution_x, sc.render.resolution_y = 1600, 900
sc.render.engine = 'BLENDER_EEVEE'
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
print('DONE')
