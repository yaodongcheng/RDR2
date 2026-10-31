# -*- coding: utf-8 -*-
"""检查一个 blend 里的材质是否真的挂上了法线/高光（只读）。

    blender -b <blend> -P tools/_probe_maps.py

打印：材质数 / 带 normal 节点数 / 带 ORM(SeparateColor) 数 / 抽样 3 个材质的节点与属性。
"""
import bpy

mats = [m for m in bpy.data.materials if m.use_nodes]
n = len(mats)
has_nm = 0
has_orm = 0
has_ab = 0
nm_nodes = 0
sep_nodes = 0
sample = []
for m in mats:
    types = {x.type for x in m.node_tree.nodes}
    if 'NORMAL_MAP' in types:
        has_nm += 1
    if 'SEPARATE_COLOR' in types or 'SEPARATE_RGB' in types:
        has_orm += 1
    if 'TEX_IMAGE' in types:
        has_ab += 1
    nm_nodes += sum(1 for x in m.node_tree.nodes if x.type == 'NORMAL_MAP')
    sep_nodes += sum(1 for x in m.node_tree.nodes
                     if x.type in ('SEPARATE_COLOR', 'SEPARATE_RGB'))
    if len(sample) < 3 and ('NORMAL_MAP' in types or 'SEPARATE_COLOR' in types):
        links = []
        for l in m.node_tree.links:
            links.append('%s.%s -> %s.%s' % (l.from_node.type, l.from_socket.name,
                                             l.to_node.type, l.to_socket.name))
        sample.append((m.name, dict(m.items()).keys(), links[:10],
                       [x.image.filepath for x in m.node_tree.nodes
                        if x.type == 'TEX_IMAGE' and x.image]))

print('PROBE 材质 %d / 有图 %d / 带法线 %d / 带ORM %d' % (n, has_ab, has_nm, has_orm))
print('PROBE 节点 NORMAL_MAP %d / SEPARATE_COLOR %d' % (nm_nodes, sep_nodes))
for nm, k, links, imgs in sample:
    print('  材质 %s  属性=%s' % (nm, list(k)))
    for i in imgs:
        print('     img %s' % i)
    for l in links:
        print('     %s' % l)
