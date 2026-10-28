# RDR2 角色模型（NPC）+ 剧情文件 解包 —— 方法 / 产物 / 踩坑

> 工作目录：`D:\BrainMaker\大镖客2解包分析` ｜ 游戏：`H:\EPICGAMES\RedDeadRedemption2`（Epic）
> 面向目标：**把解包出来的 NPC 模型拿进别的引擎/项目用**（用户诉求："我已经解包了场景，现在想在里面放 NPC"）
> 本轮新增日期：2026-10-17

---

## 0. 一句话结论

**角色模型和剧情文件都能解，而且已经解完并导出成引擎可直接吃的 glTF。**

- **NPC 模型**：`export/npc/` —— **354 个角色**（228 个剧情角色 + 主角 2 + 通用路人 6 + 动物 118），
  每个都是带贴图的 `.glb`，合计 1.7 GB，附**浏览页面** `export/npc/index.html`。
- **剧情文件**：`export/story/` —— **中文对白 33.9 万条**（16 MB 文本）、过场演出动画（181 包索引 + 3 包样本）、
  过场 CG 视频（65 个 `.bk2` / 1.1 GB）、对白语音（36 个音频包）与全部索引。

---

## 0.1 2026-10-18 更新：补齐女性角色 + 主线重要度排序

### ① 之前的剧情角色**只导了男性**，女性整体缺失（已修）

`work/npc/cs_prefixes.txt` 里 228 条**全部是 `_ms1`（男）**，一个 `_fs1`（女）都没有 ⇒
阿比盖尔、蒂莉、玛丽-贝丝、格里姆肖、莫莉、凯伦、玛丽·灵顿、凯瑟琳/佩内洛普·布雷斯韦特、
卡尔德隆修女、黑衣美人**全都不在导出里**（虽然 `.ydd` 早就抽到了 `work/npc/models/cutscene/`）。

补齐后 **`export/npc/cs/` = 282 个剧情角色**（227 男 + 55 女，另修 `cs_edmundlowry`、
删掉只有一个帽子的 `cs_mrsadler_ms1`）。总条目 **408 个**。

```bash
uv run python tools/rdr2_npc_export.py --character-file work/npc/cs_missing_prefixes.txt --out export/npc/cs
```

### ② 头发常常是**独立部件**，不补就是光头（已修）

`assemble_character()` 原来只在 merge 组里拼身体+头，**发片 `.ydd` 不在任何 merge 里** ⇒
Charles / Molly / Abel / Gavin / Vampire 等 12 个角色导出后是光头。
现在加了 `hair` 兜底槽位（和 legs/feet 同机制），只要该角色存在 `*_hair*.ydd` 就补上。

### ③ 主线重要度排名 + 浏览页重排（新增）

- 排名表：**`work/npc/story_rank.json`**（85 条，手工维护：`rank` 全局名次 / `tier` / `cn` 中文名 / `note` 身份）。
- 浏览页不再按字母平铺，改为按 **S 双主角 → A 帮派核心 → B 主线反派与章节关键 → C 支线/陌生人 → D 其他具名 NPC**
  分组，条目显示 `名次 + 中文名`，悬浮显示身份；搜索同时匹配英文名/中文名/身份说明。
- `index.csv` 新增 `rank, tier, cn_name, note` 四列。

### ④ 浏览页布光改成"影棚方案"（2026-10-18 追加）

反馈"角色脸上很黑看不清"，根因是原来的布光只有**两盏固定方向的平行光 + 一盏半球光**，
而且没有 tone mapping；RDR2 的皮肤 albedo 本身偏暗，相机一转到背光侧面，脸就直接压成黑块。

现在的做法：

