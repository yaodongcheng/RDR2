"""权重审计：按"离地高度分带"统计主导骨，检查蒙皮权重是否错位。

期望（解剖学）：
  z ≈ -0.96 ~ -0.85  靴底/脚掌 → SKEL_L_Foot(+Toe)
  z ≈ -0.85 ~ -0.55  小腿/靴筒 → SKEL_L_Calf
  z ≈ -0.50 ~ -0.10  大腿      → SKEL_L_Thigh

用法: blender -b --python tools/audit_weights.py
"""
import bpy
import os
from collections import Counter

GLB = r'D:/BrainMaker/大镖客2解包分析/export/npc/player/player_zero_walk.glb'

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=GLB)
arm = [o for o in bpy.data.objects if o.type == 'ARMATURE'][0]
# ⚠️ glTF 导入器会造一个 42 顶点的 Icosphere 占位球，不能取第一个
mesh = max([o for o in bpy.data.objects if o.type == 'MESH'], key=lambda o: len(o.data.vertices))
arm.animation_data_clear()
for pb in arm.pose.bones:
    pb.matrix_basis.identity()
bpy.context.view_layer.update()

vg = {g.index: g.name for g in mesh.vertex_groups}
mw = mesh.matrix_world
bands = [(-1.05, -0.85, '靴底/脚掌'), (-0.85, -0.60, '小腿/靴筒'),
         (-0.60, -0.40, '膝盖附近'), (-0.40, -0.05, '大腿')]
stat = {b[2]: Counter() for b in bands}
xs=[(mw @ v.co) for v in mesh.data.vertices[:2000]]
print('sample bbox x[%.2f,%.2f] z[%.2f,%.2f]'%(min(p.x for p in xs),max(p.x for p in xs),min(p.z for p in xs),max(p.z for p in xs)))
print('mesh.matrix_world=', [round(x,2) for x in mesh.matrix_world.to_translation()])
for v in mesh.data.vertices:
    if not v.groups:
        continue
    p = mw @ v.co
    z = p.z
    # 只看左腿侧（x>0）
    if p.x < 0.02:
        continue
    best = max(v.groups, key=lambda g: g.weight)
    nm = vg.get(best.group, '?')
    for lo, hi, label in bands:
        if lo <= z < hi:
            stat[label][nm] += 1
            break

print('mesh=%s verts=%d 有组=%d groups=%d' % (mesh.name, len(mesh.data.vertices),
      sum(1 for v in mesh.data.vertices if v.groups), len(mesh.vertex_groups)))
print('== 左腿按高度分带的主导骨 ==')
for lo, hi, label in bands:
    c = stat[label]
    tot = sum(c.values())
    if not tot:
        print('  %-10s (无顶点)' % label)
        continue
    top = ', '.join('%s %d%%' % (k, round(100*n/tot)) for k, n in c.most_common(4))
    print('  %-10s z[%+.2f,%+.2f] n=%-6d %s' % (label, lo, hi, tot, top))
print('AUDIT_DONE')
