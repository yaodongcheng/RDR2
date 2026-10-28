# RDR2 室内装配与烘焙 · 交接文档

> 2026-10-27。接手「把 RDR2 室内模型装进房子」这条线时看这一份。
> 涵盖：数据来源、可复用流程、关键坐标、踩过的坑、已知限制。

---

## 一、交接摘要

| 项 | 状态 |
|---|---|
| 室内模型入库 | ✅ 27 个（`roc_house_int.rpf` 的 31 个 ydr，含双人床 / 壁炉 / 橱柜 / 炉子 / 镜子） |
| MLO 布局解析 | ✅ 455 项（`roc_house_int.ytyp`），415 项装配成功 |
| 交付文件 | `deliverable/blender/willard/willard_full.blend`（1.15 GB，外观 + 室内） |
| 父级烘焙 | ✅ 已完成，415 个件各自带世界变换，`INTERIOR_ROOT` 已删 |
| 位置对齐 | ✅ 四边间隙对称（X 1.97/1.98，Y 1.25/1.24） |
| 误渲染件清理 | ✅ 13 类壳/代理由 + 6 类污渍/瓶子 已隐藏 |

**一句话**：室内已经能正确嵌进夏洛蒂家，且**这套流程可套用到其他房子**。

---

## 二、可复用的 5 步流程

### 步骤 1 · 找包并解室内模型

```
levels/rdr3/interiors/<name>_int.rpf
  ├── <name>.ytyp          ← MLO 布局（关键！）
  ├── *_int_shell_*.ydr    ← 房间壳
  ├── *_details*.ydr       ← 细节
  ├── *_fireplace.ydr 等   ← 家具
  └── *_txd.ytd            ← 贴图
```

命令：
```bash
rdr2rpf extract "H:/EPICGAMES/RedDeadRedemption2/levels_3.rpf" <outdir> "<name>_int" --recurse
rdr2rpf extract "<outdir>/.../<name>_int.rpf" <out2> ""          # 解出 ydr/ytd/ytyp
```

### 步骤 2 · 模型入库

```bash
# 先把该包的 ytd 放进贴图搜索目录
cp <out2>/*.ytd work/lib_gtxd/txd/

# 再转 mdl（脚本见 tools/add_interior.py）
uv run python tools/add_interior.py <out2>
```

> ⚠️ `add_interior.py` 之前有个 bug 会把 `index.json` 的 tex 索引覆盖成只剩新增项。
> **已修**（`tex._next = len(texmeta)`，新贴图 id 从现有条数之后开始）。用前确认这个修复还在。

### 步骤 3 · 解析 MLO 布局

```bash
uv run python tools/parse_interior_mlo.py <out2>/<name>.ytyp --out interior_layout.json
```

144 字节 entity 布局：

| 偏移 | 内容 |
|---|---|
| +8 | archetype hash |
| +32 | position（室内局部坐标） |
| +48 | rotation (x,y,z,w)，**用到 Blender 要取共轭** |
| +132 | parentIndex（65535 = 无父） |

### 步骤 4 · 装配进房子

参考 `tools/merge_interior_into_willard.py`，核心两步：

```python
# ① 用 MLO 实例变换摆位（roc_hse_int_lod 在 area ymap 里）
world    = MLO_POS + (MLO_QUAT @ local)
rot_world = MLO_QUAT @ local_rot

# ② 用房子 bbox 居中（已验证有效）
dx = house_center_x - interior_center_x
dy = house_center_y - interior_center_y
# z 用**地形高度**，不是房子 bbox 底！
```

### 步骤 5 · 清理误渲染件 + 烘焙

```bash
# 隐藏假几何
# 房间壳 / 细节 / 木结构 / 代理 / 梁 / 污渍 / 散装瓶子 —— 见 §三 清单

# 烘焙父级（关键一步，之后读 location 才可靠）
uv run python tools/bake_interior_root.py
```

烘焙用的是 Blender 官方 API：
```python
bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')
```

---

## 三、必须隐藏的"假几何"清单

这些模型**自带屋顶或地板**，和房子外壳重叠，或本身是编辑器辅助物：

