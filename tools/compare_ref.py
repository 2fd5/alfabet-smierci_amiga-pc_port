"""Compare a screen of the port with the same screen of the original (memory dumps).

    py tools/compare_ref.py ORIGINAL.bin PORT.bin OUT_PREFIX

Both dumps are the 2 MB chip RAM image: from WinUAE's debugger (tools/uae_ref.py dump)
and from the engine (autoplay/control "dump"). Compared:
  - the 8 bitplanes of the game screen at $96738 (640x256, 80 bytes per row), and
  - the colours the copper list at $591DE loads (all 256 AGA colours, per screen line,
    since a WAIT at line $F5 changes the text colour).
Both images are then rendered by this script on its own (not by the engine's renderer)
and written as OUT_PREFIX_orig.png, OUT_PREFIX_port.png and OUT_PREFIX_diff.png.
"""
import sys

import numpy as np
from PIL import Image

SCREEN, PLANE, PLANES, W, H = 0x96738, 0x5000, 8, 640, 256
COPPER = 0x591DE
DISPLAY_TOP = 0x2C          # first visible PAL line of the game screen


def words(mem, a):
    return (mem[a] << 8) | mem[a + 1]


def palettes(mem):
    """Per-line 256-colour palettes from the copper list (BPLCON3 bank + LOCT, COLORxx)."""
    pal = np.zeros((256, 3), dtype=np.int32)
    hi = np.zeros((256, 3), dtype=np.int32)
    lines = np.zeros((H, 256, 3), dtype=np.int32)
    bank, loct, line = 0, False, 0
    a = COPPER
    for _ in range(4000):
        w1, w2 = words(mem, a), words(mem, a + 2)
        a += 4
        if w1 == 0xFFFF and w2 == 0xFFFE:
            break
        if w1 & 1:                                   # WAIT
            v = (w1 >> 8) - DISPLAY_TOP
            v = max(0, min(H, v))
            lines[line:v] = pal
            line = max(line, v)
            continue
        reg = w1 & 0x1FE
        if reg == 0x106:                             # BPLCON3: bank and LOCT
            bank, loct = w2 >> 13, bool(w2 & 0x200)
        elif 0x180 <= reg < 0x1C0:
            i = bank * 32 + (reg - 0x180) // 2
            r, g, b = (w2 >> 8) & 15, (w2 >> 4) & 15, w2 & 15
            if loct:
                pal[i] = [(hi[i][0] << 4) | r, (hi[i][1] << 4) | g, (hi[i][2] << 4) | b]
            else:
                hi[i] = [r, g, b]
                pal[i] = [r * 17, g * 17, b * 17]
    lines[line:] = pal
    return lines


def render(mem):
    planes = np.frombuffer(bytes(mem[SCREEN:SCREEN + PLANES * PLANE]), dtype=np.uint8).reshape(PLANES, H, 80)
    bits = np.unpackbits(planes, axis=2)                       # 8 x 256 x 640
    idx = np.zeros((H, W), dtype=np.int32)
    for p in range(PLANES):
        idx |= bits[p].astype(np.int32) << p
    pals = palettes(mem)
    rgb = np.take_along_axis(pals, idx[:, :, None].repeat(3, axis=2), axis=1)
    return planes, idx, pals, rgb.astype(np.uint8)


def main():
    a, b, out = sys.argv[1], sys.argv[2], sys.argv[3]
    ma, mb = bytearray(open(a, "rb").read()), bytearray(open(b, "rb").read())
    pa, ia, la, ra = render(ma)
    pb, ib, lb, rb = render(mb)
    plane_diff = [(int((pa[p] != pb[p]).sum())) for p in range(PLANES)]
    pix = (ra != rb).any(axis=2)
    pal_diff = int((la != lb).any(axis=2).sum())
    print(f"bitplane bytes differing per plane: {plane_diff}")
    print(f"palette entries differing (line x colour): {pal_diff}")
    print(f"pixels differing: {int(pix.sum())} of {W * H}")
    if pix.any():
        ys, xs = np.nonzero(pix)
        print(f"  bounding box x {xs.min()}..{xs.max()}, y {ys.min()}..{ys.max()}")
    Image.fromarray(ra).save(out + "_orig.png")
    Image.fromarray(rb).save(out + "_port.png")
    d = np.zeros_like(ra)
    d[pix] = [255, 0, 255]
    Image.fromarray((ra // 3 + d).clip(0, 255).astype(np.uint8)).save(out + "_diff.png")


if __name__ == "__main__":
    main()
