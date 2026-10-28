# PSO / PSIN 格式规范（RDR2 `.ymt` 用）

> 目标：拿到能解 RDR2 对话资产（`audio/conversations.rpf/*.ymt`）的格式规范。
> 来源：**CodeWalker（dexyfex）的 `Pso.cs` 实现**（GTA V 同族格式），
> 已在 RDR2 的 `.ymt` 上**实测验证**（`tools/parse_pso.py`）。
> 日期：2026-10-23

---

## 1. 总体结构

文件是**若干「节」顺序拼接**，每节 = `tag(4) + length(4, i32) + payload`，**全部大端**。

```
PSIN | PMAP | PSCH | (STRF/STRS/STRE 或 STDN) | PSIG | CHKS
```

| 节 | tag | 作用 |
|---|---|---|
| `PSIN` | 0x5053494E | 实例数据（对象、数组、字符串块都在这段里） |
| `PMAP` | 0x504D4150 | 数据映射：根 id + 每个块 {NameHash, Offset, Unk, Length} |
| `PSCH` | 0x50534348 | 结构schema：结构体/枚举的字段定义 |
| `STDN` | 0x5354444E | 字符串/附加数据（RDR2 实测出现；GTA V 用 `STRS/STRE/STRF`） |
| `PSIG` | 0x50534947 | 签名 |
| `CHKS` | 0x43484B53 | 校验 |

实测（`WNT1_INT_CABIN` 对应资产）：

```
PSIN=9664  PMAP=104  PSCH=1052  PSIG=48  STDN=104  CHKS=20   （共 10 992 B）
```

---

## 2. PMAP（数据映射）

```
i32  RootId            // 根块 id（1 起）
i16  EntriesCount
i16  Unknown (0x7070)
若 EntriesCount<=0：再读 i16 ×4（新版本兼容）
Entries[EntriesCount]  // 每条 16 字节
    u32 NameHash
    i32 Offset          // 相对 PSIN 节起点
    i32 Unknown
    i32 Length
```

CABIN 实测：

```
root=3, 5 条
0x06a04d25 off=16    len=3584   ← 64 条台词 × 56 字节（根数组）
0x00000001 off=3600  len=1783   ← 字符串块（"WNT1_HWAA\0WNT1_INT_CABIN_1\0…"）
0xedaf33b4 off=5392  len=56
0x1638fdaa off=5456  len=112
0x7622c7f9 off=5568  len=4096
```

---

## 3. PSCH（schema）

```
u32 Count
Index[Count]  { u32 NameHash; i32 Offset }     // Offset 相对 PSCH 节起点
在 Offset 处：
    u32 packed = (type<<24) | (unk<<16) | entriesCount
    type==0 → 结构体：
        i32 StructureLength
        u32 Unk
        Entries[entriesCount] { u32 NameHash; u8 Type; u8 Unk; u16 DataOffset; u32 ReferenceKey }
    type==1 → 枚举：
        Entries[entriesCount] { u32 NameHash; i32 Key }
```

### 数据类型（`PsoDataType`）

| 值 | 类型 | 值 | 类型 |
|---|---|---|---|
| 0x00 | Bool | 0x09 | Float3 |
| 0x01 | SByte | 0x0a | Float4 |
| 0x02 | UByte | 0x0b | String |
| 0x03 | SShort | 0x0c | Structure |
| 0x04 | UShort | 0x0d | Array |
| 0x05 | SInt | 0x0e | Enum |
| 0x06 | UInt | 0x0f | Flags |
| 0x07 | Float | 0x10 | Map |
| 0x08 | Float2 | 0x1e/0x20 | HFloat/Long |

`ReferenceKey`：当字段是 Structure/Array/Enum 时，指向 schema 里对应条目的 NameHash。

---

## 4. RDR2 实测到的结构（CABIN 资产）

`PSCH` 解出 **10 个结构**，其中和对话直接相关的是：

```
0x06a04d25  len=56  18 字段   ← 一条台词（根数组元素）
    7622c7f9 Structure off=0     （引用 0x7622c7f9 结构）
    dc8b5570 Enum      off=16
    59519816 UInt      off=24
    23d8becb UInt      off=28
    …若干 Bool…
    c9e12e39 Enum      off=40
    02930011 SInt      off=48    ← 候选：说话人/角色索引
0x7622c7f9  len=64   7 字段   ← 角色/声音信息（含两个 String、两个 Enum、两个 UInt）
0x1638fdaa  len=16   4 字段   ← {String, SInt, String, UInt}（可能是 (context, id, lineKey, flags)）
```

根块 `0x06a04d25` 长度 3584 = **64 × 56**，与 `WNT1_INT_CABIN` 的 64 句完全吻合，
说明"每条台词 = 56 字节结构，按顺序排列"。

---

## 5. 已验证的解析器

`tools/parse_pso.py`：

```bash
uv run python tools/parse_pso.py raw/conversations/out/3066328914.ymt --dump
# sections: {'PSIN': 9664, 'PMAP': 104, 'PSCH': 1052, 'PSIG': 48, 'STDN': 104, 'CHKS': 20}
# PMAP root 3 entries 5
# PSCH structures 10
```

已对多个文件验证（`3066328914.ymt`、`3374884256.ymt`、`0x9526657D.ymt`），
节划分与结构数量都合理。

---

## 6. ★ 已打通：actor 索引解出来了

用上面拿到的结构，实现了 `tools/parse_conversation_actors.py`，做法：

