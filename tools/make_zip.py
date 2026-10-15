"""Pack the playable folder AlfabetSmierci/ into a spec-compliant zip (forward slashes), then verify it."""
import hashlib
import pathlib
import sys
import zipfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "AlfabetSmierci"


def main():
    out = pathlib.Path(sys.argv[1])
    files = sorted(p for p in SRC.rglob("*") if p.is_file() and "saves" not in p.parts)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for p in files:
            z.write(p, "AlfabetSmierci/" + p.relative_to(SRC).as_posix())
    with zipfile.ZipFile(out) as z:
        assert z.testzip() is None
        names = z.namelist()
        assert "AlfabetSmierci/AlfabetSmierci.exe" in names and not any("\\" in n for n in names)
        exe = z.read("AlfabetSmierci/AlfabetSmierci.exe")
    print(out, len(names), "files; exe", len(exe), "bytes, sha1", hashlib.sha1(exe).hexdigest())


if __name__ == "__main__":
    main()
