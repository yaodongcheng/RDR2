"""RDR2 资产 ⇄ **CodeWalker XML**（CW XML）读写 —— 自建，不依赖 CodeX。

## 这里说的"XML"到底是什么

社区教程里的 `.ydr.xml` / `.ydd.xml` / `.ymap.xml` = **CodeWalker XML（CW XML）**：
由 CodeWalker（GTA V）/ **CodeX**（RDR2，dexyfex，闭源）把二进制资产"反编译"成的**纯文本中间格式**，
用来在 Blender（Sollumz / RedDeadBlend2）里看/改，再用同一工具编回二进制。
社区链路：`RPF → (RSC8→RSC7) → CodeX → CW XML → Blender(Sollumz) → 编回 → LML 替换`。

**它没有加密、没有二进制负载，就是普通 XML + 空格分隔的数字** ⇒ **可解读**。
本模块用 `tools/ref/Sollumz-RDR-main/cwxml/`（Sollumz-RDR 的 XML 类定义）作为**权威 schema**：

```
<Drawable version="1">
  <Name/> <Hash/> <BoundingSphereCenter x y z/> <BoundingSphereRadius/>
  <BoundingBoxMin x y z/> <BoundingBoxMax x y z/>
  <LodDistHigh/> <LodDistMed/> <LodDistLow/> <LodDistVlow/>
  <ShaderGroup>
    <TextureDictionary version="1">
      <Item><Name/><Width/><Height/><MipLevels/><Format/><FileName/></Item>
    </TextureDictionary>
    <Shaders>
      <Item><Name>shader 名</Name><DrawBucket/><DrawBucketFlag/>
        <Parameters><BufferSizes/><Items>
          <Item name="diffusetexture_layer0" type="Texture" texture="hea_grass_val_01_abte" index="1" flags="0"/>
          <Item name="..." type="CBuffer" buffer="0" offset="0" length="4"/>
          <Item name="..." type="Sampler" index="0" sampler="3"/>
          <Item name="..." type="Unknown" index="0"/>
        </Items></Parameters>
      </Item>
    </Shaders>
  </ShaderGroup>
  <Skeleton><Bones>…</Bones></Skeleton>
  <ExtraSkeletons/>
  <LodHigh><Models><Item>…</Item></Models></LodHigh>   (LodMed/LodLow/LodVeryLow 同构)
  <Bounds type="…">…</Bounds>
</Drawable>
```

`<Item>`（LOD 模型）：
```
<Item><Flags/><HasSkin/><BoneIndex/><BonesCount/><BoneMapping/>
  <BoundingBoxMin/><BoundingBoxMax/>
  <Geometries><Item>
      <BoundingBoxMin/><BoundingBoxMax/>
      <ShaderID/>            ← 该几何体用 ShaderGroup 里第几个 shader
      <ColourSemantic/>      ← 只有地形（terrain_uber_*）才写，= 1
      <BoneIndex/><BonesCount/>
      <VertexLayout>
        <Formats>  每个元素一位数字（Sollumz 惯例：P=3 N=9 X=9 W=5 I=6 C=5 T=2）
        <NonInterleaved>True</NonInterleaved>   ← RDR2 是 SOA
        <Semantics>PNXCTT</Semantics>           ← 每个元素一个字母
      </VertexLayout>
      <Vertices>  每行一个顶点，属性组间用 TAB，组内用空格
      <Indices>   空格分隔，24 个一行
  </Item></Geometries>
</Item>
```

`.ydd` → `<RDR2DrawableDictionary version="1"><Drawables><Item><Drawable>…</Drawable></Item>…`

## 为什么我们自己就能做（不需要 CodeX / 不需要 Blender 插件）

CodeX 是闭源的，所以社区只能靠它产 XML；**而我们已经能原生解析 RSC8**
（`rdr2_ydr.py` / `rdr2_vdecl.py` / `rdr2_ytd.py` / `rdr2_shader_params.py`）
⇒ 本模块直接把二进制的数据**写成同一套 XML**（导出给 Blender 用），
也能把 XML **读回来**（修改后由我们自己的打包器回写二进制）。
Blender 插件（Sollumz / RedDeadBlend2）只是"可视化编辑器"，**不是解读 XML 的必要条件**。

用法：
    python rdr2_cwxml.py <file.ydr|ydd|yft> <out.xml> [--max-verts N]
    python rdr2_cwxml.py --read <file.xml>          # 反向解读并打印摘要
"""
import os
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rdr2_ydr as Y
import rdr2_vdecl as V
import rdr2_shader_params as SP

