"""The Player 6.0A module -> ProTracker M.K. module (lossless, symbolic).

Port of the "theplayer" depacker from libxmp's ProWizard
(C) 1998-2013 Sylvain 'Asle' Chipaux, modified by Claudio Matsuoka and Alice Rowan,
MIT licence. See CREDITS.md.

The output keeps every note, effect and sample byte; nothing is resampled.
Usage: p60a.py module.bin out.mod
"""
import struct
import sys

# ProTracker period table, octaves 1-3 (+ the extra low/high octaves P60A can address)
PERIODS = [
    1712, 1616, 1525, 1440, 1357, 1281, 1209, 1141, 1077, 1017, 961, 907,
    856, 808, 762, 720, 678, 640, 604, 570, 538, 508, 480, 453,
    428, 404, 381, 360, 339, 320, 302, 285, 269, 254, 240, 226,
    214, 202, 190, 180, 170, 160, 151, 143, 135, 127, 120, 113,
    107, 101, 95, 90, 85, 80, 76, 71, 67, 64, 60, 57,
]
# libxmp's ptk_table index 0 = no note, index 1 = C-0 (period 1712)


def _period(note):
    return PERIODS[note - 1] if 1 <= note <= len(PERIODS) else 0


def _event(c1, c2, c3):
    """Build one 4-byte PT event; returns (bytes, effect)."""
    note = c1 // 2
    period = _period(note)
    hi_ins = (c1 << 4) & 0x10
    eff = c2 & 0x0F
    if eff == 0x08:
        c2 -= 0x08
    if eff in (0x05, 0x06, 0x0A):
        c3 = ((0x100 - c3) << 4) & 0xFF if c3 > 0x7F else c3
    ev = bytes([hi_ins | (period >> 8), period & 0xFF, c2 & 0xFF, c3 & 0xFF])
    return ev, eff


def _decode_patterns(data, base, npat, taddr):
    rows = [[[bytes(4)] * 4 for _ in range(64)] for _ in range(npat)]
    for p in range(npat):
        max_row = 63
        for ch in range(4):
            pos = base + taddr[p][ch]
            k = 0
            while k <= max_row:
                c1, c2, c3 = data[pos], data[pos + 1], data[pos + 2]
                pos += 3
                if c1 & 0x80 and c1 != 0x80:          # note + empty rows / repeats
                    c4 = data[pos]
                    pos += 1
                    c1 = 0xFF - c1
                    ev, eff = _event(c1, c2, c3)
                    rows[p][k][ch] = ev
                    if eff in (0x0D, 0x0B):
                        max_row = k
                        break
                    if c4 < 0x80:
                        k += c4 + 1
                        continue
                    for _ in range(0x100 - c4):
                        k += 1
                        if k >= 64:
                            break
                        rows[p][k][ch] = ev
                    k += 1
                    continue
                if c1 == 0x80:                        # repeat earlier lines
                    c4 = data[pos]
                    pos += 1
                    resume = pos
                    lines = c2
                    rpos = pos - ((c3 << 8) + c4)
                    l = 0
                    stop = False
                    while l <= lines and k < 64:
                        r1, r2, r3 = data[rpos], data[rpos + 1], data[rpos + 2]
                        rpos += 3
                        if r1 & 0x80 and r1 != 0x80:
                            r4 = data[rpos]
                            rpos += 1
                            r1 = 0xFF - r1
                            ev, eff = _event(r1, r2, r3)
                            rows[p][k][ch] = ev
                            if eff in (0x0D, 0x0B):
                                max_row = k
                                stop = True
                                break
                            if r4 < 0x80:
                                k += r4 + 1
                                l += 1
                                continue
                            else:
                                for _ in range(0x100 - r4):
                                    k += 1
                                    if k >= 64:
                                        break
                                    rows[p][k][ch] = ev
                        if k >= 64:
                            break
                        ev, _ = _event(r1, r2, r3)
                        rows[p][k][ch] = ev
                        l += 1
                        k += 1
                    pos = resume
                    if stop:
                        break
                    continue
                ev, eff = _event(c1, c2, c3)               # plain event
                rows[p][k][ch] = ev
                if eff in (0x0D, 0x0B):
                    max_row = k
                    break
                k += 1
    return rows


def convert(data, title=b""):
    sdata, npat, flags = struct.unpack(">HBB", data[:4])
    if flags & 0x40:
        raise ValueError("packed samples not supported")
    delta = bool(flags & 0x80)
    nins = flags & 0x3F
    pos = 4
    out = bytearray(title[:20].ljust(20, b"\0"))
    sizes, addrs, isize = [0] * nins, [0] * nins, [0] * nins
    for i in range(nins):
        size, fine, vol, loop = struct.unpack(">HBBH", data[pos:pos + 6])
        pos += 6
        if size > 0xFF00:
            src = 0xFFFF - size
            sizes[i], isize[i], addrs[i] = sizes[src], isize[src], addrs[src]
        else:
            addrs[i] = addrs[i - 1] + sizes[i - 1] if i else 0
            sizes[i], isize[i] = size * 2, size
        words = sizes[i] // 2
        loop_start, loop_len = (0, 1) if loop == 0xFFFF else (loop, words - loop)
        out += bytes(22) + struct.pack(">HBBHH", isize[i], fine & 0x3F, vol, loop_start, loop_len)
    for _ in range(nins, 31):
        out += bytes(22) + struct.pack(">HBBHH", 0, 0, 0, 0, 1)
    taddr = []
    for _ in range(npat):
        taddr.append(struct.unpack(">4H", data[pos:pos + 8]))
        pos += 8
    order = []
    while len(order) < 128 and data[pos] != 0xFF:
        order.append(data[pos])
        pos += 1
    pos += 1
    out += bytes([len(order), 0x00])  # 0 = restart byte; 0x7F makes OpenMPT assume Scream Tracker quirks
    out += bytes(order).ljust(128, b"\0") + b"M.K."
    for pat in _decode_patterns(data, pos, npat, taddr):
        for row in pat:
            out += b"".join(row)
    for i in range(nins):
        smp = bytearray(data[sdata + addrs[i]:sdata + addrs[i] + sizes[i]])
        if delta:
            for j in range(1, len(smp)):
                smp[j] = (0x100 - smp[j] + smp[j - 1]) & 0xFF
        out += smp
    return bytes(out), {"patterns": npat, "samples": nins, "length": len(order), "delta": delta,
                        "sample_bytes": sum(sizes[i] for i in range(nins) if isize[i] == sizes[i] // 2)}


def module_size(data):
    """Total P60A module size in bytes (header..end of sample data)."""
    sdata, npat, flags = struct.unpack(">HBB", data[:4])
    nins = flags & 0x3F
    end = 0
    addr = 0
    sizes = []
    for i in range(nins):
        size = struct.unpack(">H", data[4 + i * 6:6 + i * 6])[0]
        if size <= 0xFF00:
            sizes.append(size * 2)
    return sdata + sum(sizes)


def main():
    data = open(sys.argv[1], "rb").read()
    mod, info = convert(data)
    open(sys.argv[2], "wb").write(mod)
    print(info, "mod bytes", len(mod))


if __name__ == "__main__":
    main()
