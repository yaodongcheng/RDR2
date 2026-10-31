# AGENTS.md —— 在本仓库工作的行为准则（每次开工先读这一页）

> **本文件是唯一规则真身**（`Source\docs\AGENTS.md`）。
> `Source\AGENTS.md`（文本层根）与 `D:\BrainMaker\大镖客2解包分析\AGENTS.md`（D 盘工作目录）
> 都只是**几行路标**，指向这里 —— 那两份里**不许写规则**，否则必然分叉。

> 适用对象：任何在这个项目里工作的 AI（Claude / Codex / Copilot / 本地 Agent）以及人。
> 与本文件冲突的临时指令，以用户当次明确指令为准；但 §0 的提交权、§2 的长任务规范、§3 的验证规范**不得绕过**。

---

## 0. 提交权：AI **禁止**自己提交（最高优先级；用户 2026-10-29 明令）

🔴 **AI / agent 不得执行 `git add` / `git commit` / `git push` / `git commit --amend` /
`git reset` / 任何改写历史或推送到远端的命令。**

- **提交只能由用户本人手动完成**，入口是 **`git_gui.py`**（用户自己启动的图形界面）。
- AI 的活儿止于：**把文件改好 → 自测通过 → 报告「待提交文件清单 + 每个文件改了什么」**。
- 需要让用户看清楚时，只跑**只读**命令：`git status --short` / `git diff --stat` / `git log --oneline`。
- 用户明确说「你提交」时才可提交，且**一次授权只对当次改动有效**，不延用到后续。

**为什么**：2026-10-29 这一轮，agent 自作主张连推了 7 个 commit（`e0cbd34` … `cacf205`），
把代码、文档、环境修复混进历史，用户没机会在提交前逐条 review，也不好拆分回退。
提交是把改动**永久写进历史**的动作 —— 只有用户有资格决定。