# ---- 元素下标 → 语义字母（与 sgaInputLayout 的元素顺序一致）----
SEM_LETTER = V.SEM_LETTER
# 语义字母 → Formats 数字（Sollumz-RDR `ydr/ydrexport.py` 的 layout_map 惯例）
FMT_DIGIT = {'P': '3', 'N': '9', 'X': '9', 'W': '5', 'I': '6', 'C': '5', 'T': '2'}

LODS = [('LodHigh', 'high'), ('LodMed', 'med'), ('LodLow', 'low'), ('LodVeryLow', 'vlow')]


def _fmt_num(x):
    if isinstance(x, int):
        return str(x)
    return f'{x:.7f}'


def _vec(tag, vals):
    e = ET.Element(tag)
    for k, v in zip('xyz', vals):
        e.set(k, _fmt_val(v))
    return e


def _fmt_val(v):
    return f'{v:.7f}' if isinstance(v, float) else str(v)


# ----------------------------------------------------------------------------- 导出
def build_shader_group(res, sg_ptr):
    """→ <ShaderGroup>"""
    grp = ET.Element('ShaderGroup')
    # 纹理字典：只列 shader 引用到的贴图名（含 W/H/Format，来自纹理描述符）
    tdict = ET.SubElement(grp, 'TextureDictionary')
    tdict.set('version', '1')
    shaders = ET.SubElement(grp, 'Shaders')
    seen = set()
    for i, reflist in enumerate(Y.parse_shader_group(res, sg_ptr)):
        si = ET.SubElement(shaders, 'Item')
        h = Y.parse_shader_hashes(res, sg_ptr)
        nm = h[i]['name'] if i < len(h) and h[i]['name'] else ''
        ET.SubElement(si, 'Name').text = nm
        ET.SubElement(si, 'DrawBucket').text = '0'
        ET.SubElement(si, 'DrawBucketFlag').text = 'false'
        params = ET.SubElement(si, 'Parameters')
        ET.SubElement(params, 'BufferSizes').text = '0'
        items = ET.SubElement(params, 'Items')
        for t in reflist:
            it = ET.SubElement(items, 'Item')
            it.set('name', t['param'] or '')
            it.set('type', 'Texture')
            it.set('texture', t['name'])
            it.set('index', str(t['slot']))
            it.set('flags', '0')
            key = (t['name'], t['w'], t['h'], t['fmt'])
            if t['name'] and t['name'].lower().startswith('blank'):
                continue
            if t['w'] and t['h'] and key not in seen:
                seen.add(key)
                ti = ET.SubElement(tdict, 'Item')
                ET.SubElement(ti, 'Name').text = t['name']
                ET.SubElement(ti, 'Width').text = str(t['w'])
                ET.SubElement(ti, 'Height').text = str(t['h'])
                ET.SubElement(ti, 'MipLevels').text = '0'
                code = (t['fmt'] >> 24) & 0xFF
                ET.SubElement(ti, 'Format').text = '%d' % code
                ET.SubElement(ti, 'FileName').text = ''
    return grp


