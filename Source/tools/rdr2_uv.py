# -*- coding: utf-8 -*-
"""RDR2 模型 UV 的 V 约定 —— **唯一真身**（2026-11-05 实测确立，别再各写一份）。

## 结论

**RDR2 顶点 UV 是「左上原点」（DirectX 约定）：v=0 落在图片顶端。**

实测证据（`val_03_saloon_ext` 招牌子网格 / `val_genstore_ext` 整面立面）：

| 项 | 实测 |
|---|---|
| 招牌左半块 | `corr(z, v) = −1.000`，拟合 `v = −0.329·z + 0.627` ⇒ **v 随高度递减** |
| 按 v=0 在**顶端**采样 | `SMITHFIELDS.` 正立；`WORTHS. / GENERAL STORE. / FRESH BREAD / …` 六处文字全对 |
| 按 v=0 在**底端**采样 | 同一个招牌变成 `FIELDS`+`SMITH` 顺序反且上下颠倒 = 「有字但认不出」 |

⇒ 之前"招牌 UV 坏了、要改平面投影"的结论是**错的**：顶点 UV 本身完全正确，
少的只是这一次 V 翻转。平铺贴图（木板/砖墙/瓦片）近似对称，翻了看不出来，
只有文字/海报/贴花会暴露 —— 这就是"只有墙的基色是对的"的由来。

## 三种消费者怎么用

| 消费者 | 原点 | 用什么 |
|---|---|---|
| **Blender**（左下） | v=0 在图片**底**端 | `to_blender_uv(u, v)` = `(u, 1 − v)` |
| **glTF**（左上，与 RDR2 同） | v=0 在图片**顶**端 | `to_gltf_uv(u, v)` = `(u, v)` —— **不要再翻**（翻了就是二次翻转） |
| **骑砍2**（D3D，理论同 DDS 左上） | 未实机验证 | 见 `docs/TODO.md`「UV V 约定」条目 |

## 谁在用

* `blender_continent.load_model_mesh()` —— 建所有场景 / 大陆 blend 的唯一网格入口；
* `blender_city_lod.read_mdl()` —— 城市 LOD 构建；
* `export_sdn_gltf.py` / `export_weapon_tint.py` —— glTF 侧（**不翻**）。
"""


def to_blender_uv(u, v):
    """RDR2 UV → Blender/OpenGL UV（翻转 V）。"""
    return u, 1.0 - v


def to_gltf_uv(u, v):
    """RDR2 UV → glTF UV（**恒等**：两者同为左上原点）。"""
    return u, v


def flip_v_inplace(uv_array, numpy_like=None):
    """numpy (N,2) 数组原地翻 V。返回同一个数组（方便链式调用）。"""
    uv_array[:, 1] = 1.0 - uv_array[:, 1]
    return uv_array
