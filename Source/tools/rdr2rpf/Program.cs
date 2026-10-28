using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using RDR2_RPF_Tool.Core;

namespace Rdr2RpfCli
{
    static class Program
    {
        static int Main(string[] args)
        {
            try { Console.OutputEncoding = System.Text.Encoding.UTF8; } catch { }
            if (args.Length < 1)
            {
                Console.Error.WriteLine("usage: rdr2rpf <list|find|extract|tree> <archive.rpf> [pattern] [outdir]");
                return 1;
            }
            string cmd = args[0].ToLowerInvariant();
            NamesContainer.LoadNames(Path.Combine(AppContext.BaseDirectory, "names.txt"));

            try
            {
                switch (cmd)
                {
                    case "list": return CmdList(args);
                    case "find": return CmdFind(args);
                    case "tree": return CmdTree(args);
                    case "extract": return CmdExtract(args);
                    case "rawdec": return CmdRawDec(args);
                    case "hashindex": return CmdHashIndex(args);
                    case "extracthash": return CmdExtractHash(args);
                    default:
                        Console.Error.WriteLine("unknown command " + cmd);
                        return 1;
                }
            }
            catch (Exception ex)
            {
                Console.Error.WriteLine("[error] " + ex.Message);
                Console.Error.WriteLine(ex.StackTrace);
                return 2;
            }
        }

        static RPF8 Open(string path)
        {
            var r = RPF8.Load(path);
            Console.Error.WriteLine($"[open] {Path.GetFileName(path)} entries={r.header.EntryCount} namesLen={r.header.NamesLength} tag={r.header.DecryptionTag} plat={(int)r.header.PlatformId}");
            return r;
        }

        static IEnumerable<KeyValuePair<string, RPF8.Entry>> Ordered(RPF8 r)
            => r.Entries.OrderByDescending(k => k.Value.GetOnDiskSize());

        static int CmdList(string[] a)
        {
            var r = Open(a[1]);
            foreach (var kv in Ordered(r))
            {
                var e = kv.Value;
                Console.WriteLine($"{e.GetOnDiskSize(),14}  res={(e.IsResource ? 1 : 0)} comp={e.GetCompressorId(),-7} {kv.Key}");
            }
            return 0;
        }

        static int CmdFind(string[] a)
        {
            var r = Open(a[1]);
            string pat = a.Length > 2 ? a[2] : "";
            foreach (var kv in Ordered(r))
            {
                if (pat == "" || kv.Key.ToLowerInvariant().Contains(pat.ToLowerInvariant()))
                    Console.WriteLine($"{kv.Value.GetOnDiskSize(),14}  {kv.Key}");
            }
            return 0;
        }

        static int CmdTree(string[] a)
        {
            var r = Open(a[1]);
            int total = 0, res = 0, rpfs = 0;
            var byExt = new Dictionary<string, int>();
            foreach (var kv in r.Entries)
            {
                var e = kv.Value; total++;
                if (e.IsResource) res++;
                string ext = Path.GetExtension(kv.Key);
                if (string.IsNullOrEmpty(ext)) ext = "(none)";
                byExt[ext] = byExt.ContainsKey(ext) ? byExt[ext] + 1 : 1;
                if (ext == ".rpf") rpfs++;
            }
            Console.WriteLine($"total={total} resource={res} nested_rpf={rpfs}");
            foreach (var k in byExt.OrderByDescending(x => x.Value).Take(60))
                Console.WriteLine($"  {k.Value,8}  {k.Key}");
            return 0;
        }

        static int CmdExtract(string[] a)
        {
            // extract <archive.rpf> <outdir> [pattern] [--recurse]
            string arch = a[1];
            string outdir = a.Length > 2 ? a[2] : "extract_out";
            string pat = a.Length > 3 ? a[3] : "";
            bool recurse = a.Contains("--recurse");
            Directory.CreateDirectory(outdir);
            int n = ExtractArchive(arch, outdir, pat, recurse, 0);
            Console.Error.WriteLine($"[done] wrote {n} files to {outdir}");
            return 0;
        }

