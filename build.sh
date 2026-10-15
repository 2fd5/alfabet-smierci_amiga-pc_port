#!/bin/sh
# Build the portable game into AlfabetSmierci/ (the folder in the repo that is ready to play):
#   AlfabetSmierci/AlfabetSmierci.exe + data/ (original disks, committed) + data/scripts/ (from scripts/).
# Needs tools/fetch_deps.sh and tools/build_deps.sh to have been run once.
set -e
cd "$(dirname "$0")"
ROOT=$(pwd)
export PATH="$ROOT/tools/toolchain/w64devkit/bin:$PATH"
D=deps/install
OUT=AlfabetSmierci
mkdir -p "$OUT/data/scripts" build work
CFLAGS="-std=c11 -O2 -Wall -Wextra -Wno-unused-parameter -I$D/include"
for f in src/*.c; do
  gcc $CFLAGS -c "$f" -o "build/$(basename "$f" .c).o"
done
g++ -O2 -s -static -mwindows build/*.o -o "$OUT/AlfabetSmierci.exe" \
  -L$D/lib -lSDL3 -lopenmpt \
  -lsetupapi -lole32 -loleaut32 -limm32 -lversion -lwinmm -lgdi32 -luser32 -lshell32 -luuid -ladvapi32 -lcfgmgr32 -lhid
rm -f "$OUT"/data/scripts/*.alf
cp scripts/*.alf "$OUT/data/scripts/"
cp dist_readme.txt "$OUT/CZYTAJ.txt"
cp LICENSE "$OUT/LICENSE.txt"
py tools/make_licenses.py "$OUT/THIRD_PARTY_LICENSES.txt" >/dev/null
echo "built $OUT/AlfabetSmierci.exe"
# portable zip (spec-compliant paths): work/AlfabetSmierci-<version>.zip
VERSION=$(grep PORT_VERSION src/version.h | cut -d'"' -f2)
py tools/make_zip.py "work/AlfabetSmierci-$VERSION.zip"