def build_geometry(res, gi, vb, ib, vd, shader_id, shader_name, max_verts=None):
    """→ <Item>（Geometries 里的一个几何体）"""
    g = ET.Element('Item')
    pos = V.read_element(res, vb['data'], vd, 0, limit=max_verts)
    if not pos:
        return None
    xs = [p[0] for p in pos]
    ys = [p[1] for p in pos]
    zs = [p[2] for p in pos]
    g.append(_vec('BoundingBoxMin', (min(xs), min(ys), min(zs))))
    g.append(_vec('BoundingBoxMax', (max(xs), max(ys), max(zs))))
    ET.SubElement(g, 'ShaderID').text = str(shader_id)

    specs = V.elements(vd)                       # [(idx, name, fmt, comps, off, step)]
    letters = ''.join(SEM_LETTER.get(i, '?') for i, *_ in specs)
    first_colour = next((i for i, *_ in specs if SEM_LETTER.get(i) == 'C'), None)
    if first_colour == 25:                       # 没有 COLOR0、从 COLOR1 起（地形）
        ET.SubElement(g, 'ColourSemantic').text = '1'
    ET.SubElement(g, 'BoneIndex').text = '-1'
    ET.SubElement(g, 'BonesCount').text = '0'

    lay = ET.SubElement(g, 'VertexLayout')
    ET.SubElement(lay, 'Formats').text = ''.join(FMT_DIGIT.get(ch, '0') for ch in letters)
    ET.SubElement(lay, 'NonInterleaved').text = 'True' if vd['hassoa'] else 'False'
    ET.SubElement(lay, 'Semantics').text = letters

    # 顶点：每行一个顶点，属性组间 TAB，组内空格
    cols = [V.read_element(res, vb['data'], vd, i, limit=max_verts) for i, *_ in specs]
    lines = []
    for vi in range(len(pos)):
        groups = []
        for c in cols:
            groups.append(' '.join(_fmt_num(x) for x in c[vi]))
        lines.append('\t'.join(groups))
    ET.SubElement(g, 'Vertices').text = '\n' + '\n'.join(lines) + '\n'

    idx = Y.read_indices(res, ib) if ib else []
    rows = [idx[i:i + 24] for i in range(0, len(idx), 24)]
    ET.SubElement(g, 'Indices').text = '\n' + '\n'.join(
        ' '.join(str(i) for i in r) for r in rows) + '\n'
    return g


def build_drawable(res, base=0, name='', max_verts=None):
    """→ <Drawable>"""
    d = ET.Element('Drawable')
    d.set('version', '1')
    ET.SubElement(d, 'Name').text = name
    ET.SubElement(d, 'Hash').text = '0'
    info, _ = Y.extract_at(res, base, 'high')
    c = [(info['bbox_min'][i] + info['bbox_max'][i]) * 0.5 for i in range(3)]
    d.append(_vec('BoundingSphereCenter', c))
    ET.SubElement(d, 'BoundingSphereRadius').text = _fmt_val(info['radius'])
    d.append(_vec('BoundingBoxMin', info['bbox_min']))
    d.append(_vec('BoundingBoxMax', info['bbox_max']))
    for k in ('LodDistHigh', 'LodDistMed', 'LodDistLow', 'LodDistVlow'):
        ET.SubElement(d, k).text = '0'
    d.append(build_shader_group(res, info['shader_group']))

    shd = Y.parse_shader_hashes(res, info['shader_group'])
    any_geom = False
    for lod_tag, lod in LODS:
        lod_e = ET.SubElement(d, lod_tag)
        models_e = ET.SubElement(lod_e, 'Models')
        models = Y.pointer_list(res, res.u64(base + {'high': 0x50, 'med': 0x58, 'low': 0x60, 'vlow': 0x68}[lod]))
        for mi, m in enumerate(models):
            geoms = Y.parse_model_geoms(res, m)
            shmap = Y.parse_model_shaders(res, m, len(geoms))
            model_e = ET.SubElement(models_e, 'Item')
            ET.SubElement(model_e, 'Flags').text = '0'
            ET.SubElement(model_e, 'HasSkin').text = '0'
            ET.SubElement(model_e, 'BoneIndex').text = '0'
            ET.SubElement(model_e, 'BonesCount').text = '0'
            geoms_e = ET.SubElement(model_e, 'Geometries')
            for gi, gptr in enumerate(geoms):
                go = res.off(gptr)
                vb = Y.parse_vertex_buffer(res, res.u64(go + 0x08))
                ib = Y.parse_index_buffer(res, res.u64(go + 0x10))
                if not vb:
                    continue
                vd = V.parse_vdecl(res, res.u64(vb['off'] + 0x38))
                if not vd:
                    continue
                sid = shmap[gi] if gi < len(shmap) else 0
                sname = shd[sid]['name'] if 0 <= sid < len(shd) else ''
                ge = build_geometry(res, gi, vb, ib, vd, sid, sname, max_verts)
                if ge is not None:
                    geoms_e.append(ge)
                    any_geom = True
    if not any_geom:
        return None
    return d