| 类别 | hash | 说明 |
|---|---|---|
| 房间壳 | `cba915be` `ac262389` `e6649809` | main / bed01 / bed02 |
| 细节件 | `b56905d2` `82519f88` `ae28fb80` `4be4a68c` | 各带屋顶 |
| 木结构 | `b2afc32a` `d6a5cf80` | bed01/bed02 的 logs，**带屋檐** |
| 阴影代理 | `54b00fdf` | 13.6×11.6×5.9 的不可见盒 |
| 反射代理 | `51b78358` | 13.5×8.9×5.6 |
| 梁 / 木块 | `b93ccef5` `f0eaad82` | |
| 地面污渍 | `d3f79faf` `59f1bb50` `3933f9d1` | `roc_dirt_stains`：**alpha 通道未处理 → 整块不透明黑** |
| 散装瓶子 | `a9d63ce4` `acec4310` `65c75ef` | `roc_hse_int_bottles01/02/03`：**6~8 m 宽、厚 0.1 m 的瓶子合集**，平铺像黑板 |

> 「散装瓶子」最坑：`roc_hse_int_bottles01/02/03` 在游戏里是桌面上散落的瓶子，
> 打包后范围 6~8 m、厚度 0.1 m，无贴图时像一块黑色地板。

**为什么贴花是纯黑**：`export_sdn_gltf` 的材质管线只取纹理 RGB，**没有接 alpha 到
`Principled BSDF` 的 Alpha**，所以原本半透明的污渍变成了不透明黑。

**根治方向**（未做）：在 `_mat_for()` 里对有 alpha 的贴图设置
`blend_method='BLEND'` 并把 `img` 的 Alpha 接到 BSDF 的 Alpha 输入。

---

## 四、踩过的坑（务必看）

### 4.1 读取不可靠（最耗时的一条）

| 读法 | 结果 | 说明 |
|---|---|---|
| `o.bound_box` | 20.2×21.1 | **旧缓存**，实际 16.0×17.5 |
| `o.matrix_world`（有 parent） | 局部坐标 | `matrix_parent_inverse` 把它抵消了（Blender 设计） |
| `evaluated_get(dg).matrix_world` | 同样局部 | 不是"没拿到"，是数学上等于 basis |
| `parent.matrix_world @ parent_inv @ basis` | 也可能错 | 不同对象的 `matrix_parent_inverse` 表示不一致 |
| **烘焙后 `o.location`** | ✅ 可靠 | 没有 parent 就没有歧义 |

**结论**：**先烘焙掉父级再算**，否则每次算出来的数都不一样。

### 4.2 判据全部失败过

| 判据 | 失败原因 |
|---|---|
| bbox 溢出最小 | 有无数个 0 分解（转任何角度都能塞进矩形） |
| shell yaw 对比 | 读的是局部（见 4.1） |
| 顶点 PCA | L 形被平均，主轴无意义 |
| OBB 最小外接矩形 | 房子 OBB 退化成正方形（14.7×14.6），角度无意义 |
| **室内 bbox 在房子 bbox 内居中** | ✅ **唯一验证有效的** |

> 房子真实墙体占地 **16.0 × 17.5**（用垂直墙面顶点算），
> 不是 `bound_box` 报的 20.2 × 21.1。

### 4.3 室内不是"一整个大房间"

三个"房间壳"里，`bed01` / `bed02` 的 XY 范围**完全落在 `shell_main` 内部**——
它们不是独立房间，是同一个大房间里的分区。

所以**室内整体 12.03 × 15.05，只占房子（15.98 × 17.54）的 75% × 86%**，
这是"房间内腔 vs 含墙厚的外轮廓"的正常比例。

### 4.4 z 要对齐地形，不是房子 bbox 底

```
房子 bbox 底 164.55，实际地面（H4 地形）165.23
→ 用 bbox 底会让室内下潜 0.5 m
```

### 4.5 房子「陷地 / 悬空」是三层叠加（修一层暴露下一层）

| # | 层 | 现象 | 修法 |
|---|---|---|---|
| ① | `settlements_bannerlord.csv` 的 `hso`/`abe`/`roc` 的 `u,v` = **`0,0`** | PAD 把点算到地图西北角 → 该片地形**从未压平** → **房子埋 9 m** | 按 `settlements_world_v2.csv` 补 u/v |
| ② | PAD 按「区域内实例 z 的**中位数**」压平 | roc 建筑高度分散（坟 158.5 / 主屋 168.6）→ 中位算成 161 → **悬空 3.45 m** | 分区装配 `--only-tile <id> --no-pad` |
| ③ | 用 IDW 把地形强压到建筑基底 | 悬空解决，但**地形起伏被抹平**（游戏里周围是坡地） | 回退，用原始 H4 |

**核对**：H4 在房子处 **165.23**、建筑底 **164.55**，差 **0.68 m** 是正常地基埋深 —— **本来就贴地**。

