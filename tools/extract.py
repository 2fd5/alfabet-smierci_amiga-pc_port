"""Extract every Alfabet Smierci asset from the original ADF images into extracted/.

    py tools/extract.py            (reads AlfabetSmierci/data/disk1..4.adf, writes extracted/)

Everything is lossless: images are indexed PNGs that keep the original colour
indices and the original 24-bit AGA palettes, music is converted symbolically
(The Player 6.0A -> ProTracker MOD, same notes and sample bytes), text is decoded
from the game's own Polish charset to UTF-8.

Output layout:
    extracted/manifest.json        source hashes and a summary
    extracted/palettes.json        the 59 palettes of the main game (index -> #rrggbb)
    extracted/scenes.json          scene table: frame file, palette, code address
    extracted/scenes/*.png         464x169 scene frames, indexed, own palette
    extracted/ui/screen.png        640x256 game screen frame (indices 128-255 = UI palette)
    extracted/ui/font_8x8.png      font sheet + font.json glyph map
    extracted/text/main.json       every string of the main game, keyed by address
    extracted/text/intro.json      intro story text
    extracted/hotspots.json        hotspot rectangle tables, keyed by address
    extracted/music/*.mod          intro and game modules + music.json
    extracted/intro/*.png          intro screens (palettes not yet recovered, see notes)
"""
import hashlib
import json
import pathlib
import re
import struct

from PIL import Image

import scene_map
from crunchmania import decrunch
from p60a import convert as p60a_to_mod
from p60a import module_size
from plchars import decode as pl_decode
from planar import decode as planar_decode

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "extracted"
LOAD = 0x3000

FRAME_W, FRAME_H, FRAME_PLANES = 464, 169, 7
SCREEN_ADDR, SCREEN_PLANE = 0x96738, 0x5000
FONT_ADDR = 0x95FAC
PAL_FIRST, PAL_COUNT = 0x59AFA, 59
UI_PALETTES = {0: "stone (default)", 1: "blue", 2: "gold"}
CURSOR_FIRST = 0x58E7E
GAME_MODULE, INTRO_MODULE = 0x1EC26, 0x5D9A
TEXT_BLOCK = (0x7A900, 0x96500)         # load addresses of the main text block
INTRO_TEXT = (0x2A1F4, 0x2AF00)
HOTSPOT_SET = b"\x00\x01\xce\xc2"        # move.l #table,$1cec2

# Frames the code shows without a fixed palette wrapper. Verified ones come from
# WinUAE captures; the rest keep their candidates until the lifter resolves them.
EXTRA_PALETTES = {
    ("d1", 0xF2B14): {"palette": 58, "verified": "WinUAE capture (disk swap screen)"},
}


def wjson(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")


def sha1(b):
    return hashlib.sha1(b).hexdigest()


def load_disks():
    return {n: (ROOT / "AlfabetSmierci" / "data" / f"disk{n}.adf").read_bytes() for n in range(1, 5)}


def palette(code, index):
    base = PAL_FIRST - LOAD + index * 0x200
    return [tuple(code[base + k * 4 + 1:base + k * 4 + 4]) for k in range(128)]


def hexcol(c):
    return "#%02x%02x%02x" % c


def save_indexed(path, pixels, w, h, pal):
    img = Image.frombytes("P", (w, h), pixels)
    flat = [v for c in pal for v in c]
    img.putpalette(flat + [0] * (768 - len(flat)))
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, optimize=True)


def extract_palettes(code):
    pals = {i: [hexcol(c) for c in palette(code, i)] for i in range(PAL_COUNT)}
    wjson(OUT / "palettes.json", 
        {"format": "128 x #rrggbb, AGA 24-bit; scene palettes fill colours 0-127, "
                   "UI palettes (0-2) fill colours 128-255",
         "ui_palettes": UI_PALETTES, "palettes": pals})
    return pals


