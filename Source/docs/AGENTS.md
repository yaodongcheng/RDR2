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

## 0.1 资产早已解包完 —— 缺模型 = **未入库 / 未构建**，禁止提议重新从 RPF 抽取（用户 2026-11-05 第三次纠正）

🔴 **`D:\BrainMaker\大镖客2解包分析\raw\all_packs\<包名>\` 是全量解包产物**（约 45 GB / 4,021 个包），
`.ydr` 按**资产名**平铺在里面。实测：307 个「模型库缺失的 LOD 模型」，**307 / 307 都在 raw 里**。

**「模型缺失」只有两种含义，两种都不需要重抽**：

| 现象 | 真实含义 | 正确处置 |
|---|---|---|
| `assets/lib_native/index.json` 查不到 | **未入库** | `tools/add_missing_models.py --apply`（读 raw，增量合并 index，不覆盖已有条目） |
| `continent_v23.blend` / 场景里没有 | **没被构建**（构建时模型库没有 ⇒ `models.get()` 返回空 ⇒ 静默 `continue`） | 先解决「未入库」，再决定要不要重建 |

**强制前置检查**（下任何「缺模型」结论前必跑）：

```python
h = joaat('<资产名>')
any(joaat(os.path.splitext(os.path.basename(p))[0]) == h
    for p in glob.glob(r'D:/BrainMaker/大镖客2解包分析/raw/all_packs/*/*.ydr'))
