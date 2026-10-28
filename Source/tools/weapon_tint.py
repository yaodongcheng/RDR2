# -*- coding: utf-8 -*-
"""RDR2 武器「调色板 / 双层」反推：把 standard_weapon_2lyr 的参数组合烘焙成一张 albedo。

## 为什么武器看起来"没贴图"

RDR2 武器的 shader 是 `standard_weapon_2lyr`，它的 albedo **不是一张现成的漫反射贴图**：

| slot | 参数 | 车枪主体绑的 | 木质握把/枪托绑的 |
|---|---|---|---|
| 0 | `tintpalettetex` | `w_repeater_carbine01_pal`（256×16，整张近乎均匀的洋红 = **占位/未使用**） | — |
| 1 | `lyr0diffusetex` | `w_blank_ab`（4×4 纯白） | `w_stock1_tintControl`（遮罩图，不是颜色） |
| 4 | `lyr1diffusetex` | `w_rust01_ab`（锈蚀层，真色） | `w_woodDamge01_ab`（木料磨损层，真色） |
| 7 | `controltexturetex` | `w_repeater_carbine01_ct`（层混合权重） | `w_stock_blank_ct` |
| 9 | `engravingtexturetex` | `w_repeater_carbine01_eg`（雕刻/蚀刻遮罩） | `w_repeater_carbine01_stock_eg` |
| 10 | `albedopalettetex` | `givemechecker`（无） | **`weapon_tint_wood`（64×128 木纹渐变 ← 木头真正的颜色来源）** |
| 11 | `engravingsecondaytexture` | `w_sharedEngravings1` | `w_sharedStockCarvings1`（法线，雕刻凹凸） |

所以：
* **木料**：颜色 = `albedopalettetex`（`weapon_tint_wood`）按 **mesh UV0** 采样 —— 直接就是木纹；
* **金属**：颜色 = `tintpalettetex`（这里被做成白色占位）× `lerp(lyr0, lyr1, control)` —— 即
  "白钢底 + 锈蚀磨损 + 蚀刻暗部"，游戏里再由武器 tint（蓝钢/黄铜/银）着色。

烘焙做法：在 **UV 空间**画一张 512² 图，逐像素按上面的公式合成，然后用同一个 UV0 贴回模型，
在 glTF 里就是一张正常的 `baseColorTexture`（法线仍用原本的 `_NM`）。

## 用法

    from weapon_tint import bake_albedo, params_of
    img = bake_albedo(params)      # params: {paramName: textureName}
"""
import os
import sys
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import export_sdn_gltf as G
import ytd_to_png as YT

# PAL（旧版 ytd_to_png 对 BGRA8 的调色板直接崩，是"武器贴图找不到"的直接原因之一）
G.decode_one = YT.decode_one

TEXLIB = None
_CACHE = {}


def texlib():
    global TEXLIB
    if TEXLIB is None:
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        TEXLIB = G.TexLib([os.path.join(root, "export/weapons/models"),
                           os.path.join(root, "raw/models/weapons")], maxs=1024)
    return TEXLIB


def _tex(name):
    if not name:
        return None
    if name.lower() in ("givemechecker", "w_blank_ab", "w_blank_ma", "w_blank_ct", "w_blank_eg"):
        return None
    im, _d = texlib().get(name)
    if im is None:
        return None
    return np.array(im.convert("RGBA")).astype(np.float32) / 255.0


def _sample(arr, U, V):
    h, w, _ = arr.shape
    x = np.clip((U % 1.0) * w, 0, w - 1e-3).astype(np.int32)
    y = np.clip((1.0 - (V % 1.0)) * h, 0, h - 1e-3).astype(np.int32)
    return arr[y, x]


def _is_placeholder_palette(arr):
    """识别"整张均匀洋红"的空调色板（神枪本体基本都是这种）。"""
    m = arr[..., :3].reshape(-1, 3).mean(0)
    sd = arr[..., :3].reshape(-1, 3).std(0).mean()
    return sd < 0.06 and abs(m[0] - m[2]) < 0.05 and m[1] < m[0] - 0.2


def params_of(shader_textures):
    """[(param, name)] → {param: name}"""
    return {(t.get("param") or ""): t.get("name") for t in shader_textures}