1. **actor 表**：在 `.ymt` 里找「16 字节条目、两个 nameHash 相同、第二个是 actorId」的块；
   nameHash = `joaat(角色名)`，可直接用 `names.txt`（294 471 条）反查成名字。
2. **逐句记录**：找「长度 = 句数 × 56」的块，第 i 条的第 **+24 字节 = actorId**。
3. 台词键/上下文从字符串块按顺序取。

`WNT1_INT_CABIN` 实测（与你给的录屏逐句核对）：

| 句 | 解出 | 录屏/字幕 |
|---|---|---|
| 2–5 | susan | 苏珊（盖斯凯尔小姐/赶紧生火/琼斯小姐/皮尔逊先生）✅ |
| 6 | abigail | 艾比盖尔「戴维死了」✅ |
| 7–8 | swanson | 斯旺森「尽了最大的努力」✅ |
| 9 | hosea | 何西阿「我们现在该怎么办？」✅ |
| 10 起 | dutch | 达奇长段独白 ✅ |
| 31–32 | dutch | 达奇「我们会找到食物」「各位，我们现在安全了」✅ |

**准确率 100%（对照 8 个已知点）**。

### 五个踩坑点（都已解决）

1. 单条对话的 actor 表也可能只有 1 条，且 `h1 != h2` → 不能要求两者相等；
2. 逐句记录的 actor 列**不是固定 +24**：不同对话步长/列位不同 →
   对每个块枚举 (步长 × 列)，取「能对上名字 + 说话人有多个不同值」的那一列
   （只按"能对上名字"会选中"整列都是同一个默认值"的错列，曾把 CABIN 全解成 arthur）；
3. 角色名有 486 个会解成 ped 模型名（`g_m_m_unicriminals_01`），已加中文标签映射（匪徒/守卫/警察…）；
4. 字符串块里同一句可能出现两次 → 需要按 line_key 去重，否则句数与记录数对不上（BANT 曾因此全空）；
5. 句号有空洞（缺字幕，如 1,2,3,5,6,8）→ 记录数要按 `max(句号)` 算，并按句号取列（不是按下标）。

6. 记录数不等于 max(句号)：`RPRSN_PREBOW` 的根块是 12 条记录，但句号只到 11 →
   需把 `max(句号)`、`max+1`、`句数` 都作为候选去试（现在会依次尝试）。

最终：解析 18 051 个对话 / 71 414 句，**58 425 句有角色名（81.8%）**；
我们剧本库 22 529 句有 actor id（98.8%）、19 729 句有名字（86.5%）。
查看器 override **22 424 条（98.3% 台词）**（含 2 513 条「未知角色」——actor id 已解出但名字哈希不在 names.txt），
剧本页 / 任务图 / 剧情回顾 三处均已显示；`conversation_index.csv` 也补上了 actor 列（71 420 行 / 58 046 行有名字）。

### 全量结果

```
解析 .ymt         18 051 / 18 417（98.0%）
台词              71 414 句
带角色名          58 173 句（81.5%）
我们剧本库        22 529 / 22 802 句有 actor id（98.8%）
                  19 729 句有角色名（86.5%）
```

产物：`export/story/conversation_actors.json/.csv/_stats.json`；查看器的
`speaker_overrides.json` 已合并这 21 005 条（优先级：手工/录屏 > .ymt）。

---

## 7. 尚未完成的一层（诚实说明）

**已拿到**：节布局、PMAP、PSCH（结构/枚举/字段/类型/偏移）、字段引用关系。

**未完成**：`PSIN` 实例数据的值解码——特别是：

- `String` 字段存的是「字符串块内偏移 + 长度/标志」的组合值（实测形如 `0x04000005`、`0x08000005`，
  高字节按 4 递增，对应字符串块里的相邻串），需要确认位域；
- `Structure` 字段在实例里是**内联**还是**指向块**（CABIN 的根是 64×56 连续数组，倾向内联）；
- 每条的 **actor 索引** 具体落在哪个字段（`SInt@48` 是当前最强候选，需用你给的
  「第 2 句=苏珊、第 31 句=达奇」做对照校验）。

按 CodeWalker 的 `PsoTypes`/`XmlPso` 继续补这两点即可完成全量 actor 解析。


---

## 8. 收尾：还差什么、为什么

| 项 | 数值 | 原因 |
|---|---|---|
| 全局对话 | 18 051 / 18 417（98.0%） | 366 个 `.ymt` 无成对字符串（非对话资产） |
| 全局台词 | 71 414 句 | — |
| 有角色名 | 58 173（81.5%） | 其余 13 245 句的 actor 哈希不在 names.txt（见下） |
| 我们剧本库 | 22 529 句有 actor id（98.8%） | — |
| 我们剧本库 | 19 729 句有名字（86.5%） | 2 513 句标为「未知角色」 |

**为什么还有 848+ 个 actor 哈希解不出**：抽样 400 个 `.ymt` 里 848 个未解析哈希，
用「names.txt 294 471 条 × 10 种前缀」共 **2 943 609** 个候选做哈希比对，只命中 **1** 个。
说明这批 actor 不是"角色名哈希"，而是另一套命名空间（本地化 key / 角色 GUID）。
要做全，需要那张表（例如 `PERSCHAR` / 角色定义资产），或运行时 hook。

### 一句话

- **能静态解的已经解完**：98% 对话、98.8% 台词都绑到了 actor；86.5% 拿到了角色名；
- 说话人已进 剧本页 / 任务图 / 剧情回顾 三处；
- 剩下 13.5% 是命名空间问题，不是解析问题。
