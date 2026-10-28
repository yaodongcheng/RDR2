"""把预览用的分块 glTF 摊平成「一行 = 一个实例的一个图元（网格）」的表。

给下游（骑砍2 / 编辑器 / DCC）用：一行就能拿到
  · 这块网格摆在哪（世界坐标 + 四元数 + 缩放）
  · 它用的漫反射 / 法线 / 高光三张贴图（相对 textures/ 的文件名）
  · 它的顶点数 / 三角数 / 局部包围盒

数据来源（唯一）：`export/previews/<town>/tiles/c*.gltf` + `.bin` + `textures/`。
glTF 里这三张图是**按材质**记录的，同一材质被多个图元共用；本表把它们展开到每一行。

用法:
  uv run python tools/build_flat_table.py                      # 默认圣丹尼斯
  uv run python tools/build_flat_table.py --town sdn --out deliverable/handoff/sdn_flat_table.csv
  uv run python tools/build_flat_table.py --town val --with-bbox 1

字段说明（坐标系 = RDR2 原生：X 东 / Y 北 / Z 上，单位米）:
  tile         分块文件名（c<k0>_<k1>.gltf）
  instance     实例名（= 模型名，同名的多个实例靠 x/y/z 区分）
  mesh,prim    该实例在 glTF 里的 meshes[i].primitives[j]
  material     材质名（= 该图元的贴图组名字）
  tex_base     漫反射贴图文件名（_ab/_al/_abal…）
  tex_normal   法线贴图（_nm.jpg；空 = 这个材质没有法线）
  tex_orm      高光/粗糙/AO 打包图（_ma_orm.jpg；空 = 没有）
  x,y,z        实例原点（世界坐标，RDR2 原生 Z-up）
  qx,qy,qz,qw  实例旋转四元数（**x,y,z,w** 顺序）
  sx,sy,sz     实例缩放
  verts,tris   该图元顶点/三角数
  bbox_min/max_*  图元局部包围盒（未乘实例变换，需自己套 x/y/z + 四元数 + 缩放）
"""
import argparse
import csv
import glob
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

HEAD = ['tile', 'instance', 'mesh', 'prim', 'material',
        'tex_base', 'tex_normal', 'tex_orm',
        'x', 'y', 'z', 'qx', 'qy', 'qz', 'qw', 'sx', 'sy', 'sz',
        'verts', 'tris',
        'bbox_min_x', 'bbox_min_y', 'bbox_min_z',
        'bbox_max_x', 'bbox_max_y', 'bbox_max_z']


def tex_name(gl, mat, slot):
    """material 上某个贴图槽 → images[].uri 的文件名（不含 textures/ 前缀）"""
    if slot == 'base':
        idx = (mat.get('pbrMetallicRoughness') or {}).get('baseColorTexture', {}).get('index')
    elif slot == 'normal':
        idx = (mat.get('normalTexture') or {}).get('index')
    else:
        p = mat.get('pbrMetallicRoughness') or {}
        idx = (p.get('metallicRoughnessTexture') or {}).get('index')
        if idx is None:
            idx = (mat.get('occlusionTexture') or {}).get('index')
    if idx is None:
        return ''
    texs = gl.get('textures') or []
    if idx >= len(texs):
        return ''
    src = texs[idx].get('source')
    if src is None:
        return ''
    uri = (gl.get('images') or [])[src].get('uri', '')
    return os.path.basename(uri)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--town', default='sdn')
    ap.add_argument('--tiles', default='', help='glTF 目录（默认 export/previews/<town>/tiles）')
    ap.add_argument('--out', default='')
    ap.add_argument('--with-bbox', type=int, default=1)
    a = ap.parse_args()

    tile_dir = a.tiles or os.path.join(ROOT, 'export/previews', a.town, 'tiles')
    out = a.out or os.path.join(ROOT, 'deliverable/handoff', a.town + '_flat_table.csv')
    files = sorted(glob.glob(os.path.join(tile_dir, '*.gltf')))
    if not files:
        sys.exit('找不到 glTF：%s' % tile_dir)

    os.makedirs(os.path.dirname(out), exist_ok=True)
    nrow = nnode = 0
    stats = dict(mat=0, base=0, nm=0, orm=0)
    with open(out, 'w', newline='', encoding='utf-8-sig') as fh:
        w = csv.writer(fh)
        w.writerow(HEAD)
        for f in files:
            gl = json.load(open(f, encoding='utf-8'))
            tile = os.path.basename(f)
            mats = gl.get('materials') or []
            meshes = gl.get('meshes') or []
            acc = gl.get('accessors') or []
            for node in gl['nodes']:
                if 'mesh' not in node:
                    continue                      # 根节点 / 空节点
                nnode += 1
                mi = node['mesh']
                t = node.get('translation', [0, 0, 0])
                q = node.get('rotation', [0, 0, 0, 1])
                s = node.get('scale', [1, 1, 1])
                for pi, pr in enumerate(meshes[mi]['primitives']):
                    m = mats[pr['material']] if 'material' in pr and pr['material'] < len(mats) else {}
                    pa = acc[pr['attributes']['POSITION']]
                    verts = pa['count']
                    tris = acc[pr['indices']]['count'] // 3 if 'indices' in pr else 0
                    bb = list(pa.get('min', [''] * 3)) + list(pa.get('max', [''] * 3)) if a.with_bbox else [''] * 6
                    w.writerow([tile, node.get('name', ''), mi, pi, m.get('name', ''),
                                tex_name(gl, m, 'base'), tex_name(gl, m, 'normal'),
                                tex_name(gl, m, 'orm'),
                                round(t[0], 3), round(t[1], 3), round(t[2], 3),
                                round(q[0], 6), round(q[1], 6), round(q[2], 6), round(q[3], 6),
                                round(s[0], 4), round(s[1], 4), round(s[2], 4),
                                verts, tris] +
                               [round(v, 3) if isinstance(v, (int, float)) else v for v in bb])
                    nrow += 1
                    stats['mat'] += 1
                    stats['base'] += 1 if tex_name(gl, m, 'base') else 0
                    stats['nm'] += 1 if tex_name(gl, m, 'normal') else 0
                    stats['orm'] += 1 if tex_name(gl, m, 'orm') else 0
    print('glTF %d 个 ｜ 实例节点 %d ｜ 表行 %d' % (len(files), nnode, nrow))
    print('  有漫反射 %d ｜ 有法线 %d ｜ 有高光 %d' % (stats['base'], stats['nm'], stats['orm']))
    print('-> %s  (%.1f MB)' % (out, os.path.getsize(out) / 1e6))


if __name__ == '__main__':
    main()
