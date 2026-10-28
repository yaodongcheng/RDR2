# AGENTS.md —— 在本仓库工作的行为准则（每次开工先读这一页）

> 适用对象：任何在这个项目里工作的 AI（Claude / Codex / Copilot / 本地 Agent）以及人。
> 与本文件冲突的临时指令，以用户当次明确指令为准；但 §2 的长任务规范和 §3 的禁令**不得绕过**。

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
ENTITIES <n> / 12 类 <k>/12 / 植被 <n> / 缺模型 <n> / 贴图 <n> → PASS|FAIL
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
| **贴图只存 tid 不存名字** | 贴图池一重建/一扩充，`s` 里的 id 全部错位 → v6 里**门被绑成草地**（`roa_clover_grass_br_01_te`）、大片发黑 | 库里/model 记录必须有**名字**；绑定一律走 `rebind_textures.py` 按名字解析，禁 fuzzy、禁按 id 索引 |
| 模型库没有 ydr 源 | 4.8 万个模型只知道 hash 和 id，无法重绑 → 44.9% 对象无 albedo | 先拿 `原型 hash → asset 名`（ymap 原型表）再抽 ydr；`export/world/continent/models.json` 是有源的那 10,893 条 |

---

## 5. 交付前自检（缺一不可）

- [ ] 构建命令带 `--full`（几何 → 分类 → 植被处理 → 地形 patch 隐藏 → manifest → 校验）
- [ ] 日志有 `SAVED` 与 `VERIFY ... → PASS`
- [ ] 用 manifest 出数字（`uv run python tools/report_manifest.py`），不靠肉眼
- [ ] 植被默认是 **隐藏**（`--veg hide`），不是删；要删必须显式 `--veg delete` 并说明理由
- [ ] 改动若涉及数据取舍，已在最高原则 §六 记录
- [ ] 产物路径与 `deliverable/` 约定一致