> 结论：**问题全在 PAD，不在高程数据**。整图里其他 POI 同样会被 PAD 误压平（PAD 只覆盖 46 个据点）。

---

## 五、已知限制

| 项 | 状态 |
|---|---|
| 小道具贴图（硬币/罐头/书/杯子） | ❌ **资源不在已解包内**。已扫 25 个 props 包 + `gtxd.rpf`/`gtxd_ann` + 3,696 个 ytd，全无。用近似色代替 |
| 密集草丛层 | ❌ 不在 ymap 实体里（GPU instanced） |
| **植被（willard）** | ✅ **2026-10-27 已删**：450 个（树/灌木/蕨/树桩），1,060→610 个对象；室内 415 件完好。脚本 `tools/strip_vegetation.py`；备份 `willard_full_withveg.blend` |
| ~~野外物件埋入地形~~ | ✅ **已澄清**：之前报的 −6.51 m 是被**植被**拉偏。按类型拆：**建筑 −0.32 m / 道具 +0.21 m（都正常）**，只有植被 −6 m（用户决定不管植被） |
| ~~铁路铁轨~~ | ✅ **2026-10-27 已修**：`RAILCELLS` **1,359 件**已装回 `continent.blend`。旧说法"主地图铁路从未解包"是**误判** —— 数据一直在 tiles 里，是 `flat_wide` 剔掉了 1,024/1,359。详见 `README.md` §0.7.1 |
| `roc_hse_int_reflection` 等代理 | 已隐藏，但未从数据层移除 |
| **地面贴花（含室外）** | ❌ 材质管线只取 RGB，alpha 未接 BSDF → 污渍/贴花渲染成不透明黑或白板。修法见 §三末 |
| **未命名部件 5 万个** | ❌ 模型从未抽出（库里只有 2 个）。ytyp 已覆盖 99.6%，见 `README.md` §0.7.2 |
| **夏洛蒂家的"对齐"是补出来的** | ⚠️ 当年用替身 `roc_hse_int_lod`（yaw −70°），真实例 `roc_house_int` 是 +30°，差 100°；靠「旋转 + bbox 居中」掰正。详见 §九 |

---

## 六、下一步建议

> **完整的全图铺量 TODO 见 `README.md` §0.6** —— 含 152 个室内包的分布、5 步流程、
> 4 个阻塞问题、优先级分档、工作量估算。这里只说结论。

**核心结论：先解决「MLO 实例定位」，室内才能批量；室外那两件全图级的事已经做完。**

| 优先级 | 事项 |
|---|---|
| ~~0~~ | ✅ **铁路铁轨 —— 2026-10-27 已完成**：`--rails` 开关 + `add_rail_network.py` 修旋向，`continent.blend` 里 `RAILCELLS` 1,359 件。验收见 `README.md` §0.7.1 |
| **0（新）** | **解 MLO 的 rooms/portals 变换**（见 §九）—— 这是室内能批量的唯一卡点 |
| **1（新）** | 补 5 万个未命名部件的模型（49,778 种 / 50,007 实例）。ytyp 已覆盖 99.6%，见 `README.md` §0.7.2 |
| **2** | 拿到 rooms 变换后：用 `tools/locate_interior_mlo.py`（136/144 可定位）+ `tools/merge_interior.py` 批量装配 |
| 3 | 假几何 hash 清单：按本栋的实际名字重新识别（或建一张全局表） |
| 4 | 地面贴花 alpha（`blend_method='BLEND'` + Alpha 连线）；注意透明排序副作用 |
| 5 | 补齐小道具贴图（`gtxds.meta` 剩下的 31 个 `gtxd_*.rpf`） |
| 6 | 地形贴合：已用 `tools/fit_terrain_to_buildings.py`（pad 模式）修主要部分，纯房屋贴地 17.3% → 47.0% |

---

## 七、关键文件索引

| 文件 | 用途 |
|---|---|
| `tools/add_interior.py` | 室内 ydr → lib_native |
| `tools/parse_interior_mlo.py` | ytyp → MLO 布局 JSON |
| `tools/make_interior.py` | 装配 + 渲染室内（不含房子） |
| `tools/merge_interior_into_willard.py` | 合并进房子（MLO 变换 + 居中 + z 对齐） |
| `tools/bake_interior_root.py` | 烘焙父级 + 隐藏污渍 |
| `tools/probe_walls_gui.py` | GUI 探针：垂直墙面轮廓 |
| `deliverable/blender/willard/willard_full.blend` | 成品 |
| `raw/_scratch/roc_interior_layout.json` | 455 项布局数据 |


