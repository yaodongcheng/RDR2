using System;using System.IO;using System.Text;using CodeWalker.GameFiles;
class P{
 static string S(byte[] d,uint off){ if(off>=d.Length) return "<"+off+">"; int e=(int)off; while(e<d.Length && d[e]!=0) e++; return Encoding.UTF8.GetString(d,(int)off,e-(int)off); }
 static void Main(string[] a){
  var p=new PsoFile(); p.Load(File.ReadAllBytes(a[0])); var d=p.DataSection.Data;
  var e0=p.DataMapSection.Entries[0]; int n=e0.Length/56;
  Console.WriteLine("lines="+n);
  for(int i=0;i<n;i++){int b=e0.Offset+i*56;Console.WriteLine($"[{i}] u24={BitConverter.ToUInt32(d,b+24)} u28={BitConverter.ToUInt32(d,b+28)} e16={BitConverter.ToUInt32(d,b+16):X8} e40={BitConverter.ToUInt32(d,b+40):X8}");}
  var e3=p.DataMapSection.Entries[3]; Console.WriteLine("speakers="+(e3.Length/16));
  for(int i=0;i<e3.Length/16;i++){int b=e3.Offset+i*16;Console.WriteLine($"  id={BitConverter.ToInt32(d,b+4)} hash={BitConverter.ToUInt32(d,b):X8} hash2={BitConverter.ToUInt32(d,b+8):X8} u12={BitConverter.ToUInt32(d,b+12):X8}");}
 }
}