> 注：`git_gui.py` 目前**不在本仓库**（`Source\tools\` 与本机都没有）。
> 这条规矩约束的是**谁来提交**，不是某个脚本是否存在；入口路径以用户当次说明为准。

---

## 1. 先读最高原则

**`docs/最高原则_单一管线与分块即裁剪.md`**（优先级高于 README 与所有专项文档）

一句话：**`continent.blend` 是唯一全集；任何区域都是它的裁剪；禁止为单个区域另写管线。**

其中 §六 是**五条绝对禁令**：

| # | 禁令 | 曾造成的后果 |
|---|---|---|
| 6.1 | 禁擅自剔除网格体 | `flat_wide(max>45)` 剔掉 31,533 个，含 45.4 m 高的火车站 → 满屏镂空 |
| 6.2 | 禁擅自改地形 | `pad_field` 压平 −1.12 m、后续拟合又顶穿公园 1.4~1.9 m |
| 6.3 | 禁靠猜测匹配贴图 | 公园草地被配成"烧焦地面" → 大片发黑 |
| 6.4 | 禁丢可读信息 | 对象名用 hash + `hex()` 不补零 → 搜不到原名、未分类 3,555 |
| 6.5 | 禁伪造环境数据 | 水面 28.5 万格 + 水位 42.75（真值 40.5）→ 卡顿 + 淹桥墩 |

**任何"看起来多余/像贴片/大概率是这张图"的判断，都不构成删改数据的理由。**

---

## 1.5 新文件放哪（2026-10-28 起，硬规矩）

🔴 **文本（文档 / 脚本）必须落在 `docs\` / `tools\`** —— 它们是指向骑砍2 mod git 仓库的 junction，
写进去 = 立刻进版本管理。**二进制（glb/blend/png/导出物）留在 D 盘原位**，不进 git。

- 写在 `Source\` 以外的东西**不会进 git**，出事就没了；
- **禁止在 D 盘根新建 `.md`**（那里只有一个 `README.md` 符号链接）；
- 新扩展名要自己在白名单 `Source\.gitignore` 里加一行 `!*.xxx`，否则收不进去。
- 📍 **文档里的 `docs/…`、`tools/…` 是相对「项目根」，不是相对当前文件**（2026-10-29 立）。
  项目根有两个等价入口，同一份文件：
  · 真身（git 仓库）= `H:\SteamLibrary\steamapps\common\Mount & Blade II Bannerlord\Modules\RDR2\Source\`
  · 入口（数据根）= `D:\BrainMaker\大镖客2解包分析\`（`docs\`、`tools\` 是指过去的 junction）
  ⇒ 在 `docs\…` 里的文档中看到 `docs/TODO.md`，仍按项目根理解，**不是** `docs/docs/TODO.md`。
  ⇒ 给**人**复制执行的命令一律写**绝对路径**（不然用户没法直接粘贴）。
- 🔴 **`glob` / `grep` 搜不到 ≠ 文件丢了**：`D:\...\docs\`、`D:\...\tools\` 是 junction，
  有的 harness 会**静默返回空**（ripgrep 默认不跟随 symlink/junction）；换成 `H:\...\Source\...`
  若不在你的 workspace 范围内，**同样会返回空**。
  ⇒ 拿到空结果的正确动作：**用 `read` 打开那个具体文件确认**，或 `dir` 列目录。
  **禁止**据此判断"文件丢了/东西没了"然后去重建、覆盖或删除（2026-10-28 另一个 agent 实测踩到）。
- 🔴🔴 **改完 `.bat` 必须确认两件事：仍是 GBK 编码 + CRLF 换行**（2026-10-28 实锤）——
  `Source\.gitattributes` 的 `-text` 只防 **git 自己**转换，**防不了编辑器保存**。
  实测有 agent 改完逻辑后，三个 bat 变成**纯 LF**（`0D 0A` 全没），而 `打开查看器.bat` 里
  有 `goto wait` / `:timeout` / `:ready` —— **纯 LF 下 goto 标签匹配是经典翻车点**。
  验收一行：`git diff` 前先确认文件里 `0d 0a` 数量 ≈ 行数、裸 `0a` = 0；
  用 PowerShell 读写这类文件必须 `[Text.Encoding]::GetEncoding(936)`，别用默认编码。
  （顺带：VS Code 里看到 `打开*.bat` 乱码是**正常**的 —— 它按 UTF-8 显示 GBK（源码实证：
  `gbk` 没有 `guessableName`、不在 `sxt` 里，所以 **VS Code 原生永远猜不出 GBK**；
  `files.encoding` 又是 `scope:6`，**按语言/按文件夹覆盖都不生效**，别浪费时间配。
  ⇒ 要看/改这些 bat，**用 Notepad++ 打开**（自动按 ANSI/GBK），保存前确认状态栏
  仍是 `ANSI` + `Windows (CR LF)`。VS Code 里只能用「Reopen with Encoding → GBK」临时看。）

完整表见 `README.md` 的「〇.1 新文档 / 新脚本放哪」。

---

## 2. 长任务执行规范（2026-10-28 事故后强制）

### 事故

`blender -b ... > log 2>&1` 一条命令阻塞执行、超时设 2 小时。
Blender 实际在 3 分钟后就被系统杀掉（内存），**但命令没返回**，
于是"以为在跑"，白白等了 30 分钟，用户还得主动来问。

### 强制规范

**凡是预计 >2 分钟的命令（Blender 构建、批量解包、全量入库），一律按下面执行：**

```bash
# 1) 后台启动，写 PID
blender ... > log 2>&1 &
PID=$!

# 2) 轮询：每 30~60 秒看进程 + 日志尾部
while kill -0 $PID 2>/dev/null; do
    sleep 60
    echo "[hb $(date +%H:%M:%S)] $(tail -1 log)"
done

