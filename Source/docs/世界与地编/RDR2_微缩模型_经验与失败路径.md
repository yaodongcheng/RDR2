# 微缩模型 / 沙盒大地图：知识总结

> 这份文档回答一个问题：**「把 46 个据点摆在一张大地图上，并且能看清每座城」这件事，项目里到底已经有什么、还缺什么、哪些路已经证明走不通。**
> 所有数字都是实测的。写于 2026-10-26，作者踩完坑之后。
> 最后更新：2026-10-26

---

## 0. 一句话结论（最重要的那条）

> **单城的"完全版"早就有了，别再自己烘。**
> `export/previews/` 里已经有 **43 个城镇的浏览器可加载真实模型**（合计 2.61 GB，圣丹尼斯 1.7 GB），
> 大地图缺的只是「远景用的轻量占位」+「点进去按需加载那座城的 tiles」这两件事，
> 而不是"把整城重新做成低模"。

我在这件事上先后重做了 6 版微缩模型（方块 → 真实网格 → 体素乐高 → 街区积木），
**全部不如直接复用 `previews/`**。教训写在 §4。

---

## 1. 盘点：项目里已经有的资产

### 1.1 单城完全版：`export/previews/`

```
export/previews/                 43 个城镇 · 合计 2.61 GB
├── index.html                   预览页（three.js GLTFLoader，逐块加载）
├── index.json                   清单：code / 名称 / 中心坐标 / 半径 / 实例数 / 字节数
└── <code>/
    ├── tiles/
    │   ├── tiles.json           本城的块清单（如圣丹尼斯 38 块）
    │   ├── c<i>_<j>.gltf        每块：meshes/material/images/nodes
    │   └── c<i>_<j>.bin         几何二进制
    └── textures/                全城共享贴图池（圣丹尼斯 4 203 张）
```

实测样本：

| 城镇 | 体积 | 块数 | 备注 |
|---|---:|---:|---|
| 圣丹尼斯 `sdn` | 1.7 GB | 38 | 983 MB 几何 + 695 MB 贴图 |
| 黑水镇 `bla` | 125 MB | — | 887 实例 / 500 模型 |
| 罗兹 `rho` | 113 MB | — | 767 实例 / 401 模型 |
| 瓦伦丁 `val` | 93 MB | — | 807 实例 / 356 模型 |

单块示例（`sdn/tiles/c0_0.gltf`）：150 meshes / 256 materials / 628 image 引用，
贴图用相对路径 `../textures/xxx.png` **共享同一贴图池**，所以块之间不会重复存图。

**这套就是"完全版圣丹尼斯"**，你在 `previews/index.html` 里看到的就是它。

### 1.2 原始整城场景：`deliverable/blender/`

| 文件 | 体积 | 内容 |
|---|---:|---|
| `sdn.blend` | 2.23 GB | 23 056 个物件 / **72 659 670 三角面** |
| `continent.blend` | 7.80 GB | 整块大陆装配 |
| `guarma.blend` | 0.29 GB | 瓜玛岛 |

注意：`.blend` 里的物件**大量共享 mesh**（实例化），且 97 个 collection 里有 65 个是隐藏的
（`glTF_not_exported` / `TILE_*`）。任何脚本要先处理这两件事才能 join（见 §5.3 / §5.4）。

### 1.3 大地图底图：已在 `deliverable/miniatures/map/data/`

```
terrain.i16         384×286 int16 高度（≈28 m/格，1/29 后≈1 m）
terrain_color.jpg   1024² 地面彩图
map.json            地理范围/高程范围
settlements.js      46 据点的世界坐标/类型/势力/成品尺寸
```

---

## 2. 正确架构：大地图 = 占位 + 按需加载

```
┌─ 远景（整图，46 城同时可见）
│   极简占位：1 个 box / 或 6~10 面的色块，几万面总量、几十个 draw call
│   ← 现在的 deliverable/miniatures/models/*.glb（46 城 18 404 面）就是这一层
│
└─ 聚焦（点某城 / 相机靠近）
    动态加载 export/previews/<code>/tiles/*.gltf（同一套真实模型）
    · 先读 tiles.json 拿块清单
    · 只加载中心 3×3 或按距离排序的前 N 块，渐进出图
    · 离开时 dispose，避免显存爆掉
```

这样做的好处：
- 近看 = 你在预览页看到的那套，质感一致，不需要任何"新烘"；
- 远景不吃显存；
- 圣丹尼斯的 1.7 GB 永远不会被一次性拉下来。

**唯一要写的新代码**：地图页里的 LOD 切换 + 分块加载 + 卸载。
参考实现就在 `export/previews/index.html` 第 300 行附近（它已经在做 `fetch(tiles.json) → 逐块 load`）。