| 项 | 内容 |
|---|---|
| 色调映射 | `ACESFilmicToneMapping`，默认曝光 **1.3** |
| **环境光 IBL** | 程序化生成的 equirect 渐变 + 左右两块"柔光箱" → `PMREMGenerator` → `scene.environment`（**这是解决"半边脸纯黑"的关键**）|
| 主光 | 暖白平行光 **1.8**，右上前方 |
| 侧补光 | 冷白 **1.1**，左前方 |
| 轮廓光 | **1.0**，背后 |
| 面光 | **每帧跟随相机**的平行光 **1.2**，方向 = 相机 → 模型中心 |
| 半球光 | **0.8** |

**标定过程（三次迭代，都是实测像素推出来的，不是拍脑袋）**：

1. 第一版 `4.6+3.2+2.2+3.2 ≈ 13`：three 物理光照下 Lambert 带 `1/π`，
   正面总辐照应 ≈ π 才能落到 `≈ albedo`。13 相当于 4 倍过曝 ⇒ 皮肤和白衣服全推成 1.0 以上、糊成白板（"像鬼"）。
2. 第二版压到 `2.4+1.6+0.8+1.4 ≈ 3.5`：不爆了，但**纯方向光**在脸侧切出硬边，
   暗面只有漫反射余量 ⇒ 另半边脸接近死黑（"还是黑"）。实测脸颊像素 `(61,34,26)`。
3. 第三版：**加 IBL 环境光**承担暗面，方向光只负责造型；脸颊升到 `(134,64,52)`，
   同时全图**纯白像素占比 0.00%**（不爆），近黑像素从 4.1% 降到 1.0~2.2%。

面板（右下角）可实时调：**曝光 / 面光 / 环境**，另有 **全身 / 头部特写** 两个构图按钮
（头部特写的视口高度约 0.59 m，专为看脸；瞄准点是包围盒顶部往下 11.5%）。

也支持 URL 直连：
`index.html?npc=cs_dutch_ms1&view=head`（`view=head` 直接进头部特写）。

### ⑤ 仍然没解决的（诚实清单）

| # | 问题 | 涉及 | 原因 |
|---|---|---|---|
| 1 | **`.yld` 完全没解析** | `cs_mrsadler_fs1`（莎迪）、`cs_cassidy_ms1` 的**头发**；部分女性外套/披肩/睡裙 | 这些部件在游戏里只有 `.yld`。`.yld` 的 drawable 结构与 `.ydd` 不同（body +0x20/+0x28/+0x30 是三个指针、+0x50 不是 model 数组），四种 LOD 都取不到网格，需按 CodeWalker 的 yld 定义重写解析器 |
| 2 | **帽子悬浮** | 阿比盖尔等戴帽角色 | 静态导出没有骨骼/socket，帽子顶点是相对头骨挂点存的，直接当世界坐标用就会浮在头顶上方 |
| 3 | **部分服饰贴图异常** | 莫莉（披肩白斑、蓝块）等 | 老问题：`_c<N>_999_ab` tint 遮罩未套调色板（`assets_tints.ymt` 未解） |
| 4 | **部分角色没有手** | 莎迪等 | 手是通用 ped 部件（`hand_MR1_*`），cutscene 包里没有，需要跨包补 |

---


## 1. 角色模型藏在哪（先定位，别猜）

RDR2 人物**不在** `common_0.rpf`。全部在 **`packs_1.rpf` → `packs/base/models/`**：

| 用途 | 包 | 说明 |
|---|---|---|
| **剧情角色**（过场用） | `metapeds_cutscene_a_f / g_l / m_r / s_z.rpf` | `cs_<名字>_ms1_merge_N.ydd` —— 228 个角色 |
| **主角** | `metapeds_player.rpf` | `player_zero_*`（Arthur）、`player_three_*`（John） |
| **通用路人** | `metapeds_a…z.rpf` | **只有部件**（`head_* / uppr_* / lowr_* / boot_* / hand_*`…），3653 件 |
| **动物** | `metapeds_animals.rpf` | `a_c_<动物>_NN_merge_N.ydd`，118 种 |
| **贴图** | `metaped_textures_*.rpf` + `metaped_textures_cutscene_*.rpf` | 共 26 个包 / **17,570 个 `.ytd`** / 8.8 GB（解出后）|
| **ped 配方** | `packs/base/data/metapeds/metapeds.rpf` | 1086 个 `<ped名>.ymt`（二进制，见 §4-④） |

