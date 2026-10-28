# TODO —— 交接版（2026-10-29 01:30）

> 交接顺序：1) 本文件 2) `AGENTS.md`（长任务/禁开大文件/已知坑）3) `docs/最高原则_单一管线与分块即裁剪.md`（五条禁令）
> 历史 TODO 在 `docs/交接与状态/TODO.md`。

---

## 0.5 上一轮的"最重要下一步"已经做完，而且**结论被推翻了**

上一轮把「补全模型库：从 ytyp 取 `assetName` → 按 hash 抽 → 入库 → 重建」列为头号任务，
目标是「未命名实例 50,007 → <5,000」。四步全部做完，实测结果：

| 步 | 原计划 | 实测结果 |
|---|---|---|
| 1 | `ytyp_archetypes.py` 增存 `assetName` 并回填 | ❌ **前提不成立**：96,141 条 archetype 的 `+88` 与 `+112` **完全相同（0 条不同）**，`name == assetName`，没有第二个名字可挖。工具已改成按对存（`tools/ytyp_assetnames.py`） |
| 2 | RPF 按 hash 定位 drawable | ✅ 新建 `rdr2rpf hashindex`（原地读嵌套 TOC）+ `tools/rpf_index.py`：18 个顶层包 → **4,021 个 RPF / 74,449 个 drawable 条目**，索引 7.1 MB |
| 3 | 抽件 + 入库 | ⚠️ 缺模型里 **1,834 个** hash 能在包里命中；抽出 1,832 个，**能解析出几何的只有 1 个**（其余全是 `_vfx/_slod/_lights/_helper/_ph/_proxy`，无面） |
| 4 | 重建 | ✅ 见 §2；**但"未命名"本身不是缺口**，见下 |

**推翻的结论**（证据全在 `docs/世界与地编/RDR2_整图覆盖率核查_20261026.md` §10）：

> 那 4.98 万个"未命名 archetype"里，**46,532 个 hash / 46,536 个实例是 LOD 合并块**
> （定义它们的 ytyp 全叫 `*_lod_combine_metadata*`；bbox 中位 **64 m**、P90 **128 m**；
> 77.5% 的实例水平 0.5 m 内就盖着已装好的具名件）。
> 游戏在运行时按子 archetype 现场合并这层远景 LOD，**磁盘上没有独立 `.ydr/.yft`**。
> 它们不是"缺件"，也不该按 HD 装进场景。

**新口径（唯一权威，脚本 `tools/audit_missing_models.py`，明细 `export/world/missing_classified.json`）**：

| 桶 | hash | 实例 | 占比 | 处置 |
|---|---:|---:|---:|---|
| `lod_block` | 46,532 | 46,536 | 88.1% | **不装**（不是缺口）；统计里单列 |
| `real_ytyp` | 3,061 | 3,268 | 6.2% | 真实件，包里查不到 → 下一步（§0.6） |
| `rpf_available`（含 nonrender/interior） | 1,833 | 2,487 | 4.7% | 包里只有无几何代理 → 装不了 |
| `no_definition`（含 interior/nonrender） | 486 | 515 | 1.0% | ytyp 里查不到，来源待查 |
| **合计** | **51,912** | **52,806** | 100% | |

验收对照：

| 旧验收 | 实测 |
|---|---|
| 未命名实例 50,007 → <5,000 | **46,536 个是 LOD 块（不是缺口）**；真实缺件 3,268 + 515 = **3,783 实例 < 5,000** ✅ |
| 圣丹尼斯未命名大件 2,124 → <300 | 严格框内缺 2,399，其中 LOD 2,116 → **真缺口 283 < 300** ✅ |

---

## 0.6 真正的下一步（都不在本管线里，需要新数据源）

1. **`real_ytyp` 3,061 个 hash**：真实 ytyp 定义（bbox 中位 7.4 m）但 RPF 里按 hash 找不到 drawable。
   下一轮要查的四个方向，按可能性排序：
   - **`drawableDictionary`**：archetype 结构里 +100 字段（对 96,141 条都能在 names.txt 里解析）
     很可能是 `.ydd` 字典名 → 抽 `.ydd` 再取里面的 drawable（当前只按 hash 找 `.ydr/.yft`）；
   - 索引只做了 `depth ≤ 6`、且只认 RPF8 格式；先把失败/跳过的包列出来（当前无告警，但没统计）；
   - `update_1..4` 只扫了 `ydr/yft`，没扫 `ydd`；
   - 也可能是 `_ph/_occ` 之类代理（3,061 里有多少是代理还没逐条核）。
