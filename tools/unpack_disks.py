"""Decrunch every CrunchMania file found on the ADF images into work/unpacked/."""
import pathlib
import sys

from crunchmania import decrunch
from scan_crm import scan

ROOT = pathlib.Path(__file__).resolve().parent.parent


def main():
    outdir = ROOT / "work" / "unpacked"
    outdir.mkdir(parents=True, exist_ok=True)
    for n in range(1, 5):
        data = (ROOT / "AlfabetSmierci" / "data" / f"disk{n}.adf").read_bytes()
        for idx, (pos, magic, _minor, ulen, plen) in enumerate(scan(data)):
            name = f"d{n}_{idx:02d}_{pos:06x}.bin"
            out, left = decrunch(data, pos)
            (outdir / name).write_bytes(out)
            print(f"{name} {magic} {plen:7d} -> {len(out):7d} unread={left}", flush=True)


if __name__ == "__main__":
    sys.exit(main())
