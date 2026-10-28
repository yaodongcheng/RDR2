"""
RDR2 .ycd (RSC8 v58 clip dictionary) decoder.
Ports the RAGE animation channel codec (CodeWalker Clip.cs) to pure Python.

Body = file[16:]  (after the 16-byte RSC8 header). RAGE pointers are
0x50000000 + system_offset (graphics base 0x60000000).
"""
import struct, math, sys, os

SYS_BASE = 0x50000000
GFX_BASE = 0x60000000

# ---------------------------------------------------------------- bit reader
class DataReader:
    def __init__(self, data, num_frames, chunk_size, frame_offset, frame_length):
        self.data = data
        self.num_frames = num_frames
        self.chunk_size = chunk_size
        self.position = 0
        self.frame = 0
        self.frame_offset = frame_offset
        self.frame_length = frame_length
        self.channel_list_offset = frame_offset + frame_length * num_frames
        self.channel_data_offset = self.channel_list_offset + 9 * 2
        self.channel_frame_offset = 0
        self.bit_position = 0

    def rd_i32(self):
        v = struct.unpack_from('<i', self.data, self.position)[0]; self.position += 4; return v

    def rd_f32(self):
        v = struct.unpack_from('<f', self.data, self.position)[0]; self.position += 4; return v

    def rd_vec3(self):
        v = struct.unpack_from('<3f', self.data, self.position); self.position += 12; return v

    def _get_bits(self, start_bit, length):
        if start_bit < 0:
            return 0
        start_byte = start_bit // 8
        bit_offset = start_bit % 8
        result = 0
        shift = -bit_offset
        cur = start_byte
        rem = length
        n = len(self.data)
        while rem > 0:
            b = self.data[cur] if cur < n else 0
            cur += 1
            if shift < 0:
                sb = (b >> (-shift)) & 0xFFFFFFFF
            else:
                sb = (b << shift) & 0xFFFFFFFF
            bm = ((1 << min(rem, 8)) - 1) << max(shift, 0)
            result = (result + (sb & bm)) & 0xFFFFFFFF
            rem -= (8 + min(shift, 0))
            shift += 8
        return result

    def read_bits(self, length):
        v = self._get_bits(self.bit_position, length); self.bit_position += length; return v

    def read_channel_count(self):
        v = struct.unpack_from('<H', self.data, self.channel_list_offset)[0]
        self.channel_list_offset += 2; return v

    def read_channel_data_bits(self):
        v = struct.unpack_from('<H', self.data, self.channel_data_offset)[0]
        self.channel_data_offset += 2; return v

    def read_channel_data_bytes(self, n):
        r = self.data[self.channel_data_offset:self.channel_data_offset+n]
        self.channel_data_offset += n; return r

    def align_channel_data_offset(self, count):
        rem = count % 4
        if rem > 0:
            self.channel_data_offset += (4 - rem) * 2

    def begin_frame(self, f):
        self.frame = f
        self.channel_frame_offset = (self.frame_offset + self.frame_length * f) * 8

    def read_frame_bits(self, n):
        v = self._get_bits(self.channel_frame_offset, n); self.channel_frame_offset += n; return v


# ---------------------------------------------------------------- channels
C_STATIC_QUAT, C_STATIC_VEC3, C_STATIC_FLOAT, C_RAW_FLOAT, C_QUANT_FLOAT, \
C_IND_QUANT_FLOAT, C_LINEAR_FLOAT, C_CACHED_Q1, C_CACHED_Q2 = range(9)


class Channel:
    def __init__(self, typ):
        self.typ = typ
        self.sequence = 0
        self.index = 0
        self.frame_offset = 0
        self.quat_index = 0
        self.reader = None
        self.values = None

    def read(self, r):
        pass

    def read_frame(self, r):
        pass

    def frame_bits(self):
        return 0

    def eval_float(self, frame):
        return 0.0


class ChStaticFloat(Channel):
    def __init__(self): Channel.__init__(self, C_STATIC_FLOAT)
    def read(self, r): self.v = r.rd_f32()
    def eval_float(self, f): return self.v


class ChStaticVec3(Channel):
    def __init__(self): Channel.__init__(self, C_STATIC_VEC3)
    def read(self, r): self.v = r.rd_vec3()
    def eval_float(self, f): return 0.0


class ChStaticQuat(Channel):
    def __init__(self): Channel.__init__(self, C_STATIC_QUAT)
    def read(self, r):
        x, y, z = r.rd_vec3()
        w = math.sqrt(max(1.0 - (x*x+y*y+z*z), 0.0))
        self.q = (x, y, z, w)
    def eval_float(self, f): return 0.0


class ChRawFloat(Channel):
    def __init__(self): Channel.__init__(self, C_RAW_FLOAT)
    def read(self, r): self.values = [0.0]*r.num_frames
    def frame_bits(self): return 32
    def read_frame(self, r):
        bits = r.read_frame_bits(32)
        self.values[r.frame] = struct.unpack('<f', struct.pack('<I', bits))[0]
    def eval_float(self, f):
        return self.values[f % len(self.values)] if self.values else 0.0