```

- 命中 ⇒ **入库/构建**问题，别提抽取；
- 未命中 ⇒ 才谈从 RPF 抽，且**先问用户**。

**同类陷阱**：`add_missing_models.py` 的 `SKIP` 正则里带着 `slod|_lod|shadow|reflection|prox`，
它**故意不补** LOD/代理类模型（当初的目的是只补"可见"模型）。所以「LOD 模型缺失」≠「数据没解包」，
正确动作是**给它加 `--include-lod` 再跑**。

🔴 **补之前先验 shader**：`export_sdn_gltf.load_model()` 对「所有 geom 的 shader 都是 `default`」的模型
**故意返回 None**（占位/代理网格，游戏自己也不渲染）。实测 2026-11-05：安尼斯堡「缺模型的 307 个 LOD」
**307/307 全是 `default` 占位** ⇒ 真模型的 LOD 一个不缺，**没有要补的东西**。
判据：`Y.parse_shader_hashes` 取出该 ydr 的 shader 名，全等于 `default` 就是占位。
`add_missing_models.py --apply` 对这类是 0 新增（实测 index.json 内容逐字段不变）。

**为什么写死这条**：同一天里我（AI）三次提议「重新从 RPF 抽取」，每次都是重复劳动，用户每次都纠正过。
第三次被当面点出来后立此条。

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

### 1.6 脚本归口、命名与清理（2026-10-31 立）

**起因**：2026-10-31 在 `D:\BrainMaker\` 根发现 **7 个一次性 `.py`**（10-30 19:42 ~ 10-31 07:26 建，全是铁路/可见性验收的临时脚本）—— 违反「文本只进 `docs/` `tools/`」，而且没人知道哪些能删。已全部归口到 `tools/`。

| 规则 | 内容 |
|---|---|
| **只放一处** | **管线/正式脚本**只放 `Source\tools\`（`D:\BrainMaker\大镖客2解包分析\tools\` 是 junction，等价）。**禁止**在 `D:\BrainMaker\` 根、`大镖客2解包分析\` 根、`work\`、`docs\`、`plans\` 下新建脚本。⚠️ **例外 = 本轮一次性探针脚本**：它与同轮产物一起放 `_scratch\<主题>\`（见下面「输出目录」），不进 `tools\` |
| **前缀 = 类别** | 无前缀 = 管线正式步骤（进 `tools/README.md` 主表）· `_check_*` = 只读体检/断言（任意 blend 可跑，打印判定）· `_probe_*` = 一次性探针/渲图（出证据用，不进管线） |
| **必须登记** | 新脚本必须往 `tools/README.md` 加一行：用途 / 输入 / 输出 / 类别。**没登记 = 下轮清理时删** |
| **一轮内收口** | `_probe_*` 在本轮结束前二选一：**删**，或**转正**（保留 + 登记 + docstring 写明对应交接章节）。D 盘根不留任何 `.py` |
| **输出目录** | 🔴 **探针产物一律放项目自己的 `D:\BrainMaker\大镖客2解包分析\_scratch\<主题>\`**（2026-11-01 用户裁定：`D:\BrainMaker\` 是**多项目共用根**，RDR2 的东西放它自己的目录里；「跑完就删」不等于「可以乱放」）。历史目录 `_railcheck/` / `_test/` 只读保留；**已登记的 7 个证据脚本沿用 `_railcheck/`**（交接 §16.6 引用了那批图），不再新建同级目录。~~旧写法 `D:\BrainMaker\_probe\<主题>\`~~ 已**废止并搬迁**（2026-11-01 收归）：历史内容在 `大镖客2解包分析\_scratch\_probe_legacy\`，根上已无 `_probe\` |
| **路径写法** | `sys.path` 用 `os.path.dirname(os.path.abspath(__file__))`；数据根用常量 `ROOT = r'D:/BrainMaker/大镖客2解包分析'`（既有约定），不写散落绝对路径 |
| **交付前** | `python -m py_compile <文件>` 过；`_check_*` 至少能在一个指定 blend（或 `--factory-startup`）上跑通并打印判定 |

> 已归口的 7 个（2026-10-30/31，登记表见 `tools/README.md`「验收渲染 / 可见性检查」）：
> `_check_tour_behavior.py` · `_check_tour_vis_unit.py` · `_probe_rail_wide.py` · `_probe_rail_close.py` ·
> `_probe_rail_ties.py` · `_probe_rail_r02.py` · `_probe_blend_ab.py`。

### 1.7 bat 脚本改动纪律（2026-10-31 立；同一天交付闪退 3 次）

🔴 **铁律：任何 `.bat` 改完，必须过 `python tools/_check_bat.py --bat "<绝对路径>" --dryrun`，PASS 才能交给用户。** 不许“改完就让人双击试试”。

同一天踩过的坑（都是通用知识，不是运气）：

| 坑 | 症状 |
|---|---|
| echo 文本里有未转义的 `<` `>` | `<路径.blend>` 被当输入重定向 → “命令语法不正确” → **批处理中止**，窗口闪退 |
| 未加引号的 `%~f0` / `%~dp0` | 路径含 `Mount & Blade` 的 `&` 裂行；日志截断、批处理岔路 |
| 普通 `dir` 行写 `2^>nul` | 报错不被抑制，满屏“找不到文件/路径” |
| `for /f` 里的 `dir` 写 `2>nul` | 反了：命令串里必须 `2^>nul` |
| `exit` 前没有 `pause` | 双击窗口直接关，用户看不到报错 |
| 成功路径没有 `pause` | `start` 之后批处理结束，窗口照样关 |
| 编码/换行不对 | 必须 **GBK + CRLF**；裸 LF 会让 `goto` 标签失效 |

`tools/_check_bat.py` 做两件事：① 静态规则逐条扫（上面每一条）② **干跑**——把 `start` 换成 echo、`pause` 换成 echo，带 `list / 19 / 99` 三种参数跑一遍，确认能解析到目标、错误分支有提示、不中途语法错。

### 1.8 分类规则唯一入口：`docs/格式与资产/分类体系与判定规则.md`

**改任何分类前先读它**（23 类 / 默认隐藏表 / 判定顺序 / 名字·几何·贴图三种来源 / 纠错清单语义 / 已验证的坑 / 标准改法）。**规则值唯一真身 = `tools/class_rules.py`**；`classify_entities.py` 只是 Blender 驱动、`class_registry.py` 只是转出口，`veg_rules.py` 放植被词表。改完跑 `python tools/_check_rules.py`（合法性 + 冗余 + `tools/rules_cases.csv` 用例回归）。

### 1.9 D:\BrainMaker 目录纪律（2026-10-31 立；起因：区域裁剪产物散到根目录被用户抓包）

| 规则 | 内容 |
|---|---|
| **根目录零文件** | `D:\BrainMaker\` **根下只允许既有的一级目录**，禁止放任何文件（脚本 / JSON / 图 / 日志 / bat）；违者一律算未归口 |
| 🔴 **RDR2 的东西只进 RDR2 的目录** | `D:\BrainMaker\` 是**多项目共用根**（还有仁王 / 势力 / video_gen …）。本项目的一切新产物（探针脚本、截图、临时 blend、manifest）放 **`D:\BrainMaker\大镖客2解包分析\_scratch\<主题>\`**，**不许**在共用根新建 `_probe\` 之类的目录（2026-11-01 用户裁定） |
| **区域裁剪固定一处** | `D:\BrainMaker\大镖客2解包分析\deliverable\blender\regions\` **只放区域 blend**（`<编号>_<tile>.blend`，与 `sdn_full2/`、`guarma/`、`willard/` 同规矩，本质就是大陆各区域的裁剪）；验证内容（manifest / 俯视图 / 图例 / `region_corrections.csv`）放同级 **`regions_support/`**（对应 `sdn_support/` 的先例） |
| **新建目录先问** | 任何新目录（包括 `%PROJ%` 下的子目录）先问用户；工具默认输出路径必须指向**已批准目录**，不许用 `%PROJ%\..` 之类的上跳路径 |
| **一次性文件即用即删** | 临时 bat / dump / 探针 JSON 用完删除，不留在 `_logs` 或数据根 |

**2026-11-01 收归后的现状**（`D:\BrainMaker\` 根已无任何 RDR2 目录/文件）：

| 旧位置（根） | 现在 |
|---|---|
| `D:\BrainMaker\_logs\`（4,742 个日志 + 根上的 `build_v1*.log` / `reclass_v17.log`） | `大镖客2解包分析\_logs\` |
| `_tmp\`（`nested_*.rpf` 解包临时区，15 GB） | `大镖客2解包分析\_tmp\`（`set TEMP` 的写法已同步） |
| `_probe\` / `_test\` / `_railcheck\` / `_tmp_itemtex\` / `tmp_rdr_probe\` | `大镖客2解包分析\_scratch\` 下的同名目录（`_probe` → `_probe_legacy`） |

> 根上剩下的 `.claude` / `.codex` / `tools`（Ghidra + JDK + SW2 逆向工具）/ `仁王…` / `势力` 等 = **其他项目或跨项目工具**，不属 RDR2，别动。

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
| 🔴 **目录联接 ≠ 第二份副本**（2026-11-01 实锤） | 判 `raw/models` 与 `export/models` "内容 100% 相同" → 删了 `raw/models`，结果 `export/models` 是**指向它的 junction**，当场悬空，15 个脚本静默拿到空池 | **比对/删除任何目录前先 `Get-Item -Force \| fl LinkType,Target`**；`STRUCTURE.md` §三有全部联接清单（`export/models → raw/models`、`export/levels/collision → raw/collision`、`work → raw` …）。联接的"内容相同"是定义使然，不构成重复证据 |
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
| **`%TEMP%` 里泄漏的 `nested_*.rpf`** | 解包工具把嵌套 `.rpf` 写在系统临时目录、异常时不删 → 实测堆了 **12,004 个 / 306.8 GB**，把 **C 盘占满**；磁盘满后 `update_4.rpf` 的嵌套包**静默解包失败**（少 4,969 个 ytd，没人报错） | 跑批量解包前：`set TEMP=D:\BrainMaker\大镖客2解包分析\_tmp & set TMP=...`（别用 C 盘）；定期 `del %TEMP%\nested_*.rpf`；**解包日志里每个包都要看 `[done] wrote N files` 的 N 是否为 0** |
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
| 🔴 **类名互为子串 → `cat_show` 打错目标**（2026-11-04 实锤） | 老代码 `if key in k` 与全等判据挤在一条 if 里、遍历到谁算谁：`cat_show('lod', False)` 命中的是 **terrain_lod**、`cat_show('decal', False)` 命中 **rail_decal** ⇒ 真正的 `lod`(40) / `decal`(88) 在 `show_all()` 之后**再也没被关掉**。用户看到的正是「面板显示隐藏、画面里还在」，**手点两下按钮才对**（面板自己走精确集合名） | `cat_show` 改成两轮：先全等（key / 中文名 / 集合名），全不中才允许片段。回归用例在 `tools/_check_tour_vis_unit.py`（合成场景里放了 `lod`/`lod_out`/`terrain_lod`、`decal`/`rail_decal` 三组碰撞） |
| **Collection.hide_viewport ≠ LayerCollection.hide_viewport** | 数据层关了、视层"眼睛"还开着 → 清单写"已隐藏"、画面仍可见 | 两套一起设：`tour._set_eye()`、`cat_show()`、`classify_entities` 默认隐藏都已统一；验收用 `tools/_check_class_visibility.py` |
| **`show_all()` / `full()` / `only()` 会把默认隐藏类放出来** | 每次"全图/恢复"都把远景碎片、地形块一起打开 | 统一按 `DEFAULT_HIDDEN` 走 `apply_defaults()`（面板「全图」已改）；`only()` 跳过默认隐藏类 |
| **`-b` 测不出启动器画面** | `blender -b` 没有视口 → autoload 走"保持文件保存态"分支；拿 `-b` 截图当证据会判错（2026-10-29 踩过） | 启动器行为只认 **GUI 双击 bat**；`-b` 只能证明文件保存态 |
| 🔴 **工具搬进仓库后 ROOT 指错，静默烂掉**（2026-11-04） | `audit_interior_placement.py` 按"文件住在数据工程 tools/ 下"算 `ROOT`，搬进 `Source/tools` 后 `assets/lib_native` 直接找不到 —— 一跑就 `FileNotFoundError`，而没人跑它就没人知道 | 要读数据工程的脚本统一 `ROOT = os.environ.get('RDR2_ROOT') or r'D:/BrainMaker/大镖客2解包分析'`（`scene_terrain.py` / `scene_interiors.py` 都这么写）；**改完必须真跑一遍**，编译通过不算 |
| 🔴 **收尾步骤重存盘 = 悄悄改掉压缩设置**（2026-11-04） | `scene_trim` 存的是 zstd 压缩包（187 MB），新加的 `scene_interiors` 用 `save_as_mainfile(compress=False)` 又存了一次 → **922 MB**，被当成"室内要 5 倍体积"查了半天 | 任何在别人存盘之后再存的脚本一律 **`compress=True`**；判据 = 文件头：`BLENDER1` 开头 = 未压缩，`28 B5 2F FD`（zstd）= 压缩。**比体积前先看这个**，否则比的是两种格式 |

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

---

## 6. 场景地形（58 张）—— 2026-11-04 教训，别再重犯

工具链（三个文件，输出 `deliverable/blender/scenes/`）：

| 文件 | 作用 |
|---|---|
| `tools/scene_terrain.py` | 场景地形：`deliverable/terrain/final` 高度 + 彩图，结构 = 活动区一块 + 远景四条带 |
| `tools/scene_interiors.py` | 场景**室内**：按 MLO 实例变换把 `*_int` 包摆进已经 trim 过的场景（`--no-interiors` 可关）；必须在 trim 之后跑 |
| `tools/scene_trim.py` | 两层裁剪 + 默认隐藏复原 + 平移（场景中心→原点） |
| `tools/build_scenes.py` | 批量驱动（断点续跑、每张验收"0 超界"、一次只跑一个 Blender） |

打开场景：**复用 `launchers/打开大陆_流畅.bat`**，直接敲 id 即可
（`打开大陆_流畅.bat bla` → `deliverable/blender/scenes/bla.blend`；**禁止另造启动 bat**）。

### 6.1 地形采样必须与 `continent_v23` 同算法（三条，缺一处就错 2~3 m）

实测基准：`continent_v23.blend` = **H4 + 全球 4 m 格点 + 最近邻**（构建命令没有 `--step`）。

1. **行索引差一格**：交付物高度图与 H4 的最佳对齐是 `dy = -1`
   （实测 shift(0,-1) 中位差 **0.014 m**；shift(0,0) 中位差 **0.678 m**）。
   公式：`fy = (y1 - y)/hres - 1`。
2. **顶点必须吸附全局格点**：`xs = arange(floor(x0/step)*step, ...)`。
   从矩形左下角起算会落在半格上，断崖处直接采到另一侧。
3. **最近邻，不要双线性**：大陆就是 `H[r, c]` 直接取格点；
   双线性会把 42.75 和 45.92 抹成 44.8，房子被埋。

**回归用例（黑水镇贫民屋，务必逐点核对）**：

| 世界坐标 | 正确值（H4 / 大陆） |
|---|---:|
| (-798.8, -1411) | **42.75** |
| (-804, -1412) | **42.75** |
| (-802, -1413) | **45.92** |

这三条错在一起时，**平地上完全看不出来**，只有断崖/陡坡才显形 —— 验收必须挑断崖点。

### 6.2 基准别选错

- **`continent_v23.blend` = 权威**（4 m 原生）；
- `regions/18_*.blend` 是 **8 m**（`--step 8` 是 2026-10-31 给分区瘦身用的参数，git `b9f3482` 可查，
  **从来不是精度标准**），拿它当标尺会得出"4 m 不如 8 m"的错误结论。

### 6.3 排查方法论（这次绕了三圈的教训）

- **先隔离，再归因**：地形-only 渲染（只留 `Terrain*`）证明"黑块/凸起在地形上"；
  `scene.ray_cast` 沿相机像素取物体名，证明"不是那个对象"。
  这次先后误判过 slod4 对象、贴花、湖底，全是没做隔离就下结论。
- **同一世界坐标 + 同一测量方法**再比较：场景已平移（局部 = 世界 − 中心），
  直接拿世界坐标去戳场景顶点会得到"最近顶点在 946 m 外"这种假结果。
- **观感差异要落到数值**：不要用"看着不一样"当证据，也不要拿"顶点间距 4 m"就宣布没问题
  （还要看：值、格点对齐、平滑着色、渲染隔离）。

### 6.4 禁止事项（用户明令）

- **禁止调整地形高度**：PAD、压平、抬升、平滑一律不许（PAD 实测让陷进去的建筑从 15 个变 40 个）；
  地形只做"忠实采样"，一旦需要"修地形"就是方案错了。
- **禁止自造启动 bat**：复用 `打开大陆_流畅.bat`（已支持场景 id）。
- **禁止擅自删对象**（"看起来不需要"的也不行）；分类器与 `DEFAULT_HIDDEN` 是唯一口径
  （`decal` 例外：启动器会额外关掉，场景 blend 里也要关）。

### 6.5 Blender 操作坑（这次踩全了）

- **脚本报错时 Blender 退出码仍是 0**：必须 grep 日志里的 `Traceback`，否则会把半成品当成功。
- **后台任务要等完成通知再读产物**：抢跑读到的是上一版文件（这次连犯三次）。
- **UV 按 loop 存**（`uv_layers.data[loop_index]`），按顶点索引写会渲染成棋盘格。
- **共享网格裁剪前先 `o.data = o.data.copy()`**，否则同模型所有实例一起被改。
- **隐藏集合里的 `matrix_world` 不可靠**：无父级对象用 `matrix_basis`。
- **`write_manifest` 会把所有集合全开**（为求矩阵），跑完必须复原默认隐藏（`restore_hidden_classes()`）。
- 🔴 **`blender_autoload.py` 打开时会 `show_all()`**（全图模式）：**集合级的隐藏会被冲掉**。
  凡"打开后必须保持隐藏"的对象（如活动区内的远景碎片），必须**对象级**再藏一次
  （`o.hide_set(True)` + `o.hide_render = True`）——`show_all` 只改集合开关，不动对象级。
  实测：只做集合级时，打开后 657 个 lod 全可视（其中 40 个顶点落在活动区）；改对象级后 617 可见、落在活动区 **0**。

### 6.6 机器闸门（规则不靠自觉）

| 件 | 作用 |
|---|---|
| `tools/scene_terrain_core.py` | **采样口径的唯一实现**（纯 Python，无 bpy）：`load_meta / heights / sample_h / axis / uv_of` |
| `tools/scene_terrain.py` | 只从 core **转出**再建网格 —— **禁止在本文件另写采样逻辑**（分叉 = 检查失效） |
| `tools/check_scene_terrain.py` | 离线自检：3 个断崖回归点对 H4 + 网格吸附 + **贴图 UV 朝向往返比对** + **三条负面测试**（"行偏移不修正""半格偏移""V 翻转"必须被抓到，证明检查有分辨力） |
| `tools/build_scenes.py` | 批量开跑**前先调自检**，不过就 `return 4` 停止，一张都不跑 |
| `tools/_check_tour_vis_unit.py` | **分类开关/可见性的合成单测**（Blender，2 秒）：类名解析、`show_all` / `apply_defaults` / `cat_show` **精确匹配** / `only` / `full`。**改过 `blender_tour` / `class_rules` / `rdr2_cat_ui` / `blender_autoload` 必跑** —— 2026-11-04 发现它缺 `terrain_lod`/`road` 一直 FAIL，因为没人跑（闸门不接进流程 = 没有闸门） |
| `tools/_check_scene_trim_clip.py` | **远景框裁剪合成单测**（Blender，2 秒）：matrix 口径 / clear 侧 / 镜像 / 包围盒高估 A~G 七条 + 负面测试。**改过 `scene_trim` 必跑**，已接进 `build_scenes.py`（不过就 `return 4`，一张都不跑） |
| `tools/export_scene_terrain_maps.py` | **每场景地形交付物**（TODO-2）：16 bit 高度图（4 m/px · 行 0 = 北）+ 全 255 材质 mask + JSON 元数据；采样与 blend 共用 `scene_terrain_core`，自检 ±0.05 m。已接进 `build_scenes.py`（导出失败/自检不过就停批） |

复现：

```powershell
Set-Location "H:\SteamLibrary\steamapps\common\Mount & Blade II Bannerlord\Modules\RDR2\Source"
python -X utf8 tools\check_scene_terrain.py -v
& "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" -b --factory-startup -P tools\_check_tour_vis_unit.py
```

预期：前一条末尾 `[check] 结论：PASS` 且三条负面测试都"被抓到"；后一条末尾 `=== UNIT OK ===`
（⚠️ Blender 的 Python 异常**退出码也是 0**，只认这行文字）。

### 6.7 地形贴图 UV 的 V 轴：**必须随 y 增大，禁止写 `1 - (...)`**（2026-11-04 实锤）

**症状**：黑水镇 bla.blend 正交顶视下，彩图里的**街道/黑条整体跑到建筑群南边约 250 m**，
用户第一眼判断是"地面 UV 整体系向南偏移"。南北方向像平移，其实是**整张贴图上下镜像**。

**根因**：贴图 PNG 是**行 0 = 北**，而 Blender 的 `v=0` 在**图像底边**（南）
⇒ 北 = 图顶 = `v=1`，正确公式是 `v = (y - fy0) / (fy1 - fy0)`。
`scene_terrain.py` 写成了 `v = 1 - (y - fy0) / span`，整张图南北翻。
`blender_continent.terrain()` 用的是正确写法（`V = (Y - Y0)/W`）——
**所以 region 18 一直是对的、场景 blend 一直是错的**，两套构建器口径不一致才是根子。

**实测证据（bla.blend 自身）**：局部 (82, 123)（= 世界 −800, −1316）UV **V = 0.4657**；
同列北端 (82, 512) `V=0.3571` < 南端 (82, −513) `V=0.6431` —— V 随 y **递减**，铁证。

**为什么之前的检查没抓到**：只验了"UV 与裁剪公式一致"（拿同一个错公式当标尺），
从没验"UV 取到的颜色 = 该世界坐标的颜色"。⇒ 判据必须能分辨两种朝向：
`check_scene_terrain.py` 的 UV 检查就是**世界→像素** 与 **世界→UV→按 Blender 规则取图**
两条路往返比对（32×32 点，正确时逐点相等），并把 V 翻转当负面测试（实测超差 92.8%）。

**修法**：V 口径只留一份实现 = `scene_terrain_core.uv_of()`；`scene_terrain._grid` 只调它。

**已受影响的产物**：`bla.blend`、`sod.blend`（都是这个脚本建的）⇒ 修完必须**重跑**这两张；
其余 55 张未建的不受影响。

### 6.8 场景室内（MLO）与野地规则（2026-11-04 黑水镇实拍验收通过）

**数据链路**：`levels/rdr3/interiors/<pkg>_int.rpf` → `raw/all_packs/<pkg>/<pkg>.ytyp`
（件是**室内局部坐标**）+ area ymap 里的 `<pkg>` MLO 实例（pos + quat）⇒ `world = P + q·local`。
与 `merge_interior_into_willard.py` / `instantiate_interiors.py` 同一套口径。

| 件 | 作用 |
|---|---|
| `tools/audit_interior_placement.py` | 审计每个 `*_int` 包：室内 bbox 是否被某栋建筑包住 → `export/world/interior_placement_audit.json`（`inside` / `host` / `gaps` / `items`）。全量 278 包 **30 s**（names.txt 与 90 个 tile json 已缓存） |
| `tools/scene_interiors.py` | 场景收尾：把 `inside=True` 且 MLO 落在活动区的包摆进 blend，集合 `ENTITIES/C_int_室内/int\|<地块>`，对象带 `int_pkg` |

**四条硬口径**

1. **只在 `scene_trim` 之后摆** —— 提前摆会被 trim 的"圈内非远景碎片"规则当垃圾删掉；
   且 trim 已完成平移，`scene_interiors` 直接按局部坐标（世界 − 场景中心）落位。
2. **宿主判据不能只看"名字前缀 + 最近"**（旧版就这么错：银行配到 `_em` 发光片、剧院配到贴花）。
   现在三档：真包住（间隙 ≥0）→ 容差内（≥ -1.5）→ 最不偏；并硬性排除 **LOD 合并块**（`_slod/_lod`）
   与 `_em/_decal/_dec/_d/_det` 附属件（名字质量降档）。`inside=True` 179/251。
3. **野地场景里，城整座用远景碎片（lod）表示**（用户裁定）：
   · `build_entities(town_rects=…)` —— 落在**据点活动区**内的非 lod 实体**不建**（日志 `据点内降 lod N`）；
   · `trim_current_scene(town_zones=…)` —— 这些范围内的 lod **不能留在活动区**（`C_lod_*` 整类默认隐藏，
     城里会空无一物），要归到可见的 `C_lod_out_远景碎片·区外`；
   · 野地**不放室内**（`scene_interiors` 直接跳过非 settlement 场景；实测不挡的话 wild_04 会多 43 套 / 6465 件）。
4. **体积**：黑水镇 **+46 MB（187.5 → 233.9 MB，压缩后）**，+1789 件 / +217 万顶点。
   🔴 **别拿"未压缩 vs 压缩"两个数比大小**：`scene_trim` 存的是 zstd 压缩包（`BLENDER1` vs zstd 魔数可查），
   而 `scene_interiors` 第一版写了 `save_as_mainfile(compress=False)`，把 187 MB 直接摊成 922 MB ——
   一度以为室内要 5 倍体积。**任何在收尾步骤里重新存盘的脚本，必须 `compress=True`**。
   `blender_continent --no-interiors` 可关。
   批量会把它写进 `scene_build_status.csv` 的 `rooms` 列（`包数/件数`）。

**验收**：日志里 `[int] 室内：N 个包 / M 个对象`；地图页 `regions_viewer.html` 点据点看紫方块。

### 6.9 远景框裁剪：三条错叠在一起 = "日志说裁了、物体还在框外"（2026-11-04 圣丹尼斯）

**症状**：`build_scenes.py --only sdn` 验收报「1 个对象超出远景框」，但日志写着
「按远景框裁掉超界几何：1 个对象」——看起来裁过了，实际几何原封不动。

**根因（三条独立错误，缺一条都不会暴露）**

1. **矩阵口径不一致**：`clip_to_rect` 用 `o.matrix_world` 定位切平面，而新建对象在
   depsgraph 跑之前 `matrix_world` 还是**单位阵**（`bb_of` 早就写明：无父级必须用
   `matrix_basis`）⇒ 切平面落到别处，一刀没切却照样 `clipped += 1`。
2. **clear 语义用反**：`bmesh.ops.bisect_plane` 的 `clear_outer` 删**法线所指**那一侧、
   `clear_inner` 删**反向**那一侧（合成实验实测：立方体 x[4,6]、切面 x=5、法线 +X，
   `clear_outer=True` 剩 x[4,5]）。外框四条边法线朝框内 ⇒ 旧代码删的是**框内**。
   附带：活动区挖空那组两个标志都是 False = 只切不删（空转），且顺序切四刀也不是挖洞
   （会删掉"任一半空间之外"的全部几何 = 整块删光）⇒ 该参数已删除。
3. **法线变换方向反了**：切平面要的是**世界→局部** `n_l = Mᵀ·n_w`（由
   `n_w·(M·p_l + t − c_w)=0` 推得），旧代码写的是 `(M⁻¹)ᵀ` —— 那是**局部→世界**。
   不旋转的物体两者恰好相同（所以早期单测全过、`bla`/`wild_10` 也没暴露），
   一旋转就切到错误方向（实测 `cor_derricks_slod_09` 绕 Z 转 15°：算出的局部法线
   y 分量符号相反，一刀切下去整块几何从"没动"变成"全删"）。
4. **包围盒高估**：`bound_box` 是**局部轴对齐**盒，乘上带旋转的矩阵后 8 个角点会比真实
   顶点范围大。实测 `cor_es_pipes_slod` 顶点 x≥511.2（在框内），角点报 498.2（越界 8 m）
   ⇒ manifest / 验收假报超界。

另外：**裁剪判定前必须先 `view_layer.update()`** —— 新建对象的 `bound_box` 未求值时是
默认 ±1 的盒，会被误判「在框内」整块跳过裁剪（实测 `cor_derricks_slod_09` 漏了 7876 个顶点）。

**修法（已落地）**

| 位置 | 怎么改 |
|---|---|
| `clip_to_rect` | 矩阵与 `bb_of` 同口径（无父级用 `matrix_basis`）；四条边一律 `clear_inner=True`；法线用 `Mᵀ`（世界→局部）；去掉 `det` 符号乘子（逆转置本身已处理镜像） |
| `trim_current_scene` | 裁剪循环前强制 `bpy.context.view_layer.update()`；裁完再 update 一次（`bound_box` 要重新求值） |
| manifest | 被裁过的对象改用 `exact_bb()`（逐顶点世界包围盒）；未裁的仍用 `bb_of`（便宜，且保守包围盒在框内 ⇒ 真实也在框内） |
| 闸门 | 新增 `tools/_check_scene_trim_clip.py`（A~G 七条 + 负面测试），已接进 `build_scenes.py` |

**影响面**：已建的 `bla` / `sod` / `wild_10` 日志里都没有「按远景框裁掉超界几何」，
说明**从未走到这条路径**，产物不受影响；只有 `sdn` 触发（14 个）。

### 6.10 活动区口径：**能走范围 P 就是活动区边界**（2026-11-04 用户裁定）

**规则**：P（据点 = 你在编辑器画的矩形；野地 = 手画矩形）是唯一的活动区边界；
**P 外一律按远景处理**（只留 `C_lod_远景碎片`，非 lod 对象删除）。
旧的"正方形档位 T + 四边各留 64 m"不再是活动区，`T` 只保留用来算远景框的尺寸。

**数据流**

| 环节 | 做法 |
|---|---|
| 生成器 | `build_scene_division.py` 把 P 的世界矩形写进 `scene_list.csv` 末尾四列：`能走_x0/y0/x1/y1`；`活动区宽/高` 改成 P 的宽高；`远景宽/高` **保持原值不变** |
| 读取 | `scene_trim.load_scene()` 读这四列 → `sc["p"]`；`rects()` 返回 `(P, 远景框)`；读不到才退回旧正方形（兼容老 CSV） |
| 构建 | `blender_continent` 的预筛、`scene_trim` 的保留/删除判定、`verify_no_visible_lod_inside`、`scene_terrain` 的活动区/条带分界、`scene_interiors` 的室内取舍，**全部用 P** |
| 远景框 | **不改**：仍按原配置的 `远景宽/高`（sdn = 4096×4096），只是不再随 P 变 |

**闸门**：`_check_scene_trim_clip.py` 的 I 项断言 `scene_list.csv` 的「能走」四列必须被读出、
`rects()` 必须拿它当活动区。

**后果（sdn 实测）**：活动区对象 29,690 → **19,763**（完全在 P 外的 9,927 个不再算高清，
其中 401 栋建筑、4,825 个道具、836 个植被按远景圈规则处理）。

### 6.11 远景碎片改从「打散分组」的远景库按需取（2026-11-04 用户裁定）

**规则**：场景的远景碎片**不再从 tile 装 lod**，改从
`deliverable/blender/continent/continent_lod_split_v23.blend` 按组 append ——
只取 bbox 与场景远景框相交的组（sdn 是 20 组 / 1,154 件）。

**为什么**：合并 LOD 块（`new_area_slod4`，x[2127,3415]）在 tile 流里是**一整块**且跨活动区 P；
按"跨边界 lod 隐藏"规则会整块被藏 ⇒ 活动区外的另一座据点（西西卡监狱，拆件 549 顶点）
在 sdn 里完全消失。远景库里 `S_sis_西西卡监狱` 有按据点切开的
`new_area_slod4__split_sis`，直接用即可，不用在 trim 里二次切割。

**实现**

| 环节 | 做法 |
|---|---|
| 远景库 | `extract_class_blend` → `backfill_lod_blend` → `split_span_blocks`（按据点 P 切）→ `group_lod_blend`（55 组）；产物 = `continent_lod_split_v23.blend` + `lod_groups.json` |
| 取用 | `blender_continent.append_lod_groups(scene)`：按 `lod_groups.json` 的 `bbox_world` 挑相交组 → `bpy.data.libraries.load(link=False)` append → 对象挂 `ENTITIES`，删临时集合 |
| tile | `build_entities` 在场景模式下**跳过所有 lod 实体**（日志 `tile lod 跳过 N（由远景库提供）`）；高清对象照旧 |
| 分类 | 拆件名字含 `slod` → `classify_name` 归 `lod`；trim 照旧：P 内隐藏 `lod` / P 外可见 `lod_out` |

**实测（sdn，2026-11-04）**：`[lod] append 20 个分组 / 1154 个远景碎片`；
`new_area_slod4__split_sis` 在 `C_lod_out_远景碎片·区外`、`ring=1`、顶点世界 bbox
x[3097.4,3414.6] y[−731.1,−487.9]；未拆整块 `new_area_slod4` 不再存在；远景框越界 **0**。
**性能**：打开 1.1 GB 库 + append 一组实测 **0.5 s**，不需要按组拆小文件。

### 6.12 `bisect_plane` 会卡死在共面地形片上 —— 隐藏类跨边界直接丢（2026-11-04）

**症状**：`rat`（岔路酒馆）构建 **40 分钟超时**，日志停在 `[trim] 保留 活动区 397 · 远景 113`
之后 —— 即远景框裁剪循环里，没有任何后续输出。

**根因**：`clip_to_rect` 对 `terrain_cell` 地形补片（`outg_a_03_hd_02`，5,473 顶点，
大片共面三角形）做 `bmesh.ops.bisect_plane` 时卡死。逐对象计时探针实测：前两个同类对象
0.01~0.02 s 就切完，到 `outg_a_03_hd_02` 直接不返回。

**修法**：`trim_current_scene` 的裁剪循环里，`cls_key in ('terrain_cell', 'terrain_lod')`
且跨远景框 → **直接丢掉，不做裁剪**（`HIDDEN_TERRAIN`）。它们本来就是整类默认隐藏的
冗余地形片，场景有自己按 H4 建的 `Terrain` 网格，丢了不可见。统计键 `删·隐藏地形跨边界`。

**实测**：`rat` 728 → **498** 对象，**21 秒**完成，0 超界，地形图 PASS。

### 6.13 补数据 / 补资产前，先查「已接受缺口」与现成管线（2026-11-04 教训）

**症状**：审计出「1,688 个模型缺 albedo」「abe/dow/twi 没有远景碎片」，第一反应是重新解包 +
另外写减面工具 —— 实际上两件都早有结论/管线，**是在重复造轮子**。

**三条判据（动手前必查）**

1. **`work/` 是 `raw/` 的 junction**（README §3「目录联接」）——两棵树是**同一份文件**，
   在 `work/all_packs` 和 `raw/all_packs` 各搜一遍 = 白搜两遍。
2. **raw 已经做过源侧闭环**（README §③：2,158 个嵌套包 / **0 空包** / 176,097 文件 / 58.58 GB），
   **不要重新解包**。`extract_ytd_all.py` 的 `state` 说"已完成"就是真的抽出过了。
3. **README §6「已知缺口」里已有的，就是已接受的**：
   - 缺 albedo 的小道具（硬币/罐头/书/杯子等）：**扫 25 个 props 包 + `gtxd.rpf` + 3,696 个 ytd 全无**，
     用近似色代替 —— 所以 `mesh_texture_audit.csv` 里那 1,688 个缺 albedo **不是新发现**；
   - `abe` / `dow` / `twi` 没有远景碎片：**现成** `tools/build_miniatures.py`（46 据点 /
     84,502 面）就是它们的"高清减面兜底"，不要另写工具；
   - 单城真实模型/微缩模型早就有（README §2.3b + `RDR2_沙箱大地图_微缩模型规格.md`），别重造。

**动作**：写"补数据/补资产"工具前，先 `grep` 一下 README §6 / TODO / `tools/` 里的相关名字
（`miniature` / `relink` / `extract_*` / `audit_*`），确认没有现成管线；有就**跑它**，没有才新写。

### 6.14 MLO 实例四元数：**不取共轭**（2026-11-05 实锤；件级与外壳恰好相反）

**症状**：`val.blend` 里选中 `val_03_stable_ext`，室内墙面与外壳墙向差 **~10°**，
室内壳 / 影子代理从屋顶、墙面穿出来（`i_c8490458` = `val_stable_int_shadow`，就是那个
15.5×15.2×8 m 的无贴图影子盒）。夏洛蒂家（`willard`）早前也撞过同一现象，当时是靠
`merge_interior_into_willard.py` 末尾「把室内 yaw 硬掰成房子 yaw + bbox 居中」收掉的 —— 那是补丁，不是根因。

**根因**：`scene_interiors.py` 把 **MLO 实例**的四元数按普通 ymap 实体一样取了共轭。
实例四元数的旋向其实是**反的**：`val_stable_int` 实例 yaw = **+5.13°**，取共轭后变 **−5.13°**，
而室内壳局部墙向 −1.64°、外壳墙向 +3.44° ⇒ 装配后 **−6.76°**，与外壳差 **10.2°**。

**判据（机器闸门）**：`tools/_check_interior_align.py`（纯 Python，不加载 blend）
—— 每个 `*_int` 包：室内 `*_shell` 墙向（4θ 矢量平均）应当等于宿主外壳墙向。

| 口径 | 可判样本 | \|Δ\| 中位 | ≤2° 占比 |
|---|---:|---:|---:|
| 实例**取共轭**（旧） | 48 | **29.7°** | 2/48 |
| 实例**不取共轭**（现） | 48 | **0.34°** | 46/48 |

**件级相反**：ytyp entity 自己的 `q` 取共轭后 93% 落在 5° 内，不取共轭只有 1%
⇒ 只有**实例**这一层是反的；件级 `lq` 与大陆外壳 `e[4:8]` **继续取共轭**，别一起改。

**修法（三处，同一行）**：

| 文件 | 改成 |
|---|---|
| `tools/scene_interiors.py` | `q = Quaternion((inst[7], inst[4], inst[5], inst[6]))` |
| `tools/instantiate_interiors.py` | 同上（大陆装配） |
| `tools/audit_interior_placement.py` | `R = quat_mat((inst[4], inst[5], inst[6], inst[7]))` |

**验收**：`python tools/_check_interior_align.py` → `结论：PASS`（负面测试必须掉到 <20%）；
重跑场景后，室内应完全落进外壳内（前后对比图留在 `_scratch/val_stable/stable_{top,iso}_{before,after}.png`）。

**补完（2026-11-05 同日）**：上面三处之外，旧写法还留在两个文件里 —— 正是夏洛蒂家那条链：
`tools/merge_interior.py`（`Q = Quaternion((q[3], -q[0], -q[1], -q[2]))`）与
`tools/merge_interior_into_willard.py`（`MLO_QUAT = Quaternion((_qw, -_qx, -_qy, -_qz))`）。
已改成不取共轭，并把 willard 脚本末尾那段「硬掰 yaw + bbox 居中」**删成只测量不执行**（根因修了还留着，
等于错两次）。另：夏洛蒂家当年还有**第二个**毛病 —— 用的是替身实例 `roc_hse_int_lod` 而非真实例
`roc_house_int`（差 100°），别把整口锅都算在共轭上。

### 6.14b MLO 实例的**查找**必须按优先级：精确 → `_main` → `_lod`（2026-11-06 用户实机）

**症状**：`val.blend` 里瓦伦丁银行室内（`i_2b046e06` = `val_bank_main_shell`）整体歪 **~100°**，室内壳从屋顶穿出来；用户实机当场指出"昨天刚修好的旋转又坏了"。

**根因**：`scene_interiors.find_mlo()` 旧写法是「遍历 tiles，**第一个**名字命中 `pkg / pkg_lod / pkg_main` 的就返回」。`val_bank_int` 的精确实例不在 tiles 里 ⇒ 先撞到 `val_bank_int_lod`（yaw **−100°**，LOD 代理的摆位与正体不同），而正确实例是 `val_bank_int_main`（yaw **0°**）。

**为什么体检没抓到**：`_check_interior_align.py` 一直用的是 `pkg → _main → _lod` 优先级 ⇒ 体检 PASS、构建歪 —— **构建/审计/体检三处口径不一致**才是真问题（§6.14 末尾记过夏洛蒂家 `roc_hse_int_lod` 同类现象，但当时只修了那一个案例，没修查找逻辑）。

**影响面（实测）**：全量 210 个 `inside` 包中 **42 个**旧写法取到 `_lod`；涉及 13 张场景（`val` / `sdn` / `bra` / `cal` / `che` / `lon` / `man` / `mic` / `pro` / `rho` / `str` / `van` / `bee`）+ `sod`（审计结论变化）。

**修法**：
- **统一实现** = `tools/parse_interior_mlo.py` 的 `find_mlo_instance()`（纯函数 `build_mlo_index()` + `pick_instance()`，优先级 精确 → `_main` → `_lod`）；
  `scene_interiors.find_mlo()`、`audit_interior_placement.load_mlo()`、`_check_interior_align.collect()` **三处全部改为调它**，禁止再各写一份；
- 审计重跑：`inside` **210 → 211**（`rho_saloon_int` / `tax_house_int` 进，`sod_house_int` 出）；旧表备份在 `_tmp/interior_placement_audit_before_20261106.json`；
- **闸门** = `tools/_check_mlo_lookup.py`（已接进 `build_scenes.py` 开跑前，不过就 `return 4`）：
  ① 优先级用例；② 真实数据 `val_bank_int` 必须 yaw≈0°；③ **反向测试**——模拟旧写法必须取到 `_lod`（否则判闸门无分辨力）。

**验收**：`val` 重建后 `i_2b046e06` yaw **0.00°**、包围盒落在 `val_bank` 内；`_check_interior_align --only val` PASS；构建日志出现 `[mlo] PASS`。

**通用教训**：**"找实例"这种语义只允许一份口径 + 一道闸门**。体检和构建各写一份，必然出现「体检绿、画面歪」；案例式修复（只改夏洛蒂家那一个）不叫修根因。

**补：只有 `_lod` 的包（2026-11-06 同一用户实机，`rho_fenceshop_int`）** —— 精确实例与 `_main` **都不在** tiles 里，只剩 `_lod`；而 LOD 代理的朝向不可信（实测 yaw **19.99°**，外壳 `rho_04_fenceshop_ext` = 0°，室内整体歪 20°）。
修法：`find_mlo_instance` 在「只有 `_lod`」时，用**同词干外壳实体**的朝向（`pkg` 去 `_int` 取最后一段 → 找名字含该段且带 `_ext` 的实体，取最近的；朝向取共轭，与普通实体一致），**位置仍用 LOD 的**。
全量只有 **2 个** inside 包走这条路（`rho_fenceshop_int` 修好；`cor_factb_int` 找不到外壳，保持原样）。闸门 `_check_mlo_lookup.py` 已加断言：`rho_fenceshop_int` 必须 yaw≈0°（并注明原始 `_lod` 是 20°）。

**同一包的第二个问题：高度也不可信** —— LOD 的 z（83.0）不是室内原点的高度，室内壳顶 86.48 m 冒出建筑顶 84.95 m 达 1.5 m。
修法（`scene_interiors.py`，只作用于「只有 `_lod`」的包）：摆完后把**整包 bbox** 与同词干外壳 bbox 做**竖直套合** ——
装得下就贴地板（外壳 zmin + 0.05），装不下就居中；实测 `rho_fenceshop_int` 下移 **-3.32 m**，
壳 z `[79.51, 83.16]` 落在建筑 `[79.46, 84.95]` 内。审计只查水平四边间隙，不覆盖竖直，所以这条只能靠构建侧兜底。

**通用规则（2026-11-06 用户裁定）——"拿墙和内部空间保证吻合"**：
1. **朝向**：用**下半截墙体**（z ≤ z0 + 0.6·高度）的 4θ 墙向量，**排除外扩屋檐**（夏洛蒂家/`rho_04_fenceshop_ext` 同款：屋檐会让"随便怎么转都看着对"）。实例 yaw = 宿主墙向 − 实体 yaw − 壳体墙向；90° 歧义用 LOD 原朝向选最近象限。
2. **宿主优先取审计表的 `host`**（真正承载房间的墙体/构件，如 `rho_04_bkdoorshut`），没有再退同词干外壳。
3. **水平 + 竖直都套合到宿主 bbox**（居中）——只做竖直会留 1.4 m 水平偏移（用户肉眼可见）。
4. 只对「没有真实例（只有 `_lod`）」的包启用；其余包直接用游戏实例（本来就是对）。
5. 🔴 **坐标系**：宿主 bbox 是世界坐标，场景对象是局部坐标（x/y 减了场景中心）——比较前必须 `-= cx/cy`，否则会差出整个场景中心（实测偏 +1217 m）。
6. **自检**：套合后仍超出宿主 bbox >0.25 m 就打 `[int] WARNING`，不静默通过（闸门不接进流程 = 没有闸门）。

**最终定稿（2026-11-06 用户验收）——「面积重合率最大」求解器**：
- 之前的来回摆动有两个真实根因：① 用**模型库 bbox**（`rho_04_bkdoorshut` 库 10.8×10.5 vs 实际网格 7.4×7.3）—— 拿错尺寸永远对不上；② 一度用 FFT 相关求位移，**符号约定反了**（位移方向取反）。
- 现在：取**真实网格顶点**做 2D 点掩膜（室内 / 墙 / 建筑），**直接网格搜索** ±1.5 m、步长 0.10 m，
  目标 = `10×(墙点被室内盖住比例) + 1×(室内点落在建筑内比例)`；取最大者（`scene_interiors._overlap_shift()`，只对 only-lod 包）。
- `rho_fenceshop_int` 最终：位移 `(-0.20, -1.00)`、score 10.381；渲染上蓝墙几乎全被房间盖住（只剩右上细线）。
  验收渲染：`_scratch/fenceshop_align/overlay_v2.png`（2026-11-06 15:16 版）。

**竖直方向（同日修正两轮，最终定稿）**：不要用 bbox 的 zmin/zmax（会被墙脚装饰、屋脊带偏），也不要拿**墙体**的 z 范围当基准。
改为 `scene_interiors._floor_roof_planes()`：在房间 XY 范围内统计建筑顶点的 **z 直方图主峰（主水平面）** ——
**固定 1~1.5 m 窗口**（百分比窗口移位后会换峰，实测差 0.6 m）：
- 房间**地板面** ↔ 建筑**地板面**（本轮实测 81.21 vs 81.27，差 6 cm）；
- 对齐后若顶 > 建筑屋顶主平面，打 WARNING（不靠"顶对齐"硬压，避免陷入地面）。
`rho_fenceshop_int` 最终：`location.z = 82.57`，房间 z `[80.75, 84.40]`（顶低于屋顶主平面 84.53，底贴地板）。
透视验收图：`_scratch/fenceshop_align/persp_overlay.png`。

### 6.15 室内宿主判据 + 阴影代理壳（2026-11-05）

两个独立的坑，都在「室内明明摆了却不对/多一块」这条线上。

**① 宿主判据会配到窗、贴花、碎石堆、地形块、电缆网格上**

`audit_interior_placement.py` 的 `_BAD_NAME` 只做**降级**（`q`），而排序键是 `(tier, q, w, d)`
—— **tier 压过一切**。小道具的 bbox 只要"恰好"包住室内就拿到 tier 0，真建筑反而被挤掉。
实测：`str_mayorshouse_int` 的宿主是 `str_03_mayorwindow`（一扇窗）、`str_dressingroom_int`
是 `str_03_mill01_ext_dcl`（贴花）、`str_genst_int` 是 `str_03_debrispile01`（碎石堆），
还有一批配到地形高度块 `j_11__hd_0_-2_3` / 电缆 `cablemesh…_hvlit`。

**修法**：`_BAD_NAME` 补 `dcl`；新增 `_PROP_NAME`（window/debris/fence/sign/post/lamp/track/road/
decal/cablemesh/`_hd_0_`/`out_`/`outg_`）并在候选循环里**直接 skip**（不是降级 —— 压不过 tier）。

| 指标 | 改前 | 改后 |
|---|---:|---:|
| 非建筑类宿主 | 77 | **6**（剩下的都是 `_dcl`，只是名字不雅，bbox 仍是建筑） |
| 结果条目 | 251 | 247 |
| `inside=True`（真正会被摆的） | 179 | **179**（不变） |

掉出的 4 个（`bac_tunnel_int` / `bac_tunnelcurve_int` / `dis_grz_statue_int` / `gua_boat_int`）
原本就是 `inside=False`、宿主是地形块，**从来就没被摆过** ⇒ 覆盖无损。

> ⚠️ §6.14 那张「48 个可判样本 / 46 个 ≤2°」的表是**在宿主判据修好之前**跑出来的。
> 宿主可能配到窗/地形块上 ⇒ 建议用修好的审计表重跑一次确认，别直接引用。

**② 阴影代理壳被当可见几何摆进场景**

室内包里 `<包>_shadow` 是**只参与投影**的低模壳（瓦伦丁马厩 `val_stable_int_shadow`：143 顶点、
无 albedo、靠 `ntex_wood` 兜底配色）。`scene_interiors.py` 原来只分「贴花 / 普通件」两类，
于是它按 `cls_key='part'` 进了可见集合 → 屋顶上多一块空壳。**用户报的"墙面没对齐"就是它**
（旋转修好后它基本缩回楼里，但仍是多余一块）。

**修法**：照抄贴花类的写法加一类
`C_int_shadow_室内阴影代理`（`COL_PROXY`，`hide_viewport/hide_render=True`，N 面板可单独勾开）。

🔴 **正则别只写 `_shadow$`（第一版就这么漏了 90%）**：命名有一整族 ——
`_shadowproxy` · `_ref_proxy` · `_shadow_proxy` · `_shadow` · `_shdw_proxy` · `_shd_proxy` ·
`_shad_proxy` · `_shdw_prxy` · `_shdwprxy` · `_shd_pxy` · `_shdw` · `_refproxy` ·
`_reflection_proxy` · `_refln_proxy` · `_refle_proxy` · `rfle_proxy` · `_proxy` · `_shadowbox`。
最终口径 = `PROXY_NAME = re.compile(r'(proxy|shadow|shdw|shd_|shad_)', re.I)`，
全量 251 个室内包里共 **326 件**（不是 15 件）。瓦伦丁 12 个包占 **20 件**
（`i_a6cc1063` = `val_saloon_int_shadowproxy` 就在其中）。
负面样例（不该命中）：`*_shell` / `*_shell_dec` / `*_ref` / `*_ground` / `p_barrel04b`。

> `_ref`（84 包 / 87 件）**暂不动** —— 还没验证它是反射代理还是低模 LOD，没证据不擅自隐藏。
> 验法：单独显示 `_ref` 与 `_shell`，若几乎重面且更糙 ⇒ 是 LOD，同样该隐藏。

**③ 附带修**：`build_scenes.py` 顶部显式 `sys.path.insert(0, TOOLS)` ——
从别的 cwd 用绝对路径调用时，末尾 `import export_scene_terrain_maps` 会报
`No module named`，场景其实已经建好却把 `scene_build_status.csv` 记成 failed。

**④ 🔴 哈希没补零 ⇒ 室内件被静默丢掉 2,495 个（最高原则 §6.4 复发）**

`scene_interiors.py` / `instantiate_interiors.py` 用 `hx = hex(e['h'])` 去查模型库，
而库的键是 **8 位** `0x%08x`。哈希小于 `0x10000000` 的会被写成 7 位（`0x00418731` → `0x418731`），
`models.get()` 查不到 ⇒ `continue`，**一个日志都不打**。

| 实测 | 数 |
|---|---:|
| 全部室内件 | 47,791 |
| 哈希带前导零 | **2,597**（5.4%） |
| 其中模型**确实在库里**（= 被吞掉的） | **2,495** |

漏的是家具、门、碎石堆这些实打实的东西（`p_debrispile01x` / `p_dooraberdeen02x` / `p_brush01x` …）。
发现路径：`cas_house_int_shdwprxy`（`0x00418731`）在瓦伦丁里根本不存在 → 顺藤摸到这一层。

**修法**：两个文件都改成 `hx = '0x%08x' % e['h']`。副作用是对象名也补零（`i_00418731`），
与 §6.4 的命名规矩一致；下游按 `name[2:10]` 取哈希的地方照常工作。
**效果**：瓦伦丁室内 **1,559 → 1,632 件（+73）**，`val.blend` 222.3 → **224.7 MB**。

**验收（瓦伦丁重跑后实测）**：

| 项 | 值 |
|---|---|
| `val_stable_int_shell` 墙向 | **3°**（宿主 `val_03_stable_ext` = 4°；修前是 −6.5°） |
| 四边间隙 W/E/S/N | **+0.67 / +0.99 / +0.81 / +5.66**（全为正） |
| 日志 | `[int] 其阴影代理壳 2 件 → 「室内阴影代理」类（默认隐藏，勾开可看）` |
| 对照图 | `_scratch/int_align/shots/final_{A_shipped,B_proxy_shown}.png` |

### 6.16 ymap 里同一栋房子摆了多层 LOD —— 名字查不到的会当 `unknown` 压在 HD 上（2026-11-05）

**症状**：瓦伦丁谷仓屋顶有一块形状不规则的深色斑（用户截图问"为什么加了 `val_01_aucbarns_barn3`
就让每个屋顶有污渍"）。

**真相：不是那栋建筑的问题，是它的 LOD 分身压在它上面。** 同一位置 2 m 内有 4 条实例：

| 距离 | 实例 | 是什么 |
|---|---|---|
| 0.00 m | `val_01_aucbarns_barn3` | HD 本体（30,879 顶点） |
| 0.00 m | `val_01_aucbarns_barn3_dec_det` | 细节贴花件 |
| 0.36 m | `0xf005a86d` | **LOD 分身**（3,359 顶点，材质 `alb_val_barn3_lod_ab`） |
| 0.36 m | `val_vfx_rain_aucbarns_barn3` | 雨效 |

🔴 **关键认识**：LOD 在 RDR2 里**不是同一实体的字段，而是 ymap 里另起的一条实例**，和本体同坐标叠着放；
`CEntityDef` 的 `lodDist`(+76) / `lodLevel`(+84) 交给引擎按距离二选一。我们是**把实例表原样全建**，
所以全部层级同时出现在场景里。

| 全图实测（233,104 个实例） | 数 | 占比 |
|---|---:|---:|
| 名字表查得到 | 183,097 | 78.6% |
| **查不到**（`e_<hash>`） | 50,007 | 21.4% |
| 其中 1 m 内还有具名实例（多半是分身/叠加件） | 39,221 | 无名的 **78.4%** |

**根因**：名字判不出 ⇒ `unknown` ⇒ **`unknown` 是可见的** ⇒ 全压在 HD 上。
瓦伦丁 607 个 `unknown` 里 **517 个**材质名带 `_lod`。

**修法**（不删，只归对类）：`class_rules.apply_texture_lod()` —— **只在已判成 `unknown` 时**，
用 `lod` 那条名字正则去匹配**贴图名**（材质名 + 完整 albedo 名，`classify_entities` 早就收集好了）：

```python
k = apply_corrections(k, n, tex_names, overrides)
k = apply_texture_lod(k, tex_names)      # ← 新增这一行
```

判据样例：`alb_val_barn3_lod_ab` / `alb_prop_lod` / `alb_p_crate01x_lod_ab` → `lod`；
`alb_nbx_roofs_shingle11_ab`（真高清）不动；已判成 `bldg` 的**一律不动**。

**效果（瓦伦丁重跑）**：`unknown` **607 → 85**，远景碎片 1,823 个整类默认隐藏；
屋顶暗斑消失（`_scratch/int_align/shots/barn_{A_with_lod,B_without_lod,C_shipped,D_lod_forced}.png`）。

> ⚠️ **不能按"没名字"一刀切隐藏**：剩下 22% 的无名件 1 m 内没有具名邻居，不是分身。
> 判据必须落在贴图证据上。也**不能删**（最高原则 §6.1）。

### 6.17 「同位置两份」是常态：贴花层 / 破损版 / 状态版都会叠在原型上（2026-11-05）

和 §6.16 同源：**RDR2 关卡把"变体"当独立实体摆在同一坐标**，引擎按状态/距离选一份，我们全建。

| 变体 | 命名 | 例子 | 叠在什么上 |
|---|---|---|---|
| 远景 LOD | `_lod/_slod`，或名字表查不到 | `0xf005a86d` | 建筑本体 |
| **建筑贴花** | `_dcl` / `_dcls` | `val_bank_dcl01`（7,679 顶点，包住整栋） | 建筑本体（墙面/屋顶污垢） |
| **破损版** | `_dmg` | `p_val_sgn_sln_01_dmg`（弹孔招牌） | 完好版 `p_val_sgn_sln_01` |
| **状态版** | `_dcl_lockdown_*` | `val_dcl_lockdown_bank` 等 11 件 | 各栋建筑（封锁状态贴花） |

**用户 2026-11-05 裁定：「建筑贴花」不能算地面贴花，单独成类。**
`_dcl` 原先只在 `LEFTOVER` 兜底里认 ⇒ 名字带 bank/shed/stable 的先被 `bldg` 抢走 ⇒ 污垢层跟着
建筑一起显示（瓦伦丁银行屋顶的"花斑"）。修法：新增类 `bldg_decal`「建筑贴花」，
**规则排在 `bldg` 之前**；地面类（`mudtrack_dcl` / `footboards_dcl`）由 `BLDG_DECAL_GROUND`
守卫跳过、仍归「地面贴花」。

**效果（瓦伦丁重跑）**：`bldg_decal` 27 件（含 `val_dcl_lockdown_*` 11 件）整类默认隐藏；
`bldg` 123 → 113；屋顶花斑消失。

> `_dmg` 破损版**暂未处理**：`p_val_sgn_sln_01` 与 `_dmg` 两份现在**都可见**（招牌上的"弹坑"就是
> 破损版叠上去的）。要不要按状态只留一份，得先定「默认取完好还是取破损」，是产品决定，不是 bug 修复。

### 6.18 室内宿主判据：**用房间壳量，不用全部件**（2026-11-05，威拉德之息暴露）

**症状**：`roc`（威拉德之息）重跑后 **0 个室内包** —— 夏洛蒂家的室内整个没摆。

**根因两层**

1. **审计量错了对象**：`audit_interior_placement.py` 用包的**全部 447 件**算包围盒，
   道具/外挂件/阴影代理把盒子撑到 18.4×27.3 m，判「超出宿主 11.15 m」。
   而用**房间壳**量：四边 **+2.33 / +0.76 / +0.41 / +1.40**，完全放得下。
   实测证实（强制 inside 摆进去）后网格包围盒 X[−6.4,6.5] Y[−8.5,7.2]，房子 X[−8.7,7.3] Y[−8.9,8.6]。
2. **审计里也有哈希没补零**（`lib.get(hex(e['h']))`）—— 与 §6.15④ 同一个 bug，只是换了个文件。

**修法**

| 改动 | 内容 |
|---|---|
| 量的对象 | 优先 `<名>_shell` / `<名>_shell_main` 的实体；没有壳才退回全部件（老行为） |
| 哈希 | `lib.get('0x%08x' % e['h'])` |
| 面积闸门 | **用壳体量时 `fits` 恒 True** —— 房间壳小、楼大是正常情况。不去掉的话 `rho_train_int` 这种「整个落在大车站里、四边全正」的会被面积比否掉（实测 True→False） |

**效果**：`inside=True` **179 → 210**；`roc_house_int` 归位；`rho_train_int` 保住。
壳命名不止 `_shell`（`roc` 用的是 `roc_hse_int_shell_main`、`bla` 是 `_mcp_shell`），
正则写成 `_shell(_main)?$`，漏一种就少一批。

> ⚠️ 这条把"能摆的室内"从 179 提到 210，**所有场景都要按新表重跑**才一致；
> 旧的 `willard_full.blend` / `merge_interior_into_willard.py` 那条链可以退役了
> —— 它的输入 `willard.blend` 已不在盘上，而且写死的是替身实例 `roc_hse_int_lod`。
> 威拉德之息现在就是普通场景 `roc`，走 `build_scenes.py --only roc`。

### 6.19 室内地面贴花：**全部子网格**都是贴花图才算（2026-11-05，一张床被误判）

**症状**：`roc.blend` 里 `i_b2afc32a`（= `roc_hse_bed01_logs`，23,256 顶点的床）被归进
「室内地面贴花」整类隐藏，床头柜、梁这类也跟着遭殃。

**根因**：`scene_interiors._is_decal()` 用 `any(...)` —— **任意一个**子网格的贴图名命中
`_dc_|decal|holepatch|drip|stain` 就算整件是贴花。那张床 8 个子网格里只有 1 个是
`roc_int_drip01`（滴渍），照样被判成贴花。

**全量分布**（911 个有命中的室内模型）：

| 命中比例（命中子网格 / 总子网格） | 件数 | 判读 |
|---|---:|---|
| **1.0** | **205** | 真贴花 |
| 0.6 ~ 0.9 | 112 | 多半是真贴花 |
| **≤0.5** | **594** | 基本是误判（家具/壳体混进一张污渍图） |

**修法**：`any(...)` → `all(...)`，且必须至少有一个有效贴图名。

```python
names = _mat_textures(m, texmeta)
if not names:
    return False
