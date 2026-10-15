"""Amiga bitplane -> PNG with a provisional palette.

planar.py in.bin out.png width height planes [interleaved|planar] [offset]
"""
import sys

from PIL import Image


def decode(data, width, height, planes, interleaved, offset=0):
    bpr = width // 8
    pix = bytearray(width * height)
    for y in range(height):
        for p in range(planes):
            if interleaved:
                base = offset + (y * planes + p) * bpr
            else:
                base = offset + (p * height + y) * bpr
            row = data[base:base + bpr]
            bit = 1 << p
            for xb, byte in enumerate(row):
                if not byte:
                    continue
                o = y * width + xb * 8
                for k in range(8):
                    if byte & (0x80 >> k):
                        pix[o + k] |= bit
    return bytes(pix)


def grey_palette(planes):
    n = 1 << planes
    pal = []
    for i in range(256):
        v = (i * 255 // (n - 1)) if i < n else 0
        pal += [v, v, v]
    return pal


def to_image(pix, width, height, palette):
    img = Image.frombytes("P", (width, height), pix)
    img.putpalette(palette)
    return img


def ham8_to_rgb(pix, width, height, base_palette):
    """AGA HAM8: bits 0-1 (planes 1-2) control (00 palette, 01 blue, 10 red, 11 green), bits 2-7 data.
    base_palette: list of 64 (r, g, b). Returns bytes RGB."""
    out = bytearray(width * height * 3)
    for y in range(height):
        r, g, b = base_palette[0]
        for x in range(width):
            v = pix[y * width + x]
            ctl, dat = v & 3, v >> 2
            if ctl == 0:
                r, g, b = base_palette[dat]
            elif ctl == 1:
                b = (dat << 2) | (b & 3)
            elif ctl == 2:
                r = (dat << 2) | (r & 3)
            else:
                g = (dat << 2) | (g & 3)
            o = (y * width + x) * 3
            out[o:o + 3] = bytes((r, g, b))
    return bytes(out)


def main():
    src, dst = sys.argv[1], sys.argv[2]
    w, h, planes = (int(x) for x in sys.argv[3:6])
    mode = sys.argv[6] if len(sys.argv) > 6 else "interleaved"
    off = int(sys.argv[7], 0) if len(sys.argv) > 7 else 0
    data = open(src, "rb").read()
    pix = decode(data, w, h, planes, mode == "interleaved", off)
    to_image(pix, w, h, grey_palette(planes)).save(dst)


if __name__ == "__main__":
    main()

