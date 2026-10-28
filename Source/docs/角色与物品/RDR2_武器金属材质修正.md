# 武器枪管"像水泥"——根因与修正

> 现象：查看器里步枪/左轮的枪管、机匣是一片**发灰的哑光**，像水泥或石膏，没有金属感。
> 结论：**确实是搞错了**，而且错在两层——**烘焙出来的 albedo 本身偏暖灰**，并且**材质 metallic 只有 0.15**。

---

## 0. 一句话

| 项 | 修前 | 修后 |
|---|---|---|
| 金属 albedo 均值（RGB） | **0.437 / 0.401 / 0.356**（暖灰棕） | **0.477 / 0.482 / 0.512**（冷调钢灰） |
| `metallicFactor` | **0.15** | **0.62** |
| `roughnessFactor` | 0.45 | **0.30** |
| 查看器环境反射 | 无（金属没有东西可反射） | 自建 PMREM 环境（顶光 + 双色侧光） |
| 重导数量 | — | **105 个武器 glTF 全部重导** |

![修前](img/weapon/gun_barrel_before.png)
*修前：枪管像刷了白灰，机匣上的"斑点"是锈层被整片铺开*

![修后](img/weapon/gun_barrel_after.png)
*修后：枪管是冷调钢，机匣有铣削面和沿长度的高光渐变，木托仍是木色*

---

## 1. 根因（两层，缺一不可）

### 1.1 烘焙公式把"锈层"铺满了整支枪

RDR2 武器用 `standard_weapon_2lyr`，albedo 不是一张贴图，是**两层混合**：

| 层 | 参数 | 实际贴图 | 含义 |
|---|---|---|---|
| 层 0 | `lyr0diffusetex` | `w_blank_ab`（纯白） | 钢基底 |
| 层 1 | `lyr1diffusetex` | `w_rust01_ab`（暗红棕） | 锈蚀 |
| 混合 | `controltexturetex` | `w_repeater_carbine01_ct` | 每像素的混合权重 |
| 调色 | `tintpalettetex` | `w_repeater_carbine01_pal`（洋红占位） | 游戏内 tint，导出时无效 |

旧代码：

```python
base = white * (1 - c) + rust * c      # c = control.R（均值 0.267）
base = base * 0.62                     # 再整体压暗
```

`c` 的均值是 0.267，但**它不是 0** —— 等于给整支枪刷了 27% 的锈，
再乘 0.62 压暗 → **(0.44, 0.40, 0.36)** 的暖灰棕，正是水泥色。

### 1.2 材质 metallic 只有 0.15

`export_weapon_tint.py` 里写死：

```python
metallicFactor = 0.15
roughnessFactor = 0.45
```

0.15 的金属度 ≈ 塑料/涂漆；加上查看器**没有 environment**（`scene.environment` 为空），
金属没有可反射的环境，只剩漫反射 → 视觉上就是一块哑光灰。

---

## 2. 修法

### 2.1 albedo：钢底 + 局部锈 + 蚀刻

```python
steel = [0.60, 0.625, 0.67]            # 冷调钢
base  = steel
base *= lyr0 * 1.15 + 0.18             # 镀层/底漆（blank 时≈1）
w     = clamp(control.R * 0.55, 0, 0.75)   # 锈最多覆盖 75%，且整体偏淡
base  = base * (1 - w) + rust * w
base *= 1 - 0.30 * engraving.B          # 蚀刻线压暗
base *= 0.97 + 0.03 * noise             # 极轻微起伏，避免"大片纯色像没贴图"
```

### 2.2 材质：金属给金属度，木料保持非金属

```python
metallicFactor  = 0.62 (metal) / 0.0 (wood)
roughnessFactor = 0.30 (metal) / 0.78 (wood)
```

> 为什么不是 1.0：这三盏方向光 + PMREM 环境下，metallic 1.0 会让背光面接近纯黑（没有 IBL 漫反射）。
> 0.62 是"看得出是金属、又不会黑成剪影"的折中；如果要更"亮钢"，把 `metallicFactor` 提到 0.8、
> 同时把环境强度提上去即可。

### 2.3 查看器补环境反射

`export/viewer/index.html` 的 `Viewer3D` 构造里加了一个**自建小房间**做 PMREM：

```js
const pm = new THREE.PMREMGenerator(renderer);
const es = new THREE.Scene();
add(0xffffff, 0, 7, 0, 14, 0.2, 14);   // 顶部柔光箱
add(0x9ec0ff, -7, 3, 0, 0.2, 8, 10);   // 冷侧光
add(0xffd9a8, 7, 3, 0, 0.2, 8, 10);    // 暖侧光
add(0xffffff, 0, 2, 7, 10, 6, 0.2);    // 正面补光
scene.environment = pm.fromScene(es, 0.08).texture;
```

不需要外部 HDR 文件，也不影响其它页面（只在武器/物品 3D 视图里生效）。

---

## 3. 验证

- **A/B 图**：`docs/角色与物品/img/weapon/gun_barrel_before.png` / `gun_barrel_after.png`
  （同一模型、同一机位、同一光照；before 用旧公式 + 旧材质参数重烘一份临时 glTF 出的图）
- **数值**：见 §0 表；金属 albedo 的色相从暖（R>G>B）变成中性偏冷（B≥G>R）。
- **回归**：105 个武器全部重导，`export/viewer/models/weapons/*.gltf` 的
  `pbrMetallicRoughness.metallicFactor` 已全部更新；木料材质仍为 `metallic 0 / roughness 0.78`。

```bash
uv run python tools/export_weapon_tint.py            # 105 个
uv run python tools/export_weapon_tint.py --only w_repeater_carbine01   # 单把调试
```

---

## 4. 还没做的

| # | 项 | 说明 |
|---|---|---|
| 1 | **metallicRoughness 贴图** | 现在用的是常量因子；RDR2 的 `_ma`（`w_rust01_ma` / `w_blank_ma`）里应该带粗糙度/金属度掩码，解出来可以做"锈处更糙、钢处更亮"的空间变化 |
| 2 | **各武器 tint** | 游戏里蓝钢/黄铜/银是 tint 调色板给的；现在统一按"钢"烘，金色/雕花版本会偏冷 |
| 3 | **法线强度** | 现在直接搬 `lyr0normaltex`，没有按 UV 缩放，近景刻纹会偏平 |