# 3) 进程消失后立刻判定（不要等超时）
if grep -q "SAVED\|saved\|完成" log; then echo "OK"; else echo "FAILED —— 看日志"; fi
```

**必须做到：**

1. **有 PID**，能判断进程是否存活
2. **有心跳**（每条轮询打一行，带时间戳）
3. **失败即报**：进程消失 + 日志无成功标志 → 立刻停下来说明原因，不许继续"等待"
4. **日志用 `PYTHONUNBUFFERED=1`**，否则缓冲会让心跳看起来空白
5. Windows bash 下 **`nohup` 不可用**，用 `&` + `kill -0` 轮询
6. 单条命令超时不要设超过实际可能的 1.5 倍

### 反例（禁止）

```bash
# 禁止：一次阻塞 2 小时，失败无感知
blender -b ... > log 2>&1; echo "exit=$?"
```

### 2.6 本机是 Windows：启动子进程只能用 `tools\run.cmd`（2026-10-29 实测）

上面 §2 的 `&` / `kill -0` 是 bash 写法，在这台机器（pwsh + 沙箱）不适用。
**从 PowerShell 直接运行控制台程序并捕获它的输出**（无论是 `|`、`>` 还是 `Out-String`），
会撞两种报错，而且都不是脚本的锅：

| 现象 | 原因 |
|---|---|
| `Access is denied`（`ApplicationFailedException`） | 沙箱禁止用管道接子进程 stdout |
| 弹窗 `应用程序无法正常启动(0xc0000142)` | 同上，进程起不来时系统弹的 GUI 错误框 |

正确姿势（`cmd` 内部重定向 = 真文件句柄，不走管道）：

```powershell
# 日志、UTF-8、退出码、带空格路径，run.cmd 都替你处理好
cmd /c 'tools\run.cmd D:\BrainMaker\build_v6.log "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" -b -P tools\blender_continent.py -- --out ... --lib ... --rails --full'

