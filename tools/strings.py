"""Dump text runs with offsets, decoding the game's Polish charset."""
import re
import sys

from plchars import decode

data = open(sys.argv[1], "rb").read()
minlen = int(sys.argv[2]) if len(sys.argv) > 2 else 6
for m in re.finditer(rb"[\x20-\x7e\xc0-\xff\n]{%d,}" % minlen, data):
    s = m.group()
    letters = sum(chr(c).isalpha() or c >= 0xC0 for c in s)
    if letters < len(s) * 0.55 or b"  " * 8 in s and letters < 4:
        continue
    print(f"{m.start():06x}: {decode(s)!r}")
