#!/bin/sh
# Build SDL3 and libopenmpt as static libraries into deps/install (run tools/fetch_deps.sh first).
# Runs under w64devkit's own shell:  tools/toolchain/w64devkit/bin/sh tools/build_deps.sh
set -e
cd "$(dirname "$0")/.."
ROOT=$(pwd)
export PATH="$ROOT/tools/toolchain/w64devkit/bin:$ROOT/tools/toolchain/cmake/bin:$PATH"
PREFIX="$ROOT/deps/install"
JOBS=${JOBS:-8}

if [ ! -f "$PREFIX/lib/libSDL3.a" ]; then
  cmake -S deps/SDL3-3.4.18 -B deps/build-sdl3 -G "Unix Makefiles" \
    -DCMAKE_MAKE_PROGRAM=make -DCMAKE_C_COMPILER=gcc -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_INSTALL_PREFIX="$PREFIX" -DSDL_SHARED=OFF -DSDL_STATIC=ON \
    -DSDL_TEST_LIBRARY=OFF -DSDL_TESTS=OFF -DSDL_EXAMPLES=OFF
  cmake --build deps/build-sdl3 -j "$JOBS"
  cmake --install deps/build-sdl3
fi

if [ ! -f "$PREFIX/lib/libopenmpt.a" ]; then
  make -C deps/libopenmpt -j "$JOBS" CONFIG=mingw-w64 WINDOWS_ARCH=amd64 \
    CC=gcc CXX=g++ LD=g++ AR=ar \
    SHARED_LIB=0 STATIC_LIB=1 EXAMPLES=0 OPENMPT123=0 TEST=0 \
    NO_ZLIB=1 NO_MPG123=1 NO_OGG=1 NO_VORBIS=1 NO_VORBISFILE=1 \
    NO_PORTAUDIO=1 NO_PORTAUDIOCPP=1 NO_PULSEAUDIO=1 NO_SDL2=1 NO_FLAC=1 NO_SNDFILE=1
  mkdir -p "$PREFIX/lib" "$PREFIX/include/libopenmpt"
  cp deps/libopenmpt/bin/libopenmpt.a "$PREFIX/lib/"
  cp deps/libopenmpt/libopenmpt/libopenmpt.h deps/libopenmpt/libopenmpt/libopenmpt_config.h \
     deps/libopenmpt/libopenmpt/libopenmpt_version.h "$PREFIX/include/libopenmpt/"
fi
echo "deps built in $PREFIX"