class ChQuantizeFloat(Channel):
    def __init__(self): Channel.__init__(self, C_QUANT_FLOAT)
    def read(self, r):
        self.value_bits = r.rd_i32(); self.quantum = r.rd_f32(); self.offset = r.rd_f32()
        self.values = [0.0]*r.num_frames
    def frame_bits(self): return self.value_bits
    def read_frame(self, r):
        bits = r.read_frame_bits(self.value_bits)
        self.values[r.frame] = bits * self.quantum + self.offset
    def eval_float(self, f):
        return self.values[f % len(self.values)] if self.values else self.offset


class ChIndirectQuantizeFloat(Channel):
    def __init__(self): Channel.__init__(self, C_IND_QUANT_FLOAT)
    def read(self, r):
        self._fbits = r.rd_i32(); self.value_bits = r.rd_i32(); self.num_ints = r.rd_i32()
        self.quantum = r.rd_f32(); self.offset = r.rd_f32()
        self.frames = [0]*r.num_frames
        num_values0 = (self.num_ints * 32) // self.value_bits if self.value_bits else 0
        num_values1 = (1 << self._fbits) - 1
        num_values = min(num_values0, num_values1)
        self.values = [0.0]*num_values
        r.bit_position = r.position * 8
        for i in range(num_values):
            b = r.read_bits(self.value_bits)
            self.values[i] = b * self.quantum + self.offset
        r.position += self.num_ints * 4
    def frame_bits(self): return self._fbits
    def read_frame(self, r): self.frames[r.frame] = r.read_frame_bits(self._fbits)
    def eval_float(self, f):
        if self.frames: return self.values[self.frames[f % len(self.frames)]]
        return self.offset


class ChLinearFloat(Channel):
    def __init__(self): Channel.__init__(self, C_LINEAR_FLOAT)
    def read(self, r):
        self.num_ints = r.rd_i32(); counts = r.rd_i32()
        self.quantum = r.rd_f32(); self.offset = r.rd_f32()
        self.bit = r.position * 8
        c1 = counts & 0xFF; c2 = (counts >> 8) & 0xFF; c3 = (counts >> 16) & 0xFF
        stream_len = len(r.data) * 8
        num_frames = r.num_frames
        chunk = r.chunk_size
        num_chunks = (chunk + num_frames - 1) // chunk if chunk else 0
        delta_offset = self.bit + num_chunks * (c1 + c2)
        r.bit_position = self.bit
        chunk_offsets = [0]*num_chunks; chunk_values = [0]*num_chunks
        frame_values = [0.0]*num_frames
        if c1 > 0:
            for i in range(num_chunks): chunk_offsets[i] = r.read_bits(c1)
        if c2 > 0:
            for i in range(num_chunks): chunk_values[i] = r.read_bits(c2)
        for i in range(num_chunks):
            doffs = chunk_offsets[i] + delta_offset
            value = chunk_values[i]
            cframe = i * chunk
            r.bit_position = doffs
            inc = 0
            for j in range(chunk):
                frame = cframe + j
                if frame >= num_frames: break
                frame_values[frame] = value * self.quantum + self.offset
                if (j + 1) >= chunk: break
                delta = r.read_bits(c3) if c3 != 0 else 0
                so = r.bit_position
                maxso = stream_len
                b = 0
                while b == 0:
                    b = r.read_bits(1)
                    if r.bit_position >= maxso: break
                delta |= ((r.bit_position - so - 1) << c3)
                if delta != 0:
                    sign = r.read_bits(1)
                    if sign == 1: delta = -delta
                inc += delta
                value += inc
        self.values = frame_values
        r.position -= 16
        r.position += self.num_ints * 4
    def eval_float(self, f):
        return self.values[f % len(self.values)] if self.values else 0.0


class ChCachedQuat(Channel):
    def __init__(self, typ): Channel.__init__(self, typ)
    def read(self, r): self.reader = r
    def frame_bits(self): return 0
    def eval_float(self, frame):
        return self._v(frame)
    def _v(self, frame):
        if self._cache is None:
            och = self.reader.sequences[self.sequence].channels
            chans = [och[i] if i < len(och) else None for i in range(4) if i != 3][:3]
            n = self.reader.num_frames
            cache = []
            for i in range(n):
                x = chans[0].eval_float(i) if chans[0] is not None else 0.0
                y = chans[1].eval_float(i) if chans[1] is not None else 0.0
                z = chans[2].eval_float(i) if chans[2] is not None else 0.0
                cache.append(math.sqrt(max(1.0 - (x*x+y*y+z*z), 0.0)))
            self._cache = cache
        return self._cache[frame % len(self._cache)]
    _cache = None


CHANNEL_CLASSES = {
    C_STATIC_QUAT: ChStaticQuat, C_STATIC_VEC3: ChStaticVec3, C_STATIC_FLOAT: ChStaticFloat,
    C_RAW_FLOAT: ChRawFloat, C_QUANT_FLOAT: ChQuantizeFloat,
    C_IND_QUANT_FLOAT: ChIndirectQuantizeFloat, C_LINEAR_FLOAT: ChLinearFloat,
}


