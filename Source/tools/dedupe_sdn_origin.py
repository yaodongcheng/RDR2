# -*- coding: utf-8 -*-
"""sdn.blend 体检/清理：找出「重复导入后塌在原点」的对象。

现象：同一批模型导入两次，第二份名字带 .001/.002 后缀、位置全变成 (0,0,0)，
      于是 2.3 万对象里约 1.7 万个堆在原点，看起来就是"切割板错位、桥和铁轨断掉"。

判定：名字带 .NNN 后缀 且 世界位置 |p| < 0.5 m 且 存在同名（去后缀）且位置正常 的对象。

    blender -b deliverable/blender/sdn.blend -P tools/dedupe_sdn_origin.py -- [--apply]
"""
import bpy, re, sys
from mathutils import Vector

RE_DUP = re.compile(r'^(.*)\.(\d{3})$')


def main():
    argv = sys.argv
    args = argv[argv.index('--') + 1:] if '--' in argv else []
    apply_ = '--apply' in args

    objs = [o for o in bpy.context.scene.objects if o.type == 'MESH']
    by_name = {}
    for o in objs:
        m = RE_DUP.match(o.name)
        base = m.group(1) if m else o.name
        by_name.setdefault(base, []).append(o)

    at_origin, dup_origin = [], []
    for base, lst in by_name.items():
        good = [o for o in lst if o.matrix_world.translation.length > 0.5]
        bad = [o for o in lst if o.matrix_world.translation.length <= 0.5]
        at_origin.extend(bad)
        if good:
            dup_origin.extend(bad)          # 已有正常副本 → 原点是重复垃圾
    print('[dedup] 网格 %d；精确重复组 %d' % (len(objs), len(by_name)))
    print('[dedup] 位于原点(|p|<0.5) %d，其中"已有正常副本"的重复件 %d' % (len(at_origin), len(dup_origin)))
    # 分类抽样
    import collections
    c = collections.Counter(RE_DUP.match(o.name).group(1) if RE_DUP.match(o.name) else o.name for o in dup_origin)
    print('[dedup] 重复件涉及模型 %d 种，前 10：' % len(c))
    for n, k in c.most_common(10):
        print('    %-44s %d' % (n[:44], k))
    br = [o for o in dup_origin if re.search(r'bridge|_bri|trestle|_tres', o.name, re.I)]
    rl = [o for o in dup_origin if re.search(r'railroad|railtie|_r_c_|_r_b_', o.name, re.I)]
    print('[dedup] 其中桥 %d、铁路道具 %d' % (len(br), len(rl)))
    for o in (br + rl)[:10]:
        print('     %s' % o.name)

    if not apply_:
        print('[dedup] dry-run，未删除。加 --apply 执行')
        return
    for o in dup_origin:
        bpy.data.objects.remove(o, do_unlink=True)
    print('[dedup] 已删除 %d 个，剩余网格 %d' % (
        len(dup_origin), sum(1 for o in bpy.context.scene.objects if o.type == 'MESH')))
    p = bpy.data.filepath
    bpy.ops.wm.save_mainfile()
    print('[dedup] 已保存 %s' % p)


main()
