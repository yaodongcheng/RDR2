# TODO —— 交接版（2026-11-05）

> 交接阅读顺序：1) 本文（最上面是**当前状态**：56 张已建完，但**室内对齐修复之后要再重跑一遍**，见第一节）2) `docs/格式与资产/分类体系与判定规则.md`（22 类 / 判定顺序 / 纠错清单）3) `docs/AGENTS.md`（**§6 场景地形全部教训**；室内看 **§6.14 / §6.15**）4) `docs/交接与状态/README_交接.md`（历史）。
> **红线**：分类规则只改 `tools/class_rules.py`；改完必须跑 `python tools/_check_rules.py`。构建前先关 RDR2（RPF 锁）。

---

## 🔴 2026-11-05 · 待执行：**室内对齐修好了，56 张场景要再重跑一遍**（约 2.5~3 h）

> 13:40 那批 56 张是在**室内摆歪**的状态下建的（见下），修完必须重跑才能吃到。

**结论**：室内墙面与外壳对不上 = **MLO 实例的四元数多取了一次共轭**（件级要取、实例不取）。
夏洛蒂家当年靠"硬掰 yaw + bbox 居中"糊过去，就是补这个错。**已根因修复**。

| 修了什么 | 位置 | 数字 |
|---|---|---|
| 实例四元数不取共轭 | `scene_interiors.py` / `instantiate_interiors.py` / `audit_interior_placement.py` / `merge_interior.py` / `merge_interior_into_willard.py`（5 处） | 室内壳墙向 −6.5° → **3°**（外壳 4°） |
| willard 脚本去掉"硬掰 yaw + 居中" | `merge_interior_into_willard.py` 末尾改成**只测量不执行** | 根因修了还留着 = 错两次 |
| 宿主判据：小道具/地形块/电缆不能当宿主 | `audit_interior_placement.py` 新增 `_PROP_NAME` + `_BAD_NAME` 补 `_dcl` | 非建筑宿主 **77 → 6**；`inside=True` 仍 179（覆盖无损） |
| 阴影/反射代理件单独成类 `int_proxy`、默认隐藏 | `class_rules.py`（登记类）+ `scene_interiors.py`（判定） | 全量 **326 件**（命名 18 种变体：`_shadowproxy` / `_ref_proxy` / `_shdw_prxy` …）；面板里是独立一栏「室内阴影代理」 |
| 🔴 **哈希没补零 ⇒ 室内件被静默丢掉** | `scene_interiors.py` / `instantiate_interiors.py` 改 `hx = '0x%08x' % e['h']` | 全量 **2,495 个模型**因此从未出现（占室内件 5.4%）；瓦伦丁 **+73 件** |
| 🔴 **名字查不到的 LOD 分身压在 HD 上** | `class_rules.apply_texture_lod()` + `classify_entities.py` 一行 | 瓦伦丁 `unknown` **607 → 85**；屋顶暗斑消失（谷仓 `e_f005a86d` 归 `lod`） |
| **建筑贴花单独成类 `bldg_decal`** | `class_rules.py`（规则排在 `bldg` 之前）+ 四处类登记 | 瓦伦丁 **27 件**默认隐藏（`bldg` 123→113）；银行屋顶"花斑"消失（`val_bank_dcl01`） |
| 🔴 **室内宿主改用房间壳量 + 审计补零** | `audit_interior_placement.py` | `inside=True` **179 → 210**；威拉德之息 `roc_house_int` 归位（原先 0 个室内包） |

> 🔴 **顺带否掉一个旧方向**：README §0.8.3 / 本文件旧版说"缺一层 CMloArchetypeDef rooms/portals 变换"——
> **不存在**。CodeWalker 的 `CMloArchetypeDef` 只有 flags + 数组，room 只有 bbox，没有任何变换字段。
> 别再往那个方向查。细节见 `docs/AGENTS.md` **§6.14 / §6.15**。

**已验收**（`val.blend` 17:50 重跑）：室内壳 3° vs 外壳 4°；四边间隙 W+0.67 E+0.99 S+0.81 N+5.66 全为正；
室内 **12 包 / 1,632 件**（旧 1,559，补零修复 +73）· `int_decal` 34 · **`int_proxy` 20**；
`i_a6cc1063` = `val_saloon_int_shadowproxy` 已归 `int_proxy`、视层隐藏；`scene_build_status.csv` = `done/ok`。

**用户验收通过（2026-11-05）**：`val`（瓦伦丁）、`roc`（威拉德之息 = 夏洛蒂家）。
`roc` 现为 **1 包 / 447 件**、四边间隙 **+2.16/+0.23/+0.59/+1.54**、`int_decal` 3 件（`roc_dirt_stains` 系列）。
`bla` 11/1,763 · `sdn` 22/4,136 已按新表重建，但**建在"严格贴花"修之前**，`int_decal` 计数会下降。

**要做**：
```powershell
Set-Location "H:\SteamLibrary\steamapps\common\Mount & Blade II Bannerlord\Modules\RDR2\Source"
python -X utf8 tools\build_scenes.py --force
```

**验收判据（缺一不可）**：
1. 每张日志里都有 `[int] 其阴影代理壳 N 件`（有 shadow 件的包才会 > 0）；
2. `scene_build_status.csv` 56 行全 `done`；
3. 抽查 3 张：室内 `*_shell` 与宿主 `*_ext` 墙面平行；机器判据 = `python -X utf8 tools\_check_interior_align.py`
   （4θ 矢量平均，口径见 `docs/AGENTS.md` §6.14；宿主判据修好后这张表才有意义，之前跑过的不作数）；
4. `rooms` 列与旧值**允许变**（宿主判据改了 ⇒ 被摆的包会变），但要能对上 `inside=True` 的 179。

---

## 🔴🔴 2026-11-05 · 联合重跑（UV 的 V + 远景 LOD 名字 + 室内贴花）——**历史执行记录**

> ⚠️ 这一节描述的批次**已于 2026-11-05 13:40~14:37 跑完**（56 张）。
> 但**室内对齐的修复是在它之后才落地的**（见上一节）⇒ 这 56 张还要再重跑一遍。

> 两件事必须**同一次跑完**：
> ① 下一节的 **UV 的 V 翻转**（代码已改好、一次都没跑）；
> ② **远景 LOD 名字缺口**（`docs/交接与状态/RDR2_远景LOD名字缺口_20261105.md`：names.txt 缺
> `*_children` 父名 → 全图 158 个街区 LOD 被判成 `e_<hash>` / `veg`，每座城的远景都偏稀）。
> 分两次跑 = 远景库翻两遍、场景建两遍，白烧 3~5 小时。

### 0. 哪些生成 blend 要重跑（结论）

| 产物 | 含远景碎片？ | 要重跑？ | 说明 |
|---|---|---|---|
| `continent/continent_v23.blend` | 是（全部） | ❌ **不动** | **红线**，只当抽 LOD 的源。要修它 = 全量重建 v24（60~90 分钟），本次不做。 |
| `continent/continent_lod_split_v23.blend` | 是（LOD 库） | ✅ **重建** | 旧库两处都不对：UV 旧 + 缺 158 个街区 LOD。新出 `_v24_raw`（未翻）→ `_v24`（已翻）。 |
| `scenes/*.blend`（56 张） | 是（每张都 append LOD 库） | ✅ **全部重建** | 高清/室内当场读模型，自动吃新 UV；远景来自 LOD 库，靠 v24。 |
| `regions/*.blend`（22 张） | 是（每张 1~512 条 LOD） | ⚠️ 不重建 | 只作区域检查 / backfill 源；当成品看的话要单独 `flip_uv_in_blend.py` 补翻（另议）。 |
| `guarma/guarma.blend`、`willard/*`、`characters/*` | 部分 | ❓ 另议 | 不在 56 场景链路里，本次不动。 |

### 1. 执行顺序（固定，别跳；每步不过就停）

工作目录（下面命令都从这里起算）：

```powershell
Set-Location "H:\SteamLibrary\steamapps\common\Mount & Blade II Bannerlord\Modules\RDR2\Source"
```

**开跑前先关 RDR2**（RPF 锁）。

| # | 做什么 | 命令 | 判据 |
|---|---|---|---|
| **1** | UV 闸门 | `python -X utf8 tools\check_uv_v_convention.py --scene val` | 递减 **671** / 递增 98 → **PASS** |
| **2** | 闸门负面测试 | `python -X utf8 tools\check_uv_v_convention.py --selftest` | **必须 FAIL**（98/671） |
| **3** | 分类自检 | `python -X utf8 tools\_check_rules.py` | **PASS**（36 条用例） |
| **4** | 远景分组表（第一遍，**必须先抛开旧部件表**） | `python -X utf8 tools\build_lod_groups.py --parts ""` | CSV 里出现 **5 条 `assign_via=span`**（`new_area_slod4` / `nopq_07_10_area_slod4` 等）；同时清单出现 `val_02_slod` … `val_07_slod`（158 个街区 LOD 已被补充名认回） |
| **5** | 从 v23 抽 LOD 库 | 见下方命令块 **⑤** | 日志 `ONLY_lod_远景碎片` 数量应 ≈ **2,320 + 158**，不是 2,261 |
| **6** | 补区域 57 条 | **⑥** | 追加 57 条左右 |
| **7** | 切跨据点块 | **⑦** | 5 父块 → 11 件 |
| **8** | 分组表（第二遍，带部件） | `python -X utf8 tools\build_lod_groups.py` | 5 父块 → 11 个拆分件（日志 `拆分件替换：5 个跨据点整块 → 11 个部件`） |
| **9** | 按据点分组 | **⑨** | 55 组；S_val 的数量应含 `val_02_slod` 等 |
| **10** | 🔴 **补翻 UV** | **⑩** | 日志 `v 均值 前 X → 后 = 1−X`；新文件约 **0.36 GB**（compress=True，比未压缩的 1.13 GB 小是正常的）；场景带 `uv_v_flipped=1` |
| **11** | 把 `LOD_SPLIT_BLEND` 指到 v24 | 改 `tools\blender_continent.py` 第 23 行 | 不指 = 日志 `[lod] 缺远景库/分组表，跳过` |
| **12** | 只重建 `val` | `python -X utf8 tools\build_scenes.py --only val --force` | `scene_build_status.csv` 该行 `done`；`placement_val.jsonl` 行数应与旧值核对（UV/改名不改对象数，变了就是别处动了东西） |
| **13** | 用户目视 `val.blend` | 启动器 `打开大陆_流畅.bat val` | 招牌 `SMITHFIELDS.` 正立；远景里能看到街区 LOD |
| **14** | 批量 56 张 | `python -X utf8 tools\build_scenes.py --force` | 2~4 小时；一次只跑一个 Blender |

**⑤ 抽 LOD 库（新文件名，不覆盖 v23 库）**

```powershell
cmd /c 'tools\run.cmd D:\BrainMaker\大镖客2解包分析\_logs\lod_split_v24.log "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" -b "D:\BrainMaker\大镖客2解包分析\deliverable\blender\continent\continent_v23.blend" -P tools\_unbuffer.py -P tools\extract_class_blend.py -- --keep lod --keep terrain_lod --out "D:\BrainMaker\大镖客2解包分析\deliverable\blender\continent\continent_lod_split_v24_raw.blend"'
```