def construct_channel(typ):
    if typ == C_CACHED_Q1: return ChCachedQuat(C_CACHED_Q1)
    if typ == C_CACHED_Q2: return ChCachedQuat(C_CACHED_Q2)
    cls = CHANNEL_CLASSES.get(typ)
    return cls() if cls else None


class AnimSequence:
    def __init__(self):
        self.channels = []
        self.is_type7_quat = False
    def evaluate_quat(self, frame):
        def ev(c):
            return c.eval_float(frame) if c is not None else 0.0
        if self.is_type7_quat:
            t7 = None
            for c in self.channels:
                if isinstance(c, ChCachedQuat): t7 = c; break
            x = ev(self.channels[0]) if len(self.channels) > 0 else 0.0
            y = ev(self.channels[1]) if len(self.channels) > 1 else 0.0
            z = ev(self.channels[2]) if len(self.channels) > 2 else 0.0
            n = t7.eval_float(frame) if t7 is not None else 0.0
            # ★ 2026-10-17 修正：RDR2 的缓存四元数是 (x, y, z, 缓存值=w)，
            #   `quat_index` **不是**"缺失分量该插在哪一位"。按 CodeWalker 的 quat_index 摆放
            #   会把"三个显式分量全 0、缓存 = 1"的骨解成 (0,0,1,0) 这种 180° 翻转
            #   （实测：idle 的 SKEL_R_Clavicle / walk 的 SKEL_Spine6、SKEL_R_Forearm …，
            #    症状是整段骨架 head.z 0.65→0.35、手臂横张）。
            #   改成恒按 (x,y,z,w) 后 idle/walk 立刻直立。
            if QUAT_INDEX_MODE == 'cw':
                qi = t7.quat_index if t7 is not None else 3
                if qi == 0: q = (n, x, y, z)
                elif qi == 1: q = (x, n, y, z)
                elif qi == 2: q = (x, y, n, z)
                else: q = (x, y, z, n)
            else:
                q = (x, y, z, n)
            return _qnorm(q)
        # generic: gather 4 floats
        v = [0.0, 0.0, 0.0, 0.0]; c = 0
        for ch in self.channels:
            if c >= 4: break
            if ch is None:
                c += 1; continue
            if isinstance(ch, ChStaticVec3):
                for n in range(3):
                    if c + n >= 4: break
                    v[c+n] = ch.v[n]
                c += 3
            elif isinstance(ch, ChStaticQuat):
                for n in range(4):
                    if c + n >= 4: break
                    v[c+n] = ch.q[n]
                c += 4
            else:
                v[c] = ch.eval_float(frame); c += 1
        return tuple(v)


def _qnorm(q):
    n = math.sqrt(sum(c*c for c in q))
    return tuple(c/n for c in q) if n > 1e-9 else (0, 0, 0, 1)


def parse_sequence(data, num_frames, chunk_size, frame_offset, frame_length):
    r = DataReader(data, num_frames, chunk_size, frame_offset, frame_length)
    channel_list = []
    channel_lists = [None]*9
    frame_offset_acc = 0
    for i in range(9):
        count = r.read_channel_count()
        chans = [None]*count
        for c in range(count):
            ch = construct_channel(i)
            cdb = r.read_channel_data_bits()
            if ch is not None:
                ch.read(r)
                seq = cdb >> 2
                idx = cdb & 3
                if isinstance(ch, ChCachedQuat):
                    ch.quat_index = idx
                    idx = 3 if ch.typ == C_CACHED_Q1 else 4
                ch.sequence = seq; ch.index = idx
                channel_list.append(ch)
                ch.frame_offset = frame_offset_acc
                frame_offset_acc += ch.frame_bits()
            chans[c] = ch
        r.align_channel_data_offset(count)
        channel_lists[i] = chans
    for f in range(num_frames):
        r.begin_frame(f)
        for i in range(9):
            for ch in channel_lists[i]:
                if ch is not None: ch.read_frame(r)
    if not channel_list:
        return []
    nseq = max(c.sequence for c in channel_list) + 1
    seqs = [AnimSequence() for _ in range(nseq)]
    for i in range(nseq):
        this = [c for c in channel_list if c.sequence == i]
        if not this:
            continue
        m = max(c.index for c in this) + 1
        chans = [None]*m
        for j in range(m):
            for c in this:
                if c.index == j: chans[j] = c; break
        seqs[i].channels = chans
        if any(chans):
            for ch in chans:
                # ★ 2026-10-16 修正：CachedQ2(type8) 与 CachedQ1(type7) 走**同一条**缓存四元数路径
                #   （只存 3 分量 + w 由模长补全）。原先只认 Q1 ⇒ Q2 的骨回落到"通用路径"，
                #   把 3 个量化的**位移**浮点当成 x,y,z ⇒ |q|≈0.18 被导出器当成"非四元数"丢掉。
                #   实测 `SKEL_L_Thigh`(tag 65478) 正是 Q2 形式 ⇒ 一直被误杀。
                if isinstance(ch, ChCachedQuat):
                    seqs[i].is_type7_quat = True
    r.sequences = seqs
    return seqs