一次要到「模型 + 它的全部贴图」，用**递归关键词**抽最省事：

```bash
cd tools/rdr2rpf/bin/Release/net9.0
./rdr2rpf.exe extract "H:/EPICGAMES/RedDeadRedemption2/packs_1.rpf" <out> "cs_dutch" --recurse
# → 38 个 .ydd + 9 个 .yld + 104 个 .ytd（模型和贴图一次到位）
```

---

## 2. 怎么把 `.ydd` 变成人（管线）

```
packs_1.rpf
  └─(rdr2rpf --recurse)─► <角色>_merge_N.ydd          ← DrawableDictionary（一个人 = 11 个子 drawable）
  └─(rdr2rpf --recurse)─► metaped_textures_*/**.ytd   ← 多纹理字典
        │
        ├─ tools/rdr2_ydr.py     解析 Dictionary/Drawable/Geometry（★ 现成代码，别重写）
        ├─ tools/rdr2_vdecl.py   读顶点声明 VertexDeclarationG9（SOA）→ POSITION/NORMAL/TEXCOORD0/
        │                        BLENDWEIGHTS/BLENDINDICES/COLOR0/TANGENT
        ├─ tools/rdr2_tex_index.py  为全部 .ytd 建「贴图条目名 → (文件,下标)」全局索引（32721 条）
        ├─ tools/ytd_to_png.py     按条目下标解出 PNG（BC1/BC3/BC5/BC7/RGBA/BGRA 全支持）
        │
        └─ tools/rdr2_npc_export.py  ← **本轮新写**：拼装 + 材质 + 写 glTF(.glb) + manifest.json
```

### 2.1 角色拼装（关键：`merge_N` 是**分组**，不是整套换装）

实测 `cs_dutch_ms1`：

| 文件 | 内容 |
|---|---|
| `merge_17` | 大衣/靴/裤/手套/腰带 + 头发/胡须（**没有脑袋**）|
| `merge_22` | 头 + 眼 + 牙 + 眉 + 头发 + 胡须（**只有脑袋这一组**）|
| `merge_27` | 头 + 裸上身 + 背带 |

⇒ **一个完整的人 = 身体组 + 头部组**，必须**跨文件取并集**（`tools/rdr2_npc_export.py`
的 `assemble_character()`）：身体取顶点最多的那组，头部取部件最全的那组，按 albedo 贴图名去重。

**兜底**：主角这类角色下肢/靴子根本不在任何 merge 里（是 `*_pants_*` / `*_boot_*` 独立部件），
所以脚本会检查"有没有 lowr/pant/leg/boot"，缺了就补同前缀下最大的一件。

### 2.2 贴图解析（`.ytd` 是**多纹理字典**）

⚠️ **按文件名匹配贴图是行不通的**。shader 里写的是**贴图条目名**
（例：`CS_Dutch_MS1_Holster_Belt_001_c0_000_ab`），而它可能躺在
`cs_dutch_ms1_merge_6.ytd`（一个文件里 **32 张**纹理）里。

⇒ 必须先建全局索引（`tools/rdr2_tex_index.py`，26 个包 17,570 个 `.ytd` → 32,721 条目），
再按名字反查 `(文件, 条目下标)`，只解那一张。

---

## 3. ★ 四个必须知道的坑（都是实测踩出来的）

### ① `COLOR0` 会把皮肤染成**纯绿**（本轮最大坑）

RDR2 人物顶点里的 `COLOR0` **不是颜色**，而是 **palette/tint 选择子**：

```
实测 head_mr1_0026 / hand_MR1_000 的 COLOR0 均值 = (0.107, 1.000, 0.000, 1.000)
                                                  ↑R=索引  ↑G=1  ↑B=0  ← "纯绿"
```