> 🔴 **别写 `--keep lod,terrain_lod`**：经 `cmd /c` 时逗号会被 cmd 当参数分隔符，`terrain_lod` 掉出来变成裸参数
> （2026-11-05 实测 `error: unrecognized arguments: terrain_lod`，exit=2）。两个 `--keep` 最稳。
```

**⑥ 补区域 57 条**（就地改 `_v24_raw`）

```powershell
cmd /c 'tools\run.cmd D:\BrainMaker\大镖客2解包分析\_logs\lod_backfill_v24.log "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" -b "D:\BrainMaker\大镖客2解包分析\deliverable\blender\continent\continent_lod_split_v24_raw.blend" -P tools\_unbuffer.py -P tools\backfill_lod_blend.py -- --csv "D:\BrainMaker\大镖客2解包分析\deliverable\handoff\lod_fragments.csv"'
```

**⑦ 切跨据点块**（就地改 `_v24_raw`）

```powershell
cmd /c 'tools\run.cmd D:\BrainMaker\大镖客2解包分析\_logs\lod_splitblocks_v24.log "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" -b "D:\BrainMaker\大镖客2解包分析\deliverable\blender\continent\continent_lod_split_v24_raw.blend" -P tools\_unbuffer.py -P tools\split_span_blocks.py -- --csv "D:\BrainMaker\大镖客2解包分析\deliverable\handoff\lod_fragments.csv" --spec "D:\BrainMaker\大镖客2解包分析\_scratch\settlement_plan\scene_specs.json" --out-parts "D:\BrainMaker\大镖客2解包分析\deliverable\handoff\lod_split_parts.json"'
```

**⑨ 按据点分组**（就地改 `_v24_raw`）

```powershell
cmd /c 'tools\run.cmd D:\BrainMaker\大镖客2解包分析\_logs\lod_regroup_v24.log "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" -b "D:\BrainMaker\大镖客2解包分析\deliverable\blender\continent\continent_lod_split_v24_raw.blend" -P tools\_unbuffer.py -P tools\group_lod_blend.py -- --csv "D:\BrainMaker\大镖客2解包分析\deliverable\handoff\lod_fragments.csv" --groups "D:\BrainMaker\大镖客2解包分析\deliverable\handoff\lod_groups.json"'
```

**⑩ 补翻 UV → 最终 v24**

```powershell
cmd /c 'tools\run.cmd D:\BrainMaker\大镖客2解包分析\_logs\lod_uv_flip.log "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" -b "D:\BrainMaker\大镖客2解包分析\deliverable\blender\continent\continent_lod_split_v24_raw.blend" --python "D:\BrainMaker\大镖客2解包分析\tools\flip_uv_in_blend.py" -- --out "D:\BrainMaker\大镖客2解包分析\deliverable\blender\continent\continent_lod_split_v24.blend"'
```

### 2. 本次一并生效的三件事

- **室内对齐（2026-11-05 新增，见本文最上面那一节）**：MLO 实例四元数不取共轭 + 宿主判据
  + 阴影代理壳单独隐藏类。`val.blend` 已验收，**56 张都要靠重跑吃到**。

- **室内地面贴花**：`scene_interiors.py` 现在按模型贴图名判 `int_decal`（第 22 类，默认隐藏）；
  重建场景后自动出现集合 `ENTITIES/C_int_decal_室内地面贴花/int_decal|<地块>`。
- **纠错语义**：`class_rules.apply_corrections` 改成「名字+贴图都写 ⇒ 两者都要命中」，
  不再把所有 `e_*` 判成 `veg`。

### 3. 本次执行记录（2026-11-05，边跑边记）

| 步 | 结果 |
|---|---|
| ⑤ 抽 LOD 库 | `lod` **2,418**（旧 2,261，**+157**）· `terrain_lod` 32 · `_v24_raw` **1.13 GB** |
| ⑥ 补区域 | **+57**（`wild2000_03_02` 15 + `wild2000_04_02` 42）· 父集合 2,475 · PASS |
| ⑦ 切跨据点块 | 5 父块 → **11 拆分件** · PASS |
| ⑧ 分组表第二遍 | **2,481 片** · PASS |
| ⑨ 按据点分组 | `S_val_瓦伦丁` **87**（旧 66）· 全库归位 2,481 · **0 未匹配** · PASS |
| ⑩ 补翻 UV | `continent_lod_split_v24.blend` **360 MB**（压缩后）· `uv_v_flipped=1` · 翻转数学核对通过 |
| ⑫ 只重建 val | **6,225 对象**（远景 893）/ 144 s / **220.8 MB**；`placement_val.jsonl` **7,645** 行；`rooms` **11/1499**；`int_decal` **32 件** |
| UV 招牌 A/B | `Source\_scratch\uv_ab.png`：旧口径乱码 → 翻 V 后 **`SMITHFIELDS`** 正立 |
| 批 56 张 | 后台运行，日志 `D:\BrainMaker\大镖客2解包分析\_logs\build_all_v24b.log`（2026-11-05 13:40 起，含 alpha 修复 + fragslod 规则） |
| ⑬ 只重建 val（**室内修复之后**） | 6,225 对象（远景 893）/ 156 s / **224.7 MB**；`rooms` **12/1632**（旧 11/1499）；`int_decal` 34 · **`int_proxy` 20**；`done/ok` |

**踩到并已写进上面步骤的两个顺序坑**：
1. `--keep lod,terrain_lod` 经 `cmd /c` 逗号会被当分隔符 → 用两个 `--keep`；
2. 旧 `lod_split_parts.json` 还在时先跑第一遍 `build_lod_groups`，会把 5 个父块直接替换成部件，
   ⑦ 就 `待拆整块 0 个` → 第一遍必须 `--parts ""`。

### 4. 2026-11-05 · 贴图 alpha 全量修复（UV 之后的第二个全局问题）

**根因**：模型库是 2026-10-28 建的，当时贴图池/索引与现在不同 → 一批「源格式 DXT5/BC7（有 alpha）」
的贴图被导出成了 **RGB**。材质在创建时按 PNG 判断 alpha，于是透明背景被画成实心片
（招牌上的灰方块、树冠卡片、道路污渍片）。

**全量普查（39,827 张库贴图）**：

| 状态 | 数量 |
|---|---:|
| RGBA 正常 | 21,193 |
| RGB + 源格式无 alpha（正常） | 16,023 |
| **RGB + 源可带 alpha（丢了）** | **2,611** |
| └ 解出来确实有透明、已补写 | **1,782** |

**使用面（56 张场景 / 206,790 个对象）**：**12,668 个对象**用到过丢 alpha 的贴图。
按类：`road 350/781 = 44.8%` · `veg 3,863/11,820 = 32.7%` · `underground 2,205/7,776` ·
`bldg 1,319/4,814` · `decal 469/2,882 = 16.3%` · `rail_decal 47/490`。

**已做**：

1. `tools/refill_lib_tex_alpha.py`（新）—— 逐张重解码、补写 1,782 张；幂等，`--dry` 可统计。
2. `continent_lod_split_v24.blend` 重挂材质（2,512 网格 / 3,225 槽），远景碎片也吃 alpha。
3. `relink_materials.py` 补 `i_<hash>` 兜底（室内件原来没有 `hash` 属性，重挂不到）。
4. `region_corrections.csv` 第 341 行：`^e_` + `_slod|fragslod|_dslod` 贴图 → `lod`。
   （AND 修正后暴露的副作用：以前所有 `e_*` 被误判 veg 隐藏，修正后无真名的那批落回 unknown 可见；
   这条把其中「碎片 LOD」重新收进隐藏类。v23 名字上命中 3,740 / 改变 3,478。）

**val 验证（2026-11-05 13:30 重建）**：招牌 `SALOON`/`MEALS`/`CLOSED` 清晰、灰方块消失；
decal/road/rail_decal 里「丢 alpha」的对象 **归零**；碎片 LOD 灰块消失。

**仍是已知缺口（不是 alpha）**：少数道具模型本身没有 albedo（`models[h].s[0][0] == -1`，
如 `p_group_valcrates02` 的 `p_group_valcrates02_ab` 没被抽出）→ 暖灰材质。属「缺贴图」清单。

### 4b. 2026-11-05 · 无贴图模型通用材质 + 高度图贴花（alpha 之后的第三/第四件事）

**① 无贴图模型：按类别给「通用材质」，不再是纯色平涂**

- 规模：全 56 场景 **19,872 个对象 / 1,999 个模型**整个模型没有 albedo（室内 4,765 对象 / 724 模型）。
- 做法：
  - `tools/ntex_palette.py` 判定**类别**（木/金属/布/纸/玻璃/食物/绳/皮革/陶/石/土/水/植被）+ 金属度/粗糙度/贴图尺度；
  - `tools/ntex_materials.py`（新）给每类挑一张**库内真实贴图**（木类 = `abe_woodbeam01_ab` 等），
    用 **Box 投影**（Object 坐标）铺开；金属类 metallic=0.85；取不到贴图才退回纯色；
  - `blender_continent._ntex_generic()` 在 `_mat_for()` 三张图全缺时调用；
    `load_model_mesh(..., name_hint=模型名)` 传名，室内（`scene_interiors.py`）也传。
- 🔴 **关键坑**：`.mdl` 的 texId 是 **u32**，缺失值是 **`0xFFFFFFFF` 不是 -1**。
  原来只判 `< 0` → 全部缺失件都被当成"有效 texId"，通用材质根本没生效（2026-11-05 实测）。
  已在 `_mat_for` 里把 `0xFFFFFFFF` 归一成 -1。
- 验证：val 里 `i_28bbc12d`（`p_table_cs34_sml` 桌子）材质 = `ntex_wood`，带真实木纹（不是平涂）。

**② 高度图贴花：alpha 是脚印遮罩，不能当颜色、也不能一藏了之**

- `l_09_heighttracks_decals01/02/03`、`p_14_02_track_dec_01/02/03`（val 3 / cal 3 / sdn 1）的 albedo 槽
  放的是**高度图**（`*_height_*`，RGB = (R,255,255)）：
  - RGB 当颜色 = **青色脚印**；
  - **alpha 通道才是脚印遮罩**（黑底 + 灰色脚印，实测均值 3/255、最大 137/255）；
  - R 通道是高度（背景恒定值，脚印处凹陷）。
- 做法：`mat_rdr2.make_height_decal()`（`get_or_make` 里按贴图名 `_height_` 分流）：
  深泥色底 + **alpha×4 当透明度** + R 经 ColorRamp 做明暗起伏 → 深色泥脚印，不再是青色。
- 🔴 另一个坑：这些贴花的数据 z 来自游戏，和 H4 地形差 1~2 m——不贴地会**浮在地面上被阳光照亮**
  （看成浅色印子）。`blender_continent.build_entities()` 里对高度图贴花 + muddyroad 贴花
  **逐顶点**贴到 `ground_z(x,y)+0.05`（抬 5 cm 防 z-fighting），不再只是中心点贴地。
- 验证：val 路面出现**深色泥脚印**，无青色；`_check_rules.py` PASS（纠错表里原先那条
  `height→placeholder` 已删除，不再隐藏）。

**③ 模型里「部分子网格没贴图」= 外壳/背板 → 真透明**

- 典型：`val_03_jail_ext` 第 15 槽（1,988 面，盖住砖墙）、`val_freightstn` 第 16 槽（3,336 面，屋顶外壳）。
- 做法：`_mat_for()` 发现「模型里其它子网格有贴图、唯独这块没有」→ 用 `invisible_shell`（Transparent BSDF）。
- 🔴 **必须设混合模式**：`surface_render_method='BLENDED'` + `blend_method='BLEND'`。
  只挂 Transparent BSDF 不设混合模式，EEVEE 按不透明渲染 = **纯黑**（用户 2026-11-05 看到屋顶黑块，
  误以为"透明会漏"，实际是黑材质；改正后屋顶完整、监狱外壳透明露出砖墙）。
- 整模型全缺贴图才走通用材质（`ntex_palette`/`ntex_materials`），部分缺不套通用色。

### 5. 跑完的验收判据（缺一不可）

1. `lod_groups.json` 里 `S_val_瓦伦丁` 的 `count` 明显变大（应含 `val_02_slod` … `val_07_slod`）；
2. `val.blend` 里远景能看到成片街区（对照图 `deliverable/blender/continent/shots/val_lod_before_after.png`）；
3. 招牌文字正立、无深红实心板；
4. `scene_build_status.csv` 56 行全 `done`；`rooms` 与旧值一致（UV/改名不影响室内件数）；
5. `_check_rules.py` PASS、UV 闸门 PASS。

---

## 🔴 2026-11-05 · 待执行：**UV 的 V 约定**（已改代码，一张 blend 都还没重跑）

> 🟢 本节是**联合重跑**的一部分：执行顺序已合并到上面「联合重跑」那一节，
> 本节保留根因与证据（为什么翻、怎么验），**不要按本节末尾的 1~8 步单独跑**。

> 用户现象：`val.blend` 里酒馆招牌「有字但认不出」、街上杂物比游戏里多得多。
> 第一件事已查清并改好代码；第二件事只查到「数据缺字段」这一层，见本文下一节。

### 1. 根因（一句话）

**RDR2 模型 UV 的 V 原点在图片顶端（DirectX 约定）；Blender 在底端。管线一直按原样塞进去 ⇒ 所有模型的贴图都上下镜像了一次。**
平铺贴图（木板 / 砖墙 / 瓦片）近似对称，翻了看不出来；**文字、海报、贴花、玻璃一翻就废**。
这就是"只有墙面基色是对的、招牌全是乱码"的由来。**贴图文件本身没问题，不用重新解包。**

### 2. 证据（都能复算，别再靠推）

| 项 | 实测 |
|---|---|
| 招牌左半块 UV | `corr(z, v) = −1.000`，拟合 `v = −0.329·z + 0.627` ⇒ **v 随高度递减** |
| 同一几何 + 同一张 `tex/11074.png`，按现状采样 | `FIELDS`+`SMITH` 顺序反**且**上下颠倒（= 用户看到的乱码） |
| 同上，只把 V 翻过来 | **`SMITHFIELDS.` 正立**，与游戏截图一致 |
| 杂货铺 `val_genstore_ext` 独立复验 | `WORTHS.` / `GENERAL STORE.` / `FRESH BREAD` / `PROP. L. WORTH` / `CLOTH LINEN` / 底部 `GROCERIES DRY GOODS…` **六处文字一次全对** |
| 闸门 | `python -X utf8 tools\check_uv_v_convention.py --scene val` → 3,066 模型 / **769 个竖立面子网格** / 递减 **671** · 递增 98（**87%**）→ **PASS**；`--selftest` 翻一次后变 98·671 → **FAIL**（分辨力已验） |

> ⚠️ 之前有一版结论说"招牌不能靠顶点 UV0、要改平面投影"——**那是错的**。平面投影只对
> 正对镜头的平招牌凑巧成立（这块招牌的 UV 对世界 z 严格线性，所以任何近似都"看着对"），
> 海报 / 贴花 / 玻璃 / 斜招牌一个都修不到。真正的修法只有**翻 V**。

### 3. 已经改好的代码（**没有提交 git，用户自己提交**）

| 文件 | 改了什么 |
|---|---|
| `tools/rdr2_uv.py`（**新**） | V 约定的**唯一真身**：`to_blender_uv()` / `to_gltf_uv()` + 证据与三端口径 |
| `tools/blender_continent.py` | `load_model_mesh()` 写 UV 前 `v = 1 − v`；新增 `--alpha on\|off`、`--no-uv-flip`（复现旧错误用）；启动打 `MATERIAL two_layer=… alpha=… uv_v_flip=…` |
| `tools/mat_rdr2.py` | 新增 `alpha_mode()`：albedo 的 alpha 接进 BSDF，按判据设 `DITHERED`（镂空）/ `BLENDED`（半透明）；材质上记 `alpha_mode` 自定义属性 |
| `tools/blender_city_lod.py` | 同上翻 V（城市 LOD 也读同一份 `.mdl`） |
| `tools/export_sdn_gltf.py` | 🔴 **去掉** `1.0 - u[1]` —— RDR2 与 glTF **同为左上原点**，那行是二次翻转 |
| `tools/export_weapon_tint.py` | 同上 |
| `tools/check_uv_v_convention.py`（**新**） | 闸门：判"v 是否随高度递减"；`--selftest` 负面测试必须 FAIL；`--png <mdl> <sub> --out …` 出 A/B 对照图 |
| `tools/flip_uv_in_blend.py`（**新**，**未跑过**） | 给**预建 blend**（远景库）整体补翻一次 V；幂等标记 `uv_v_flipped`，拒绝翻两遍、拒绝覆盖源文件 |
| `tools/build_scenes.py` | 把 UV 闸门接进批量开跑前的检查（不过就 `return 4`，不会白跑 4 小时） |

**Alpha 那条的单独证据**：`tex/11074.png` alpha==0 占 **68.2%**、<128 占 **80.6%**，透明区 RGB 均值 **(106, 72, 73)** 深红棕 ⇒ 不接 alpha 就是一块深红实心板（游戏里是"字直接刷在粉墙上"）。`--alpha off` 可回退做 A/B。

### 4. 下一步：要跑的东西（**按顺序，别跳；每步不过就停**）

先设工作目录，下面命令都从这里起算：

```powershell
Set-Location "H:\SteamLibrary\steamapps\common\Mount & Blade II Bannerlord\Modules\RDR2\Source"
```

| # | 做什么 | 谁 | 命令 / 判据 |
|---|---|---|---|
| **1** | 过闸门（不开 Blender，约 2 秒） | agent | `python -X utf8 tools\check_uv_v_convention.py --scene val` → **PASS**（递减 671 / 递增 98）；再跑 `--selftest` → **必须 FAIL**（98 / 671）<br>⚠️ `build_scenes.py` 每批开跑前会自动跑这一条，不过就 `return 4` 停批 |
| **2** | 一张图定案（不开 Blender） | agent | `python -X utf8 tools\check_uv_v_convention.py --png 3a/0x3adbe18d.mdl 10 --out _scratch\uv_ab.png`<br>判据：**下半张读成 `SMITHFIELDS.`**；上半张是乱码（那是旧口径，留作对照）<br>不是这样 ⇒ **停下查管线有没有二次翻转，别往下走** |
| **3** | 🔴 **远景库补刀**（不做的话，重建完远景碎片仍是反的） | agent | 见下方「3 详解」 |
| **4** | **只重建 `val` 一张**（约 2~5 分钟） | agent | `python -X utf8 tools\build_scenes.py --only val --force`<br>判据：`scene_build_status.csv` 该行 `done`；重出的 `placement_val.jsonl` 仍是 **7,645** 行（UV 改了不影响对象数，变了就是别处动了东西）；日志里 `[lod] append … 个远景碎片` 有数字、不是"缺远景库" |
| **5** | 开 `val.blend` 目视 | 用户 | `Start-Process -FilePath "H:\SteamLibrary\steamapps\common\Mount & Blade II Bannerlord\Modules\RDR2\Source\launchers\打开大陆_流畅.bat" -ArgumentList "val"`<br>判据：① 酒馆招牌 = `SMITHFIELDS.` **正立**；② 杂货铺 = `WORTHS. GENERAL STORE.`；③ 招牌周围**不再有深红实心板**（alpha 生效）；④ **活动区外**的远景碎片也应当是对的（第 3 步没做就会看到反的） |
| **6** | 通过才批量 | agent | `python -X utf8 tools\build_scenes.py --force`<br>56 张约 **2~4 小时**；一次只跑一个 Blender；**开跑前先关 RDR2**（RPF 锁） |
| **7** | glTF 预览重出并复核 | agent | 网页预览若出现文字上下颠倒 ⇒ 预览侧别处还有一次翻转，按 `tools/rdr2_uv.py` 的口径对齐 |
| **8** | 区域 blend / 大地图 / 其它预建 blend | **先问用户** | `continent_v23.blend` 是**红线不许改**，要修就出 v24；`regions\*.blend`（22 块）、`deliverable\blender\willard\*` 同样是旧口径（都是预建资产，重跑场景改不到，需逐个 `flip_uv_in_blend.py` 或重建） |

**3 详解（远景库）**：场景里的远景碎片不是当场建的，而是
`blender_continent.append_lod_groups()` 用 `bpy.data.libraries.load(..., link=False)`
从 `deliverable\blender\continent\continent_lod_split_v23.blend` 整块 append ——
UV 在 2026-11-01 建库时就烘死了，**重跑场景修不到**。（室内件不受影响：
`scene_interiors.py` 当场调 `load_model_mesh()`，自动吃到修复。）

```powershell
& "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" -b "D:\BrainMaker\大镖客2解包分析\deliverable\blender\continent\continent_lod_split_v23.blend" --python "D:\BrainMaker\大镖客2解包分析\tools\flip_uv_in_blend.py" -- --out "D:\BrainMaker\大镖客2解包分析\deliverable\blender\continent\continent_lod_split_v24.blend"
```

- 判据：日志 `v 均值 前 X → 后 ≈ 1−X`；新文件约 **1.1 GB**；场景上写入 `uv_v_flipped=1`。
- 然后把 `tools\blender_continent.py` **第 23 行**的
  `LOD_SPLIT_BLEND = …continent_lod_split_v23.blend` 改成 **v24**（不指就白翻，
  日志里 `[lod] 缺远景库/分组表，跳过` 就是漏了这一步的典型症状）。
- ⚠️ 本脚本**写好了但一次都没跑过**（写的时候 Blender 被占用，不允许并跑）——第一次跑先看日志，
  再随便挑一个远景碎片确认 UV 是不是 `1 − v`。

**🔴 两条禁令**：① 别用 `--no-uv-flip` 去"对比一下"——它只为复现旧错误存在；
② 别手改 `tools/rdr2_uv.py` 之外的任何地方去实现翻转，那是唯一真身。

### 5. 未决（**不能靠猜，必须验**）

1. 🔴 **骑砍2 侧（TRF + DDS）的 V 原点在哪** —— D3D 惯例是左上（与 RDR2 同），照理不用再翻；但引擎加载时会不会再翻一次，**只能拿一件带字的网格进游戏看一眼**。这条定了才知道 TRF 导出要不要把 Blender 这次的翻转再翻回去。**批量出 TRF 之前必须先做这个最小实验。**（TRF 走 `Scripts/export_rdr2_trf_from_scenes.py` 从场景 blend 出，所以 blend 修好后 TRF 自动继承。）
2. `--alpha` 的默认开会不会让某些材质（玻璃 / 铁艺）出现排序闪烁 —— 重建后抽查；要退就 `--alpha off` 重建对比，或把 `mat_rdr2.alpha_mode()` 的 `blend` 判据收紧成只留 `clip`。
3. 远景库翻完之后，**区域 blend（22 块）和 `continent_lod_split_v23` 的旧文件**要不要一起换 —— 等用户裁定。

---

## 🔴 2026-11-05 · 待查：街上的杂物比游戏里多（**已定位到"多的是哪一层"**）

> 用户点名的样本：`p_barrel_cor01x` 在 blend 里出现在瓦伦丁酒馆前，但游戏里走过去看不到。

### 1. 先排除"数据造假"：我们的实例表是忠实拷贝

| 对账 | 结果 |
|---|---|
| `town_data/val.js` vs `jklm_7_10_area_lod_combine_metadata/val_*.ymap` | **2,263 : 2,263**，同名同位置 **<0.5 m 的 1,832 条、对不上 0 条**（另 431 条是 names.txt 查不到的哈希） |

⇒ 不存在"我们多编了实体"。

### 2. 真正多出来的是**另一层 ymap**

瓦伦丁能走范围 P 内，按来源拆开：

| 来源 | 实体 | 文件 |
|---|---:|---:|
| `val_*.ymap`（城镇常驻层，= `val.js` 的全部来源） | **2,263** | 43 |
| **哈希命名 ymap**（`0x3B8F523D.ymap` 这种） | **1,617** | 110 |

- 那 110 个文件里 **87 个文件 ≤10 个实体**（合计 240 个）——是**小规模布景/条件加载**的样子；
- 我们的 `build_continent_index.py` 把 `town_data/*.js`（`_misc.js` 等）**全量平铺合并**，游戏是**按 ymap 为单位加载**的。

### 3. 用户点名的那个桶，出处已查实

- `0x3B8F523D.ymap` **整个文件只有 6 个实体**：`p_cart01x` ×1 + `p_barrel_cor01x` ×4（+1），
  坐标 `(-310.0, 792.8)` 与我们的实例**逐位相同**；
- 同簇还有 `p_woodramp01x` / `p_dollynbx01x` / `p_cask01x` / `p_cratecover07x`（来自 `0x79A4CBF8` / `0x7CE0F18D`）；
- 位置关系：**酒馆 `val_03_saloon_ext` 在它正北 14.8 m**，周围 3~4 m 内还有 3 台 `p_cart01x`
  ⇒ 这是一个**装卸角/后院布景**，不是街面散件。
- 结论：桶在游戏数据里**确实存在**（不是我们摆错），但它在**独立的小 ymap** 里，
  与我们当常驻画出来是两回事。**"游戏里看不看得到"取决于这层 ymap 是否被加载**，这一条需实机对照才能定论。

### 4. 🔴 更正旧说法：`+72` **不是 flags**

| 字段 | 实测 |
|---|---|
| `+72` u32 | 同一个 `0x7CE0F18D.ymap` 里是 **1,2,3,…,11 的连续编号**，其余大量 `0xFFFFFFFF`；names.txt 里 **0/1305** 查得到 ⇒ 更像 **GUID / 序号**，不是可见性真值位 |
| `+76` f32 | **`lodDist` 是真的**：瓦伦丁 1,593 条里 `-1`（不限）321 条，其余 19/30/40/50/60/70/80/90/114/120/200 各有几十上百 |

⇒ `docs/格式与资产/RDR2_ymap实体变换解析.md` 里「+72 u32 flags」需按此更正
（那篇的样例 `flags=3` 也是同一类小整数）。
**"隐藏 visible 属性"这个假设目前没有证据**——别再按它写代码。

### 5. 下一步（只读先量，别急着改管线）

1. 统计 56 张场景各有多少实体来自「哈希命名 ymap」——定量它对"杂物感"的贡献；
2. 判据：这些小 ymap 是不是**条件加载**（剧情态/场景布置）。可选证据 = 实机对照同坐标是否常驻，
   或从 `.ymf`/脚本里找加载引用；**在拿到证据之前不要按"隐藏"逻辑删东西**；
3. **`lodDist` 可以直接接进管线**（每实体一个丢弃距离）——它不依赖任何未验证假设，
   而且顺带省面数；
4. **`_dmg` 去重**可以先做：名字以 `_dmg` 结尾的 **50 件里有 45 件与完好版距离 0.0~0.1 m**
   （`p_lampexterior01x` 4 件全压在同一点），同坐标二选一（默认留完好版）。

**既有实测（`placement_val.jsonl`，7,645 个对象）**：小件合计 **5,320**
（`part` 2,608 · `prop` 2,168 · `junk` 398 · `veh` 62 · `decal` 84），占 70%，`bldg` 仅 123；
名字含 crate / barrel / debris / wagon = 287 / 209 / 196 / 61；室内 11 包 / 1,499 件。

---

## ✅ 本次收口（2026-11-04）—— 一句话版

| # | 修了什么 | 判据 / 现状 |
|---|---|---|
| 1 | 地形贴图 **UV 南北镜像**（黑水镇街道整体错位 250 m） | V 必须随 y 递增；`check_scene_terrain` **PASS**（含 UV 往返 + 负面测试）；实机确认 |
| 2 | **分类 72 个 unknown → 0** | 补的是写法变体（`_ext` 结尾 / `res_01` / `scafold` 拼写 / 缺词）；34 条用例 **PASS** |
| 3 | **室内 MLO 落位**（黑水镇 12 套 / 1789 件） | **实拍对比通过**；`rooms=12/1789` |
| 4 | **野地「城整座只留 lod」**（走到 P 边界切场景） | `wild_10`：据点内降 lod 2262；P 内 66 个对象**全是 `lod_out`**，非 lod 0 个 |
| 5 | 收尾存盘 **compress=False 导致体积误报 5 倍** | 已改 `compress=True`；bla **187.5 → 233.9 MB（+25%）**，不是 922 MB |
| 6 | 地图页 **「含室内场景的房间」层** + 滚轮缩放 | 171 间；点据点才显示、**无按钮**、滚轮放大自动出名字 |
| 7 | 闸门补强 | 地形 UV 检查、分类碰撞用例、`rooms` 列、批量开跑前双闸门 |

> 表内第 3 / 5 条是**旧 T 口径**的历史记录（黑水镇 12 套、233.9 MB）；P 口径重建后为 **10 套 / 1,618 件、206.8 MB**，见下节 A 表。
>
> 下一步 = **TODO-6 用户逐张预览**（`sdn` / `val` / `wild_04`）；全量 **56 张已建完**，见下节。

---

## ✅ 2026-11-05 · 全量资产清单 + LOD 验证（骑砍2 导入准备）

| 项 | 结果 |
|---|---|
| 全量清单 | `deliverable/handoff/asset_inventory_*`：**39,990 个模型**（大地图 ∪ 56 场景）· **23,328 张贴图**（5.75 GB，缺失 0）· 大地图 2,238 碎片（2,324 实例）+ 46 微缩 |
| **导入子集** | `asset_import_models.csv` / `asset_import_textures.csv`：**24,424 个模型**（9,265 个 ≥2,000 面要做 LOD）· **22,504 张贴图** · 160,193 个对象 · 277M 实例三角面 |
| 导入范围 | 导 16 类（bldg/part/prop/junk/veg/rock/stone/struct/ruin/veh/rail/rail_decal/road/decal/unknown/lod_out）；不导 6 类（terrain_cell/terrain_lod/underground/watertile/placeholder/lod） |
| LOD | **7 槽位**（0~6，LOD5/6 复用 LOD4 的 12%）；`Scripts/export_rdr2_trf_from_scenes.py` **直接从场景 blend 出 TRF**，sdn 样本验证通过（木栈桥/站台/木屋结构保持；薄钢水塔 12% 有屋顶折面，用户已接受） |
| 贴图格式 | **DDS**（落地 DXT5 与 PNG 一致；源文件更小） |
| 旧资产 | 🔴 **作废**：`rdr2_sanit_denis` / 5,211 个 FBX / 旧 tpac（用户裁定圣丹尼斯旧城是实验，要重做） |

> **骑砍2 侧的落地计划** = `Modules/LivingWorldNpcs/plans/大镖客2还原/00-总纲.md`（本文只做数据契约，两边不复制全文）。

---

## ✅ 2026-11-04 · 圣丹尼斯（sdn）已建 —— 全量开工前先看这条

> 🔴 **口径变更（2026-11-04 用户裁定）**：**能走范围 P 就是活动区边界，P 外一律按远景处理**
> （只留远景碎片；远景零室内）。旧的"正方形档位 T + 四边各留 64 m"作废，`T` 只保留用来算远景框。
> 数据 = `scene_list.csv` 末尾四列 `能走_x0/y0/x1/y1`（生成器写）；构建侧全部改读 P。
> 详见 `docs/AGENTS.md` **§6.10**。

| 项 | 结果 |
|---|---|
| 产物 | `deliverable/blender/scenes/sdn.blend` **825.4 MB** |
| 对象 | 20,522（活动区 19,763 / 远景 759），删除 958 |
| 室内 | **21 包 / 3,760 件**（全部落在 P 内；整体包围盒相对 P 四面外溢 **0**） |
| 越界 | **0 个**（远景框 4096×4096，**未改**） |
| 耗时 | 426 s（含室内 + 远景库 append） |
| 远景来源 | 🔴 **改为从打散分组远景库按需 append**：20 组 / 1,154 件；tile 里的 lod 跳过 896 |
| 预览 | 城区顶视 / 西边界特写已出图核对；西西卡拆件 `new_area_slod4__split_sis`（549 顶点）已可见 |

**⚠️ 另修了远景框裁剪的 4 个叠加 bug**（矩阵口径 / clear 侧 / 法线方向 / 包围盒高估），
详见 `docs/AGENTS.md` **§6.9**；闸门 `tools/_check_scene_trim_clip.py`（A~I 九条 + 负面测试），
已接进 `build_scenes.py`（不过就 `return 4`）。
`bla` / `sod` / `wild_10` 也已按 **P 口径**重建（见下面全量表）。

---

## ✅ 2026-11-04 · 全量 **56 张已建完**（原「下一步」）

| 项 | 结果 |
|---|---|
| 场景 | **56 / 56 `done`**（57 张子场景里瓜玛没有尺寸，不跑） |
| 对象 | 合计 **186,134**（远景 `lod_out` 合计 20,724） |
| 越界 | **56 张全部 0 个** |
| 室内 | 按 P 口径摆；sdn 21 套 / 3,760 件、bla 10 套 / 1,618 件、sod 1 套 / 224 件，野地全 0 |
| 体积 | blend 合计 **9.9 GB**；地形图 56×3 = **32.3 MB** |
| 地形图 | **56 张全 PASS**（最大误差 0.000 m） |
| 状态表 | `deliverable/blender/scenes/scene_build_status.csv` 全部 `done` |

**批量中修的两个问题**

1. **`rat` 超时 40 分钟**：`bisect_plane` 卡死在共面地形片（`outg_a_03_hd_02`）。
   修法 = 隐藏类（`terrain_cell` / `terrain_lod`）跨边界**直接丢、不裁剪**；`rat` 728 → 498 对象、21 秒完成。
   详见 `docs/AGENTS.md` **§6.12**。
2. **远景碎片来源**：改为从打散分组远景库按需 append（§6.11），tile 里的 lod 一律跳过。

### A. 地基现状（每一条都跑过、有数字）

| 件 | 状态 |
|---|---|
| 地形（UV / 采样 / 自检） | ✅ `check_scene_terrain.py` **PASS**（含 UV 朝向往返 + 三条负面测试） |
| 分类（21 类，`unknown=0`） | ✅ `_check_rules.py` **PASS**（34 条用例）；黑水镇 72→0 |
| 室内 MLO 摆放 | ✅ 黑水镇按 P 口径 **10 套 / 1,618 件**（旧 T 口径 12 套 / 1,789 件）；`sod` 1 套 / 224 件 |
| **野地「城只留 lod」** | ✅ `wild_10` 试点：`据点内降 lod 2262`；P 内对象 66 个**全是 `lod_out`**、非 lod 0 个；野地不放室内 |
| 分类开关单测 | ✅ `_check_tour_vis_unit.py` → `=== UNIT OK ===` |
| 审计表 | ✅ 251 包 / `inside=True` 179；全量重算 **30 s** |
| 批量构建 | ✅ **56 / 56 `done`**（`scene_build_status.csv` 全 done，剩 0 张） |
| 地图页房间层 | ✅ 171 间，滚轮放大看名字（无按钮） |
| **远景碎片来源** | ✅ **从打散分组远景库按需 append**（`continent_lod_split_v23.blend`，与远景框相交的组）；tile 里的 lod 一律跳过。实测 sdn 20 组 / 1,154 件；西西卡拆件 `new_area_slod4__split_sis` 可见。详见 `docs/AGENTS.md` **§6.11** |
| **每场景地形图**（高度 + mask） | ✅ **56 张全 PASS** → `deliverable/blender/scenes/terrain/`：`<id>_height_16bit.png`（16 bit · 4 m/px · 行 0 = 北）+ `<id>_mask.png`（全 255）+ `<id>_terrain.json`；自检最大误差 **0.000 m**；工具 `tools/export_scene_terrain_maps.py`，**已接进 `build_scenes.py`**（每建完一张自动导，自检不过就停批） |

### B. TODO-3 / 4 / 5 已出（2026-11-04）

| # | 产物 | 数字 |
|---|---|---|
| **TODO-3** | `deliverable/handoff/mesh_texture_audit.csv` + `texture_list.csv` + `mesh_texture_audit.json`（`tools/audit_mesh_textures.py`） | 用到模型 **39,946**（索引里 0 个找不到）；贴图 **20,888** 张（文件缺失 **0**）；缺 albedo **1,688** / normal **6,529** / ma **7,267**（单独列出）。🔴 **缺 albedo 是已知接受缺口**（README §6「小道具贴图缺失」：扫 25 个 props 包 + `gtxd.rpf` + 3,696 个 ytd 全无，用近似色代替）——**不是新缺陷，不要再重新解包** |
| **TODO-4** | `deliverable/blender/scenes/placement_<id>.jsonl` × 56（`tools/export_scene_placements.py`） | 69 MB；字段 = hash / model_hash / cls / ring / loc / quat / scale / bbox / part_key / split_of / int_pkg / tile；**对账 = manifest + 室内件，56 张全一致** |
| **TODO-5** | `deliverable/handoff/prefabs/<group_id>.json` + `prefabs_index.json`（`tools/build_lod_prefabs.py`） | **55 组 / 2,324 碎片**，每组计数与 `lod_groups.json` 一致；局部坐标 `gx,gy,gz` 相对组锚点。🔴 空组 `abe/dow/twi` 的"高清减面兜底"**已有现成管线** `tools/build_miniatures.py`（46 据点微缩代理，目标面数见 `RDR2_沙盒大地图_微缩模型规格.md`）——**不要另造减面工具** |

### C. 只剩 TODO-6：用户逐张预览

- 大 / 中 / 野地各开一张：`sdn`（圣丹尼斯）· `val`（瓦伦丁）· `wild_04`（最大野地）
- 命令：`Start-Process -FilePath "H:\SteamLibrary\steamapps\common\Mount & Blade II Bannerlord\Modules\RDR2\Source\launchers\打开大陆_流畅.bat" -ArgumentList "sdn"`
- 看：P 内高清 / P 外只剩远景碎片 / 无品红 / 室内集合在 `ENTITIES/C_int_室内`
- 你说"可以" → TODO-6 勾掉，`region/` 的清理再动。

> 抽样验收入口：`打开大陆_流畅.bat <id>`（大中小各一张看即可）。

### D. 命令（重跑用；全部已 done，只有 `--force` 才重建）

```powershell
Set-Location "H:\SteamLibrary\steamapps\common\Mount & Blade II Bannerlord\Modules\RDR2\Source"

# 重跑样板：一座城 + 一张野地
python -X utf8 tools\build_scenes.py --only val,wild_04 --force

# 全量（断点续跑：已 done 的自动跳过；现在剩 0 张）
python -X utf8 tools\build_scenes.py
```

> 批量驱动一次只跑一个 Blender；开跑前自动过**两道闸门**（地形自检 + 分类开关单测），
> 任一张 FAIL 立即停批。**不要**自己另写循环、不要并发。
> 每张结束把 `rooms`（包数/件数）写进 `scene_build_status.csv`。

### E. 历史验收基线（旧 T 口径；**实际以 `scene_build_status.csv` 为准**）

P 口径实测：**32 个据点有室内**（野地一律 `0/0`），合计 **129 包 / 20,656 件**。
下表是**旧 T 口径**的预算，仅作口径差异参考（sdn 31→21 包、5,922→3,760 件）：

| 场景 | 预计（旧 T 口径） | 场景 | 预计 |
|---|---:|---|---:|
| sdn 圣丹尼斯 ✅ | **21 / 3760**（P 口径实测） | str 草莓镇 | 8 / 873 |
| bra 布雷斯韦特庄园 | 11 / 2306 | lak 拉凯 | 7 / 733 |
| val 瓦伦丁 | 15 / 2095 | ora 奥兰治 | 7 / 676 |
| bla 黑水镇 ✅ | 12 / 1789 | lag 拉格拉斯 | 7 / 676 |
| rho 罗兹 | 8 / 1474 | han 垂犬牧场 | 4 / 577 |
| bee 比彻之愿 | 2 / 1376 | arm 犰狳镇 | 4 / 548 |
| van 范霍恩 | 10 / 1289 | 其余 20 个据点 | 见审计表 |

数字对不上就是哪里错了（最常见：宿主判错被踢掉 / 野地误摆了室内），别放过。

### E. 预算与风险

| 项 | 估计 |
|---|---|
| 时间 | 单张 0.5~6 分钟（圣丹尼斯最久），51 张约 **2~4 小时**；跑之前先关 RDR2 |
| 体积 | 室内约 **+26 KB/件（压缩后）**；全部 28,129 件 ≈ **+0.7 GB**。D 盘余 2.7 TB，够 |
| 最可能翻车的三处 | ① 某城宿主判错（`inside=True` 但配到隔壁）→ 穿墙；② 野地规则漏挡 → 城里出现高清；③ 并发跑两个 Blender |

---

## ✅ 2026-11-04 · 已定位：`bla.blend` 建筑与地形贴图错位 = **贴图 UV 南北镜像**（已修，待重跑）

**症状（用户）**：`bla.blend` 正交顶视下，彩图里的街道/黑条整体跑到建筑群**南边约 250 m**，
看着像"地面 UV 整体向南偏移"。用户把一个房子拖到黑条中心，读出局部 (90, −110) = 世界 (−792, −1549)。

**根因（一句话）**：`tools/scene_terrain.py` 的 V 轴写反了 —— 贴图是**行 0 = 北**的 PNG，
而 Blender 的 `v=0` 在**图像底边（南）**，所以 V 必须随 y 增大；代码写成了 `v = 1 - (...)`，
于是**整张贴图上下翻转**（不是平移）。`blender_continent.terrain()` 一直是对的
⇒ **region 18 对、场景 blend 错**，两套构建器口径不一致才是根子。

**实测证据**

| 项 | 数值 |
|---|---|
| 贴图里黑条的真实位置（世界） | x[−812,−791] · y[−1364,−1262]，中心 (−801, **−1315**) |
| 当前 UV 渲染后黑条落在 | 镜像到 y ≈ **−1565**（x 不变） |
| 用户在视口读到 | (−792, **−1549**) —— 与镜像预测差 9/16 m（拖拽目视误差内）✅ |
| `bla.blend` 实际 UV | 局部 (82,123)=世界(−800,−1316) → **V=0.4657**；北端 V=0.3571 < 南端 V=0.6431 ⇒ V 随 y 递减 = 翻转 |
| 建筑分布 | 161 栋里 124 栋在 y[−1450,−1200)，中位 y=−1323 —— 正压在黑条 (−1315) 上，与贴图原本是对齐的 |

**之前为什么没抓到**：只验了"UV 与裁剪公式一致"（同一个错公式当标尺）、"采样到黑"
（黑区面积大，翻转后仍能采到黑）—— 两个判据都**没有分辨力**。

**修法（已落盘）**

- `tools/scene_terrain_core.py` 的 `uv_of()`：`v = (y − fy0)/(fy1 − fy0)`（V 口径唯一实现）；
- `tools/scene_terrain.py::_grid`：删掉自己那份 V 计算，只调 `uv_of()`；
- `tools/check_scene_terrain.py`：新增**贴图 UV 朝向往返比对**（世界→像素 vs 世界→UV→按 Blender
  取图规则，32×32 点必须逐点相等）+ 负面测试（V 翻转必须被抓到，实测超差 92.8%）。
  现状：`python -X utf8 tools\check_scene_terrain.py -v` → **PASS**，三条负面测试全"被抓到"。

**已重跑并复验（2026-11-04 14:10）**：`python -X utf8 tools\build_scenes.py --only bla,sod --force`
→ bla 6770 对象 / 72 s / 187.5 MB，sod 919 对象 / 22 s / 37.0 MB，两张都 `done`。
复验 `bla.blend` 的 UV：局部 (82,123)=世界(−800,−1316) → **V=0.5343**（重跑前 0.4657）；
北端 (82,+512) V=0.6429 > 南端 (82,−513) V=0.3569 ⇒ V 随 y 递增 = 朝向对了。

另外 55 张还没建，不受影响。**教训已写进 `AGENTS.md` §6.7**。

**（历史存档）当时双方的观察**（已解释，不必再查）：

- 数据侧量到的一切都自洽：建筑世界坐标、地形高度、UV 公式、彩图采样四者互相一致 ——
  因为它们**都用了同一个翻转口径**，自洽 ≠ 正确。
- 用户看到的"错位"才是对的那个信号；镜像判据就是从这里反推出来的。

---

## ✅ 2026-11-04 · 启动器/面板：勾选显示"隐藏"，画面里却还在

**症状（用户）**：用 `打开大陆_流畅.bat bla` 打开后，RDR2 面板里「远景碎片（活动区内那 40 个）」是**不勾**的，
但画面里它们**就是显示着**；手动点两下按钮才正常。

**根因（一句话）**：`blender_tour.cat_show()` 的匹配判据里混了**子串匹配**，而类名天生互为子串 ——
`lod` ⊂ `terrain_lod`／`lod_out`，`decal` ⊂ `rail_decal`。遍历到谁算谁，于是：

| 启动器调的 | 实际打到的集合 | 后果 |
|---|---|---|
| `cat_show('lod', False)` | **terrain_lod** | 真正的 `C_lod_远景碎片`(40) 没关，`show_all()` 打开后再没人关 → 画面露出 |
| `cat_show('decal', False)` | **rail_decal** | 88 个地面贴花同样漏出来 |

面板勾选态来自**文件保存态**（是对的），所以出现"面板说隐藏、画面在显示"的分裂。
手点两下能好，是因为面板开关走**精确集合名**（第一下开、第二下关，才真关到 `C_lod`）。

**实测（同一份 bla.blend，复刻 autoload 的两步）**：修前 `lod` / `decal` = 可见；
修后 `lod` 隐藏、`decal` 隐藏、`rail_decal` 不再被误关、`lod_out`(617) 仍按设计显示。

**修法**：`cat_show` 改成**两轮匹配** —— 先全等（key / 中文名 / 集合名），全不中才允许片段。
**影响面**：所有用启动器打开的 blend（大陆 / 22 个区域 / 场景）都吃这一条；改的是脚本，
**不用重建任何 blend**，重开 Blender 即生效。

**顺带发现的第二个问题：那个单元测试早就烂了。**
`tools/_check_tour_vis_unit.py` 里 SPECS 缺 `terrain_lod` / `road`，一跑就 assert 失败
（分类表后来加了这两类，测试没跟上）—— 因为**没有任何地方会跑它**，坏了半年没人知道。
现在：SPECS 补齐 + 新增"子串碰撞"回归断言（lod/lod_out/terrain_lod、decal/rail_decal），
并登记为「改过 `blender_tour` / `class_rules` / `rdr2_cat_ui` / `blender_autoload` **必跑**」（AGENTS §6.6）。

> 教训一句话：**闸门不接进流程 = 没有闸门**；**类名互为子串时，模糊匹配必然打错目标**。

---

## ★ 2026-11-04 · 黑水镇：未分类清零 + 12 套室内落位

### 1. 分类：`unknown` 72 → **0**（bla.blend 已重建验证）

补的都是**写法变体**漏网（详见 `docs/格式与资产/分类体系与判定规则.md` §5 新行）：

| 漏的原因 | 补法 |
|---|---|
| `bldg` 只认 `_ext_`（带尾下划线），`bla_bakery_ext` 这类**结尾**写法全漏 | `(?<!arch)_ext(?=_|$)` |
| `res01` 认、`res_01` 不认 | `res_?\d\d` |
| `scaffold` 在数据里拼成 `scafold` | `scaf+old` |
| `photograph` 认、`photo` 不认 | `photo` |
| 词表里根本没有 restaurant / bakery / cafe / cityhall / hardware / lawyer / fishmonger / slum / corner / construction / barber / news | 全部补进 `bldg` |
| `_glue` 认、`policeglue`（不带下划线）不认 | `glue` |
| `codemarkings` / `objectNNN` / `horsejump` / `fman` / `planeNNN` / `burial_hole` / `parklights` / `amb_*` | 分别进 decal / prop / junk / part |

**回归**：`tools/rules_cases.csv` 补 **10 条**用例（34 条），`python tools/_check_rules.py` → **PASS**。
重建后 bla manifest：`bldg 161→203`、`prop 2978→3007`、`unknown 72→0`，其余类基本不动。

### 2. 室内：**12 套 / 1789 件**已摆进 bla.blend

| 项 | 结果 |
|---|---|
| 摆进的包 | 银行 176 · 理发 88 · 马车房 195 · 围栏店 99 · 杂货铺 283 · 监狱 123 · 照相馆 52 · **酒馆 395** · 剧院 106 · 火车 101 · 码头棚屋 ×2（qua_shack01/02，64+107） |
| 没摆 | `bla_tailor_int`（室内 20.6×11.8 vs 宿主 4.4×8.4，**宿主匹配错**：模型库里缺 `bla_tailor01x`，审计抓到了邻居） |
| 位置口径 | MLO 实例 `(pos, quat)` → `world = P + q·local`，与 `merge_interior_into_willard.py` / `instantiate_interiors.py` 同一套 |
| 坐标 | 场景**局部**坐标（世界 − 场景中心），与 trim 口径一致 |
| 集合 | `ENTITIES/C_int_室内/int|<地块>`，面板「RDR2 分类开关」里显示为「室内 (1789)」，可单独关 |
| 体积 | bla.blend **187.5 → 233.9 MB（压缩后，+46 MB / +25%）**；室内 217.5 万顶点、占全场景 13.4%。嫌大：`blender_continent --no-interiors`。⚠️ 曾一度记成 "187 → 922 MB"——那是我第一版收尾脚本用 `compress=False` 存盘把文件摊开了，**不是室内的真实代价**（见 AGENTS §6.8 第 4 条） |

**管线接法**：`blender_continent.py --scene … --full` 在 `scene_trim` **之后**自动调 `tools/scene_interiors.py`。
必须在 trim 之后 —— 室内件不是地图实体，提前摆会被"圈内非远景碎片"规则当垃圾删掉。

### 3. 顺带修的两个工具问题

- 🔴 **`audit_interior_placement.py` 的 `ROOT` 指错**：它按"文件在数据工程 tools/ 下"算路径，搬进仓库后
  `assets/lib_native` 直接找不到（一跑就 FileNotFoundError）。已改成 `RDR2_ROOT` 环境变量 + 默认数据工程路径
  （与 `scene_terrain.py` 等同一口径），并给 names.txt / 90 个 tile json 加了**进程内缓存**（278 个包从十几分钟 → **30 秒**）+ `--only` 过滤。
- **审计表重生成**：`export/world/interior_placement_audit.json` 136 → **251** 条；
  其中 **51 个包结论变了**（旧表是 10 月的，之后模型库/tile 有更新）—— 以后重建大陆的室内会按新表走。

### 4. 还没做的

- 室内是**整包平铺**，没有门 / 房间裁剪（与圣丹尼斯同一现状）——"推门进屋"要另做 MLO rooms/portals；
- 室内对象**不进 manifest**（manifest 由 trim 在摆室内之前写），所以批量验收的"0 超界"不覆盖它们；
- ~~其余 55 张场景还没跑~~ ✅ **56/56 已建完**（2026-11-04，P 口径 + 远景库）；
- **22 个区域 blend 和大陆 v23 还是旧分类**（`bldg 161 / unknown 72` 那套）。要统一就走
  `reclassify.py`（18~20 分钟，不重建几何）；本轮只重建了 bla。

### 5. 地图页新增「含室内场景的房间」层（`regions_viewer.html`）

**用户要求**：世界坐标标到地图上方便实拍找房；单独一层；**点了据点才显示**。

- 数据 = `export/world/interior_placement_audit.json` 里 `inside=True` 的包（= 场景里真摆进去的那批），
  用室内 bbox 中心当坐标；归属按「落在哪个据点的 P 矩形里」判，落不进的取 800 m 内最近据点。
- 页面：紫色小方块 + 悬停显示「包名 / 宿主建筑 / 世界坐标」；右上角有「含室内场景的房间：开/关」；
  左侧详情面板列出该据点全部房间（名字 + 坐标）。
- **放大 / 退出（2026-11-04 用户第二轮、第三轮）**：**没有额外按钮**，全靠鼠标：
  · 🔴 **滚轮缩放随时可用** —— 原代码 `if (!state.edit) return` 把滚轮锁在编辑模式里，等于没有；
    现在非编辑态也滚轮缩放，最小 60 地图单位（≈295 m 宽，原来是 150）；
  · 🔴 **点地图空白不再取消选中** —— 原来 `#map` 的 click 会清空选择，滚轮时手一抖房间层就没了；
    现在只有「**再点同一个据点**」或「**按 Esc**」取消；
  · **左侧清单点一行 → 单间放大**（view.w = 60）；
  · 标签按「**相邻房间的屏幕间距 ≥16 px**」自动出现；字号写死 13 px 屏幕高（不吃 `--k` 的 clamp，
    否则深放大时字会变成几十像素）；标签去掉据点前缀（`bla_new_bank_ext` → `new_bank_ext`）、
    同一栋楼的多个室内只标一次、与方块间距按屏幕像素算；
  · 深放大（view.w < 220）时**不画据点大名字和星标**，否则会盖住整片房间。
- **生成器不是手改 HTML**：改的是 `D:\BrainMaker\大镖客2解包分析\_scratch\settlement_plan\build_settlement_map.py`
  （新增 `_load_rooms()` + `drawRooms()` + `#l-rooms` 图层），重跑该脚本产出页面。
- 现状：全图 **171 间**有室内（圣丹尼斯 21 / 瓦伦丁 12 / 黑水镇 12 …）。

**连带修好：审计的宿主匹配**（`audit_interior_placement.py`，2026-11-04）
旧判据只按「名字前缀 + 最近」，会挑到 `_em`/贴花条/隔壁小屋。现在改为三档：
① 真包住（四边间隙 ≥0）且面积不超过室内的 4 倍 → 取最贴合的那栋；
② 容差内（≥ -1.5）→ 同上；③ 都包不住 → 取最不偏的。
外加两条硬排除：**LOD 合并块**（`_slod/_lod`，曾把瓦伦丁银行判给 `val_02__em_slod`）不能当宿主；
名字是 `_em/_decal/_dec/_d/_det` 的附属件降档。
结果：`inside=True` 185 → **179**（挑错宿主的被踢出去，比如瓦伦丁银行、黑水镇裁缝铺）。
⚠️ 这条改的是 `inside` 本身 —— **以后重建大陆/场景，室内会按新表摆**，与之前跑出来的不一样属正常。
宿主名现在也写进审计表（`host` 字段），地图页和实拍对照都用它。

---

## ★ 2026-11-04 · 场景构建管线（本会话落地，可复现）

### 工具（三个 + 一个闸门）

| 文件 | 作用 |
|---|---|
| `tools/scene_terrain.py` | 场景地形：高度 + 彩图贴图 + **单平面水面**；活动区一块 + 四块远景条带，**全部 4 m** |
| `tools/scene_terrain_core.py` | **采样口径唯一实现**（纯 Python）：`sample_h`（最近邻 + 行偏移 −1）、`axis`（全局格点吸附）、回归点 |
| `tools/scene_trim.py` | 两层裁剪 + 默认隐藏复原 + 平移；远景碎片两类；水面/地形不参与平移 |
| `tools/build_scenes.py` | 批量驱动：**开跑前先跑 `check_scene_terrain.py`**（不过就 `return 4`），逐张验收"0 超界" |
| `tools/check_scene_terrain.py` | 地形算法自检 + **两条负面测试**（行偏移/半格偏移必须被抓到） |

### 已确认的关键口径

1. **地形 = H4 原样**：最近邻 + **行索引 −1**（交付物高度图与 H4 的最佳对齐是 shift(0,−1)，中位差 0.014 m）+ 顶点吸附全局 4 m 格点。**禁止任何地形高度修正（PAD/压平/平滑）**。
2. **场景目录 = `deliverable/blender/scenes/`**（不是 `_scratch`）；贴图在 `scenes/tex/<id>_color.png`，blend 里用相对路径。
3. **远景碎片分两类**（分类器新增 `lod_out`）：`lod` = 活动区内（默认隐藏，保留不删）、`lod_out` = 活动区外（默认显示）。`lod_out` 由场景裁剪按几何改标，大陆/旧分区里永远为空。
4. **水面**：单平面覆盖远景范围，水位取该场景范围内水位中位数（黑水镇 40.5 / 西盆地 −22）；材质深蓝 alpha 0.72。
5. **打开方式**：`launchers/打开大陆_流畅.bat` 已支持场景 id（`打开大陆_流畅.bat bla`）；**禁止另造启动 bat**。
6. **瓜玛合并**：阿瓜多切斯 / 瓜玛营 相距约 342 m → **合并为 1 张**。总数 **57 张子场景 + 1 张大地图**（`scene_list.csv` 已重生成）。

### 现状

| 项 | 状态 |
|---|---|
| `bla.blend` | ✅ 按 P 口径重建（6,213 对象；远景 676；室内 10 套 / 1,618 件） |
| `sod.blend` | ✅ 按 P 口径重建（267 对象；远景 190） |
| 其余 54 张 | ✅ **全部已建**（2026-11-04，合计 56/56） |
| 交接规范 | ✅ 写进 `README_骑砍2交接.md` §0.6/§0.7（场景数 57+1、每场景 5 件交付物、两层内容、预览门槛、TODO-0~6） |

### 下一步（顺序）

1. ✅ 贴图 UV 南北镜像已修并重跑（见本节顶部第一篇）。
2. ✅ `build_scenes.py` 全量 56 张已建完（P 口径 + 远景库 + 地形图 + 摆放清单）。
3. ✅ TODO-2~5 已出；**只剩 TODO-6 用户预览**（见本文顶部 C 节）。

---

## ★ 2026-11-03 · 远景碎片 → 据点分组（骑砍2 大地图城镇 prefab）—— ✅ 数据已出

**一句话**：2,324 个可用远景碎片，**1,212 个分到 41 个据点**、1,068 个分到 12 块野地、44 个瓜玛、0 落空。
数据 = `deliverable/handoff/lod_fragments.csv` + `lod_groups.json`；规则与口径见
`docs/世界与地编/RDR2_据点分级与场景边界方案.md` §8.1；唯一实现 = `tools/build_lod_groups.py`
（对 22 个区域 manifest 反验包围盒，最大误差 0.005 m）。

**合并 LOD 已按据点边界切开**（2026-11-04 用户裁定，5 块 → 11 件）：
`new_area_slod4` → 圣丹尼斯 4,232 面 + 西西卡 292 面；`nopq_11_14_area_slod4` →
卡利加 591 / 罗兹 741 / 布雷斯特 513 / 圣丹尼斯 13；`rstu_96_99_area_slod4` → 风滚草 644 / 犰狳镇 280；
`nopq_07_10_area_slod4` → 黑水镇（余量空）；`bra01pr_combo10_slod` → 罗兹 198 / 布雷斯特 390。
🟢 `*_area_slod*` 是**建筑/道具的整区合并 LOD**，不是地形；整区块只要压到据点就拆（哪怕只压 1 个）。
拆分器 `tools/split_span_blocks.py`，部件表 `deliverable/handoff/lod_split_parts.json`，
CSV 里带 `part_key` 列；`build_lod_groups.py` 会自动用部件替换整块。

**马掌望台范围已扩**（2026-11-04 用户用 `regions_viewer.html` 编辑导出）：`hso` 能走范围改成
`x[-424.4, 54] y[-245.3, 146]`，把西边**烧毁村庄林帕尼**包进来；活动区 512 → **768**、远景 2048。
导出的 T=512 会被生成器 clamp 回 -382（最西那栋仍在外），合并时**改成 640** 再跑。
4 个原有碎片（`bur01_combo_slod` / `bur_house_02_lod` 等）现在全部 `inside hso`，野地 `wild_04` 少 4 个。

**只放远景碎片的浏览版** = `deliverable/blender/continent/continent_lod_split_v23.blend`
（1.1 GB；`ONLY_lod_远景碎片` **2,324** + `ONLY_terrain_lod_地形远景块` 31；
2026-11-01 建，2026-11-03 从 `_scratch/lod_only/` 归位并重算贴图相对路径；生成器 `tools/extract_class_blend.py`）。
2026-11-04 补齐 v23 之后区域新增的 57 条（`tools/backfill_lod_blend.py`）、把跨据点整块切开
（`tools/split_span_blocks.py`），并按本表把 `ONLY_lod_远景碎片` 拆成 **55 个子集合**
（`S_<据点>_<中文名>` 41 / `W_wild_01..12` / `G_<瓜玛>` 2，`tools/group_lod_blend.py`，幂等可重跑）——
各组数量与 `lod_groups.json` 逐组一致。**没有 `X_未匹配`、没有第三个地形集合**。

**遗留（更新于 2026-11-04）**：

1. ✅ **3 个小点位没有远景碎片**（`dow` / `twi` / `abe`）—— **已解决**：现成
   `tools/build_miniatures.py`（46 据点微缩代理，合计 84,502 面；abe 330 / dow 252 / twi 362），
   已重跑，产物在 `deliverable/miniatures/`。**不要再另造减面工具。**
2. ✅ **网格导出**：`tools/build_lod_prefabs.py` 已按组出 `deliverable/handoff/prefabs/<group_id>.json`
   （55 组 / 2,324 碎片，`gx,gy,gz` 相对组锚点）；**OBJ/GLB 不另导**——骑砍2 侧按 prefab JSON 实例化。
3. 237 个 `lod` 实例在解包里没有网格（摆不出来），和「817 个 archetype 缺模型」同一类（已接受）。

---

## ★ 2026-11-03 · 世界场景划分 —— ✅ 定稿（**57 张子场景**；2026-11-04 瓜玛两处合并为一）

**一句话**：**57 张子场景 = 44 张据点 + 12 张野地 + 1 张瓜玛岛**（瓜玛两处相距约 342 m，合并；另加 1 张大地图 = 总共 58 张图）。数据、页面、编辑器、自检全部就绪；下一件事是**在骑砍2里建场景**（先 P0 验证，再批量）。

### 定稿数字

| 层 | 数量 | 说明 |
|---|---:|---|
| 据点地图 | 44 | 9 城 + 11 堡 + 2 藏身处 + 11 村 + 5 营地 + 6 点位；能走范围 = 建成区外扩的**外切矩形**，两两不重叠；合计 **8.44 km²** |
| 野地地图 | 12 | 用户手画的**横平竖直矩形**，3.25–7.20 km²，合计 **59.24 km²**；编号 `wild_01..wild_12`（北→南、行内西→东） |
| 瓜玛岛 | **1** | 阿瓜多切斯 / 瓜玛营 相距约 342 m，**合并成一张**（2026-11-04） |
| **总计** | **57** | 44 + 12 + 1 |

**🔴 2026-11-04 定稿：场景只有两层 —— 能走范围 P 就是活动区边界**

| 层 | 大白话 | 地形 | 数据列（`scene_list.csv`） |
|---|---|---|---|
| **玩家活动区 = 能走范围 P** | 玩家走得到的地面，走到 P 边界被挡住（`border_hard`）；**P 外一律按远景处理** | 4 m | 末尾四列 `能走_x0 / 能走_y0 / 能走_x1 / 能走_y1`（生成器写） |
| **远景范围** | P 每边再往外扩一圈，只做背景、走不到；**零室内** | 4 m | `远景宽_m` / `远景高_m`（沿用原配置，**不随 P 变**） |

- 据点 P = 建成区外切矩形（用户画/生成）；野地 P = 手画矩形。
- ~~据点活动区是正方形（512~1,536）；每边至少留 64 m~~ —— **2026-11-04 作废**，P 就是边界。
- 🔴 **远景框宽高、每边外扩必须是 128 的倍数**（地形按 128 m 节点整块切；生成器已自动取整）。
- 🔴 **远景区域完全不放室内**：`scene_interiors` 只摆 MLO 实例落在 P 内的包，P 外零室内。

### 🔴 规则（用户裁定，别再改）

1. **据点能走范围 = 外切矩形**（建成区 + 边距），裁进自己的场景尺寸；相邻重叠沿中线对切 → 两两不重叠。
2. **野地能走范围 = 横平竖直的矩形**（用户手画）；**宁可重叠、不留缺口**（缺口那块没有地图，重叠由「离哪个野地中心近」消化）。
3. **野地矩形包含据点范围**：野地场景里据点用 `C_lod_远景碎片`；玩家走到据点矩形边界 → 弹「是否进入 XX」→ 切据点场景。
4. **地图区 = 官方地图上「有画面」的那一片**（`地图下载/大陆地图_缩略.jpg`；空白羊皮纸 = 地图外，只做远景）；**水面也算可走**。地图区 **48.12 km²**（陆地 40.03 + 水面 8.10）。
5. 水面/地图外的判定都在 `build_scene_division.py` 里，别在别处另写一套。

### 自检现状（`scene_division_check.json`，`build_scene_division.py` 每次重跑都打印）

| 项 | 值 |
|---|---:|
| 缺口 | 0.0003 km²（300 m²，几处 <200 m² 细渣） |
| 野地互相重叠 | 0.0038 km²（一处 `wild_06/wild_09` 边角 3,788 m²，故意留的） |
| 据点两两重叠 | 0 |
| **PASS** | ✅ True |

### 数据与脚本（都在 `D:\BrainMaker\大镖客2解包分析\_scratch\settlement_plan\`）

| 文件 | 作用 |
|---|---|
| **`scene_specs.json`** | **权威数据**：44 据点 + 12 野地的 P/T/W/O、缺口/重叠几何、问题清单。页面和文档都读它 |
| **`docs/世界与地编/scene_overrides.json`** | 🔴 **人工改动 + 进 git**（用户导出合并进来的）：`settlements`（改过的据点矩形）+ `wilds_final`（**12 块野地的最终清单**，权威）。构建脚本**优先读这份**，读不到才回落到 `_scratch/settlement_plan/` 那份 |
| `settlements_p.json` / `bubbles.json` | 据点 / 野地的 P 多边形（构建产物） |
| `scene_division_check.json` | 自检数字 |
| `build_scene_division.py` | **唯一入口**：读上面这些 → 算 P/T/W/O → 写 `scene_specs.json` 等 |
| `build_settlement_map.py` | 生成页面 `docs/世界与地编/regions_viewer.html`（含编辑模式） |
| `autofix_gaps.py` | 自动补缝（把窄缝用≤300 m 的边延伸补掉；用前先备份 overrides） |

**重跑**：`python -X utf8 build_scene_division.py` → `python -X utf8 build_settlement_map.py`（输出最后一行必须是 `PASS`）。

### 页面 / 编辑器（`docs/世界与地编/regions_viewer.html`）

- 只读态 = 汇报页；点左上角「**编辑模式：关**」→ 开 = 图形编辑器（**同一个页面，没有第二个**）。
- 能改：据点拖 8 把手改 P、改 T/W；野地拖矩形把手 / 拖顶点 / 「重画矩形」/「按外接矩形」/「多边形转矩形」/「野地全转矩形」；**＋新建野地 / 删除这个野地**；「吻合邻居」（据点 60 m 内的边对成一条线）；「吸附」（30 m 内咬住邻居边/顶点，橙虚线提示）。
- 视图：滚轮缩放、空白拖动平移；「显示全部活动区」「缺口/重叠：开/关」（缺口红、重叠橙，**显示时加粗到 30 m 宽**，否则 2 m 的缝看不见）。
- **保存**：改动自动存浏览器 localStorage（带 BUILD_ID，页面重新生成后旧缓存自动失效）；点「导出改动」→ `scene_overrides.json`（**只含改过的项，是增量**）→ 由 Claude 合并进 `_scratch\settlement_plan\scene_overrides.json` 再重跑。
- 导出里的 `wilds_final` 一旦存在就是**权威**：构建完全按它来（编号、矩形、每边外扩都以它为准；活动区由矩形自动取整到 128），`deleted_wilds` 对它无效。

### ✅ 已完成（RDR2 侧）：按新的 57 张划分重跑 blend（2026-11-04）

**现状**
- `continent_v23.blend` = 全集（7.3 GB，**红线，不许改**）。
- **56 张子场景已全部建完**（`deliverable/blender/scenes/`，见本文顶部）：
  - 活动区 = **能走范围 P**（用户画的矩形；P 外一律按远景处理）；
  - 远景碎片 = 从打散分组远景库按需 append（合并块已按据点 P 切开）；
  - 每张自动出高度图 + 材质 mask + 摆放清单。
- 旧的 22 块 `regions/`（2,000 m 瓦片切法）**已被场景目录取代**，等你验证后再决定删不删。

**本轮完成（原计划）**
1. ✅ 「按场景切 blend」脚本 = `tools/build_scenes.py` + `scene_terrain/scene_trim/scene_interiors`；
2. ✅ 试点：`sdn`（最大城）+ `wild_10`（野地）先行验证；
3. ✅ 批量 **56/56 done**（瓜玛无尺寸，不跑）；
4. ✅ 0 超界、地形图全 PASS；**下一步是骑砍2 建场景**（待 TODO-6 预览确认）。

> 地形精度（建场景时用）：**活动区内 4 m 网格，活动区外 16 m**；地形按 128 m 节点切，活动区宽高与外扩都是 128 的倍数，细/粗正好落在节点边界上。

> 骑砍2 侧的**对外接口 / 57 张场景清单 / 素材总表**不写在本文 —— 见 [README_骑砍2交接.md](README_骑砍2交接.md) §0.5。

**不要做**
- 不要动 `continent_v23.blend`（红线）；要升级出新版本号。
- 不要直接拿旧的 2,000 m region 拼场景（尺寸/边界都对不上）。

### 交接注意（别再踩）

- **文档/配图已同步 58 张**：`RDR2_据点分级与场景边界方案.md`（据点 44 全表 + 野地 12 全表 + §13 编辑器用法）+ `img/scene_division_63.png`（图名沿用旧名，内容已换）。
- **不要手改** `scene_specs.json` / `scene_overrides.json`；改数据走编辑器导出或改脚本。
- 每次重新生成页面，BUILD_ID 会变 → 用户浏览器里的旧缓存自动失效（不会再套回旧图形）。
- 用户导出是**增量**：合并时 settlements 取并集、`wilds_final` 以最新为准，**别用新文件覆盖旧的**（会丢前面的修改）。合并目标是**仓库里的** `docs/世界与地编/scene_overrides.json`。
- `scene_specs.json` / `bubbles.json` / `settlements_p.json` 是**生成物，不进 git**（跑 `build_scene_division.py` 就有）。

---

## ★ 2026-11-02 · 地形**两级**管线 —— 已重跑出图，⏳ **等用户逐条验收**

**一句话**：管线现在只做「原始 → 高原/平原」两级，每级一套完整的高度图 + 彩图，可单看可单独用。
🔴 **2026-11-02 按用户裁定砍掉两级**：
· **「水域加深」** —— 按单级水位挖/填，把圣路易斯河河床从 −28 m 抬到 +7 m（错的）；
· **「统一水位陆地修正」** —— 按「骑砍2 只有一个水面」垫高干地，前提不成立（已确认是**两块不同高度的水位**）。
⇒ **地形高度本身是对的，管线不再按水位动地形。**

**产物**：`deliverable\terrain\stages\`（**明细与验证方法见 `deliverable\terrain\README.md`**）

| 级 | 做了什么 | 改动面积 | z 区间 |
|---|---|---|---|
| `00_raw` | 外延包补过的原始地形，未塑形 | — | −56.9 ~ 690.3 m |
| `01_plateau_plain` | 西北高原（720 m + fBm + 150 m 高斯隆起，只抬外延区）/ 东南平原（42 m 合成） | 20.6 km² | −56.9 ~ 690.3 m |

**脚本**：`tools/make_terrain_stages.py`（两级）+ `tools/make_terrain_stage_compare.py`（对比图）；
参数与噪声种子 `import` 自 `tools/build_final_map_heightmap.py`，不另抄。

**本轮已修 / 已清**

- 🔴 **彩图不再重上色**（用户裁定）：各级 `color_1m.png` = **原始地形材质**（`world_ground_final_out.png` 原色）。
  旧做法「改动区按同高程带均值重刷」= 平坦色块 + 硬边界；之后又试了三种（高程重映射 / 局部色差场 /
  按同高程找最近真实数据整块拼贴），全部失败：
  · 高程重映射：79.5% 找不到同高程目标，退回色块；
  · 局部色差场：整片染成紫红；
  · 同高程最近真实地块拼贴：**数据量根本不够**——东南要铺 6.57 km²，该区 32~52 m 的真实地块只有 **0.04 km²**；
    西北目标 720 m，全图 ≥690 m 的真实数据是 **0**。结果就是同一块纹理被反复复制，出现网格状重复。
- 已删除的阶段目录：`02_water_deepen` / `03_unified_water` / `02_unified_water`；
  对比图只保留 `stages_height.png` / `stages_color.png` / `diff_00_01.png`。

**新发现：彩图有 512 m 瓦片接缝（2026-11-02，待用户定方案）**

- 彩图由 480 块 512 m 瓦片拼成，全图 **23 条横缝 + 23 条竖缝**；最明显的一条在世界 **y≈0 / 左侧**（缝上下 150 m 均值差 **11.3**）。
- 三种后处理都试过：
  | 方法 | 缝差 | 副作用 |
  |---|---:|---|
  | 渐变色调对齐（±220 m，4 遍） | 11.3 → 2.0 | 缝附近出现**亮带** |
  | 硬台阶对齐（下半整块平移） | ≈0 | 23 条累计**漂移发白**，整图报废（已删） |
  | **柔化（±40 m 垂直模糊）** | 硬线消失 | 缝附近 80 m 软过渡、轻微糊 |
- 柔化产物（**未覆盖源文件、未进管线**）：`export\world\world_ground_final_out_seamsoft.png`
- 对比图：`_scratch\color_repaint\cmp_soft_A.png` / `cmp_soft_SE.png`
- **待用户选**：① 用柔化版（要重跑 final/stages/weights）② 保持原样 ③ 柔化+轻色调对齐组合。
- 实话：真正无缝需要源瓦片一致（重新导出/统一校色），纯后处理只能在「硬线」和「糊」之间取舍。

**已知问题（既有问题，待用户裁定处理）**

| # | 问题 | 实测 |
|---|---|---|
| 1 | ~~与出厂文件不一致 / 改动幅度太小~~ | 随「水域加深」「统一水位」两级一起删除，不再适用 |
| 2 | **高度图矩形接缝台阶**（外延包 ↔ 主瓦片） | 竖直 **x≈−732**、水平 **y≈−2048**，两侧高差 >20 m；**出厂文件同样存在**（上游导出，本管线改不了） |
| 3 | **彩图 512 m 瓦片接缝** | 见上表；柔化版已出，等用户选（采用后要重跑 final/stages/weights） |

**下一步**：用户逐条指出「哪里不符合预期」→ 按条改；候选处理见 `deliverable\terrain\README.md` §三「已知问题」。

---

## ★ 2026-11-02 · 水面改成**两级**（瀑布两侧水位差 62 m）—— ✅ 数据与脚本已完成，⏳ **blend 尚未重建**

**用户实机确认**：圣路易斯河（瀑布以西）水面比主水系（平铁湖 / 海岸）低，实机里就是那道瀑布
（截图：峡谷大瀑布，骑马视角）。**地形不用改**——标高数据是对的，错的是「水面只有一个平面」。

| 项 | 值 |
|---|---|
| 主水系（平铁湖 + 海岸 + 东侧河流） | **40.5 m**（`water.xml` 真值，沿用原单平面的高度） |
| 西盆地（圣路易斯河 / 新奥斯汀，瀑布以西） | **−22 m**（西盆地岸线中位 −16.8，按主水系「岸线 45.5→水面 40.5」同样扣 5 m） |
| 两级交界 | ≈ **(−2000, −3177)**，x −2400~−1600 / y −3450~−2900 |
| 高山小湖（40 个零碎水体） | 各自岸线中位（58~243 m），**不参与两级**，否则会被压到 40.5 埋掉 |

**产物**

- `export\world\water_level_map_2lv.npy` —— 两级水位图（2048²，行 0=南，NaN=陆地）
- `tools\water_two_levels.py` —— 建 **三个**对象（默认 **32 m** 网格，约 1 万四边形；
  ⚠️ 2026-10-28 否掉的是 8 m / 28.5 万四边形 + 半透明版本，视口会卡，别退回去）：
  · **`Water_Main`** —— 主水系，默认 40.5 m
  · **`Water_West`** —— 西盆地，默认 −22 m
  · **`Water_Alpine`** —— 高山小湖（58~243 m），各湖保留自己的水位

🔴 **水位可调**（同旧版 `make_water_dynamic()`）：选中 `Water_Main` / `Water_West` →
物体属性 → 自定义属性 **`water_level`**，改数值水面立刻升降（网格顶点 z=0，对象按 `water_level` 移动）。
上面 40.5 / −22 只是**初值**，准不准以实机为准 —— 直接调旋钮，不用改脚本重跑。

**已同步改过的脚本**（都按 `Water` / `Water_*` 前缀找水面，不再写死单对象）

| 脚本 | 改了什么 |
|---|---|
| `blender_continent.py` `water()` | 单平面 → 调用 `water_two_levels.build()`；两级图缺失时退回旧图，再失败才退回单平面 |
| `blender_crop_continent_to_map.py` | 裁框后重建水面 → 两级、只留框内四边形 |
| `blender_sync_blend_to_heightmap.py` | 同上 |
| `blender_tour.py` | `decimate` / `undecimate` / 性能提示 覆盖所有水面对象 |
| `blender_probe_maparea.py` | 水面面数按所有水面对象求和 |
| `blender_rebuild_ground.py` | `clear_old()` 清掉所有水面对象 |
| `clamp_water.py` / `lower_water_local.py` / `carve_water_channel.py` | 逐个水面对象处理（原来是单对象） |
| `replace_water_plane.py` | 改成委托 `water_two_levels.build()`（原「一张平面 40.5」的做法作废） |
| `rebuild_water_from_map.py` | 同上，委托两级构建 |
| `rebuild_water_levels.py` | 头部标注：**只负责算单级水位图**，建水面走 `water_two_levels.py` |

**状态**：按用户 2026-11-02 指示，**没有重建 blend**（`continent_v23.blend` 是红线内的主产物，不许动）。
下次建大陆 / 裁框 / 同步时新脚本自动生效。冒烟测试已在小 blend（`16_wild2000_01_02`）跑通：
`Water_Main 8124 四边形` / `Water_West 1770 四边形`。

**遗留**：两张水位图并存 —— `water_level_map.npy`（单级，旧）与 `water_level_map_2lv.npy`（两级，新）。
旧图仍被 `build_final_map_heightmap.py` / `make_terrain_stages.py`（节点 2 的水深）引用；
是否切到两级图、以及 `02_water_deepen` 要不要按西盆地重算，等用户裁定。

---

## ★ 待办 · 瓜玛岛地形对齐（2026-11-02 用户裁定：**暂不处理**）

**目标**（等用户说做的时候再动手）：出一版 `guarma_height.png` / `guarma_color.png`，
和 `地图下载\瓜玛岛.jpg` 精确贴合，跟大陆那套（`deliverable\terrain/on_map\`）同口径。

**卡在哪**：官方瓜玛地图**没有配准数据**（`地图下载\配准结果.json` 里只有大陆的 5 个控制点），
而且那张图是**手绘风美术地图**（纸边 + 示意海岸线），轮廓对不上真实地形，自动匹配不可靠。

**需要用户提供**：2 个以上「像素坐标 ↔ 世界坐标」对应点。已知世界坐标：

| 地点 | 世界坐标 |
|---|---|
| 阿瓜多切斯 Aguasdulces | `1364.0, -6992.5` |
| 瓜玛营 Guarma Camp | `1426.3, -7328.9` |

**取点工具**：`python tools\make_map_aligned_terrain.py`（不带参数）会生成
`deliverable\terrain/on_map\guarma_grid.png`（200 px 红网格 + 坐标标注）。
拿到点后：

```powershell
python "H:\SteamLibrary\steamapps\common\Mount & Blade II Bannerlord\Modules\RDR2\Source\tools\make_map_aligned_terrain.py" --guarma-pts "<px>,<py>,1364.0,-6992.5;<px>,<py>,1426.3,-7328.9"
```

---

## ★ 2026-11-01 · 两层材质 B —— ✅ 已实施（规则见 `docs/格式与资产/RDR2_贴图分层与两层材质.md`）

### 0. 一句话（修正自原判断）

码头/墙体"整块发黑"有**两个原因**，原 TODO 只抓到了一个半：

1. 🔴 **主因：贴图池的 PNG 被缩图缩黑了。** PIL 12 对 RGBA 做 `resize` 是**按 alpha 预乘**的重采样，
   alpha 稀疏的贴图 RGB 会被乘暗。实测 `nbx_wall_woodplank_11long_rotted_ab`：
   **源 0.30 → 池子里 0.034**（原 TODO 记的"RGB 0.034、是遮罩"其实是这个 bug 的产物）。
   同时旧代码 `resize((512,512))` 还把 1024×512 的墙板纵向拉长一倍。
   修法 = `ytd_to_png.resize_max()`：**RGB 与 alpha 分开缩** + 等比。
2. **次因：两层材质只导了第 0 层。** `standard_2lyr*` 是 `lyr0 + lyr1 + control`，
   `standard_dirt` 是 `diffusetex + diffusetex2`。现已全部接上。

### 1. 做完了什么

| # | 内容 | 落在哪 |
|---|---|---|
| 1 | 贴图池刷新（修缩图缩黑 + 长宽比） | `tools/refresh_tex_pool.py`（新）；全量 32,878 张，**3,348 张被改写** |
| 2 | 两层取图规则 + 遮罩通道自动判定 | `tools/tex_slots.py` 的 `pick_layers()` / `mask_channel()` / `alpha_std()` |
| 3 | 抽 `l1/ct/dt/nm2/ma2/pl` 并写索引 | `tools/extract_slot_textures.py`（四段式扩展，写 `models[h].lyr` 与 `tex[i].ch`） |
| 4 | 材质节点 `mix(lyr0, lyr1, w)` | `tools/mat_rdr2.py`（颜色/法线/ORM 同一 Fac） |
| 5 | 构建与重挂开关 | `blender_continent --lyr on|off`、`relink_materials --lyr on|off` |
| 6 | 文档 | `docs/格式与资产/RDR2_贴图分层与两层材质.md`（新）· `tools/README.md` |

**全库实测（2026-11-01，68,744 个源模型）**：
* 绑上两层的模型 **7,984 个 / 21,870 个槽位**（第 1 层 21,662、control 9,035、dirt 9,740）；
* 其中 **6,965 个模型真有混合权重**（`python tools/audit_two_layers.py`）：
  `ctrl.R` 4,300 · `ctrl.G` 3,150 · `ctrl.B` 968 · `ctrl.A` 358 · `l1.alpha` 8,602 · 无权重（退回单层）4,073 槽；
* 调色板内嵌在 `.ydr` 体内，已解出 **9,147 张**进池，**但材质暂不使用**（语义未验证，见下）。

**验收（2026-11-01 已做）**：
* 🔴 **区域 #20 已用两层材质重建到官方路径** `deliverable\blender\regions\20_wild2000_05_02.blend`（959 MB，旧版 955 MB 已挪到
  `_scratch\two_layer\region20_prev.blend` 作回退）→ `VERIFY ENTITIES ... PASS` · `_check_region.py` **PASS**（18 类逐项一致）；
  清单已归位 `regions_support\20_wild2000_05_02\`；
* 场景内 **4,378 个材质里 1,356 个带两层混合（31%）**；
* 圣丹尼斯码头（世界坐标 ≈ `2543, -1570, 46`）同机位 A/B 出图：
  旧 blend 的木桩/栈桥是一片褐色糊，新 blend 能看到一根根木桩与板缝
  （图在 `D:\BrainMaker\大镖客2解包分析\_scratch\two_layer\region\region_sdn_dock_{old,new}.png`）。
  🔴 探针产物一律放**项目自己的** `大镖客2解包分析\_scratch\<主题>\`，不许放 `D:\BrainMaker\` 根（2026-11-01 用户裁定，见 AGENTS §1.9）。

### 2. 关键判定（留档，别再重查）

* **混合方向**：`w 大 → 第 1 层`。依据 = 控制图资产名直接叫第 1 层的素材
  （`nbx_ground_grass_bay_lsuh_mb` ↔ lyr1 `nbx_ground_grass_bay_lsuh_ab`），
  以及社区实现 Sollumz-RDR `RDR_create_2lyr_shader`（`diff_lyr_mix` 的 Color2 = `lyr1diffusetex`）。
* **取哪个通道**：不写死 R —— 专用 `_ct` 是灰度、复用 `_mb` 时往往只有一个通道在变，
  所以按**方差最大**挑，结果存在 `tex[i].ch`。
* **`standard_dirt` 没有控制图** → 第 1 层 `_abal` 的 **alpha** 就是权重（实测 alpha 0~0.89 起伏）。
* **调色板先不用**：码头那张 256×4 是「绿 / 青 / 白」渐变条，直接乘会把木头染绿；
  它要配合逐顶点 `COLOR0` 选择子（`tintpaletteselector` CBuffer）才有意义 —— 未验证。
* **逐顶点 `COLOR1`** 与 control 贴图**互不相关**（实测 |r| < 0.4），是两条独立通道；
  要用它得给 `.mdl` 加逐顶点属性并重导几何 —— 本轮没做。

### 3. 下一步（真要做的话）

1. 区域重建后**肉眼抽查码头/城墙/室内墙面**（区域 #20 已重建，见下）；
2. 若某个模型的两层看起来"反了"，先看材质的 `layer_mix` 自定义属性（记录权重来源），
   再用 `--lyr off` 对照 —— 不要靠改公式猜；
3. 想更进一步就是 §2 最后两条（调色板 / 逐顶点权重），都要先解 CBuffer 或改 `.mdl`。

### 4. 已知风险（保留）

- 材质每槽最多多 2~4 张图节点（第 1 层 albedo/法线/ORM + 控制图），大陆重建时间会变长；
- `control` 有 25 个 SDN 模型取不到（`nbx_wall_woodplank_14long_ct` 不在已解包的任何 `.ytd` 里）
  → 这些槽退回单层，不报错。

---

### 5. 本轮（2026-11-01）其他已完成事项

- 22 个区域裁剪全部 PASS；`unknown` 在 #19/#20 已清零（#20：254 个缩略图目视 → 250 条纠错 #91~340）。
- 分类规则：`struct` 只留桥/栈桥；码头→建筑；信号灯→部件；tower/build/kitchen/coop/tabacco/boathouse/props/水面/道岔等词缀。
- 修掉构建 bug：材质名截断（贴图纠错漏匹配）、隐藏集合 `matrix_world` 未求值（包围盒/埋深错误）。
- 资产目录重构复核通过；探针"专用目录 + 用完即删"规矩已落到
  `docs/格式与资产/分类体系与判定规则.md` §6.1。

---

## ✅ 2026-11-01 · 批量生成 22 个「有网格」的区域裁剪（已完成，保留作流程参考）

> ✅ **2026-11-01 已完成**：22/22 块 `status=done`，`_check_region` 全部 PASS；
> 本节保留作流程/命令参考。**上一件事（两层材质 B）也已在同日落地**，见上面那一节；
> 现在要重做区域/大陆时会自动带两层材质（`--lyr off` 可回退）。

### 0. 一句话

大陆 v23 目前还是 **17 类旧规则**；分类规则已升级到 **21 类**（新增 `road`、`ruin`、`rail_decal`），区域 #19 已验证 PASS。接下来把**可见对象 > 0** 的 22 个区域各裁一个 blend，逐个对账；全部 PASS 后再对大陆跑一次，出 v24。

### 1. 目录约定（2026-10-31 用户裁定，照 `sdn_full2/`、`guarma/`、`willard/` 的先例）

```
D:\BrainMaker\大镖客2解包分析\deliverable\blender\
├── regions\                         ← 只放区域 blend
│   └── <编号>_<tile>.blend          （例：19_wild2000_04_02.blend）
└── regions_support\                 ← 验证内容
    ├── region_list.csv              ← 批量清单 + 状态（已建：22 行，19=done，其余 todo）
    ├── region_corrections.csv       ← 全局纠错清单（一份，共用）
    ├── overview\                    ← 全图俯视图/图例（可选）
    └── <编号>_<tile>\               ← 每区域一个验证子目录
        └── manifest_<编号>_<tile>.json / .jsonl
```

- **`regions\` 里只允许 `.blend`**；manifest / 预览图 / CSV 一律进 `regions_support\`。
- 日志：`D:\BrainMaker\大镖客2解包分析\_logs\region_<编号>.log`。
- 编号 = 俯视图图例的 `#1~#47`（`regions_support\tile_legend.csv`）。

### 2. 要跑的区域（22 块）

不做：24 个「可见对象 = 0」的块；4 个只有 4 个对象的边角桩（#1/#2/#8/#9）；**瓜玛 #40**（战役不含它）。

| 批 | 编号 | tile | 可见对象 |
|---|---|---|---:|
| 1 | #19 | `wild2000_04_02` | 26,018（**已完成**） |
| 1 | #20 | `wild2000_05_02` | 21,855 |
| 2 | #18 | `wild2000_03_02` | 15,199 |
| 2 | #12 | `wild2000_04_01` | 12,062 |
| 2 | #11 | `wild2000_03_01` | 11,556 |
| 2 | #13 | `wild2000_05_01` | 11,081 |
| 2 | #23 | `wild2000_01_03` | 8,158 |
| 2 | #17 | `wild2000_02_02` | 7,077 |
| 2 | #24 | `wild2000_02_03` | 4,077 |
| 3 | #10 | `wild2000_02_01` | 3,008 |
| 3 | #25 | `wild2000_03_03` | 2,027 |
| 3 | #26 | `wild2000_04_03` | 1,717 |
| 3 | #4 | `wild2000_03_00` | 1,347 |
| 3 | #22 | `wild2000_00_03` | 1,232 |
| 3 | #5 | `wild2000_04_00` | 1,066 |
| 3 | #6 | `wild2000_05_00` | 697 |
| 3 | #3 | `wild2000_02_00` | 78 |
| 3 | #27 | `wild2000_05_03` | 57 |
| 3 | #33 | `wild2000_04_04` | 29 |
| 3 | #16 | `wild2000_01_02` | 11 |
| 3 | #21 | `wild2000_06_02` | 7 |
| 3 | #30 | `wild2000_01_04` | 2 |

### 3. 单块命令（可直接复制的模板）

**A. 从零构建一块**（Blender 进程内跑完整链：几何 → 分类 → 植被/地形/LOD 隐藏 → 清单）

```powershell
Set-Location "H:\SteamLibrary\steamapps\common\Mount & Blade II Bannerlord\Modules\RDR2\Source"
cmd /c 'tools\run.cmd D:\BrainMaker\大镖客2解包分析\_logs\region_20.log "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" -b --python tools\_unbuffer.py -P tools\blender_continent.py -- --out "D:\BrainMaker\大镖客2解包分析\deliverable\blender\regions\20_wild2000_05_02.blend" --lib "D:\BrainMaker\大镖客2解包分析\assets\lib_native" --only-tile wild2000_05_02 --step 8 --rails --full --no-water --corrections "D:\BrainMaker\大镖客2解包分析\deliverable\blender\regions_support\region_corrections.csv"'
```

**B. 已建好的区域只重跑分类/纠错**（约 3~5 分钟，不重建几何）

```powershell
Set-Location "H:\SteamLibrary\steamapps\common\Mount & Blade II Bannerlord\Modules\RDR2\Source"
cmd /c 'tools\run.cmd D:\BrainMaker\大镖客2解包分析\_logs\region_20_fix.log "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" -b "D:\BrainMaker\大镖客2解包分析\deliverable\blender\regions\20_wild2000_05_02.blend" -P tools\_unbuffer.py -P tools\_apply_corrections.py -- --corrections "D:\BrainMaker\大镖客2解包分析\deliverable\blender\regions_support\region_corrections.csv" --out "D:\BrainMaker\大镖客2解包分析\deliverable\blender\regions\20_wild2000_05_02.blend"'
```

**C. 对账（每块必跑）**

```powershell
python "H:\SteamLibrary\steamapps\common\Mount & Blade II Bannerlord\Modules\RDR2\Source\tools\_check_region.py" --tile wild2000_05_02 --audit "D:\BrainMaker\大镖客2解包分析\deliverable\blender\regions_support\20_wild2000_05_02\manifest_20_wild2000_05_02.jsonl"
```

> 说明：A 构建会把 manifest 写在 blend 旁边。**必须**把它移到 `regions_support\<编号>_<tile>\`（`_apply_corrections.py` 会自动挪；纯 A 构建要手动 `Move-Item`）。判据永远是 `_check_region.py` **PASS**（21 类计数逐项一致）。

### 4. 批量驱动（已实现：`tools/build_regions.py`，2026-10-31）

要求：

| 项 | 规定 |
|---|---|
| 输入 | `regions_support/region_list.csv`（列：`number,tile,blend,visible,status`） |
| 执行 | **一次一个 Blender**（内存/磁盘），顺序按编号；每块调 A 命令 |
| 断点 | `status=done` 跳过；`--resume` 默认开启；`--force` 重跑；`--only 19,20` 指定 |
| 归位 | 构建完把 `manifest_<编号>_<tile>.json/.jsonl` 移到 `regions_support\<编号>_<tile>\` |
| 对账 | 立刻跑 `_check_region.py`；**FAIL 就停**，不继续下一块 |
| 日志 | `D:\BrainMaker\大镖客2解包分析\_logs\region_<编号>.log`；驱动自身日志 `_logs\build_regions.log` |
| 备份 | 构建前设 `save_version=0`，**不生成 `.blend1`**（`reclassify.py` 已有先例） |
| 状态 | 每块结束更新 `region_list.csv` 的 `status`（todo/done/failed） |

### 5. 验收 / 停止条件

- 单块：**以 `_check_region.py` PASS 为准**。
  🔴 `manifest` 的 `verdict` 在小区域常常是 `CHECK` —— **不是失败**：第 1 步的 18 类覆盖判据
     是给大陆用的，野外小块本来就没有 rail/watertile/bldg 这些类。看 `veg_should_delete==0` 即可。
  🔴 `unknown` 允许为 0 或非 0；区域检查期对账带 **`--allow-stale-underground`**：v23 有 2,312 个对象的
     包围盒是局部坐标（矩阵未求值），埋深判定失真；该开关只把「underground 差额恰好等于其他类差额」
     降级为警告，其它差异仍 FAIL。**大陆最终重跑（v24）之后必须去掉这个开关做严检。**
- 批量：22 块 `status=done`，无 `failed`。
- 任何一块 FAIL：**停止批量**，修规则/纠错 → 跑 `_check_rules.py` → 用 B 命令重跑该块。

### 6. 磁盘 / 时间

- 单块约 **0.4~0.9 GB**（`--step 8 --no-water`；#19 实测 860 MB），22 块合计约 **10~15 GB**；
- 单块 5~12 分钟，**22 块约 3~4 小时**；
- 做完不用的块可删（`region_list.csv` 留状态，`--only` 可重跑）。

---

## ★ 批量之后：大陆收口（v24）

> 🔴 2026-10-31 用户明确要求：**先把每个分块做对，最后才重跑一次大陆**。本轮只做到分块（22/22 done），
> 大陆重跑**未执行**（曾误启动一次，产物已删除）。开工前先征得用户同意。
> 重跑之后：`_check_region.py` 必须**去掉 `--allow-stale-underground`** 对所有区域做严检。

1. 用**同一份纠错清单**把 v23 重分类成 v24（**新建文件，不覆盖 v23**）：

```powershell
Set-Location "H:\SteamLibrary\steamapps\common\Mount & Blade II Bannerlord\Modules\RDR2\Source"
cmd /c 'tools\run.cmd D:\BrainMaker\大镖客2解包分析\_logs\continent_v24.log "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" -b "D:\BrainMaker\大镖客2解包分析\deliverable\blender\continent\continent_v23.blend" -P tools\_unbuffer.py -P tools\_apply_corrections.py -- --corrections "D:\BrainMaker\大镖客2解包分析\deliverable\blender\regions_support\region_corrections.csv" --out "D:\BrainMaker\大镖客2解包分析\deliverable\blender\continent\continent_v24.blend"'
```

2. 验收：manifest `verdict=PASS`（`unknown` 允许为 0，看 `classes_missing` 为空）、`_check_region.py` PASS；`_check_class_visibility.py` 确认 `road` 隐藏、`ruin` 显示。
3. 之后所有区域重建都自动继承 21 类 + 纠错清单。

---

## 当前状态（2026-10-31 晚）

### 区域批量：**22/22 全部完成**（`region_list.csv` 全 `done`）

- 产物：`deliverable\blender\regions\<编号>_<tile>.blend`（每块 0.1~0.9 GB）
- 清单：`regions_support\<编号>_<tile>\manifest_<编号>_<tile>.jsonl`
- 对账：全部 **PASS**；只有 #18 触发 1 条警告（v23 多出 underground 31 个，旧包围盒失真），其余 21 块逐类严格一致
- 驱动：`tools/build_regions.py`（断点续跑；FAIL 即停；一次一个 Blender）

### 本轮修掉的两个构建 bug（影响所有块的正确性）

1. **材质名截断**：`mat_rdr2.mat_name` 超 60 字符会截成 `alb_<前26字符>__<哈希>`，贴图纠错在构建侧漏匹配 → 贴图匹配时必须同时喂 `m['albedo']` 全名。
2. **隐藏集合不进 depsgraph**：后台模式下隐藏集合里的对象 `matrix_world` 不更新 → 包围盒/埋深/贴地判定全错（v23 清单里 2,312 个对象的 `bb` 是局部坐标）。已在 `classify_entities` / `write_manifest` 里强制「全开集合 + `view_layer.update()`」。
3. 连带：**修复前建的区域必须重建**（已全部重建完毕），否则几何判定不可信。

### 区域 #19（已完成，可作模板）

- `deliverable/blender/regions/<编号>_<tile>.blend` = 22 块，按 **`wild2000_XX_YY` 的 2,000 m 瓦片网格**切。**这 22 块已全部 `_check_region.py` PASS**（网格/分类/贴图齐全），但那是**旧的切法**。
- 29,843 对象 / **19 类 19/19** / 对账 **PASS**
- 隐藏 4,598（lod 512 / terrain_cell 999 / veg 2,502）
- **unknown 已清零**（`com_plane001` 目视确认完全埋在地下 → underground）——430 → 0，2026-10-31 纠错行 16~41

### 分类体系（现已 21 类，规则唯一真身 = `tools/class_rules.py`）

- 新增类：`road`（道路，**默认隐藏**）· `ruin`（废墟，**默认显示**）；
- 硬规则：**名字含 `junc` 一律 road**（无例外）；名字含 `ruin` 一律 ruin（`lod/underground` 除外）；
- 纠错清单：`regions_support\region_corrections.csv`（40 条，id 1~4 / 6~41；16~41 = 区域 #19 的 unknown 清理）；
- 回归：`tools/rules_cases.csv`（16 条用例），`_check_rules.py` 全过；内置关键词最近补了 `infirmary`（bldg）、`_bri(?!ck)`（struct）
- 改分类流程与坑：见 `docs/格式与资产/分类体系与判定规则.md`。

### 相关脚本

| 脚本 | 用途 |
|---|---|
| `tools/class_rules.py` | **规则唯一真身**（21 类 / RULES / 硬规则 / 纠错解析） |
| `tools/classify_entities.py` | Blender 驱动（建集合树、几何兜底） |
| `tools/_apply_corrections.py` | 已建区域重跑分类（含纠错、清单归位） |
| `tools/_check_region.py` | 区域对账（v23 + 纠错 vs 区域 manifest） |
| `tools/_check_rules.py` | 规则自检（合法性 / 冗余 / 用例） |
| `tools/_probe_tile_atlas.py` / `_probe_tile_labels.py` | 整图俯视渲染 / 地块编号 |
| `打开大陆_流畅.bat` | 双击选编号打开区域（`regions\<编号>_<tile>.blend`） |

---

## 遗留清理（2026-11-04 核对）

| 文件 | 原因 | 现状 |
|---|---|---|
| `deliverable\blender\regions\19_wild2000_04_02.blend1` | Blender 自动备份（860 MB） | ✅ 已不存在（用户已清） |
| `_logs\test2.bat` / `test_launcher.bat` / `bat_dump.txt` | 调试 bat 临时文件 | ✅ 已不存在（用户已清） |
| `deliverable\blender\regions_support\_probe_cards_wide.json` / `_probe_crosscards.json` | 一次性探针输出 | ⏳ 仍在（约 0 MB）；`regions/` 清理时一并删 |
| 探针预览图 `deliverable\blender\scenes\shots\` + `_scratch\sdn_check\` | 本轮场景核对用 | ⏳ 12 MB，看完可删 |

---

## 禁止事项（交接红线）

1. **不要改 `continent_v23.blend`**（7.3 GB 主产物）；要升级就出 `continent_v24.blend`；
2. **不要在 `D:\BrainMaker` 根放任何文件**；新目录先问（见 `AGENTS.md` §1.9）；
3. **不要手动改 `regions_support\region_corrections.csv` 之外再抄一份规则**；规则值只进 `class_rules.py`；
4. **不要跳过 `_check_rules.py` / `_check_region.py`**；
5. **不要同时跑两个 Blender**（内存/磁盘竞争）；
6. **不要生成 `.blend1`**（构建脚本设 `save_version=0`）。