# 心跳（每 30~60 s 一行，带时间戳；进程没了立刻判定，别等超时）
$log = 'D:\BrainMaker\build_v6.log'
while (Get-Process blender -ErrorAction SilentlyContinue) {
  Start-Sleep 30
  "[hb {0}] {1}" -f (Get-Date -Format HH:mm:ss), (Get-Content $log -Tail 1)
}
```

判定：日志末行 `[rc] exit=0` + 有 `SAVED` / `VERIFY ... PASS` → 成功；
日志停在半路且没有 `[rc]` 行 → 进程被杀（多半是内存），立刻停下来报原因。

### 2.7 禁止把「重建 blend」当进度条（2026-10-30 实锤，浪费约 3 小时）

重建一次 60~90 分钟，而且**只要上游（`index.json` / `tiles/`）还会变，这次重建就全废**。
2026-10-30 连续踩了三次：

| 版本 | 想验证什么 | 结果 |
|---|---|---|
| v14 | 铁路补进来了 | 建完才发现 `.yft` 从未入库、还有 1,136 个零四元数 |
| v15 | 全量合并 | 建到 40% 自己发现上面两个问题，停掉 |
| v16（第一次） | "看着齐了" | 违背本条，被用户当场指出 |

**硬规矩**：重建只允许作为**最后一步**，且必须同时满足：

1. `python tools/audit_full_extraction.py` 四列都收口（包级 0 空 / 模型级失败逐条说明 / 实例级缺模型分桶 / 变换 100%）；
2. 上游文件**冻结**：跑完审计之后 `index.json` 与 `tiles/` 不再有任何写入；
3. 明确写下"这次建的是定稿数据，之后只在它上面出图/出清单"。

**数据没定稿时想确认几何对不对，用这两个代替重建**（都只读、秒级）：

```powershell
python tools/audit_full_extraction.py        # 四列数字
blender -b -P tools/_probe_ann_mini.py -- --x 2884 --y 1348 --w 900   # 只装地形块+指定对象的小场景
```

### 2.8 版本节奏：一次只交一个版本，**最多保留 3 个**（2026-10-30 用户明令）

**事故**：一天里连出 v18 → v23 六个版本（每个 7.2~7.8 GB，合计约 **43 GB**），用户一个都没验收就被新版本顶掉。
用户原话：**"我还没验收一个版本，你居然自己擅自跑多个版本，你不知道这个很浪费存储空间和我的时间吗"**。

**硬规矩**：

1. **一次只推进一个版本**：用户在验收某个 `continent_vNN.blend` 时，不许在背后再滚新版本。
2. **磁盘上最多保留 3 个版本**（当前 + 两个可回退的旧版）。出新版后，**第 4 个及更早的删掉**
   —— 删除命令交给用户执行（见 CLAUDE.md「删除操作被权限拦截 = 交给用户」）。
3. **不要"原地覆盖"同一个版本**（2026-10-30 用户补充：覆盖错了没法回归）。重建 = **新版本号**，
   旧版留作回退，数量由第 2 条控制。
4. **新版本号只在两种情况建**：① 用户验收后要修下一处；② 用户明确要求对比版。
   用户说"先别做 vXX"之后，任何后续版本**先问**。
5. 重建前先答"这次改动能用只读方式验吗"——`_check_class_visibility.py` / `audit_full_extraction.py` /
   `manifest_from_jsonl.py` 能算的，就不要靠"再建一版看看"。
6. 重建前确认用户当前正在看哪个文件；回执写明**新版本号 + 建议保留/删除哪几个**。
7. `reclassify.py` 已关掉 `.blend1` 备份（`save_version = 0`），别再造备份文件。

---

## 3. 验证规范（不许为了"看一眼"打开 6 GB 文件）

| 禁止 | 替代 |
|---|---|
| `blender -b continent.blend -P check.py` 只查几个对象 | 构建时输出 **`manifest.json`**（对象名/hash/位置/bbox/分类/隐藏标记），之后一律读 JSON |
| 改一行代码就全量重建（25 分钟） | 先 `--only-tile wild2000_04_02`（约 3~6 分钟）验证逻辑 |
| 用"看起来正常"当验收 | 给**数字**：对象数、覆盖率、贴地率、缺失数 |

`--full` 现在会自动产出三份清单（与 blend 同目录）：

| 文件 | 内容 |
|---|---|
| `manifest_<blend名>.jsonl` | 每行一个对象：名/hash/分类/地块/hid/hide_tag/位置/世界 bbox/贴图名 |
| `manifest_<blend名>.json` | 汇总：计数、分类、材质/贴图、植被隐藏数、PASS 判定 |
| `manifest.json` | 恒定指向最新一次的汇总（小文件） |

核对**不需要开 Blender**：

```bash
uv run python tools/report_manifest.py                     # 打印上面那行数字 + 明细
uv run python tools/report_manifest.py --find new_gar06_park_terrain   # 按贴图名/对象名/hash 查
uv run python tools/report_manifest.py --class rail --limit 20
```

**每次构建结束必须打印可核对的一行：**

```
ENTITIES <n> / 13 类 <k>/13 / 植被 <n> / 缺模型 <n> / 贴图 <n> → PASS|FAIL
```

---

## 4. 已知坑（踩过的，别再踩）

| 坑 | 现象 | 对策 |
|---|---|---|
| `--lib` 传相对路径 | `bpy.data.images.load` 报 `Cannot read '.../tex/NNNN.png'` | **必须绝对路径** |
| `dump_model_lib.py` 直接重跑 | index 从 54,925 被覆盖成 10,076（它只处理 `models.json` 的 10,893 条） | 先备份 index；只能增量补，不能整体重跑 |
| `strip_vegetation` 用 `ent.objects` | 分类后对象在子集合里 → 数到 0 个 | 用 `all_objects` |
| `hex(hash)` 不补零 | `0x0777d697` → `e_777d697` | `'0x%08x'` |
| `only()` 遇到空地块 | 全部集合被隐藏 → 画面清空 | 目标地块无对象时保持原状 |
| 混合管线的产物 | `sdn_full/sdn_full2` 与 `continent` 内容不可比 | 只认 `blender_continent.py` 的产物 |
| `.bat` / 老文档是 **GBK(936)** | 按 UTF-8 读直接报 `invalid UTF-8 text`（一次性踩两个文件） | 用 `python tools/read_text.py <文件>`（自动 utf-8→gbk→big5→latin1）；PowerShell 用 `Get-Content -Encoding Default`。**不要把 .bat 转成 UTF-8**：cmd 按 936 解析批处理，转码后 echo 的中文会乱 |
| 从 pwsh 直接起 python/blender/chcp | `Access is denied`，或弹窗 `0xc0000142`，日志空白 | 一律 `cmd /c 'tools\run.cmd <日志> <程序> <参数...>'`（见 §2.6） |
| 子进程日志中文乱码 | 子进程按 GBK 写、读的时候按 UTF-8 | `tools\run.cmd` 已内置 `PYTHONIOENCODING/ PYTHONUTF8=utf-8`；自己起进程时手动设 |
| Blender 日志要等退出才刷新 | 跑 10 分钟日志还是空白的（心跳失效） | `-b` 后加 `--python tools/_unbuffer.py`，把内嵌 Python 的 stdout 改成行缓冲 |
| `strip_vegetation` 逐个删对象 | 9,676 个要 10 分钟以上（28 GB 场景里每次 remove 都触发集合维护） | 默认 `--mode hide`：移集合约 1.5 分钟，且不丢数据（最高原则 6.1）；确实要删才 `--mode delete` |
| 长时间盯着构建 | 分不清"在算"和"卡死" | `.\tools\watch_build.ps1`：给出日志行数增量/最后写入秒数/内存/CPU 累计，判定 RUNNING·BUSY·STALLED·EXITED |
| **贴图只存 tid 不存名字** | 贴图池一重建/一扩充，`s` 里的 id 全部错位 → v6 里**门被绑成草地**（`roa_clover_grass_br_01_te`）、大片发黑 | 库里/model 记录必须有**名字**；绑定一律走 `rebind_textures.py` 按名字解析，禁 fuzzy、禁按 id 索引。**2026-10-29 起构建也按名字建材质**（`alb_<贴图名>`），并改成**一个子网格一个材质槽**（不再按 tid 去重） |
| **`hex()` 不补零（6.4 复发）** | `dump_model_lib.write_model()` 用 `hex(h)` 造文件名 → index 里同时有 `0x4ac59bc` / `0x04ac59bc`；**367 个模型只有不补零的键**，构建按 `'0x%08x'` 查不到 → 算成"缺模型" | 文件名/JSON 键/对象名一律 `'0x%08x'`；已用 `tools/normalize_lib_index.py` 以磁盘 `.mdl` 为准重建过 index |
| **Workbench/Solid 不看节点树** | 材质只设了 `Principled BSDF` 的颜色，默认视图里却是**一片白**（Workbench 用 `mat.diffuse_color`，默认 0.8 灰白）→ 被误判成"城区地面发白/白块" | 每个材质都设 `mat.diffuse_color`（无 albedo → 暖灰 0.30/0.27/0.23；水面 → 蓝）+ `mat.roughness` |
| **把 LOD 合并块当缺口** | 「未命名 5 万」其实是 46,532 个 LOD 合并块（`*_lod_combine_metadata*`），磁盘上无独立资源 | 先跑 `tools/audit_missing_models.py` 分桶；`lod_block` 不计缺口、不装、不删（最高原则 §6.6） |
| **`uv run python` 没有第三方库** | 里跑 `numpy`/`PIL` 直接 `ModuleNotFoundError`（uv 起的是空环境；项目没有 pyproject） | 需要 numpy/PIL 的脚本用系统 `python`（3.12 已装）；小脚本才用 `uv run python` |
| 模型库没有 ydr 源 | 4.8 万个模型只知道 hash 和 id，无法重绑 → 44.9% 对象无 albedo | 先拿 `原型 hash → asset 名`（ymap 原型表）再抽 ydr；`export/world/continent/models.json` 是有源的那 10,893 条 |
| **`%TEMP%` 里泄漏的 `nested_*.rpf`** | 解包工具把嵌套 `.rpf` 写在系统临时目录、异常时不删 → 实测堆了 **12,004 个 / 306.8 GB**，把 **C 盘占满**；磁盘满后 `update_4.rpf` 的嵌套包**静默解包失败**（少 4,969 个 ytd，没人报错） | 跑批量解包前：`set TEMP=D:\BrainMaker\_tmp & set TMP=...`（别用 C 盘）；定期 `del %TEMP%\nested_*.rpf`；**解包日志里每个包都要看 `[done] wrote N files` 的 N 是否为 0** |
| **两个解包进程同时读一个包** | 后起的报 `The process cannot access the file ... because it is being used by another process`（`levels_7.rpf` 实测），该包静默少抽 | 解包任务**串行**：一个包抽完再抽下一个；`hashindex`（只读 TOC）可以和别的并存，`extract` 不行 |
| **`extract_textures_from_game --only txd`** | 只下钻名字带 `txd` 的嵌套包 → **世界贴图大量在 `props/p_xxx.rpf` 里**，导致贴图名覆盖率只有 54%（36.2% 引用查不到图） | 要全量就用 `tools/extract_ytd_all.py`（`extract --recurse`，不看包名）；按包名过滤只适合"只要 gtxd"的场合 |
| **`.ydd` 里的子 drawable 用自己的 hash** | `real_ytyp` 3,061 个"按 hash 找不到 .ydr"其实是压在字典里；字典文件 hash ≠ 子 drawable hash | 先用 `tools/ydd_index.py` 建"子 hash → (文件, 偏移)"，再 `tools/ingest_ydd_models.py` 取；别再用"按 hash 找 ydr"判"模型不存在" |
| **PowerShell 变量名大小写不敏感** | `$T`（路径）与 `$t`（文件内容）是**同一个变量** → 读文件后路径被内容覆盖，`WriteAllText` 报"路径中具有非法字符"或直接写错文件 | 路径用 `$path`、内容用 `$text`；写文件一律 `[System.IO.File]::WriteAllText($path, $text, UTF8NoBOM)` |
| **`.mdl` 的 MAGIC 是 8 字节** | 写成 `buf[:8] != b'RMDL1'`（5 字节）**永远成立** → 补 tid 的脚本静默跳过 **55,608 个 .mdl**，还打印"成功 0 个" | `MAGIC = b'RMDL1' + bytes(3)`；改 `.mdl` 的脚本都必须先断言 `head[:8] == MAGIC` 并统计**实际写入数** |
| **贴图表换了文件路径后不刷新图片** | 贴图表整表重建后，同名材质仍指向旧文件（`tex/0352.png`）→ 看着"改了却没变" | `relink_materials.py` 的 `make_material` 必须 `_set_image()` **比对路径并重载**，不能"材质名已存在就直接返回" |
| **`manifest_from_jsonl.main()` 被程序内调用** | 传参报 `main() takes 0 positional arguments but 1 was given` → 回退到 Blender 内慢速汇总（20~35 分钟） | 入口统一 `def main(argv=None): ap.parse_args(argv)` |
| **`st`（槽位法线/高光）只活在 `index.json`** | `normalize_lib_index.py` / `rebind_textures.py` / `rebind_models_from_sources.py` / `fix_ydd_textures.py` 都按磁盘 `.mdl` 或旧 `s` 重建 `s`，**会把 `models[h].st` 丢掉** → 重建出来的 blend 又退回"只有漫反射"，而且**没有任何报错** | 跑完这几个工具后必须再跑 `python tools/extract_slot_textures.py --stage bind && --stage apply`（它按 `s` 重算 `st`），再用 `tools/audit_three_maps.py` 看覆盖是不是还 >90% |
| **`bsdf.inputs` 里没有 `'Red'`** | 写 ORM 时 `if kr in bsdf.inputs`（kr='Red'）恒 False → 分离节点的 Color 接上了、Metallic/Roughness 没接，肉眼只看到"粗糙度没变化" | 判 `'Metallic' in bsdf.inputs`。已在 `tools/mat_rdr2.py` 注释里标注 |
| **cmd 把逗号当分隔符（第 N 次）** | `--at 2560,-1450` 传到 argparse 只剩 `2560` → `unrecognized arguments: -1450` | 参数拆成 `--x 2560 --y=-1450`，别拼 `x,y` |
| **直接双击 `.blend` 打开 = 看到全开的 LOD/地形块/植被** | "默认隐藏"**不在 blend 里**，在启动器调用的 `tools/blender_autoload.py`。绕过它直接打开 → 满屏白色 LOD 地形 + 褐色浮岛 | 验收一律用 **`打开大陆_流畅.bat`**（自动挑最新的 `continent_v*.blend` 并执行 autoload）。2026-10-30 用户在 v16 上踩到这条；当天已把"启动器到底藏不藏得住"的五层根因全部修掉（见交接 §16） |
| **分类集合名不能盲切**（`split('_', 2)`） | `C_terrain_cell_地形块` 被切成 key=`terrain` → `cat_show('terrain_cell')` 找不到、`DEFAULT_HIDDEN` 判定永不成立 ⇒ **"地形块"这一类从来没被隐藏**（旧版靠中文名 `'地形块'` 匹配才碰巧躲过） | 解析统一走 `blender_tour._parse_cat()`（已知类名最长前缀匹配）；类名表唯一一份在 `tools/class_registry.py` |
| **Collection.hide_viewport ≠ LayerCollection.hide_viewport** | 数据层关了、视层"眼睛"还开着 → 清单写"已隐藏"、画面仍可见 | 两套一起设：`tour._set_eye()`、`cat_show()`、`classify_entities` 默认隐藏都已统一；验收用 `tools/_check_class_visibility.py` |
| **`show_all()` / `full()` / `only()` 会把默认隐藏类放出来** | 每次"全图/恢复"都把远景碎片、地形块一起打开 | 统一按 `DEFAULT_HIDDEN` 走 `apply_defaults()`（面板「全图」已改）；`only()` 跳过默认隐藏类 |
| **`-b` 测不出启动器画面** | `blender -b` 没有视口 → autoload 走"保持文件保存态"分支；拿 `-b` 截图当证据会判错（2026-10-29 踩过） | 启动器行为只认 **GUI 双击 bat**；`-b` 只能证明文件保存态 |

---

## 5. 交付前自检（缺一不可）

- [ ] 构建命令带 `--full`（几何 → 分类 → 植被处理 → 地形 patch 隐藏 → manifest → 校验）
- [ ] 日志有 `SAVED` 与 `VERIFY ... → PASS`
- [ ] 用 manifest 出数字（`uv run python tools/report_manifest.py`），不靠肉眼
- [ ] 植被默认是 **隐藏**（`--veg hide`），不是删；要删必须显式 `--veg delete` 并说明理由
- [ ] 改动若涉及数据取舍，已在最高原则 §六 记录
- [ ] 产物路径与 `deliverable/` 约定一致
- [ ] **重建前上游已冻结**（§2.7）：`audit_full_extraction.py` 四列收口，且 `index.json` / `tiles/` 自审计后**没有任何写入**（用文件 `LastWriteTime` 证明，构建开始时间必须晚于最后一次写入）
- [ ] **没有自己提交**（§0）：改动留在工作区，输出「待提交清单（`git status --short`）+ 每项说明」交给用户，由他用 `git_gui.py` 提交
