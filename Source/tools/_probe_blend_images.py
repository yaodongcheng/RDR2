# -*- coding: utf-8 -*-
"""探针：列出一个 .blend 里所有 image 的 name / filepath / packed。"""
import bpy
print('IMAGES', len(bpy.data.images))
for im in list(bpy.data.images)[:30]:
    print('IMG', repr(im.name), '|', repr(im.filepath), '| packed=', bool(im.packed_file))
print('MATERIALS', len(bpy.data.materials))