return all(DECAL_TEX.search(n) for n in names)
```

**效果（威拉德之息重跑）**：`int_decal` **14 → 3**，剩下的 3 件是 `roc_dirt_stains` 系列
（136~190 顶点）；那张床回到 `part`。

> ⚠️ `val` / `bla` / `sdn` 是在这条修之前建的，它们的 `int_decal` 计数（34 / 22 / 64）会一起下降。

### 6.20 🔴🔴 场景地形读的是「给骑砍2 大地图改过」的高度图（2026-11-05，安尼斯堡半城泡水里）

**症状**：`ann.blend` 里半个城泡在水里，而区域 blend `13_wild2000_05_01.blend` 同一位置正常。

**根因**：两条链读的**不是同一份地形数据**：

| 链 | 数据源 |
|---|---|
| 区域 / 大陆（`blender_continent`） | **原生** `work/terrain/H4.npy` ✅ |
| **场景（`scene_terrain`）** | `deliverable/terrain/final/height_4m_16bit.png` ❌ |

而那只 PNG 来自 `build_final_map_heightmap.py` —— **它是给骑乘2 大地图用的，会主动改地形**：
抬西北高原（+150 m）、压南边平原、**把内陆水系挖平到固定深度**（河 12~35 / 塘 8~18 / 湖 25~60 / 海 90~300）。

实测安尼斯堡 y=1348 往东剖面：x≥2960 之后**恒定 z=7.1**（= 水位 40.5 − 33.4，正好在"河 12~35"区间），
原生 H4 那里是 43 → 19 的正常河床。水位 40.5 一盖 ⇒ 整段河被淹。

违反最高原则 §6.2「地形只用 RDR2 原生高度，不做压平/拟合/局部拉伸」。

**修法**（不动大地图那张，另出一张给场景用）：

| 件 | 做什么 |
|---|---|
| `tools/build_scene_heightmap_native.py`（新增） | 从 `H4.npy` 生成 `height_4m_16bit_native.png`：**同一世界框、同一 zmin/zmax 编码**，只换数据源 ⇒ 坐标口径不变 |
| `tools/scene_terrain_core.py` | 这张图存在就优先用，`row_shift` 从 1 改 **0**（原生图不需要补偿） |
| `tools/check_scene_terrain.py` | 负面测试从「把行偏移改成 0」改为「**在正确值上再偏一格**」—— 否则对原生图失去分辨力 |

> 🔴 **生成时两个坑**：① H4 **行 0 = 南**（`r=(y-Y0)/res`），交付图**行 0 = 北**，按反了整张图上下翻转；
> ② 像素要**左上角对齐**（不加 0.5），加半像素 = 全图偏半格，回归点差 **0.64 m**，被闸门当场抓到。

**影响面（P 内 \\|差\\|>5 m 的面积占比）**：`sis` 62.7% · `dewclm` 49.8% · `wild_07` 47.9% ·
`lag` 42.3% · `van` 38.1% · **`sdn` 34.0%** · `ann` 20.2% · `bla` 12.5% · `roc` 4.7% · `val` 2.0%。
**56 张里 23 张的 P 内超过 5% 面积受影响** ⇒ 必须全量重跑。

### 6.21 分类词表里的**裸子串**会误伤（2026-11-05，锅炉房被判成地面贴花）

**症状**：`ann_boilerhse`（整栋锅炉房）被归成「地面贴花」整类隐藏。

**根因**：`decal` 规则里 `oil(slick)?` 是裸子串 —— `b`**`oil`**`erhse` 里的 "oil" 命中。
同族隐患：`rut` 会命中 `strut`（支撑）。

**修法**（`class_rules.py`）：

| 词 | 改成 |
|---|---|
| `oil(slick)?` | `oil_?(slick\|spill\|stain\|puddle)\|oilslick`（只认油污语境） |
| `rut` | `(?<![a-z])rut(?![a-z])`（只认独立词） |
| `bldg` 词表 | 补 `boilerhse`（hse = house 缩写，原来谁都不认，修完会掉 unknown） |
| `part` 词表 | 补 `conv\d\|conveyor`（矿场输送带，14 个；`struct` 按 2026-10-31 裁定只放桥） |

**效果**：全库 **279 个名字**改类（prop 103 / unknown 77 / veh 51 / bldg 17 / part 16 …）；
`ann` 的 `地面贴花` **88 → 33**、`bldg` 101 → 125、`unknown` 53 → 46。

> **写词表铁律**：加词之前先想「它会不会是别的词的子串」。宁可写 `_oil_` / `(?<![a-z])x(?![a-z])`，
> 不要写裸词。教训与 §6.19（任意一个子网格命中就算贴花）同源：**判据越短，误伤越大**。

### 6.22 量位置别读**隐藏集合**里的 `matrix_world`（2026-11-05，我自己错了两次）

**症状**：探针量出来"安尼斯堡的 LOD 碎片全堆在原点"，差点当成 bug 报出去。

**真相**：`matrix_basis` 是 (57.7, 9.8, 44.2)（正确），`matrix_world` 是 (0,0,0)。
因为 `C_lod_远景碎片` / `C_int_decal_*` 这类集合**默认隐藏**，而**隐藏集合里的对象不被 depsgraph 求值**
⇒ `matrix_world` 停在单位阵。

**正确做法**（探针里先做这两步再量）：

```python
for c in bpy.data.collections:
    c.hide_viewport = False; c.hide_render = False