---

## 八、用户当前关注点（2026-10-27 交接时）

| 优先级 | 内容 |
|---|---|
| **P0（已完成）** | ~~**建筑网格 + 铁路铁轨**~~ → 铁路 2026-10-27 已装回（1,359 件）；建筑主体 99.6% 在场景里 |
| **P0（进行中）** | **补 5 万个未命名部件**：这才是"建筑拼不起来"的真正原因（≥8 m 大件 44,900，圣丹尼斯 2,124）。ytyp 已覆盖 99.6% |
| 已验证 | 建筑贴合度 **−0.32 m**（正常）、旋转（四元数共轭）已在全图生效；**铁路不能用来验证共轭**（97.6% yaw=0） |
| 用户明确不管 | 植被（−6 m，分布极宽）、完全复原 |
| 次要 | 室内铺量（152 个包）、地面贴花 alpha、小道具贴图 |

---

## 九、2026-10-27 复核：室内这条线的真实状态（必读）

### 9.1 结论先说

| 项 | 状态 |
|---|---|
| 游戏内室内包 | **144 个**（`levels_rdr3/interiors/*_int.rpf`；本交接文早期写 152 是按目录推测，实际列表见 `export/world/interior_pkgs.txt`） |
| 已完成装配 | **1 个**（罗兹威拉德之息 = 夏洛蒂家） |
| **能否定位 MLO 实例** | ✅ **136 / 144 = 94%**（精确 129 + `_lod` 4 + `_main` 3） |
| **室内对齐是否正确** | ❌ **未验证通过** —— 见 9.2 |

### 9.2 夏洛蒂家的"对齐"其实是补出来的

当年用的是**替身** `roc_hse_int_lod`，而游戏里的真实实例是 `roc_house_int`：

| | 位置 | yaw |
|---|---|---|
| 替身 `roc_hse_int_lod` | (2990.42, 2188.85, 168.44) | **−70°** |
| 真实 `roc_house_int` | (2991.00, 2190.40, 166.80) | **+30°** |

差：水平 **1.71 m**、垂直 **1.60 m**、yaw **100°**。

因为替身摆位不对，脚本里又加了「旋转到房子 yaw + bbox 居中 + z 贴地形」把结果强行掰正 ——
所以 `四边间隙 X 1.97/1.98、Y 1.25/1.24 的"对称"是算出来的，不是数据本身。**

用真实例直接装配的实测（`willard.blend` + 415 件）：

| 方式 | 可见室内 bbox 间隙 | 现象 |
|---|---|---|
| 替身 + 强制对齐（现状） | X 3.80/4.35 · Y 2.94/2.61 | 塞得进去，旋转是掰的 |
| **真实例，不对齐** | X 2.08/0.45 · Y 3.84/2.31 | **家具从屋顶西/北侧露出**；壳 yaw −170° vs 房子 100°（差 90°） |
| 真实例 + 额外 ±90°/180° | 出现负间隙 | 没有单一 yaw 能修好 |

### 9.3 缺的那一层：MLO rooms/portals

现在只解析了 ytyp 里的 **144 字节 entity 块**（hash / pos / quat / scale / parentIndex）。
RDR2 室内真正的房间布局在 **`CMloArchetypeDef` 的 rooms / portals** 里（每个 room 有自己的变换），
少了这层，直接用 entity 块摆位就会"整体偏出去 + 差 90°"。

**下一步**（约半天）：
1. 在 `tools/parse_interior_mlo.py` 里加 rooms/portals 段解析；
2. 用 3 栋已知房子做三角验证：`roc_house_int`（有外部对照）、`val_hotel_int`、`new_com_bank_int`；
3. 找出"room 变换 → 世界"的固定映射后，再用
   `uv run python tools/locate_interior_mlo.py --json mlo.json` +
   `blender -b <house.blend> -P tools/merge_interior.py -- --pkg <pkg> ...` 批量跑。

### 9.4 已交付工具

| 文件 | 作用 |
|---|---|
| `tools/locate_interior_mlo.py` | 包名 → MLO 实例（pos/quat/yaw/scale）+ 最近宿主建筑；`--json` 导出 |
| `tools/merge_interior.py` | 通用装配；`--align` 复刻老行为、`--extra-yaw` 试验额外旋转、`--show-shell` 测量用 |
| `export/world/interior_pkgs.txt` | 144 个包名清单 |