def extract_scenes(code, disks):
    calls = scene_map.main_calls(code)
    frames = {}
    for c in calls:
        for w in c["file"]:
            key = ("d1", w["main_offset"] + LOAD) if w["disk"] == 1 else (f"d{w['disk']}", w["index"])
            frames.setdefault(key, {"source": w, "palettes": set(), "code": []})
            if c["palette_index"] is not None and len(c["file"]) == 1:
                frames[key]["palettes"].add(c["palette_index"])
            frames[key]["code"].append(c["code"])
    # first file of each data disk: palette decided by position in the palette bank
    first_file = {3: "d2", 16: "d3", 39: "d4"}
    for c in calls:
        if len(c["file"]) > 1 and c["palette_index"] in first_file:
            frames[(first_file[c["palette_index"]], 0)]["palettes"].add(c["palette_index"])
    # stored (uncompressed) frames are never referenced through the decruncher
    for n, files in scene_map.disk_files().items():
        for f in files.values():
            frames.setdefault((f"d{n}", f["index"]), {"source": {"disk": n, **f}, "palettes": set(), "code": []})

    table = []
    for key in sorted(frames, key=lambda k: (k[0], k[1])):
        fr = frames[key]
        src = fr["source"]
        if key[0] == "d1":
            raw = decrunch(code, key[1] - LOAD)[0]
            name = f"main_{key[1]:06x}"
        else:
            adf = disks[src["disk"]]
            raw = decrunch(adf, src["adf_offset"])[0] if src["packed"] else \
                adf[src["adf_offset"]:src["adf_offset"] + scene_map.FRAME_SIZE]
            name = f"disk{src['disk']}_{src['index']:02d}"
        pals = sorted(fr["palettes"])
        extra = EXTRA_PALETTES.get(key)
        verified = None
        if extra:
            pals, verified = [extra["palette"]], extra["verified"]
        elif len(pals) == 1:
            verified = "code: palette wrapper called after decrunch"
        pix = planar_decode(raw, FRAME_W, FRAME_H, FRAME_PLANES, False)
        pal = palette(code, pals[0]) if pals else [(i * 2, i * 2, i * 2) for i in range(128)]
        save_indexed(OUT / "scenes" / f"{name}.png", pix, FRAME_W, FRAME_H, pal)
        table.append({"frame": name, "png": f"scenes/{name}.png", "palette": pals[0] if pals else None,
                      "palette_verified": verified, "source": {k: (hex(v) if isinstance(v, int) and k != "disk" and k != "index" else v)
                                                               for k, v in src.items()},
                      "shown_by_code": fr["code"]})
    wjson(OUT / "scenes.json", 
        {"format": "464x169, 7 bitplanes, colours 0-127; drawn at screen (16,16)",
         "frames": table})
    return table


