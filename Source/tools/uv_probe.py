"""UV 探针：把 .ydr 顶点的「位置 + 各类候选 UV」导出，并用 WebGL 页面逐候选渲染比对。

当前结论（2026-10-14）：
  * 顶点布局 = **位置：平面 f32×3**（`data[0 : 12*count]`），其余 `28 B/vert` 是别的属性。
  * `rest` 段前 4 字节当 **4×int8 SNORM** 时与「几何法线」最吻合
    （|n| 均值 1.013，|dot| 均值 0.639，30% 的面 >0.9）⇒ 疑似**打包法线**。
  * 其余 4 字节 lane（i16/u16/f16 各种解释）都还没对上 UV；
    逐三角面做「UV 是位置的仿射函数」检验会欠定（3 点 4 未知）而失效，不可用。
  * 因此改用**渲染比对**：同一贴图 + 同一模型 + 不同候选 UV → 看木纹是否沿墙面规则排列。

用法:
  python uv_probe.py <file.ydr> <out.html> [--tex <albedo.png>]
  # 生成的 out.html 里 4×N 个格子，每格一个候选 UV，直接截图比对
"""
import sys, os, json, base64, struct, io

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import numpy as np
from PIL import Image
from rdr2_ydr import Res, parse_drawable_dictionary, extract_at


def gather(res, base):
    """取第一个可解析几何的 VB/IB + 顶点位置"""
    info, ms = extract_at(res, base, 'high')
    pos = []; idx = []; b = 0
    for m in ms:
        pos += m['positions']; idx += [i + b for i in m['indices']]; b += m['vertex_count']
    return (np.array(pos, dtype=np.float32).reshape(-1, 3), np.array(idx, dtype=np.int64), b) if idx else (None, None, 0)


def main():
    ydr, out = sys.argv[1], sys.argv[2]
    tex = sys.argv[sys.argv.index('--tex') + 1] if '--tex' in sys.argv else None
    res = Res(open(ydr, 'rb').read())
    # 找 VB：用 rdr2_ydr 的几何解析拿位置；这里直接复用 extract_at 的第一个 mesh
    info, ms = extract_at(res, 0, 'high')
    if not ms:
        print("no meshes"); return
    m0 = ms[0]
    cnt = m0['vertex_count']
    # 定位该 VB 的 data 指针（用 stride/计数反查不到，改为直接用 positions 长度推断）
    # 简化：使用 parse 出的位置 + 在 body 中搜索完全相同的 12*count 字节块
    P = np.array(m0['positions'], dtype=np.float32).reshape(-1, 3)
    I = np.array(m0['indices'], dtype=np.int64)
    raw = P.tobytes()
    off = res.body.find(raw)
    print(f"positions block @0x{off:x} count={cnt} tris={len(I)//3}")
    rest = np.frombuffer(res.body[off + 12 * cnt: off + 40 * cnt], dtype=np.uint8).reshape(cnt, 28)
    cands = []
    for j in range(7):
        a = rest[:, j * 4:(j + 1) * 4].copy()
        cands.append((f"lane{j} i16snorm", a.view('<i2').astype(np.float32) / 32767.0))
        cands.append((f"lane{j} u16", a.view('<u2').astype(np.float32) / 65535.0))
    tail = rest[:, 16:28].copy().view('<f4').reshape(cnt, 3)
    cands.append(("tail f32 0,1", tail[:, :2]))
    cands.append(("tail f32 0,2", tail[:, [0, 2]]))
    page = open(os.path.join(HERE, "uv_probe_template.html"), encoding="utf-8").read()
    three = open(os.path.join(HERE, "..", "export/levels/town/three.module.js"), encoding="utf-8").read().replace("</script", "<\/script")
    texb64 = ""
    if tex and os.path.exists(tex):
        im = Image.open(tex).resize((512, 512)).convert('RGB'); bio = io.BytesIO(); im.save(bio, 'PNG')
        texb64 = base64.b64encode(bio.getvalue()).decode()
    pl = dict(POS=P.ravel().tolist(), IDX=I.ravel().tolist(),
              CANDS=[dict(name=n, uv=np.nan_to_num(np.round(v, 4)).ravel().tolist()) for n, v in cands],
              TEX=texb64)
    open(out, 'w', encoding='utf-8').write(
        page.replace('__THREE__', three).replace('__PAY__', json.dumps(pl, separators=(',', ':'))))
    print("wrote", out, len(cands), "candidates")


if __name__ == '__main__':
    main()
