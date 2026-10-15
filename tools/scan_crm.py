"""Find CrunchMania headers in raw disk images.

Header: 4-byte id (CrM!/CrM2/Crm!/Crm2), u16 minor, u32 unpacked len, u32 packed len.
"""
import struct
import sys

IDS = (b"CrM!", b"CrM2", b"Crm!", b"Crm2")


def scan(data):
    out = []
    for magic in IDS:
        pos = data.find(magic)
        while pos != -1:
            if pos + 14 <= len(data):
                minor, ulen, plen = struct.unpack(">HII", data[pos + 4:pos + 14])
                if 0 < plen < ulen < 4_000_000 and pos + 14 + plen <= len(data):
                    out.append((pos, magic.decode(), minor, ulen, plen))
            pos = data.find(magic, pos + 1)
    return sorted(out)


def main():
    for path in sys.argv[1:]:
        data = open(path, "rb").read()
        print(f"=== {path}")
        for pos, magic, minor, ulen, plen in scan(data):
            end = pos + 14 + plen
            print(f"  @{pos:06x} {magic} minor={minor:04x} unpacked={ulen:7d} packed={plen:7d} end={end:06x}")


if __name__ == "__main__":
    main()
