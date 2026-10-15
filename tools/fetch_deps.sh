#!/bin/sh
# Download the build toolchain and engine dependencies (nothing is installed system-wide).
#   tools/toolchain/w64devkit   portable GCC (MinGW-w64)
#   tools/toolchain/cmake       portable CMake
#   deps/SDL3-*                 SDL3 sources
#   deps/libopenmpt-*           libopenmpt sources (makefile release)
set -e
cd "$(dirname "$0")/.."
mkdir -p tools/toolchain deps
dl() { [ -f "$2" ] || curl -sSL -o "$2" "$1"; }
dl https://github.com/skeeto/w64devkit/releases/download/v2.10.1/w64devkit-x64-2.10.1.7z.exe tools/toolchain/w64devkit.7z.exe
dl https://github.com/Kitware/CMake/releases/download/v4.4.4/cmake-4.4.4-windows-x86_64.zip tools/toolchain/cmake.zip
dl https://github.com/libsdl-org/SDL/releases/download/release-3.4.18/SDL3-3.4.18.tar.gz deps/SDL3.tar.gz
dl "https://lib.openmpt.org/files/libopenmpt/src/libopenmpt-0.8.9+release.makefile.tar.gz" deps/libopenmpt.tar.gz
[ -d tools/toolchain/w64devkit ] || (cd tools/toolchain && ./w64devkit.7z.exe -y >/dev/null)
[ -d tools/toolchain/cmake ] || (cd tools/toolchain && unzip -q cmake.zip && mv cmake-4.4.4-windows-x86_64 cmake)
[ -d deps/SDL3-3.4.18 ] || (cd deps && tar xzf SDL3.tar.gz)
[ -d deps/libopenmpt ] || (cd deps && mkdir libopenmpt && tar xzf libopenmpt.tar.gz -C libopenmpt --strip-components=1)
echo "deps ready"