2. **室内 319 个 hash**：卡在 MLO `rooms/portals` 变换（老阻塞，见 §5 #室内）。
3. **~~贴图表 id↔名字↔文件 三者有错位~~ → 已彻底重做**（2026-10-29，详见覆盖率核查 §11）：
   贴图表整表按**名字**重建（`id = 名字排序下标`，`tex/<id>.png` 由 ytd 按名字解出），
   55,608 个模型全部按**源文件**重绑，`.mdl` 回写 221,494 个子网格；
   审计 600 模型 / 2,416 子网格 → **绑错 0**。剩余 2,813 个名字（2.0% 引用）所有包里都没有图。
4. `no_definition` 486 个 hash：来源不明（ytyp 里没有），下一轮用 `archetype_swaps.ymt` 之类查。

---

## 一句话状态

**唯一主产物：`deliverable/blender/continent/continent_v9.blend`**（7.32 GB）
对象 **147,500** / `ENTITIES` **103,898** / 隐藏 43,599 / 贴图用 **6,967** / 无 albedo **17,682** / manifest → **PASS**。
模型库 **55,608** / 贴图表 **11,504**（按名字排序定 id；磁盘 ytd 名字索引 128,289）；缺模型 51,912 hash，其中 **88.1% 是 LOD 合并块（非缺口）**。

---

## 1. 五分钟上手

```
① 双击 打开大陆_流畅.bat   → 自动打开目录里最新的 continent_v*.blend（当前 v9）
② 3D 视图按 N              → 「RDR2」页签：12 类开关 / 全图·当前地块 / 水面 / 水位 / 植被
③ 验贴图                   → 搜 new_gar06_park_terrain（材质名现在是 alb_<贴图名>）
④ 不开 blend 核对          → uv run python tools/report_manifest.py
⑤ 缺模型到底缺什么         → python tools/audit_missing_models.py
```

默认隐藏的集合（想看要单独勾）：`HIDDEN_VEG`（植被）· `HIDDEN_TERRAIN_CELL`（地形 patch）·
`HIDDEN_LOD`（远景 LOD 碎片）· `HIDDEN_PARKED`（地图外 1 km 的 `*_tempbox*` 占位盒）

---

## 2. 文件清单

### 有效产物

| 文件 | 大小 | 说明 |
|---|---|---|
| `deliverable/blender/continent/continent_v9.blend` | 7.32 GB | **本轮主产物**：对象 **147,500** / `ENTITIES` **103,898** / 隐藏 **43,599**（地形 30,549、植被 10,860、LOD 2,186、占位 4）/ 12 类 11 类有对象（`int` 与 v8 同缺）/ 贴图用 **6,967** / 无 albedo **17,682**（贴图重做前 62,467）/ manifest → **PASS** |
| `deliverable/blender/continent/continent_v8.blend` | 6.81 GiB | 上一版，保留作对照（可删） |
| `.../manifest_continent_v9.json` / `.jsonl` / `manifest.json` | 30.7 MB | 对象级清单 + 汇总（汇总由 `manifest_from_jsonl.py` 0.5 秒反算） |
| `docs/世界与地编/img/verify/v9_city.png` | — | **v9 俯视验证图**（水已蓝、无纯白块）；同目录 `v8_city.png` 是对照 |
| `export/world/missing_classified.json` | 9.9 MB | **缺模型的分类明细**（逐 hash：桶/名字/来源 ytyp/bbox） |
| `export/levels/town/archetype_assetnames.json` | 13.2 MB | 96,141 条 archetype：hash → assetName/bbox/来源 ytyp |
| `work/rpf_index/all.tsv` | 7.1 MB | RPF 全量 drawable 索引（包 + hash + 大小 + 名字） |
| `deliverable/blender/sdn_full2/sdn_full2.blend` | 1.30 GiB | 圣丹尼斯单城 r=2000（历史管线产物，只作证据） |
| `deliverable/blender/willard/willard_full.blend` | 1.03 GiB | 夏洛蒂家（**旧管线产物**：对象全 `e_<hash>`、Water 仍是 2048² 网格） |
| `deliverable/blender/guarma/guarma.blend` | 0.29 GiB | 瓜马岛 |
| `assets/lib_native/` | — | 模型 **55,608** / 贴图 **7,074**（含 1,782 张按 id 补登记的孤儿贴图） |

### 建议删除（等你点头，脚本可一次性清）

