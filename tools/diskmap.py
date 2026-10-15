"""Per-track overview of raw ADF images: entropy, zero ratio, magic tags."""
import math
import sys
from collections import Counter

TRACK = 512 * 11  # 5632 bytes, one side of one cylinder

MAGICS = {
    b"FORM": "IFF", b"ILBM": "ILBM", b"8SVX": "8SVX", b"BODY": "BODY",
    b"CMAP": "CMAP", b"PP20": "PowerPacker", b"IMP!": "Imploder",
    b"ATN!": "Imploder(ATN)", b"CrM!": "CrunchMania", b"CrM2": "CrunchMania2",
    b"RNC\x01": "RNC1", b"RNC\x02": "RNC2", b"M.K.": "ProTracker",
    b"\x00\x00\x03\xf3": "HUNK_HEADER", b"TPWM": "TPWM", b"S404": "StoneCracker4",
    b"FIRE": "FIRE", b"AmBk": "AMOS bank", b"AMOS": "AMOS", b"DSK": "DSKtag",
}


def entropy(b):
    c = Counter(b)
    n = len(b)
    return -sum(v / n * math.log2(v / n) for v in c.values())


def main(path):
    data = open(path, "rb").read()
    for t in range(len(data) // TRACK):
        chunk = data[t * TRACK:(t + 1) * TRACK]
        tags = sorted({name for m, name in MAGICS.items() if m in chunk})
        zero = chunk.count(0) / len(chunk)
        print(f"trk {t:3d} off {t*TRACK:06x}  H={entropy(chunk):4.2f} z={zero:4.2f} {' '.join(tags)}")


if __name__ == "__main__":
    main(sys.argv[1])
