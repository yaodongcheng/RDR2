"""Parse RDR2 .ytyp (RAGE Meta) -> {archetypeHash: (minx,miny,minz,maxx,maxy,maxz)}"""
import struct, sys, os, json, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rage_meta import parse, SYS

def archetype_struct(d, structs):
    best=None
    for nh,nm,size,cnt,ep in structs:
        offs={}
        for e in range(cnt):
            o=(ep-SYS)+e*16
            _,doff,dt=struct.unpack_from('<iiB',d,o)
            offs.setdefault(doff,set()).add(dt)
        # archetype: float3 @32, float3 @48, Hash @88, Hash @112
        if 32 in offs and 0x33 in offs[32] and 48 in offs and 0x33 in offs[48] and 88 in offs and 0x4A in offs[88]:
            if best is None or size<best[1]: best=(nh,size)
    return best

def scan(root):
    out={}
    files=glob.glob(os.path.join(root,'**','*.ytyp'),recursive=True)
    got=0
    for f in files:
        try:
            d=open(f,'rb').read()[16:]
            structs,blocks=parse(d)
        except Exception:
            continue
        nh,size=archetype_struct(d,structs)
        if nh is None: continue
        for bnh,dl,dp in blocks:
            if bnh==nh and size and dl>=size and dl%size==0:
                base=dp-SYS
                for i in range(dl//size):
                    o=base+i*size
                    h1=struct.unpack_from('<I',d,o+88)[0]
                    h2=struct.unpack_from('<I',d,o+112)[0]
                    mnx,mny,mnz=struct.unpack_from('<3f',d,o+32)
                    mxx,mxy,mxz=struct.unpack_from('<3f',d,o+48)
                    for h in (h1,h2):
                        if h: out.setdefault(h,[round(mnx,2),round(mny,2),round(mnz,2),round(mxx,2),round(mxy,2),round(mxz,2)])
                got+=1
    print(f"parsed {got} ytyp files with archetypes -> {len(out)} archetype hashes")
    return out

if __name__=='__main__':
    root=sys.argv[1]; out=sys.argv[2]
    m=scan(root)
    json.dump({str(k):v for k,v in m.items()}, open(out,'w'), separators=(',',':'))
    print("wrote",out)