---

## 3. 如果一定要做"轻量版"（比如需要 46 城同时近看）

结论：**形状能保住，材质做不到**。

- ✅ 形状：`Decimate → DISSOLVE(planar, 6°)` 按共面合并，实测
  **26 498 030 → 11 401 517 →（轻量 COLLAPSE）→ 2 697 315 面**，街区/码头/桥/船全部保留。
  这是唯一不碎的减面方式。
- ❌ 材质：`.blend` 是一物件一材质，join 后 **5 076 个 material**；直接导出 **433 MB**。
  要压到可用必须做**贴图图集烘焙**（把几千张贴图打成 2~4 张 4K 图集 + UV 重映射），
  预计数小时工程量，且做完也只是"能近看"，不如直接按需加载 `previews/`。

---

## 4. 负面清单：不要再走这 6 条路

| # | 做法 | 结果 | 根因 |
|---|---|---|---|
| 1 | 每栋建筑套方块 + 坡屋顶 | 纸片感 | 没有真实体量 |
| 2 | 读真实 `.mdl`，按面面积裁面 | 碎成木片 | 建筑是**薄壳**，裁掉小面只剩栅栏 |
| 3 | 读真实 `.mdl`，顶点聚类 | 尖刺 | 聚类平均薄壳顶点，直接爆开 |
| 4 | Blender 逐物件 Decimate 到 ~420 面 | 废墟感（481 615 面） | 每栋楼面数太少，等于拆墙 |
| 5 | Blender 整体 join 后 COLLAPSE 到 50 万面 | 碎片 + 2 277 材质 | 塌陷对薄壳不友好 |
| 6 | 街区积木（30 m 网格并街区，一街区一块） | 已交付但不满足质感 | 只是"方块的城市"，不是那座城 |

> 共同错误：**默认"必须重新做低模"**。真相是单城完全版已经存在（§1.1）。

---

## 5. 五个必须知道的硬坑

### 5.1 轴序是 `(x, 高度, z)`
写反会把整座城"立起来"（垂直方向变成南北跨度），表现为"城是一堵 60 m 高的墙"或"房子浮空"。
自己拼几何时踩过三次。见 `tools/build_miniatures_blocks.py` 的 `add_box()` 注释。

### 5.2 `town_data` 里大量 bbox 是占位单位立方体
`export/levels/world/town_data/*.js` 的实例带 6 个 local bbox，很多是 `-0.5 ~ 0.5`。
照它算占地 → 房子变薄片。正确做法：用模型自身尺寸（`deliverable/handoff/model_ledger.csv` 的 `sx/sy/sz`）× 实例 scale。

### 5.3 `.blend` 里 65 个隐藏 collection → 对象选不中
`select_set(True)` 无效、`join()` 只合到零星几个对象，出现 **"joined tris 2556"** 这种假结果。
解法：先把对象 `unlink` 再 `link` 到新建的 `BAKE` collection。

### 5.4 物件共享 mesh → 必须 `make_single_user`
否则 `Cannot apply to a multi user: Object "...", Mesh "..."`。
`bpy.ops.object.make_single_user(object=True, obdata=True)` 之后再 join。

### 5.5 材质数随物件线性增长
`sdn.blend` join 后 5 076 个 material → 5 076 次 draw call。**这是所有"导出即用"尝试失败的直接原因。**

---

## 6. 复现命令

```bash
cd "D:/BrainMaker/大镖客2解包分析"

# 单城完全版（已有的那套），重新生成：
uv run python tools/build_settlement_previews.py      # 43 城，输出到 export/previews/
# 预览：起服务后打开 export/previews/index.html

# 大地图占位层（当前交付）：
uv run python tools/build_miniatures_blocks.py        # 46 GLB（街区积木）
uv run python tools/audit_miniatures.py               # 46/46 通过
uv run python tools/build_sandbox_map.py              # 地形/颜色/摆放表
# 预览：export/miniatures/map/index.html

# 保形减面（如需轻量版，Blender，单城 20~30 分钟）：
blender -b -P tools/blender_city_flatcolor.py -- \
  --blend deliverable/blender/sdn.blend \
  --out deliverable/miniatures/hi/sdn_hero.glb --angle 6 --max-tris 1400000
```

---

## 7. 交接清单（下次接手先看这三条）

1. **先 `ls export/previews/`**：单城真实模型已存在，别重复造。
2. **大地图只写"占位 + 按需加载"**：占位层用 `miniatures/models/`，聚焦时加载 `previews/<code>/tiles/`。
3. **要动 `.blend` 先做两件事**：`BAKE` collection 搬家、`make_single_user`；否则 join 出来是假的。