glTF 规范里 `COLOR_0` 会**乘到 baseColor 上** ⇒ 导出后**整张脸 + 双手变成亮绿色**。
⇒ **默认不导出 `COLOR_0`**（`--keep-vertex-color` 才会带）。这一条修完，肤色立刻正常。

### ② 顶点坐标有 **+1.0000 m** 的 up 偏移

人物几何相对"根骨（≈骨盆高度）"存放，而 Drawable 头里的 bbox 是**绝对高度**。
实测 5 个角色（cs_dutch merge_17/18、player_zero/three、cs_billwilliamson）恒差 **+1.0000**。
不补这个平移，模型脚底落在 y = −1，进引擎要手调；补了就"脚踩 y = 0"。
脚本里用「header bbox z0 − 顶点 zmin」自动求，取中位数。

### ③ 贴图里有**两类"不是最终颜色"的图**（原文件本身就是绿的）

| 类型 | 特征 | 实测 | 处理 |
|---|---|---|---|
| tint 遮罩 | 名字 `_c<N>_999_ab` | `LOWR_MR1_039_C1_999_ab` RGB≈(31,106,**4**) | `--no-neutralize` 可关；默认**降饱和**成中性灰 |
| 发片图 | 头发/胡须 | `hair_gen_999` RGB≈(52,119,**37**) A=72；`beard_mr1_000` RGB≈(43,123,**29**) | 同上 + `alphaMode=MASK`（发片必须做 alpha 裁剪，否则成一坨实心块）|

真色来自 tint 调色板（`assets_tints.ymt`，二进制 PSIN），**本轮未解**，所以先降饱和保可用。

### ④ ped → 部件的**配方解不了**（通用路人的唯一缺口）

`packs/base/data/metapeds/metapeds.rpf` 里每个 ped 一个 `.ymt`（1086 个），
但它是 **`PSIN` 二进制元数据**：**全文无字符串、不含部件名的 joaat 哈希**（已实测搜不到），
内容形如 `{u16 idx, f32 x,y,z}` 的偏移表 —— 离线无法还原"某 ped 由哪几件部件组成"。

⇒ 通用路人（`a_m_m_*` / `a_f_*`）**没法精确还原成游戏里那一只**。
本轮的做法：按**性别码**（`mr1`=男 / `fr1`=女）从部件池**按槽位各取一件**
（head / hair / beard / eyes / teeth / uppertorso / uppr / lowr / boot / hand），
拼出**结构完整、比例正常**的"同类路人" —— 已人工核验可用，但**不是**某个具名 ped 的精确还原。

---

## 4. 产物清单

```
export/npc/                                  （1.7 GB）
├─ index.html                                ★ 浏览 354 个 NPC（three.js 已内联，1.7 MB）
├─ 打开查看器.bat                        ★ **双击这个启动**：起本地服务 + 打开页面
├─ index.csv                                  清单（名字/分类/部件数/顶点/面/贴图/来源）
├─ cs/<角色名>/<角色名>.glb                     228 个剧情角色
│     ├─ textures/*.png                       该角色用到的 albedo/normal PNG（备查）
│     └─ manifest.json                        部件/材质/贴图/来源 明细
├─ player/player_zero|player_three/*.glb      主角 Arthur / John
├─ generic/generic_male|female_0N/*.glb       6 个通用路人（示意拼装，见 §3-④）
└─ animals/<动物名>/*.glb                      118 种动物
```

