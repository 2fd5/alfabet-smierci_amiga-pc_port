"""CrunchMania (CrM! / CrM2) decruncher, pure Python.

Format: 'CrM!' | u16 ? | u32 raw_len | u32 packed_len | packed stream.
The stream is read backwards in big-endian 16-bit words, bits LSB first,
and the output is written backwards. The last 6 bytes of the stream hold
the initial bit buffer (u32) and its fill level (u16).
"""
import struct
import sys


class BitReader:
    def __init__(self, data, start, end):
        self.data = data
        self.start = start
        self.pos = end - 6
        content, shift = struct.unpack(">IH", data[self.pos:self.pos + 6])
        self.bits = content >> (16 - shift) if shift <= 16 else content
        self.nbits = shift + 16

    def _refill(self):
        if self.pos - 2 < self.start:
            raise ValueError("input underrun")
        self.pos -= 2
        word = (self.data[self.pos] << 8) | self.data[self.pos + 1]
        self.bits |= word << self.nbits
        self.nbits += 16

    def read(self, count):
        while self.nbits < count:
            self._refill()
        val = self.bits & ((1 << count) - 1)
        self.bits >>= count
        self.nbits -= count
        return val

    def bit(self):
        return self.read(1)


def _huff(reader, table):
    """table: dict {(length, code): value}, codes read MSB first."""
    code = 0
    length = 0
    while True:
        code = (code << 1) | reader.bit()
        length += 1
        if (length, code) in table:
            return table[(length, code)]
        if length > 16:
            raise ValueError("bad huffman code")


def _read_lzh_table(reader, code_len):
    max_depth = reader.read(4)
    if not max_depth:
        raise ValueError("bad lzh table")
    counts = [reader.read(min(i + 1, code_len)) for i in range(max_depth)]
    table = {}
    code = 0
    for depth in range(1, max_depth + 1):
        for _ in range(counts[depth - 1]):
            value = reader.read(code_len)
            table[(depth, code >> (max_depth - depth))] = value
            code += 1 << (max_depth - depth)
    return table


LEN_TABLE = {(1, 0b0): 0, (2, 0b10): 1, (3, 0b110): 2, (3, 0b111): 3}
DIST_TABLE = {(1, 0b0): 0, (2, 0b10): 1, (2, 0b11): 2}
LEN_BITS = (1, 2, 4, 8)
LEN_ADD = (2, 4, 8, 24)
DIST_BITS = (9, 5, 14)
DIST_ADD = (32, 0, 544)


def decrunch(buf, offset=0):
    magic = buf[offset:offset + 4]
    if magic not in (b"CrM!", b"CrM2"):
        raise ValueError(f"not CrunchMania: {magic!r}")
    raw_len, packed_len = struct.unpack(">II", buf[offset + 6:offset + 14])
    start = offset + 14
    reader = BitReader(buf, start, start + packed_len)
    out = bytearray(raw_len)
    op = raw_len

    def copy(dist, count):
        nonlocal op
        if count > op:
            raise ValueError("output overrun")
        for _ in range(count):
            op -= 1
            if op + dist >= raw_len:
                raise ValueError("bad distance")
            out[op] = out[op + dist]

    if magic == b"CrM!":
        while op > 0:
            if reader.bit():
                op -= 1
                out[op] = reader.read(8)
                continue
            li = _huff(reader, LEN_TABLE)
            count = reader.read(LEN_BITS[li]) + LEN_ADD[li]
            if count == 23:
                count = reader.read(5) + 15 if reader.bit() else reader.read(14) + 15
                if count > op:
                    raise ValueError("literal run overrun")
                for _ in range(count):
                    op -= 1
                    out[op] = reader.read(8)
            else:
                if count > 23:
                    count -= 1
                di = _huff(reader, DIST_TABLE)
                dist = reader.read(DIST_BITS[di]) + DIST_ADD[di]
                copy(dist, count)
    else:
        while True:
            ltab = _read_lzh_table(reader, 9)
            dtab = _read_lzh_table(reader, 4)
            for _ in range(reader.read(16) + 1):
                sym = _huff(reader, ltab)
                if sym & 0x100:
                    op -= 1
                    out[op] = sym & 0xFF
                else:
                    db = _huff(reader, dtab)
                    dist = (reader.read(1) + 1) if not db else ((reader.read(db) | (1 << db)) + 1)
                    copy(dist, sym + 3)
            if not reader.bit():
                break
    return bytes(out), reader.pos - start


def main():
    path, off = sys.argv[1], int(sys.argv[2], 0)
    data = open(path, "rb").read()
    out, left = decrunch(data, off)
    print(f"ok raw={len(out)} unread_input_bytes={left}")
    if len(sys.argv) > 3:
        open(sys.argv[3], "wb").write(out)


if __name__ == "__main__":
    main()