| 目录/文件 | 占用 | 原因 |
|---|---|---|
| `work/lib_gtxd/txd_game/` | **28.5 GiB** | 19,058 个 ytd，几乎全是 `ui_*`/`metaped_*`（角色/UI），场景不用 |
| `archive/废弃_sdn_full管线/` | 4.3 GiB | 废弃 glTF 管线产物 |
| `continent_v8.blend1` / `willard_full_orig.blend` | 6.81 + 1.03 GiB | 上一版/原始备份 |
| `assets/lib_native/index_before_*` | 3 × 8.8 MB | 本轮三次改库的备份，确认后可删 |

### 已删除（别再找）

`continent.blend`(9.87 GB) · `continent_v2`(8.07) · `v3`(8.07) · `v4`(7.90) · `v5`(6.31) · `v6`(6.36) ·
`raw/verify/tile_test.blend`(2.43) · `raw/_scratch/tile_test/tile_v6test.blend`(0.93) · `raw/sdn/test_ground.blend`(0.02)。
**v7 从未生成。** 合计释放 49.94 GiB。

---

## 3. 关键脚本

| 脚本 | 用途 |
|---|---|
| `tools/blender_continent.py` | **唯一构建入口**：`--rails --full [--veg hide\|delete\|keep] [--pad] [--bbox x0,y0,x1,y1] [--only-tile <id>]` |
| `tools/postprocess_continent.py` | 补跑分类/植被/地形隐藏/清单 |
| `tools/report_manifest.py` | **不开 Blender 核对** + `--find/--class/--tile` 查询 |
| `tools/audit_missing_models.py` | **缺模型分类**（LOD 块 / 真件 / 包里有无 / 来源 ytyp）+ 据点拆分 |
| `tools/ytyp_assetnames.py` | 1,026 个 ytyp → 96,141 条 archetype（hash / assetName / bbox / 来源） |
| `tools/rpf_index.py` | RPF 全量索引（调 `rdr2rpf hashindex`） |
| `tools/extract_by_hash.py` | 按 **RPF 条目 hash** 抽 drawable（调 `rdr2rpf extracthash`） |
| `tools/normalize_lib_index.py` | **修 index.json 未补零 key**（本轮找回 367 个模型） |
| `tools/patch_ground_town_white.py` | 地面色图"无数据白"体检/补洞（默认 probe） |
| `tools/write_manifest.py` | 写对象级清单；材质名 `alb_<贴图名>` / `nonalbedo_*` 都认 |
| `tools/rebind_textures.py` | 模型→贴图**按名字**重绑（禁 fuzzy） |
| `tools/relink_materials.py` | 给**已存盘** blend 按当前 index 重挂材质（槽位按子网格序，不再"首次出现去重"） |
| `tools/hide_lod.py` / `hide_terrain_patches.py` | 远景 LOD / 地形 patch / 地图外占位盒 → 隐藏集合（都不删） |
| `tools/classify_entities.py` | 12 类分类（本轮修 `privy` 被分进植被） |
| `tools/render_check.py` | 无 GUI 俯视检查图（Workbench+TEXTURE，几秒一张） |
| `tools/extract_missing_from_game.py` / `ingest_extracted_models.py` | 抽缺失模型 / 增量入库（先备份 index） |
| `tools/run.cmd` / `read_text.py` / `_unbuffer.py` / `watch_build.ps1` | 本机起子进程 / 读 GBK / 行缓冲 / 长任务看门狗 |

---

## 4. 常用命令

```powershell
# 全量重建（实测 45~55 分钟）
cmd /c 'tools\run.cmd D:\BrainMaker\build_vN.log "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" -b --python tools\_unbuffer.py -P tools\blender_continent.py -- --out D:\BrainMaker\大镖客2解包分析\deliverable\blender\continent\continent_vN.blend --lib D:\BrainMaker\大镖客2解包分析\assets\lib_native --rails --full'

# 小范围试验（3~6 分钟）：单地块 + bbox
cmd /c 'tools\run.cmd D:\BrainMaker\_t.log "<blender>" -b --python tools\_unbuffer.py -P tools\blender_continent.py -- --out D:\BrainMaker\_test\t.blend --lib <abs>\assets\lib_native --rails --full --only-tile wild2000_05_00 --bbox 2900,2100,3100,2300'

# 单步补丁（加载+存盘 7~10 分钟）
cmd /c 'tools\run.cmd D:\BrainMaker\_p.log "<blender>" -b <blend> --python tools\_unbuffer.py -P tools\hide_lod.py -- --shots'

# 核对 / 缺口 / 库
uv run python tools/report_manifest.py --find new_gar06_park_terrain
python tools/audit_missing_models.py
python tools/rpf_index.py
python tools/extract_by_hash.py --dry
python tools/normalize_lib_index.py --dry
```