        static int ExtractArchive(string archPath, string outdir, string pat, bool recurse, int depth)
        {
            var r = Open(archPath);
            int count = 0;
            foreach (var kv in Ordered(r))
            {
                var e = kv.Value;
                string name = kv.Key;
                string sub = Path.Combine(outdir, name);
                bool match = pat == "" || name.ToLowerInvariant().Contains(pat.ToLowerInvariant());
                bool isRpf = name.EndsWith(".rpf", StringComparison.OrdinalIgnoreCase);

                if (!match && !(recurse && isRpf)) continue;
                if (e.IsSignatureProtected) { Console.Error.WriteLine($"[skip] signature protected {name}"); continue; }

                byte[] bytes;
                try { bytes = r.GetFile(name); }
                catch (Exception ex) { Console.Error.WriteLine($"[warn] {name}: {ex.Message}"); continue; }

                if (isRpf && recurse)
                {
                    // nested archive: write to temp, recurse
                    string tmp = Path.Combine(Path.GetTempPath(), $"nested_{depth}_{Guid.NewGuid():N}.rpf");
                    File.WriteAllBytes(tmp, bytes);
                    string nd = Path.Combine(outdir, Path.GetFileNameWithoutExtension(name) + "_rpf");
                    Directory.CreateDirectory(nd);
                    try { count += ExtractArchive(tmp, nd, pat, recurse, depth + 1); }
                    catch (Exception ex) { Console.Error.WriteLine($"[warn] nested {name}: {ex.Message}"); }
                    finally { try { File.Delete(tmp); } catch { } }
                    if (match) { Directory.CreateDirectory(Path.GetDirectoryName(sub)); File.WriteAllBytes(sub, bytes); count++; }
                    continue;
                }

                Directory.CreateDirectory(Path.GetDirectoryName(sub));
                File.WriteAllBytes(sub, bytes);
                count++;
                if (count % 200 == 0) Console.Error.WriteLine($"[..] {count} files");
            }
            return count;
        }

        // ---------------- hashindex ----------------
        // 递归列出（含嵌套 .rpf：直接在父包内定位 TOC，不解包）所有 drawable 条目：
        //   <archive>  <hash>  <size>  <ext>  <name>
        // 用途：把「场景 archetype hash」直接和 RPF 条目 hash 对撞，不需要名字、
        // 也不需要先把 57 GB 嵌套包全部解出来。
        static int CmdHashIndex(string[] a)
        {
            // hashindex <top.rpf> <out.tsv> [exts=ydr,yft] [maxDepth=6]
            string arch = a[1];
            string outPath = a.Length > 2 ? a[2] : "hashindex.tsv";
            string exts = a.Length > 3 ? a[3] : "ydr,yft";
            int maxDepth = a.Length > 4 ? int.Parse(a[4]) : 6;
            var want = new HashSet<string>(
                exts.Split(new[] { ',', ';', '|' }, StringSplitOptions.RemoveEmptyEntries),
                StringComparer.OrdinalIgnoreCase);

            using var fs = new FileStream(arch, FileMode.Open, FileAccess.Read, FileShare.Read,
                                          1 << 20, FileOptions.RandomAccess);
            using var w = new StreamWriter(outPath, false, new System.Text.UTF8Encoding(false), 1 << 20);
            int done = 0, files = 0;
            var sw = System.Diagnostics.Stopwatch.StartNew();
            IndexArchive(fs, 0, fs.Length, Path.GetFileName(arch), want, w, 0, maxDepth,
                         ref done, ref files, sw);
            w.Flush();
            Console.Error.WriteLine($"[hashindex] archives={done} drawables={files} " +
                                    $"elapsed={sw.Elapsed.TotalSeconds:F0}s -> {outPath}");
            return 0;
        }

