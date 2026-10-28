using System;
using System.IO;
using System.Linq;
using System.Text;
using System.Collections.Generic;
using CodeWalker.GameFiles;

// 通用 PSIN(.ymt/.meta PSO) 结构 + 数据导出器。
// 用法: pso_xml <in.ymt> <out.txt>
// 输出两段：schema（每个结构的字段/类型/偏移/引用）+ data（每条记录的全部标量字段）
class P
{
    static uint J(string s){uint h=0;foreach(char c in s.ToLower()){h+=(byte)c;h+=h<<10;h^=h>>6;}h+=h<<3;h^=h>>11;h+=h<<15;return h;}
    static Dictionary<uint,string> Nm=new();
    static string N(uint h){ if(Nm.TryGetValue(h,out var s))return s; var e=((MetaName)h).ToString(); return e==h.ToString()?("0x"+h.ToString("X8")):e; }

    static void Main(string[] a)
    {
        foreach (var l in File.ReadLines(@"D:/BrainMaker/大镖客2解包分析/tools/rdr2rpf/bin/Release/net9.0/names.txt"))
        { var n=l.Trim(); if(n.Length==0) continue; var h=J(n); if(!Nm.ContainsKey(h)) Nm[h]=n; }

        var p = new PsoFile();
        p.Load(File.ReadAllBytes(a[0]));
        var data = p.DataSection.Data;
        var sb = new StringBuilder();

        // ---- schema
        var structs = new Dictionary<uint, PsoStructureInfo>();
        for (int i = 0; i < p.SchemaSection.Entries.Length; i++)
            if (p.SchemaSection.Entries[i] is PsoStructureInfo si) structs[(uint)si.IndexInfo.NameHash] = si;

        sb.AppendLine("# SCHEMA structures=" + structs.Count);
        foreach (var kv in structs.OrderByDescending(k => k.Value.StructureLength))
        {
            var si = kv.Value;
            sb.AppendLine($"STRUCT {N(kv.Key)} size={si.StructureLength} fields={si.Entries.Length}");
            foreach (var f in si.Entries)
                sb.AppendLine($"   +{f.DataOffset,-5} {f.Type,-10} {N((uint)f.EntryNameHash),-38} ref=0x{f.ReferenceKey:X8} {N(f.ReferenceKey)}");
        }

        // ---- data map
        sb.AppendLine();
        sb.AppendLine("# DATA entries=" + p.DataMapSection.Entries.Length);
        for (int mi = 0; mi < p.DataMapSection.Entries.Length; mi++)
        {
            var e = p.DataMapSection.Entries[mi];
            var tn = N((uint)e.NameHash);
            structs.TryGetValue((uint)e.NameHash, out var si);
            int len = si?.StructureLength ?? 0;
            int count = len > 0 ? e.Length / len : 0;
            sb.AppendLine($"BLOCK[{mi}] {tn} off={e.Offset} bytes={e.Length} structLen={len} count={count}");
        }

        // ---- 逐条记录导出（挑有 Name 字段的结构；没有就导最大的那个）
        PsoStructureInfo best = null; int bestIdx = -1;
        for (int mi = 0; mi < p.DataMapSection.Entries.Length; mi++)
        {
            var e = p.DataMapSection.Entries[mi];
            if (!structs.TryGetValue((uint)e.NameHash, out var si)) continue;
            if (si.Entries.Any(f => N((uint)f.EntryNameHash) == "Name")) { best = si; bestIdx = mi; break; }
        }
        if (best == null)
        {
            for (int mi = 0; mi < p.DataMapSection.Entries.Length; mi++)
            {
                var e = p.DataMapSection.Entries[mi];
                if (!structs.TryGetValue((uint)e.NameHash, out var si)) continue;
                if (si.StructureLength <= 0) continue;
                if (best == null || si.StructureLength > best.StructureLength) { best = si; bestIdx = mi; }
            }
        }
        if (best != null)
        {
            var e = p.DataMapSection.Entries[bestIdx];
            int count = e.Length / best.StructureLength;
            var nameF = best.Entries.FirstOrDefault(f => N((uint)f.EntryNameHash) == "Name");
            sb.AppendLine();
            sb.AppendLine($"# RECORDS struct={N((uint)e.NameHash)} count={count}");
            var cols = new List<string>();
            foreach (var f in best.Entries)
                if (f.Type != PsoDataType.Array && f.Type != PsoDataType.Structure && f.Type != PsoDataType.Map)
                    cols.Add(N((uint)f.EntryNameHash));
            sb.AppendLine("idx,name," + string.Join(",", cols));
            int limit = Math.Min(count, 4000);
            for (int i = 0; i < limit; i++)
            {
                int b = e.Offset + i * best.StructureLength;
                var line = new StringBuilder();
                string nmv = "";
                if (nameF != null && b + nameF.DataOffset + 4 <= data.Length)
                {
                    uint h = BitConverter.ToUInt32(data, b + nameF.DataOffset);
                    nmv = N(h);
                }
                line.Append(i).Append(',').Append(nmv.Replace(",", ";"));
                foreach (var f in best.Entries)
                {
                    if (f.Type == PsoDataType.Array || f.Type == PsoDataType.Structure || f.Type == PsoDataType.Map) continue;
                    int o = b + f.DataOffset;
                    if (o + 4 > data.Length) { line.Append(','); continue; }
                    string v;
                    switch (f.Type)
                    {
                        case PsoDataType.Bool: v = (data[o] != 0).ToString(); break;
                        case PsoDataType.UByte: v = data[o].ToString(); break;
                        case PsoDataType.SByte: v = ((sbyte)data[o]).ToString(); break;
                        case PsoDataType.UShort: v = BitConverter.ToUInt16(data, o).ToString(); break;
                        case PsoDataType.SShort: v = BitConverter.ToInt16(data, o).ToString(); break;
                        case PsoDataType.UInt: v = BitConverter.ToUInt32(data, o).ToString(); break;
                        case PsoDataType.SInt: v = BitConverter.ToInt32(data, o).ToString(); break;
                        case PsoDataType.Float:
                        case PsoDataType.HFloat:
                            v = BitConverter.ToSingle(data, o).ToString("0.####"); break;
                        case PsoDataType.Float2:
                            v = BitConverter.ToSingle(data, o).ToString("0.###") + "|" + BitConverter.ToSingle(data, o + 4).ToString("0.###"); break;
                        case PsoDataType.Float3:
                        case PsoDataType.Float3a:
                            v = BitConverter.ToSingle(data, o).ToString("0.###") + "|" + BitConverter.ToSingle(data, o + 4).ToString("0.###") + "|" + BitConverter.ToSingle(data, o + 8).ToString("0.###"); break;
                        case PsoDataType.Float4:
                        case PsoDataType.Float4a:
                            v = BitConverter.ToSingle(data, o).ToString("0.###") + "|" + BitConverter.ToSingle(data, o + 4).ToString("0.###") + "|" + BitConverter.ToSingle(data, o + 8).ToString("0.###") + "|" + BitConverter.ToSingle(data, o + 12).ToString("0.###"); break;
                        case PsoDataType.String:
                            { uint h = BitConverter.ToUInt32(data, o); v = N(h); } break;
                        default: v = BitConverter.ToUInt32(data, o).ToString(); break;
                    }
                    line.Append(',').Append(v);
                }
                sb.AppendLine(line.ToString());
            }
        }

        // --- 调试：前 3 条记录逐字节差异定位
        if (a.Length > 2 && a[2] == "--raw")
        {
            for (int mi = 0; mi < p.DataMapSection.Entries.Length; mi++)
            {
                var e2 = p.DataMapSection.Entries[mi];
                if (!structs.TryGetValue((uint)e2.NameHash, out var s2)) continue;
                if (s2.StructureLength <= 0 || e2.Length / s2.StructureLength < 2) continue;
                int n2 = e2.Length / s2.StructureLength;
                var sb2 = new StringBuilder();
                int diffs = 0;
                for (int o = 0; o < s2.StructureLength; o++)
                {
                    byte b0 = data[e2.Offset + o];
                    byte b1 = data[e2.Offset + s2.StructureLength + o];
                    if (b0 != b1) { diffs++; if (diffs <= 40) sb2.Append(o).Append(": ").Append(b0).Append("->").Append(b1).Append("  "); }
                }
                Console.WriteLine($"[{N((uint)e2.NameHash)}] n={n2} len={s2.StructureLength} diffBytes={diffs}");
                Console.WriteLine("   " + sb2.ToString());
            }
            return;
        }

        File.WriteAllText(a[1], sb.ToString(), new UTF8Encoding(false));
        Console.WriteLine("ok " + a[1]);
    }
}