stack = [bpy.context.view_layer.layer_collection]
while stack:
    nd = stack.pop(); nd.hide_viewport = False; nd.exclude = False; stack.extend(nd.children)
bpy.context.view_layer.update()
```

同族坑：新建对象（`scene_interiors.build`）在 `view_layer.update()` 之前也是单位阵（AGENTS §6.9 第 1 条）。
**报"位置不对"之前，先确认量的是求值后的世界矩阵，或直接读 `matrix_basis`。**

### 6.23 地面贴花/街面要**逐顶点贴到地形网格面**，不是最近邻（2026-11-06，用户实机 `bla_street_a` 被地形盖住）

**症状**：`bla.blend` 里 `bla_street_a`（79×86 m、0.45 m 厚的街面）中间一段被地形盖住；同族 `bla_street_c_dec` 更严重。

**实测（对地形网格做射线）**：`bla_street_a` **21.8%** 顶点在地形面下（最深 0.17 m）、`bla_street_a_dec` 45.8%、`bla_street_c_dec` 53.4%。

**根因两层**：
1. 逐顶点贴地原来只认「`_height_` 贴图」和「`muddyroad`」两族，街面（`road`）没被纳入；
2. 贴地采样用的是 `ground_z()`（**最近邻**格点），而地形网格是 4 m 格点**线性插值**的面 —— 坡地上最近邻比网格面低，贴完仍会陷进去（`bla_street_b` 残留 16.7%、最深 0.4 m）。

**修法**（`blender_continent.build_entities`）：
- 判据扩展：`road / decal / track_decal` + 薄（模型 bbox z ≤ 2.5 m）+ 水平（四元数 x/y ≈ 0）+ 中心离地 ≤ 2 m → 逐顶点贴地；
- 采样换成 `ground_z_surface()`（全局 4 m 格点**双线性**，与 `scene_terrain._grid` 同一张面）；
- 采样坐标必须带**对象实际旋转**（`ob.rotation_quaternion.copy()`，含 `conj` 口径）——
  `bla_street_b_dec` 是 90° yaw，漏旋转会采到镜像位置（第一次修反而从 16.6% 变 29.6%）。

**结果**：`bla_street_a` 21.8% → **0.0%**；`street_a_dec` / `street_c_dec` 0.0%；`street_b` 0.9%（最深 0.034 m）；`street_b_dec` 0.0%。

**顺带**：`p_08_ftr_regular/endsum`（142×103 m 地形补片）仍有 1.2~1.6% 顶点埋深 ≤0.37 m（地形补丁接缝处），但它们是 `decal` 类**默认隐藏**，不影响画面。

**车辙脚印（既有）**：`l_09_heighttracks_decals01/02/03`、`p_14_02_track_dec_*` 早在 2026-11-05 就处理过 —— 材质走 `mat_rdr2.make_height_decal`（alpha 当脚印遮罩、深泥色）+ 逐顶点贴地；`muddyroad` 走 `make_mud_decal`。这次只是把同一套贴地机制扩展到街面/地面补片。




### 6.24 🔴 室内管线速查（2026-11-07 立；以后查"这栋为什么歪了/怎么调"只看这一节）

**一、数据从哪来（四份，缺一不可）**

| 东西 | 位置 | 说明 |
|---|---|---|
| 室内包定义 | `raw/all_packs/<包名>/<包名>.ytyp` | Rockstar 的 MLO 清单：每件 = 模型哈希 + 本地 pos/quat（`cor_factb_int` 共 325 条） |
| 哈希 → 名字 | `tools/rdr2rpf/bin/Release/net9.0/names.txt` + `tools/name_source.py` | **纯文本名字表**，用 **joaat** 算哈希建 `{hash: name}`；`X_children` 会补出父名 `X`。**不是 JSON** |
| 哈希 → 模型/贴图槽 | `assets/lib_native/index.json` | `{hash: {b: bbox, s: [[alb,nm,ma]], f: "c4/0x….mdl"}}`，**不含名字** |
| 包 → 宿主建筑 | `export/world/interior_placement_audit.json` | 按包围盒包含关系算的 `host`；算不出时用 `parse_interior_mlo.HOST_OVERRIDE` 手工对位 |

**二、对象身上的属性（判断来历只认属性，不认名字）**

| 属性 | 谁有 | 含义 |
|---|---|---|
| `int_pkg` | 室内件 | 所属室内包名；**没有它 = 世界实体** |
| `int_model` | 室内件 | 模型原名 |
| `hash` | 都有 | 模型哈希（室内件也写，可按哈希反查） |
| `built_loc` | 室内件 | 构建时的位置，`tools/interior_pkg_tool.py` 用它算"你手动挪了多少" |

命名规则：**查得到模型名就用模型名**（`cor_factb_shell_int`），查不到才 `i_<hash>`。
⚠️ 室内件和世界实体**共用命名空间**（同一个模型两边都有）⇒ Blender 去重后缀（`.033`）可能落在任意一侧，**名字分不出内外**。

**三、朝向（`parse_interior_mlo.find_mlo_instance` 唯一口径，构建/审计/体检三处共调）**

优先级：**精确实例 → `_main` → `_lod`**。只有 `_lod` 时 LOD 朝向不可信（实测歪 80°），改用宿主外壳的四元数**取共轭**（室内侧不取共轭，件级取共轭）。
宿主来源：审计表 `host` → `HOST_OVERRIDE`（显式对位）→ 同词干 `*_ext`。
2026-11-07 时点全库只有 2 个包走 LOD 路线：`cor_factb_int`（对位到 `cor_factoryes`）、`rho_fenceshop_int`（同词干）。

**四、落位（`scene_interiors.build`，只对"只有 _lod"的包跑）**

1. **水平**：先按宿主 `*_fakeint` 包围盒**对中**，再用 `_overlap_shift` 面积重合率求解器微调（搜索半径 ±1.5 m，跨不过大偏差）；
2. **竖直**：**顶部对齐 fakeint**（室内顶 = fakeint 顶 − `FAKEINT_TOP_MARGIN`，当前 0.00）；
3. **自检**：`_roof_clearance_drop` 按 1 m 网格比对"室内任意点上方是否还有建筑"（用户原则），**只报警不自动压**（自动压会把地板带沉）；
4. 越界告警按**件数**判（单件管线/设备件伸到房外属正常）。

**五、台账与人工修正（两张 CSV，都在 `docs/世界与地编/`）**

| 文件 | 谁写 | 语义 |
|---|---|---|
| `interior_fit.csv` | 构建自动写（生成物，禁手改） | 每场景每包一行：`orient / lod_yaw → yaw / dx,dy,dz / fit / clear_m / objects` |
| `interior_fit_overrides.csv` | 人手维护 | **绝对覆盖**：写了就不跑自动套合 |

- 修正表列：`pkg,dx,dy,dz,yaw,note`；`yaw` 留空 = 用自动朝向；
- 🔴 **yaw 的旋转中心 = 包原点（MLO 实例位置的竖轴）**，整包刚体一起转；
- 构建会把自动结果**追加**进修正表（只追加，不覆盖已改的行）；删整行 = 回到自动；
- `dx,dy,dz` 记的是**总位移**（对中 + 求解器之和）—— 曾经只记求解器那一步，导致写回修正表后整包跑偏 3 m。

**六、工具**

| 工具 | 用途 |
|---|---|
| `python tools/backfill_interior_fit.py` | 从所有 `_logs/scene_*.log` 回填台账（不开 Blender） |
| `tools/interior_pkg_tool.py`（Blender 内跑） | 按 `int_pkg` 一次选中**整包**；再跑一次打印"相对构建时挪了多少" |
| `tools/_check_mlo_lookup.py` | 闸门：实例查找优先级 + `cor_factb_int ≈ −5°` 回归 |
| `tools/_probe_{yaw,obj,clearance,int_bbox}.py` | 量朝向/包围盒、查对象来历、量穿顶 |

**七、两个坑（都踩过）**

- 隐藏集合里的 `matrix_world` **不求值**（读出来是 0）——量位置只认 manifest 的 `bb` 或先 `view_layer.update()`；
- 构建被打断会留下**半截 blend**（实测 721 MB，正常 196.6 MB）——见到体积异常先重建。