> ⚠️ 需要 `numpy`/`PIL` 的脚本用 **`python`**（系统 Python 3.12 已装）；`uv run python` 是空环境，
> 只适合不依赖第三方库的小脚本。

---

## 5. 未完成（按优先级，2026-10-29 重排）

| # | 事项 | 现状（数据） | 下一步 |
|---|---|---|---|
| **1** | `real_ytyp` 3,061 个 hash 无几何 | 真实 ytyp 定义、包里按 hash 找不到 drawable | 先抽 `.ydd`：archetype 的 +100 字段很像 `drawableDictionary`；见 §0.6 |
| **2** | 室内 319 个 hash | 146 包已解包、2,301 模型入库、79 包已摆；缺 MLO `rooms/portals` 变换 | 用 3 栋已知房子做三角验证（老阻塞） |
| 3 | 贴图"根本不是那张图" | ✅ **已彻底重做**（详见覆盖率核查 §11）：从 13 个包抽全 **57,235 个 ytd**（41.1 GB → 落盘 34,622 个），名字索引 **6,431 → 128,289**；55,608 个模型**全部**按源文件重绑（0 失败、几何 100% 一致）；贴图表按名字重建 **11,504 条**（`id = 名字排序下标`）；`.mdl` 回写 **221,494 个子网格**；审计 600 模型 / 2,416 子网格 → **绑错 0** | 残余：**2,813 个名字没有图**（占引用 2.0%），13 个包已抽完，下一步查 `appdata0_update.rpf` 与加密子包 |
| 4 | 地面贴图"无数据白" | 图内 1.84 M px（1.46%）近白，全在 **y > 3200 的地图北缘**（真实地图外） | 已确诊**不是**城区发白；要不要补由你定（`patch_ground_town_white.py`） |
| 5 | 城区"白块" | ✅ **已定位并修**：不是地面色图，是"无 albedo 材质"在 Workbench 里用默认 0.8 灰白 | v9 起材质带 `diffuse_color`（暖灰），重建后复看 |
| 6 | 水面灰板 | ✅ 已修：v9 起水材质带 `diffuse_color` + `surface_render_method='BLENDED'` | 重建后复看 |
| 7 | willard 陷地未验证 | ✅ 已数值化验证（见"本轮已做掉"）：主屋 dz −0.69 m = 正常埋深 | 无 |
| 8 | 资产快照未上传 | ✅ 已上传：`python git_assets.py save --yes` → 远程 `assets` 分支 `94c08a2`，6 个文件 57.5 MB | 换机时 `python git_assets.py load` |
| 9 | `HIDDEN_LOD` 2,187 与 HD 重叠 | 已隐藏不删 | 保持默认隐藏 + N 面板开关 |

### 本轮已做掉（别再查）

- ~~`--bbox` 未做~~：已加（按实体原点过滤，精确裁剪仍用 `crop_blend.py`）
- ~~classify 的 `ivy` 误命中 `privy`~~：正则改 `(?<![a-z])ivy|(?<![a-z])vine`
- ~~两个 z≈−1002 m 的异常对象~~：查清是 RDR2 关卡设计"停"在地图外的 4 个 `*_tempbox*` 占位盒，
  数据不改，`hide_tag='parked_offmap'` → `HIDDEN_PARKED`
- ~~blend 材质仍是旧 tid~~：根修完成——材质按**贴图名字**建（`alb_<name>`）、
  **一个子网格一个槽**（不再去重），已存盘 blend 可用 `relink_materials.py` 按槽位重挂
- ~~`index.json` key 未补零~~：`normalize_lib_index.py` + `write_model` 改 `'0x%08x'`，找回 **367** 个模型
- ~~1,782 张孤儿贴图（"白块"根因）~~：`tex/` 里有 7,074 张 PNG，`tex` 表只登记 5,292 张 →
  32.5% 子网格引用越界 tid。`register_orphan_textures.py` 按 **id** 补登记（`tex<id>` + `x:1` 标记，
  抽样像素比对 5/5 一致），**20,858 个模型 / 23,099 个实例恢复 albedo**；v9 已 `--relink` 重挂
