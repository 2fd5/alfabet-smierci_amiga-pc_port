"""Assemble THIRD_PARTY_LICENSES.txt for the portable build from the original licence files.

Covers everything linked into AlfabetSmierci.exe: SDL3, libopenmpt, the ProWizard-derived
P60A converter (src/audio.c), the MinGW-w64 runtime and the GCC runtime library.
"""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent

PROWIZARD = """ProWizard (The Player 6.0A depacker), ported to C in src/audio.c
Copyright (C) 1998 Sylvain "Asle" Chipaux
Copyright (C) 2006-2013 Sylvain "Asle" Chipaux
Modified by Claudio Matsuoka; modified in 2021-2024 by Alice Rowan

Permission is hereby granted, free of charge, to any person obtaining a
copy of this software and associated documentation files (the "Software"),
to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense,
and/or sell copies of the Software, and to permit persons to whom the
Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
"""

SECTIONS = [
    ("SDL3 3.4.18 (zlib licence) - Sam Lantinga and SDL contributors", "deps/SDL3-3.4.18/LICENSE.txt"),
    ("libopenmpt 0.8.9 (BSD-3-Clause) - OpenMPT Project Developers and contributors", "deps/libopenmpt/LICENSE"),
    ("miniz (MIT) - Rich Geldreich, RAD Game Tools, Valve Software; built into libopenmpt",
     "deps/libopenmpt/include/miniz/LICENSE"),
    ("minimp3 (CC0 1.0) - Lion (lieff); built into libopenmpt", "deps/libopenmpt/include/minimp3/LICENSE"),
    ("stb_vorbis (MIT or public domain) - Sean Barrett; built into libopenmpt",
     "deps/libopenmpt/include/stb_vorbis/stb_vorbis.c#L5553"),
    ("ProWizard / libxmp The Player depacker (MIT)", None),
    ("MinGW-w64 runtime (statically linked C runtime start-up and helpers)",
     "tools/toolchain/w64devkit/COPYING.MinGW-w64-runtime.txt"),
    ("GCC runtime libraries (libgcc, libstdc++): GPL-3.0 with the GCC Runtime Library Exception 3.1",
     "deps/gcc-exception-3.1.txt"),
]


def main():
    out = ["Alfabet Śmierci (PC port) - third-party licences", "=" * 60, "",
           "The game itself (graphics, music, text, design) is (C) 1995/1996 Arte / Seven Stars",
           "Multimedia, Maciej 'Maniak' Frontkiewicz, Ryszard 'Justus' Bagiński and Michał 'Dixan05'",
           "Prochownik. The data files in data/ are the original game disks.", "",
           "The executable contains the following third-party code:", ""]
    for title, path in SECTIONS:
        out += ["-" * 72, title, "-" * 72, ""]
        if path is None:
            out.append(PROWIZARD)
        else:
            path, _, line = path.partition("#L")          # "#Lnnn": the licence starts at line nnn
            text = (ROOT / path).read_text(encoding="utf-8", errors="replace")
            out.append("\n".join(text.split("\n")[int(line) - 1:]) if line else text)
        out.append("")
    dest = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "THIRD_PARTY_LICENSES.txt"
    dest.write_text("\n".join(out), encoding="utf-8")
    print("wrote", dest)


if __name__ == "__main__":
    main()