        static void IndexArchive(FileStream fs, long baseOff, long avail, string label,
                                 HashSet<string> want, StreamWriter w, int depth, int maxDepth,
                                 ref int done, ref int files, System.Diagnostics.Stopwatch sw)
        {
            done++;
            byte[] hdr = new byte[16];
            if (avail < 16 + 256) return;
            fs.Seek(baseOff, SeekOrigin.Begin);
            if (fs.Read(hdr, 0, 16) != 16) return;
            uint magic = BitConverter.ToUInt32(hdr, 0);
            if (magic != 0x52504638)
            {
                Console.Error.WriteLine($"[hashindex] {label}: not RPF8 (magic={magic:X8})，跳过");
                return;
            }
            int count = BitConverter.ToInt32(hdr, 4);
            int namesLen = BitConverter.ToInt32(hdr, 8);
            ushort tag = BitConverter.ToUInt16(hdr, 12);
            ushort plat = BitConverter.ToUInt16(hdr, 14);
            if (count <= 0 || count > 4_000_000) return;
            long tocLen = (long)count * 24;
            if (16 + 256 + tocLen > avail) return;

            byte[] toc = new byte[tocLen];
            fs.Seek(baseOff + 16 + 256, SeekOrigin.Begin);
            int read = 0;
            while (read < toc.Length)
            {
                int n = fs.Read(toc, read, toc.Length - read);
                if (n <= 0) return;
                read += n;
            }
            if (tag != 255)
            {
                try { toc = Cipher.GetCipher(tag, (Platform)plat).Decode(toc); }
                catch (Exception ex)
                {
                    Console.Error.WriteLine($"[hashindex] {label}: TOC 解密失败 {ex.Message}");
                    return;
                }
            }

            for (int i = 0; i < count; i++)
            {
                ulong v1 = BitConverter.ToUInt64(toc, i * 24);
                ulong v2 = BitConverter.ToUInt64(toc, i * 24 + 8);
                uint hash = (uint)v1;
                byte extId = (byte)((v1 >> 48) & 0xFF);
                bool isRes = ((v1 >> 56) & 1) != 0;
                bool sigProt = ((v1 >> 57) & 1) != 0;
                int size = (int)(v2 & 0xFFFFFFF) << 4;
                long offset = (long)((v2 >> 28) & 0x7FFFFFFF) << 4;
                int comp = (int)((v2 >> 59) & 0x1F);

                string ext = RPFHelper.GetFileExt(extId, (Platform)plat);
                string name = RPFHelper.GetFileName(hash) + ext;
                string bare = name.TrimStart('.').ToLowerInvariant();

                if (ext.Equals(".rpf", StringComparison.OrdinalIgnoreCase))
                {
                    // 嵌套包：未压缩、无签名保护才能原地读 TOC
                    if (depth < maxDepth && comp == 0 && !sigProt && !isRes && size > 0
                        && offset + size <= avail)
                        IndexArchive(fs, baseOff + offset, size, label + "::" + name,
                                     want, w, depth + 1, maxDepth, ref done, ref files, sw);
                    continue;
                }
                if (want.Count > 0 && !want.Contains(ext.TrimStart('.')))
                    continue;
                w.Write(label);
                w.Write('\t');
                w.Write("0x" + hash.ToString("x8"));
                w.Write('\t');
                w.Write(size);
                w.Write('\t');
                w.Write(ext);
                w.Write('\t');
                w.WriteLine(name);
                files++;
                if ((files & 0xFFFF) == 0)
                    Console.Error.WriteLine($"[hashindex] drawables={files} archives={done} " +
                                            $"elapsed={sw.Elapsed.TotalSeconds:F0}s");
            }
        }

        // ---------------- extracthash ----------------
        // 按 **RPF 条目 hash** 递归抽文件（嵌套包原地 TOC，不解整包）。
        //   extracthash <top.rpf> <hashlist.txt> <outdir> [exts=ydr,yft]
        static int CmdExtractHash(string[] a)
        {
            string arch = a[1];
            string listPath = a[2];
            string outdir = a[3];
            string exts = a.Length > 4 ? a[4] : "ydr,yft";
            var want = new HashSet<uint>();
            foreach (var ln in File.ReadAllLines(listPath))
            {
                var t = ln.Trim();
                if (t.Length == 0 || t.StartsWith("#")) continue;
                if (t.StartsWith("0x", StringComparison.OrdinalIgnoreCase)) t = t.Substring(2);
                if (uint.TryParse(t, System.Globalization.NumberStyles.HexNumber,
                                  System.Globalization.CultureInfo.InvariantCulture, out uint hv))
                    want.Add(hv);
            }
            var extSet = new HashSet<string>(exts.Split(','), StringComparer.OrdinalIgnoreCase);
            Directory.CreateDirectory(outdir);
            using var fs = new FileStream(arch, FileMode.Open, FileAccess.Read, FileShare.Read,
                                          1 << 20, FileOptions.RandomAccess);
            int got = 0, seen = 0;
            var sw = System.Diagnostics.Stopwatch.StartNew();
            ExtractHashArchive(fs, 0, fs.Length, Path.GetFileName(arch), want, extSet, outdir,
                               0, 6, ref got, ref seen, sw);
            Console.Error.WriteLine($"[extracthash] matched={got} archives={seen} " +
                                    $"elapsed={sw.Elapsed.TotalSeconds:F0}s");
            return 0;
        }