def extract_ui(code):
    o = SCREEN_ADDR - LOAD
    pix = planar_decode(code[o:o + SCREEN_PLANE * 8], 640, 256, 8, False)
    for i, name in UI_PALETTES.items():
        pal = [(0, 0, 0)] * 128 + palette(code, i)
        save_indexed(OUT / "ui" / f"screen_{name.split()[0]}.png", pix, 640, 256, pal)
    font = code[FONT_ADDR - LOAD:FONT_ADDR - LOAD + 0x780]
    img = Image.frombytes("1", (640, 24), font)
    img.save(OUT / "ui" / "font_8x8.png")
    glyphs = {}
    for c in range(0x20, 0x110):
        if c > 0xFF:
            break
        i = c - 0x20
        glyphs[pl_decode(bytes([c]))] = {"code": c, "x": (i % 80) * 8, "y": (i // 80) * 8}
    wjson(OUT / "ui" / "font.json", 
        {"sheet": "font_8x8.png", "cell": [8, 8], "line_height": 10,
         "note": "glyph for byte c sits at ((c-0x20) % 80 * 8, (c-0x20) // 80 * 8)",
         "glyphs": glyphs})


def split_strings(blob, base):
    out = {}
    for m in re.finditer(rb"[^\x00]+", blob):
        s = m.group()
        printable = sum(32 <= c < 127 or c >= 0xC0 or c == 10 for c in s)
        letters = sum(chr(c).isalpha() or c >= 0xC0 for c in s)
        if len(s) >= 2 and printable == len(s) and letters >= max(1, len(s) // 3):
            out[base + m.start()] = pl_decode(s)
    return out


def extract_cursors(code):
    """Mouse pointers: attached sprite pairs, 16x16 lores, colours 128+1..15 (UI palette)."""
    pal = palette(code, 0)
    names = ["hand", "hand_pressed", "wait_0", "wait_1", "wait_2", "wait_3"]
    for i, name in enumerate(names):
        even = CURSOR_FIRST + i * 0x90
        odd = even + 0x48
        img = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
        for y in range(16):
            ea, eb = struct.unpack(">HH", code[even - LOAD + 4 + y * 4:even - LOAD + 8 + y * 4])
            oa, ob = struct.unpack(">HH", code[odd - LOAD + 4 + y * 4:odd - LOAD + 8 + y * 4])
            for x in range(16):
                b = 15 - x
                v = (ea >> b & 1) | (eb >> b & 1) << 1 | (oa >> b & 1) << 2 | (ob >> b & 1) << 3
                if v:
                    img.putpixel((x, y), pal[v] + (255,))
        (OUT / "ui" / "cursors").mkdir(parents=True, exist_ok=True)
        img.save(OUT / "ui" / "cursors" / f"{name}.png")
    wjson(OUT / "ui" / "cursors" / "cursors.json", {
        "format": "16x16 lores sprite pixels (each is 2 hires pixels wide), hot spot (0,0) = mouse position",
        "cursors": names, "source": f"attached sprite pairs from ${CURSOR_FIRST:05X}, stride $90"})


def extract_text(code, intro):
    texts = split_strings(code[TEXT_BLOCK[0] - LOAD:TEXT_BLOCK[1] - LOAD], TEXT_BLOCK[0])
    # every address the code loads into a2 (the print routines take the text in a2)
    refs = set()
    for m in re.finditer(rb"\x45\xf9(....)", code, re.S):
        a = struct.unpack(">I", m.group(1))[0]
        if TEXT_BLOCK[0] <= a < TEXT_BLOCK[1]:
            refs.add(a)
            if a not in texts:
                end = code.index(b"\0", a - LOAD)
                texts[a] = pl_decode(code[a - LOAD:end])
    main = [{"addr": f"${a:05X}", "referenced_by_code": a in refs, "text": t} for a, t in sorted(texts.items())]
    (OUT / "text").mkdir(parents=True, exist_ok=True)
    wjson(OUT / "text" / "main.json", main)
    intro_t = split_strings(intro[INTRO_TEXT[0] - LOAD:INTRO_TEXT[1] - LOAD], INTRO_TEXT[0])
    wjson(OUT / "text" / "intro.json", 
        [{"addr": f"${a:05X}", "text": t} for a, t in sorted(intro_t.items())])
    return len(main), len(refs)


def extract_hotspots(code):
    tables = {}
    for m in re.finditer(rb"\x23\xfc(....)" + re.escape(HOTSPOT_SET), code, re.S):
        a = struct.unpack(">I", m.group(1))[0]
        o = a - LOAD
        rects = []
        while code[o:o + 2] != b"\xba\xca" and len(rects) < 64:
            x1, x2, y1, y2 = struct.unpack(">4H", code[o:o + 8])
            rects.append({"id": len(rects) + 1, "x1": x1, "x2": x2, "y1": y1, "y2": y2})
            o += 8
        entry = tables.setdefault(f"${a:05X}", {"rects": rects, "activated_at": []})
        entry["activated_at"].append(f"${m.start() + LOAD:05X}")
    wjson(OUT / "hotspots.json", 
        {"format": "mouse coordinates: x = hires pixel (0-639), y = half-line (screen line = y // 2); "
                   "inclusive; id = 1-based order; list terminated by $BACA in the original",
         "tables": tables})
    return len(tables), sum(len(t["rects"]) for t in tables.values())


def extract_music(code, intro):
    (OUT / "music").mkdir(parents=True, exist_ok=True)
    info = {}
    for name, blob, addr in (("game", code, GAME_MODULE), ("intro", intro, INTRO_MODULE)):
        m = blob[addr - LOAD:]
        mod, meta = p60a_to_mod(m[:module_size(m)])
        (OUT / "music" / f"{name}.mod").write_bytes(mod)
        info[name] = {"source": f"P60A module at ${addr:05X}", **meta}
    wjson(OUT / "music" / "music.json", 
        {"replayer": "The Player 6.0A (patched: start order = long at $7C0B6)",
         "playback": "libopenmpt, Amiga resampler emulation, A1200 filter",
         "modules": info})


# Intro screen -> palette (load address of 256 x 0RGB), verified pixel-exact against WinUAE.
INTRO_PALETTES = {0x7D9DC: 0x76250}


def extract_intro_screens(intro):
    nested = {0x73DF8: (320, 256, 8), 0x7CC40: (320, 256, 8), 0x7D9DC: (640, 256, 8),
              0x89EA6: (320, 256, 6), 0x8ACA2: (320, 256, 6), 0x8B8DC: (320, 256, 6)}
    for off, (w, h, p) in nested.items():
        raw = decrunch(intro, off)[0]
        pix = planar_decode(raw, w, h, p, False)
        if off in INTRO_PALETTES:
            a = INTRO_PALETTES[off] - LOAD
            pal = [tuple(intro[a + k * 4 + 1:a + k * 4 + 4]) for k in range(256)]
            name = "title"
        else:  # palette not recovered yet: grey ramp placeholder
            pal = [(i, i, i) for i in range(256)] if p == 8 else [(i * 4, i * 4, i * 4) for i in range(64)]
            name = "pending_palette"
        save_indexed(OUT / "intro" / f"intro_{off:05x}_{name}.png", pix, w, h, pal)


def main():
    disks = load_disks()
    OUT.mkdir(exist_ok=True)
    intro = decrunch(disks[1], 0x2C00)[0]
    code = decrunch(disks[1], 0x38400)[0]
    extract_palettes(code)
    scenes = extract_scenes(code, disks)
    extract_ui(code)
    extract_cursors(code)
    n_text, n_refs = extract_text(code, intro)
    n_tabs, n_rects = extract_hotspots(code)
    extract_music(code, intro)
    extract_intro_screens(intro)
    manifest = {
        "sources": {f"disk{n}.adf": sha1(b) for n, b in disks.items()},
        "scenes": len(scenes),
        "scenes_with_verified_palette": sum(1 for s in scenes if s["palette_verified"]),
        "strings": n_text, "strings_referenced_by_code": n_refs,
        "hotspot_tables": n_tabs, "hotspots": n_rects,
    }
    wjson(OUT / "manifest.json", manifest)
    print(json.dumps(manifest, indent=1))


if __name__ == "__main__":
    main()
