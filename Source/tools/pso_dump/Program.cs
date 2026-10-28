using System;using System.IO;using System.Linq;using System.Text;using System.Collections.Generic;using CodeWalker.GameFiles;
class P{
 static uint J(string s){uint h=0;foreach(char c in s.ToLower()){h+=(byte)c;h+=h<<10;h^=h>>6;}h+=h<<3;h^=h>>11;h+=h<<15;return h;}
 static Dictionary<uint,string> Nm=new();
 static string N(uint h){if(Nm.TryGetValue(h,out var s))return s;var e=((MetaName)h).ToString();return e==h.ToString()?("0x"+h.ToString("X8")):e;}
 static void Main(string[] a){
  foreach(var l in File.ReadLines(@"D:/BrainMaker/大镖客2解包分析/tools/rdr2rpf/bin/Release/net9.0/names.txt")){var n=l.Trim();if(n.Length==0)continue;var h=J(n);if(!Nm.ContainsKey(h))Nm[h]=n;}
  var p=new PsoFile();p.Load(File.ReadAllBytes(a[0]));var data=p.DataSection.Data;
  var types=new Dictionary<uint,PsoStructureInfo>();
  for(int i=0;i<p.SchemaSection.Entries.Length;i++) if(p.SchemaSection.Entries[i] is PsoStructureInfo si) types[(uint)si.IndexInfo.NameHash]=si;
  var sb=new StringBuilder();sb.AppendLine("map_index,type,entry,name_hash,name,model_hash,model,extra_hash,extra");
  int total=0;
  for(int mi=0;mi<p.DataMapSection.Entries.Length;mi++){
   var e=p.DataMapSection.Entries[mi];
   if(!types.TryGetValue((uint)e.NameHash,out var si)) continue;
   var fn=si.Entries.FirstOrDefault(f=>N((uint)f.EntryNameHash)=="Name");
   var fm=si.Entries.FirstOrDefault(f=>N((uint)f.EntryNameHash)=="Model");
   if(fn==null||fm==null) continue;
   var fe=si.Entries.FirstOrDefault(f=>N((uint)f.EntryNameHash).StartsWith("0x"));
   int count=e.Length/si.StructureLength;
   for(int i=0;i<count;i++){
    int b=e.Offset+i*si.StructureLength;
    uint nh=BitConverter.ToUInt32(data,b+fn.DataOffset);
    uint mh=BitConverter.ToUInt32(data,b+fm.DataOffset);
    uint eh=fe!=null?BitConverter.ToUInt32(data,b+fe.DataOffset):0;
    sb.AppendLine($"{mi},{N((uint)e.NameHash)},{i},{nh:X8},{N(nh)},{mh:X8},{N(mh)},{eh:X8},{(fe!=null?N(eh):"")}");
    total++;
   }
  }
  File.WriteAllText(a[1],sb.ToString(),new UTF8Encoding(true));
  Console.WriteLine("items "+total);
 }
}