def export(path, out, max_verts=None):
    res = Y.Res(open(path, 'rb').read())
    stem = os.path.splitext(os.path.basename(path))[0]
    if path.lower().endswith('.ydr'):
        root = build_drawable(res, 0, stem, max_verts)
    else:                                        # .ydd / .yft
        root = ET.Element('RDR2DrawableDictionary')
        root.set('version', '1')
        wr = ET.SubElement(root, 'Drawables')
        for h, off in Y.parse_drawable_dictionary(res) if path.lower().endswith('.ydd') else []:
            d = build_drawable(res, off, '0x%08X' % h, max_verts)
            if d is not None:
                it = ET.SubElement(wr, 'Item')
                it.append(d)
        if not list(wr):                          # .yft：取主 drawable
            inf, ms = Y.extract_frag(path)
            if inf:
                d = build_drawable(res, inf['base'], stem, max_verts)
                if d is not None:
                    it = ET.SubElement(wr, 'Item')
                    it.append(d)
            if not list(wr):
                return None
    if root is None:
        return None
    _indent(root)
    ET.ElementTree(root).write(out, encoding='UTF-8', xml_declaration=True)
    return root


def _indent(elem, level=0):
    pad = '\n' + '  ' * level
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = pad + '  '
        for i, ch in enumerate(elem):
            _indent(ch, level + 1)
            if not ch.tail or not ch.tail.strip():
                ch.tail = pad + '  ' if i < len(elem) - 1 else pad
    elif level and (not elem.tail or not elem.tail.strip()):
        elem.tail = pad


# ----------------------------------------------------------------------------- 读回（"是否可以解读"的证明）
def read(path):
    root = ET.parse(path).getroot()
    print(f'root=<{root.tag}> version={root.get("version")}')
    n_draw = 0
    for d in root.iter('Drawable'):
        n_draw += 1
        name = (d.findtext('Name') or '').strip()
        print(f'  <Drawable> {name}')
        sg = d.find('ShaderGroup')
        if sg is not None:
            for s in sg.iter('Item'):
                if s.get('type') == 'Texture':
                    print(f'     param {s.get("name"):<28} slot={s.get("index"):<3} tex={s.get("texture")}')
        for lod in ('LodHigh', 'LodMed', 'LodLow', 'LodVeryLow'):
            for gm in d.iter(lod):
                for ge in gm.iter('Item'):
                    if ge.find('Vertices') is None:
                        continue
                    layers = ge.find('VertexLayout')
                    sem = (layers.findtext('Semantics') or '').strip() if layers is not None else '?'
                    nonint = (layers.findtext('NonInterleaved') or '').strip() if layers is not None else ''
                    vs = (ge.findtext('Vertices') or '').strip().split('\n')
                    ins = (ge.findtext('Indices') or '').split()
                    print(f'     {lod} geom shaderID={ge.findtext("ShaderID")} semantics={sem} '
                          f'nonInterleaved={nonint} verts={len([v for v in vs if v.strip()])} '
                          f'indices={len(ins)} first_vertex="{vs[0][:60] if vs else ""}"')
    print(f'  共 {n_draw} 个 Drawable')
    return root


if __name__ == '__main__':
    if '--read' in sys.argv:
        read(sys.argv[sys.argv.index('--read') + 1])
    else:
        src, out = sys.argv[1], sys.argv[2]
        mv = None
        if '--max-verts' in sys.argv:
            mv = int(sys.argv[sys.argv.index('--max-verts') + 1])
        r = export(src, out, mv)
        print('wrote', out, os.path.getsize(out), 'bytes' if r is not None else '(空)')