        struct RpfEnt
        {
            public uint hash;
            public byte extId;
            public bool isRes, sigProt;
            public int size;
            public long offset;
            public int comp;
            public ulong v1, v2, v3;
        }

        static RPF8.Rpf8Header? ReadToc(FileStream fs, long baseOff, long avail, out RpfEnt[] entries)
        {
            entries = null;
            if (avail < 16 + 256) return null;
            byte[] hdr = new byte[16];
            fs.Seek(baseOff, SeekOrigin.Begin);
            if (fs.Read(hdr, 0, 16) != 16) return null;
            if (BitConverter.ToUInt32(hdr, 0) != 0x52504638) return null;
            var h = new RPF8.Rpf8Header
            {
                Magic = 0x52504638,
                EntryCount = BitConverter.ToInt32(hdr, 4),
                NamesLength = BitConverter.ToInt32(hdr, 8),
                DecryptionTag = BitConverter.ToUInt16(hdr, 12),
                PlatformId = (Platform)BitConverter.ToUInt16(hdr, 14)
            };
            if (h.EntryCount <= 0 || h.EntryCount > 4_000_000) return null;
            long tocLen = (long)h.EntryCount * 24;
            if (16 + 256 + tocLen > avail) return null;
            byte[] toc = new byte[tocLen];
            fs.Seek(baseOff + 16 + 256, SeekOrigin.Begin);
            int read = 0;
            while (read < toc.Length)
            {
                int n = fs.Read(toc, read, toc.Length - read);
                if (n <= 0) return null;
                read += n;
            }
            if (h.DecryptionTag != 255)
            {
                try { toc = Cipher.GetCipher(h.DecryptionTag, h.PlatformId).Decode(toc); }
                catch { return null; }
            }
            entries = new RpfEnt[h.EntryCount];
            for (int i = 0; i < h.EntryCount; i++)
            {
                ulong v1 = BitConverter.ToUInt64(toc, i * 24);
                ulong v2 = BitConverter.ToUInt64(toc, i * 24 + 8);
                ulong v3 = BitConverter.ToUInt64(toc, i * 24 + 16);
                entries[i] = new RpfEnt
                {
                    hash = (uint)v1,
                    extId = (byte)((v1 >> 48) & 0xFF),
                    isRes = ((v1 >> 56) & 1) != 0,
                    sigProt = ((v1 >> 57) & 1) != 0,
                    size = (int)(v2 & 0xFFFFFFF) << 4,
                    offset = (long)((v2 >> 28) & 0x7FFFFFFF) << 4,
                    comp = (int)((v2 >> 59) & 0x1F),
                    v1 = v1,
                    v2 = v2,
                    v3 = v3
                };
            }
            return h;
        }

