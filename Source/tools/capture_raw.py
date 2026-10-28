"""按地址连续采样一段内存（用于抓活的 pose 数组：不带骨名，不能靠骨名定位）。"""
import argparse, importlib.util, os, struct, time
spec = importlib.util.spec_from_file_location('cap', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'capture_john_walk.py'))
cap = importlib.util.module_from_spec(spec); spec.loader.exec_module(cap)

ap = argparse.ArgumentParser()
ap.add_argument('--addr', required=True)
ap.add_argument('--tag', default='raw')
ap.add_argument('--follow', type=int, default=200)
ap.add_argument('--interval', type=float, default=0.1)
ap.add_argument('--bytes', type=lambda x: int(x, 0), default=0x800, help='每次采样字节数')
a = ap.parse_args()

p = cap.Proc(cap.find_pid())
addr = int(a.addr, 0)
outdir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'work', 'npc', 'live')
os.makedirs(outdir, exist_ok=True)
ts = time.strftime('%H%M%S')
binp = os.path.join(outdir, '%s_%s.bin' % (a.tag, ts))
meta = os.path.join(outdir, '%s_%s.json' % (a.tag, ts))
n_ok = 0
with open(binp, 'wb') as f:
    for i in range(a.follow):
        b = p.read(addr, a.bytes)
        if b:
            f.write(b.ljust(a.bytes, b'\x00'))
            n_ok += 1
        time.sleep(a.interval)
import json
json.dump(dict(addr=addr, bytes=a.bytes, samples=n_ok, interval=a.interval), open(meta, 'w'))
print('写出 %s（%d 次 × %d 字节）' % (binp, n_ok, a.bytes))
p.close()
