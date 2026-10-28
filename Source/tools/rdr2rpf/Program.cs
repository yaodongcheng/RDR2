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
