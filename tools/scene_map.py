"""Recover the scene table (frame file + palette) from the main game binary.

Every location shows its frame with:
    movea.l #src,a0 ; movea.l #$610fe,a1 ; jsr $4e5dc     (CrunchMania decrunch)
and then fades in its palette through a small wrapper:
    [bsr $1cc2a] ; movea.l #pal,a0 ; bsr $19332 ; bsr $1c0da|$1c050 ; rts

Data disks are loaded whole at BLOB_BASE, so src - BLOB_BASE is the offset of the
CrunchMania file inside the disk blob (blob = ADF from offset $1600). Sources below
BLOB_BASE point into the main binary itself.
"""
import json
import pathlib
import re
import struct
import sys

from scan_crm import scan

ROOT = pathlib.Path(__file__).resolve().parent.parent
LOAD = 0x3000            # main binary load address
BLOB_BASE = 0x10181A     # where a data disk blob is loaded
BLOB_START = 0x1600      # blob starts at this ADF offset
PAL_FIRST, PAL_COUNT = 0x59AFA, 59
PAL_COPY = 0x19332       # copies 128 x 0RGB from a0 to the fade target
FRAME_SIZE = 68614


def disk_files():
    """{disk: {blob_offset: (index, packed, adf_offset)}} including raw (stored) frames."""
    out = {}
    for n in (2, 3, 4):
        adf = (ROOT / "AlfabetSmierci" / "data" / f"disk{n}.adf").read_bytes()
        files = {}
        prev_end = BLOB_START
        idx = 0
        for pos, _m, _minor, _ulen, plen in scan(adf):
            if pos - prev_end == FRAME_SIZE:  # stored, uncompressed frame in a gap
                files[prev_end - BLOB_START] = {"index": idx, "packed": False, "adf_offset": prev_end}
                idx += 1
            files[pos - BLOB_START] = {"index": idx, "packed": True, "adf_offset": pos}
            idx += 1
            prev_end = pos + 14 + plen
        out[n] = files
    # disk 3 ends with a stored frame after the last CrM file
    adf3_end = 0xC7DF0
    out[3][adf3_end - BLOB_START] = {"index": len(out[3]), "packed": False, "adf_offset": adf3_end}
    return out


def palette_wrappers(code):
    """{call_target: palette_address} for every wrapper that loads a fixed palette."""
    wrappers = {}
    for m in re.finditer(rb"\x20\x7c(....)\x61\x00(..)", code, re.S):
        pal = struct.unpack(">I", m.group(1))[0]
        disp = struct.unpack(">h", m.group(2))[0]
        if m.start() + 6 + 2 + disp + LOAD != PAL_COPY:
            continue
        entry = m.start() + LOAD
        wrappers[entry] = pal
        if code[m.start() - 4:m.start() - 2] == b"\x61\x00":  # preceded by bsr $1cc2a
            wrappers[entry - 4] = pal
    return wrappers


def main_calls(code):
    """Every frame decrunch in the main binary with its file and the palette set after it."""
    disks = disk_files()
    wrappers = palette_wrappers(code)
    calls = []
    for m in re.finditer(rb"\x20\x7c(....)\x22\x7c\x00\x06\x10\xfe\x4e\xb9\x00\x04\xe5\xdc", code, re.S):
        src = struct.unpack(">I", m.group(1))[0]
        at = m.start() + LOAD
        if src >= BLOB_BASE:
            off = src - BLOB_BASE
            where = [{"disk": n, **disks[n][off]} for n in disks if off in disks[n]]
        else:
            where = [{"disk": 1, "main_offset": src - LOAD}]
        # first palette wrapper called after the decrunch
        pal = None
        window = code[m.end():m.end() + 0x400]
        for j in re.finditer(rb"\x4e\xb9(....)", window, re.S):
            tgt = struct.unpack(">I", j.group(1))[0]
            if tgt in wrappers:
                pal = wrappers[tgt]
                break
        calls.append({"code": hex(at), "src": hex(src), "file": where,
                      "palette": hex(pal) if pal else None,
                      "palette_index": (pal - PAL_FIRST) // 0x200 if pal else None})
    return calls


def main():
    code = (ROOT / "work" / "unpacked" / "d1_01_038400.bin").read_bytes()
    json.dump(main_calls(code), sys.stdout, indent=1)


if __name__ == "__main__":
    main()
