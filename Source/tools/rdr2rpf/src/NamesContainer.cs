using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;

namespace RDR2_RPF_Tool.Core
{
    // Loads the hash -> asset-name table (names.txt) used to resolve RPF8 hash-keyed entries.
    public static class NamesContainer
    {
        public static Dictionary<uint, string> Names = new Dictionary<uint, string>();

        public static void LoadNames(string path)
        {
            if (!File.Exists(path))
            {
                Console.Error.WriteLine("[names] names.txt not found at " + path + " - entries stay as 0xHASH");
                return;
            }
            int n = 0;
            foreach (string line in File.ReadAllLines(path))
            {
                if (string.IsNullOrEmpty(line)) continue;
                AddName(line.Replace("%platform%", "x64"));
                AddName(line.Replace("%platform%", "ps4"));
                n++;
            }
            Console.Error.WriteLine($"[names] loaded {n} lines -> {Names.Count} hashes");
        }

        private static void AddName(string name)
        {
            uint h = JOAATHash.Calc(name);
            if (!Names.ContainsKey(h)) Names.Add(h, name);
        }
    }
}