- ~~willard 陷地未验证~~：改用 `tools/audit_ground_contact.py` 在**当前管线产物**上出数：
  willard 区 8 个建筑件中位 dz **−0.15 m**、贴地 50%，主屋 `roc_01_ext_home01` dz **−0.69 m**
  （= 文档记录的正常地基埋深 0.68 m）。旧的 `willard_full.blend` 是旧管线产物（对象全是 `e_<hash>`、
  Water 仍是 2048² 网格 4.19 M 顶点），**不作为验收对象**

---

## 6. 本轮已完成（2026-10-29，别重复）

| 项 | 结果 |
|---|---|
| ytyp 按对解析 | 1,026 个 ytyp / **96,141** 条 archetype；证明 `name == assetName`（0 条不同） |
| RPF 全量索引 | **4,021** 个 RPF（含嵌套）/ **74,449** 个 drawable 条目 / 7.1 MB TSV |
| 缺模型分类 | 51,912 hash → `lod_block` 46,532 / `real_ytyp` 3,061 / `rpf_available` 1,833 / `no_definition` 486 |
| 按 hash 抽件 | 新建 `extracthash`，抽出 6 个（缺模型里只剩 8 个没抽过） |
| 入库 | 再入库 1 个（其余 1,831 个 load 返回 None：`_vfx/_slod/_lights`，无几何） |
| index 规范化 | 3,430 个非规范 key → 全部 `0x%08x`；**找回 367 个此前查不到的模型** |
| 材质根修 | 按贴图名建材质 + 一子网格一槽（`alb_<name>`），`relink_materials` 同步改成按槽位 |
| 视口色 | 无 albedo 材质/水面/顶点色材质都设 `diffuse_color`（Workbench 不再一片白） |
| 地图外占位盒 | 4 个 `*_tempbox*` → `hide_tag='parked_offmap'` → `HIDDEN_PARKED` |
| `--bbox` | 已加（`--bbox x0,y0,x1,y1`，坐标 = RDR2 世界米） |
| 分类正则 | `privy` 不再进植被；`p_ivy_01`/`ragwort_vine` 仍进植被 |
| 重建 | `continent_v9.blend`（`--rails --full`）+ `--relink` 重挂材质（**191,158 个材质槽**）+ manifest：**对象 147,500 / ENTITIES 103,898 / 隐藏 43,599 / 待隐藏未隐藏 0 / 贴图用 6,967 / 无 albedo 17,682 → PASS** |
| 俯视验证图 | `docs/世界与地编/img/verify/v9_city.png`（水蓝、无纯白块）对照 `v8_city.png` |
| 清单收尾提速 | `tools/manifest_from_jsonl.py`：`write_manifest` 的收尾两遍扫描 20~35 分钟 → **0.5 秒** |
| **贴图彻底重做** | 抽全 57,235 个 ytd（41.1 GB）→ 名字索引 **128,289**；55,608 模型全量按源重绑；贴图表 **11,504 条**（名字排序定 id）；`.mdl` 回写 **221,494 子网格**；审计 **绑错 0**；relink 换 **191,158 个材质槽** |
| 已知坑补充 | `--only txd` 抽不到世界贴图（ytd 藏在 props 包里）；`extracthash` 遇到游戏在跑会锁包 |
| 文档 | 覆盖率核查 §10（含 §10.6 孤儿贴图）、最高原则 §6.4 两次复发 + §6.6、AGENTS §4、tools/README、本文件、README |

---

## 7. 已知坑（详见 AGENTS.md §4）

- **贴图只存 tid 不存名字 → 池子一变就串号**：现已改为按名字建材质，别再退回按 tid
- **`hex()` 不补零**（6.4 复发）：材质名、文件名、index key、对象名一律 `'0x%08x'`
- **Workbench / Solid 不看节点树**：材质必须设 `diffuse_color`，否则一律默认灰白（白块）
- 已存盘 blend 不会跟随 index 更新：重绑之后必须 relink 或重建
- 长任务别用阻塞命令；实测单步"加载+存盘"= 7~10 分钟
- 从 pwsh 直接起 python/blender → `Access is denied` / `0xc0000142` 弹窗 → 走 `tools\run.cmd`
- Blender `-b` 日志全缓冲 → 加 `--python tools/_unbuffer.py`
- 游戏运行时 rpf 被独占锁 → 抽包前先关 RDR2
- `cmd` 把 `--packs a,b,c` 的逗号当分隔符 → 用空格
- `--lib` 必须绝对路径
- `uv run python` 没有第三方库（numpy/PIL）→ 用 `python`