def key_of(params):
    return "|".join("%s=%s" % (k, params.get(k) or "") for k in sorted(params))


def bake_albedo(params, size=512):
    """按 standard_weapon_2lyr 的参数组合烘一张 UV 空间 albedo → (size,size,3) float"""
    k = (key_of(params), size)
    if k in _CACHE:
        return _CACHE[k]
    u = (np.arange(size) + 0.5) / size
    U, V = np.meshgrid(u, u)

    pal = _tex(params.get("tintpalettetex"))
    apal = _tex(params.get("albedopalettetex"))
    l0 = _tex(params.get("lyr0diffusetex"))
    l1 = _tex(params.get("lyr1diffusetex"))
    ct = _tex(params.get("controltexturetex"))
    eg = _tex(params.get("engravingtexturetex"))

    # ---- standard / standard_alpha / looking_glass 系列：直接有 diffusetex ----
    # 望远镜、相机、套索、鱼竿这类"工具"走的是 standard，不是 2lyr，以前没接这条分支 → 烘出来是纯白
    diff = _tex(params.get("diffusetex"))
    if diff is not None and apal is None:
        base = _sample(diff, U, V)[..., :3].copy()
        if pal is not None and not _is_placeholder_palette(pal):
            base = base * _sample(pal, U, V)[..., :3]
        out = np.clip(base, 0.02, 1.0)
        _CACHE[k] = out
        return out

    if apal is not None:
        # ---- 木料 ----
        # lyr1 (=w_woodDamge01_ab) 才是真正的木纹 albedo（带年轮/磨损），
        # albedopalette (weapon_tint_wood) 是"色调 LUT"，单独用会出现糖果条纹，
        # 所以：底色取 lyr1；没有 lyr1 才退回 LUT。
        if l1 is not None:
            out = _sample(l1, U, V)[..., :3].copy()
            out *= 0.75                                  # woodDamge 是线性色，直接用会偏黄，压到深棕
        else:
            out = _sample(apal, U, V)[..., :3].copy()
        if ct is not None:
            c = _sample(ct, U, V)
            out *= (0.86 + 0.28 * c[..., 1:2])           # control.G = 木纹明暗
        if eg is not None:
            e = _sample(eg, U, V)
            out *= (1.0 - 0.18 * e[..., 1:2])            # 雕刻缝压暗
    else:
        # ---- 金属：**钢底色 × 局部锈蚀** + 蚀刻暗部 ----
        # 旧公式 base = 白 × (1-c) + 锈 × c 再 ×0.62，等于把整支枪涂成"暖灰棕"，
        # 在查看器里（metallic 0.15、无环境光）就是一块**水泥**。
        # 正确读法：lyr1 是锈层，只在 control 遮罩处出现；主体应该是冷调钢。
        steel = np.array([0.60, 0.625, 0.67], np.float32)
        base = np.ones((size, size, 3), np.float32) * steel
        if l0 is not None:
            # lyr0 是"底漆/镀层"，w_blank_ab 时等于 1，不影响
            base = base * np.clip(_sample(l0, U, V)[..., :3] * 1.15 + 0.18, 0.3, 1.15)
        if l1 is not None:
            rust = _sample(l1, U, V)[..., :3]
            # control 的 R 通道 = 层混合权重（实测均值 0.27，只在边缘/缝隙升高）
            c = _sample(ct, U, V)[..., :1] if ct is not None else np.zeros((size, size, 1), np.float32)
            w = np.clip(c * 0.55, 0.0, 0.75)          # 锈最多覆盖 75%，且整体偏淡
            base = base * (1.0 - w) + rust * w
        if eg is not None:
            e = _sample(eg, U, V)[..., 2:3]           # 蚀刻图在 B 通道
            base = base * (1.0 - 0.30 * np.clip(e, 0, 1))
        # 极轻微的高频起伏，避免大片纯色看起来像"未贴图"
        noise = (0.97 + 0.03 * np.sin(U * 37.0) * np.sin(V * 41.0))[..., None]
        base = base * noise
        out = base
    out = np.clip(out, 0.02, 1.0)
    _CACHE[k] = out
    return out