export/story/                                （1.6 GB）
├─ dialogue_chinesesimp.txt                  ★ 简体中文对白 339,635 条（含中文 153,830 条，16 MB）
├─ movies/movies/*.bk2                       过场 CG 视频 65 个（1.1 GB，Bink2）
├─ cutscene/cuts_fin1|mud1|gng1/             过场演出动画样本（.ycd + .yad）
├─ audio/peds00/                             NPC 语音样本 36 个（ADAT 容器 + Vorbis）
├─ *_index.txt                                四类文件的完整条目索引（lang/cutscene/movies/audio）
└─ bk2_headers.txt                           65 个 .bk2 的头部校验
```

### 4.1 浏览页必须走本地服务（`file://` 的限制）

**启动方式：双击 `根目录「打开查看器.bat」`**（起本地服务 `127.0.0.1:8788/npc` 并打开浏览器）。

原因是 `file://` 下浏览器会拦两样东西：

| 被拦的 | 后果 | 处理 |
|---|---|---|
| `import ... from './lib/three.js'`（ES module）| 整段脚本不执行 → 列表空 + 视口黑 | ✅ **three.js 源码内联**，运行时 `Blob` + `import()` |
| `fetch('xxx.glb')` | 模型永远加载不出来 | ❌ `file://` 下无法绕过 → **必须走本地服务** |

所以：
- 用 bat（http）打开 → 一切正常；
- 直接双击 `index.html`（file://）→ 界面/列表正常，但**模型加载不出来，页面会显示一条红字提示你改用 bat**。

> 如果确实需要"拷到任何地方双击都能开"，可以加 `--b64` 生成 base64 伴生文件
> （`uv run python tools/build_npc_viewer.py --b64`），代价是体积接近翻倍（+1.5 GB）——**默认不开**。
> 加 `--purge-b64` 可一键删掉这些伴生文件。

### 4.2 浏览页面怎么用

```
双击 根目录「打开查看器.bat」   ← 推荐（也是唯一能看模型的方式）
```

页面左侧按「主角 / 剧情角色 cs_* / 通用路人 / 动物」分组，可搜索（`dutch`、`player`、`wolf`…），
右侧即时渲染所选 NPC，顶部信息条显示部件数/面数/贴图数和来源 `.ydd`。
也支持直连某个角色：`http://127.0.0.1:8788/npc/index.html?npc=cs_dutch_ms1`

### 4.3 导进别的引擎

`.glb` 是通用格式：UE（Interchange/glTF 导入）、Unity（glTFast）、Blender、Godot 都能直接读。
每个角色的 `manifest.json` 记录：
- `parts` / `prims` / `verts` / `tris` / `textures`
- `part_meta[]`：每个部件 → 用了哪张 albedo/normal、全部 shader 贴图槽位（含 `_ma`/`_mb`）
- `sources[]`：来自哪几个 `.ydd`（可回溯）

坐标系：RDR2 是 **Z-up**，导出时转成 glTF 的 **Y-up**：`(x, y, z)_rdr2 → (x, z, −y)`，
**脚底 y = 0**，单位米，身高 1.7~1.85 m。

---

## 5. 已知限制（交付前请知悉）

| # | 限制 | 影响 | 后续方向 |
|---|---|---|---|
| 1 | **通用路人不是精确还原**（§3-④） | 只能当"同类路人"，不是某个具名 ped | 解 `PSIN` 元数据（需要 schema/CodeWalker 级的 meta 定义） |
| 2 | **tint 遮罩贴图未套调色板**（§3-③） | 部分服饰/头发是**中性灰**而非游戏原色 | 解 `assets_tints.ymt` |
| 3 | 主角的**服装是模块化**的（几百件） | 本轮只取了"最大的一组 + 下肢/靴兜底"，不是游戏里某套具体穿搭 | 按部件名挑一套 |
| 4 | **无骨骼/蒙皮动画**（只导了静态绑定姿势） | 模型是 A/T-pose，不能动 | 顶点里**已有** `BLENDWEIGHTS/BLENDINDICES` 和 `Skeleton` 指针，可继续做骨骼导出 |
| 5 | 眼睛贴图是**占位图** | `Eyes_Gen_0000_c0_999_ab` / `Eye_Cap_Gen_0000` 实测是同心圆色斑，不像眼睛 | 该 ped 可能走"眼球 shape/blend"而非贴图 |
| 6 | 头发/胡须是**单层发片** | 近看像灰帽子，没有发束立体感 | RDR2 本身如此（发片 + 染色） |
| 7 | `script_rel.rpf`（任务脚本 `.ysc`）**没解** | TFIT2 key `0xC6` 不在密钥表里（`Can't get encoder key!`） | 补密钥表；本轮用户未勾选该项 |

---

## 6. 复现（端到端命令）

```bash
cd "D:/BrainMaker/大镖客2解包分析"
UV="C:/Users/yaodongcheng/AppData/Roaming/com.brainmaker.client/cowork-updates/uv-binary/uv.exe"
RP="tools/rdr2rpf/bin/Release/net9.0/rdr2rpf.exe"
GAME="H:/EPICGAMES/RedDeadRedemption2"

# 1) 抽模型（含贴图，递归关键词）
"$RP" extract "$GAME/packs_1.rpf" work/npc/models/cutscene "cs_" --recurse   # 或按角色名

# 2) 抽贴图包并建全局索引（一次性，约 8.8 GB / 7 秒建索引）
"$RP" extract "$GAME/packs_1.rpf" work/npc/nested_tex "packs/base/models/metaped_textures_cutscene_a_f.rpf"
"$RP" extract work/npc/nested_tex/packs/base/models/metaped_textures_cutscene_a_f.rpf work/npc/textures/metaped_textures_cutscene_a_f ""
"$UV" run python tools/rdr2_tex_index.py --dir work/npc/textures --out work/npc/index/tex_index.json

# 3) 导一个角色（自动拼身体组+头部组+下肢兜底，含贴图）
"$UV" run python tools/rdr2_npc_export.py --character cs_dutch_ms1 --out export/npc/cs

# 4) 批量（每行一个前缀）
"$UV" run python tools/rdr2_npc_export.py --character-file work/npc/cs_prefixes.txt --out export/npc/cs
"$UV" run python tools/rdr2_npc_export.py --character-file /tmp/pl.txt --model-dir work/npc/models/player --out export/npc/player
"$UV" run python tools/rdr2_npc_export.py --character-file work/npc/animal_prefixes.txt --model-dir work/npc/models/animals --single --out export/npc/animals

# 5) 通用路人（先生成拼装清单，再导出）
"$UV" run python tools/make_generic_peds.py --per-gender 3
"$UV" run python tools/rdr2_npc_export.py --compose-file work/npc/generic_spec.json --out export/npc/generic

# 6) 浏览页 + 清单
"$UV" run python tools/build_npc_viewer.py

# 7) 视觉自检（渲染多视角，交给视觉模型核验）
BL="C:/Program Files/Blender Foundation/Blender 5.2/blender.exe"
"$BL" -b --python tools/render_glb_views.py -- "D:/.../export/npc/cs/cs_dutch_ms1/cs_dutch_ms1.glb" "D:/.../work/npc/verify" dutch

# 8) 剧情：中文对白
"$UV" run python tools/yldb_dump.py --dir work/story/lang/chinesesimp --out export/story/dialogue_chinesesimp.txt
```

---

## 7. 本轮新增工具

| 工具 | 作用 |
|---|---|
| `tools/rdr2_npc_export.py` | ★ 核心：`.ydd` 角色 → `glb` + 贴图 + manifest（含拼装/COLOR0/up 偏移/发片 MASK/tint 降饱和）|
| `tools/rdr2_tex_index.py` | 为全部 `.ytd` 建「贴图条目名 → (文件,下标)」全局索引 |
| `tools/make_generic_peds.py` | 按性别码拼通用路人的部件清单 |
| `tools/yldb_dump.py` | `.yldb` → 可读中文对白文本 |
| `tools/build_npc_viewer.py` | 生成 `index.html` + `index.csv` + 启动 bat |
| `tools/render_glb_views.py` | Blender 渲染 glb 多视角 PNG（交付前视觉自检）|

（`tools/rdr2_ydr.py` / `rdr2_vdecl.py` / `ytd_to_png.py` / `rdr2rpf` 为既有能力，本轮直接复用。）