        static void ExtractHashArchive(FileStream fs, long baseOff, long avail, string label,
                                       HashSet<uint> want, HashSet<string> extSet, string outdir,
                                       int depth, int maxDepth, ref int got, ref int seen,
                                       System.Diagnostics.Stopwatch sw)
        {
            seen++;
            var hd = ReadToc(fs, baseOff, avail, out var ent);
            if (hd == null || ent == null) return;
            var h = hd.Value;
            for (int i = 0; i < ent.Length; i++)
            {
                var e = ent[i];
                string ext = RPFHelper.GetFileExt(e.extId, h.PlatformId);
                bool isRpf = ext.Equals(".rpf", StringComparison.OrdinalIgnoreCase);
                if (isRpf)
                {
                    if (depth < maxDepth && e.comp == 0 && !e.sigProt && !e.isRes && e.size > 0
                        && e.offset + e.size <= avail)
                        ExtractHashArchive(fs, baseOff + e.offset, e.size,
                                           label + "::" + RPFHelper.GetFileName(e.hash) + ext,
                                           want, extSet, outdir, depth + 1, maxDepth,
                                           ref got, ref seen, sw);
                    continue;
                }
                if (!want.Contains(e.hash)) continue;
                if (!extSet.Contains(ext.TrimStart('.'))) continue;

                // 与 RPF8.GetFile 同一套解码：签名头 → RSC8 头 → 解密 → 解压 → 重建 RSC8
                long off = baseOff + e.offset;
                int raw = e.size;
                if (e.sigProt) { raw -= 0x100; off += 0x100; }
                if (e.isRes) { off += 16; raw -= 16; }
                if (raw <= 0) continue;
                byte[] buf = new byte[raw];
                fs.Seek(off, SeekOrigin.Begin);
                int rd = 0;
                while (rd < raw)
                {
                    int n = fs.Read(buf, rd, raw - rd);
                    if (n <= 0) break;
                    rd += n;
                }
                if (rd != raw) continue;

                var entry = new RPF8.Entry { platform = h.PlatformId };
                entry.Val1 = e.v1;
                entry.Val2 = e.v2;
                entry.Val3 = e.v3;
                try
                {
                    if (e.isRes || e.comp != 0)
                    {
                        buf = Cipher.DecodeBlock(buf, entry);
                        buf = Compression.DecompressFile(buf, entry.GetOrignalSize(),
                                                         entry.GetCompressorId());
                    }
                    RSC8.CreateRsc8(ref buf, entry, true);
                }
                catch (Exception ex)
                {
                    Console.Error.WriteLine($"[extracthash] 0x{e.hash:x8} 解码失败: {ex.Message}");
                    continue;
                }
                string name = RPFHelper.GetFileName(e.hash) + ext;
                if (name.Contains("/") || name.Contains("\\"))
                    name = name.Replace('/', '_').Replace('\\', '_');
                File.WriteAllBytes(Path.Combine(outdir, name), buf);
                got++;
                if ((got & 0x3F) == 0)
                    Console.Error.WriteLine($"[extracthash] got={got} elapsed={sw.Elapsed.TotalSeconds:F0}s");
            }
        }

        static int CmdRawDec(string[] a)
        {
            byte[] all = File.ReadAllBytes(a[1]);
            uint magic = BitConverter.ToUInt32(all, 0);
            int cnt = BitConverter.ToInt32(all, 4);
            int namesLen = BitConverter.ToInt32(all, 8);
            ushort tag = BitConverter.ToUInt16(all, 12);
            ushort plat = BitConverter.ToUInt16(all, 14);
            Console.WriteLine($"magic={magic:X8} cnt={cnt} namesLen={namesLen} tag={tag} plat={plat}");
            int entriesStart = 16 + 256;
            int n = cnt * 24;
            byte[] ent = new byte[n];
            Array.Copy(all, entriesStart, ent, 0, n);
            byte[] raw = (byte[])ent.Clone();
            byte[] dec = RDR2_RPF_Tool.Core.Cipher.GetCipher(tag, (RDR2_RPF_Tool.Core.Platform)plat).Decode(ent, null, null);
            Console.WriteLine("RAW  : " + BitConverter.ToString(raw, 0, 48).Replace("-", " "));
            Console.WriteLine("DEC  : " + BitConverter.ToString(dec, 0, 48).Replace("-", " "));
            for (int i = 0; i < Math.Min(cnt, 12); i++)
            {
                ulong v1 = BitConverter.ToUInt64(dec, i * 24);
                ulong v2 = BitConverter.ToUInt64(dec, i * 24 + 8);
                ulong v3 = BitConverter.ToUInt64(dec, i * 24 + 16);
                byte ext = (byte)((v1 >> 48) & 0xFF);
                Console.WriteLine($"[{i}] v1={v1:X16} hash={(uint)v1:X8} ext={ext} res={(v1 >> 56) & 1} v2={v2:X16} v3={v3:X16}");
            }
            return 0;
        }

    }
}
