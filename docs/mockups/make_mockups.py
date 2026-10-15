"""Checkpoint A mockups, built only from the game's own extracted art, palette and font.

    py docs/mockups/make_mockups.py      (needs extracted/ from tools/extract.py)

Everything is composed in "Amiga space" (x = hires pixel, y = PAL line) and only scaled
at the very end: x2 horizontally, x4 vertically (= 640x512 line-doubled, then x2) which
is how the engine will show the game on a 1920x1080 display.
"""
import json
import pathlib
import sys

import numpy as np
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from plchars import TABLE  # noqa: E402

EX = ROOT / "extracted"
OUT = pathlib.Path(__file__).resolve().parent

SX, SY = 2, 4                    # Amiga space -> 1080p screen pixels
W, H = 960, 270                  # 1920x1080 in Amiga space
GAME_X, GAME_Y = 160, 7          # where the 640x256 game screen sits
PANEL_W = 160

ENCODE = {v: k for k, v in TABLE.items()}
FONT = np.array(Image.open(EX / "ui" / "font_8x8.png").convert("1"), dtype=bool)


def rgb(img):
    return np.array(img.convert("RGB"))


UI = Image.open(EX / "ui" / "screen_stone.png")
UI_RGB = rgb(UI)
UI_BLUE = rgb(Image.open(EX / "ui" / "screen_blue.png"))
UI_PAL = UI.getpalette()


def ui_colour(i):
    return tuple(UI_PAL[i * 3:i * 3 + 3])


STONE = [ui_colour(i) for i in (214, 242, 243, 245, 247, 248, 249, 250, 251, 252, 253, 254)]
DARK = ui_colour(205)
TEXT = (0xCC, 0xCC, 0xCC)         # text colour the game sets for colour 255 ($0CCC)
TEXT_HI = (0xFF, 0xFF, 0xFF)      # highlighted text ($0FFF)
BEIGE = ui_colour(253)


ACUTE = set("ŚŹĆŃ")


def text(canvas, x, y, s, colour, sx=1, sy=1):
    """Draw with the game's 8x8 font. sx/sy scale glyphs in Amiga space."""
    for ch in s:
        code = ENCODE.get(ch, ord(ch)) if ord(ch) > 127 else ord(ch)
        i = code - 0x20
        gx, gy = (i % 80) * 8, (i // 80) * 8
        g = FONT[gy:gy + 8, gx:gx + 8]
        g = np.repeat(np.repeat(g, sy, axis=0), sx, axis=1)
        h, w = g.shape
        region = canvas[y:y + h, x:x + w]
        region[g[:region.shape[0], :region.shape[1]]] = colour
        if sx > 1 and ch in ACUTE:
            # the 8x8 font marks Ś/Ź/Ć/Ń with a notch that vanishes when enlarged;
            # headings get an explicit acute accent above the letter instead
            ax = x + 4 * sx
            canvas[y - 2, ax:ax + 2 * sx] = colour
            canvas[y - 3, ax + sx:ax + 3 * sx] = colour
        x += 8 * sx
    return x


def text_width(s, sx=1):
    return len(s) * 8 * sx


def centred(canvas, cx, y, s, colour, sx=1, sy=1):
    text(canvas, cx - text_width(s, sx) // 2, y, s, colour, sx, sy)


def marble_stone(w, h, offset=0, ramp=STONE[4:10]):
    """The game's own marble texture (bottom panel), remapped by brightness rank onto the
    stone ramp of the UI palette. Slabs of 50 lines are stacked like masonry."""
    src = MARBLE[4:54, 8:632].astype(int)
    lum = src.sum(axis=2)
    order = np.argsort(np.argsort(lum.ravel()))
    q = (order * len(ramp) // order.size).reshape(lum.shape)
    tex = np.array(ramp, dtype=np.uint8)[q]
    out = np.zeros((h, w, 3), np.uint8)
    y, k = 0, 0
    while y < h:
        x0 = (offset + k * 197) % (tex.shape[1] - w)
        part = tex[:, x0:x0 + w]
        if k % 2:
            part = part[:, ::-1]
        n = min(50, h - y)
        out[y:y + n] = part[:n]
        if y:
            out[y - 1] = STONE[2]     # mortar line between slabs
            out[y] = STONE[-1]
        y += 50
        k += 1
    return out


def bevel(canvas, x, y, w, h, light, dark):
    canvas[y, x:x + w] = light
    canvas[y:y + h, x] = light
    canvas[y + h - 1, x:x + w] = dark
    canvas[y:y + h, x + w - 1] = dark


# Original UI pieces (screen coordinates in the 640x256 UI image)
SLOT = UI_RGB[16:28, 519:627]          # grey slate inventory slot, 108x12 incl. bevel
BAR = UI_RGB[88:100, 511:634]          # pink-maroon header bar
MARBLE = UI_RGB[198:256, 0:640]        # bottom marble text panel
MARBLE_BLUE = UI_BLUE[198:256, 0:640]


def slot(canvas, x, y, label, colour=TEXT):
    canvas[y:y + 12, x:x + 108] = SLOT
    centred(canvas, x + 54, y + 2, label, colour)


def left_panel(vertical_word=True):
    p = marble_stone(PANEL_W, 256, offset=40)
    bevel(p, 0, 0, PANEL_W, 256, STONE[-1], DARK)
    bevel(p, 1, 1, PANEL_W - 2, 254, STONE[-2], STONE[1])
    x0 = 44 if vertical_word else 26
    p[10:22, x0:x0 + 108] = BAR[:, 7:115]      # header bar cut to slot width
    centred(p, x0 + 54, 12, "OPCJE", TEXT_HI)
    rows = [
        ("Muzyka", "volume"),
        ("Skala  x2", None),
        ("Pełny ekran", None),
        ("Zapisz", None),
        ("Wczytaj", None),
        ("Autorzy", None),
        ("Narzędzia", None),
        ("Wyjście", None),
    ]
    y = 30
    for label, kind in rows:
        slot(p, x0, y, label if kind is None else "", TEXT)
        if kind == "volume":
            text(p, x0 + 6, y + 2, label, TEXT)
            for k in range(6):  # volume blocks, 4 of 6 lit
                c = TEXT_HI if k < 4 else STONE[2]
                p[y + 3:y + 9, x0 + 62 + k * 7:x0 + 67 + k * 7] = c
        y += 15
    if vertical_word:
        vertical(p, 8, "ALFABET")
    return p


def vertical(p, x, word):
    """Letters stacked top to bottom, glyphs x4 wide, x2 tall (= square 32x32 on screen),
    carved into the stone: dark top-left edge, light bottom-right edge, darker fill."""
    y = (256 - len(word) * 18) // 2 + 4
    for ch in word:
        text(p, x - 1, y - 1, ch, DARK, 4, 2)
        text(p, x + 1, y + 1, ch, STONE[-1], 4, 2)
        text(p, x, y, ch, STONE[3], 4, 2)
        y += 18


def right_panel(vertical_word=True):
    p = marble_stone(PANEL_W, 256, offset=300)
    bevel(p, 0, 0, PANEL_W, 256, STONE[-1], DARK)
    bevel(p, 1, 1, PANEL_W - 2, 254, STONE[-2], STONE[1])
    if vertical_word:
        vertical(p, PANEL_W - 8 - 32, "ŚMIERCI")
    return p


def screen_with_panels(game, vertical_words=True):
    c = np.zeros((H, W, 3), np.uint8)
    c[GAME_Y:GAME_Y + 256, 0:PANEL_W] = left_panel(vertical_words)
    c[GAME_Y:GAME_Y + 256, GAME_X + 640:GAME_X + 640 + PANEL_W] = right_panel(vertical_words)
    c[GAME_Y:GAME_Y + 256, GAME_X:GAME_X + 640] = game
    return c


def to_screen(c):
    return Image.fromarray(np.repeat(np.repeat(c, SY, axis=0), SX, axis=1))


def game_screen_station():
    scenes = json.loads((EX / "scenes.json").read_text(encoding="utf-8"))["frames"]
    st = next(f for f in scenes if f["frame"] == "disk2_02")
    scr = UI_RGB.copy()
    scr[16:16 + 169, 16:16 + 464] = rgb(Image.open(EX / st["png"]))
    # hover text the way the game prints it in the marble panel (x=16, y=203, 10-line rows)
    text(scr, 16, 203, "Dworzec", TEXT_HI)
    text(scr, 16, 213, "Stary dworzec kolejowy... Pamięta chyba czasy J23.", TEXT)
    cur = np.array(Image.open(EX / "ui" / "cursors" / "hand.png").convert("RGBA"))
    cur = np.repeat(cur, 2, axis=1)  # sprite pixels are lores = 2 hires pixels
    cx, cy = 300, 60
    m = cur[..., 3] > 0
    scr[cy:cy + 16, cx:cx + 32][m] = cur[..., :3][m]
    return scr


def title_screen():
    t = rgb(Image.open(EX / "intro" / "intro_7d9dc_title.png"))
    centred(t, 360, 234, "Port by Pete Roman, for Seven Stars Multimedia", (0xB6, 0xB6, 0xB6))
    centred(t, 360, 244, "and Maciej 'Maniak' Frontkiewicz, with love", (0xB6, 0xB6, 0xB6))
    return t


def rope_frame(canvas, src):
    """Frame from the original scene-window frame: corners + tiled edges (src = UI rgb)."""
    corner = 20
    tl = src[0:corner, 0:corner]
    tr = src[0:corner, 496 - corner:496]
    bl = src[197 - corner:197, 0:corner]
    br = src[197 - corner:197, 496 - corner:496]
    left = src[40:140, 0:corner]
    right = src[40:140, 496 - corner:496]
    top = src[0:corner, 240:241]
    bottom = src[197 - corner:197, 240:241]
    h, w = 196, 640
    for y in range(corner, h - corner):
        canvas[y, 0:corner] = left[(y - corner) % left.shape[0]]
        canvas[y, w - corner:w] = right[(y - corner) % right.shape[0]]
    canvas[0:corner, corner:w - corner] = np.repeat(top, w - 2 * corner, axis=1)
    canvas[h - corner:h, corner:w - corner] = np.repeat(bottom, w - 2 * corner, axis=1)
    canvas[0:corner, 0:corner] = tl
    canvas[0:corner, w - corner:w] = tr
    canvas[h - corner:h, 0:corner] = bl
    canvas[h - corner:h, w - corner:w] = br


def credits_original():
    s = np.zeros((256, 640, 3), np.uint8)
    rope_frame(s, UI_RGB)
    s[198:256] = MARBLE
    title_c, head_c, name_c = TEXT_HI, BEIGE, TEXT
    centred(s, 320, 26, "ALFABET ŚMIERCI", title_c, 2, 1)
    centred(s, 320, 38, "Arte  *  Seven Stars Multimedia  (C) 1995/1996", head_c)
    rows = [("Programowanie", "Maciej 'Maniak' Frontkiewicz"),
            ("Grafika", "Ryszard 'Justus' Bagiński"),
            ("Muzyka i scenariusz", "Michał 'Dixan05' Prochownik")]
    y = 58
    for role, who in rows:
        text(s, 316 - text_width(role), y, role, head_c)
        text(s, 332, y, who, name_c)
        y += 12
    thanks = ["Autorzy chcieliby serdecznie podziękować:",
              "Dyrekcji Szpitala Rejonowego w Żywcu,",
              "a w szczególności panu Czesławowi Kapale",
              "oraz personelowi oddziału chirurgii.",
              "Klubowi \"Śrubka\", Firmie \"EL DORADO\" i Firmie \"AB..Z\"",
              "oraz mieszkańcom Żywca, Jeleśni i okolic..."]
    y = 104
    for i, line in enumerate(thanks):
        centred(s, 320, y, line, head_c if i == 0 else name_c)
        y += 10
    centred(s, 320, 168, "1/4   kliknij: dalej", STONE[4])
    centred(s, 320, 210, "Port by Pete Roman, for Seven Stars Multimedia", TEXT_HI)
    centred(s, 320, 222, "and Maciej 'Maniak' Frontkiewicz, with love", TEXT_HI)
    return s


def credits_tools():
    s = np.zeros((256, 640, 3), np.uint8)
    rope_frame(s, UI_BLUE)
    s[198:256] = MARBLE_BLUE
    head = (0xC8, 0xD0, 0xF0)
    centred(s, 320, 26, "NARZĘDZIA I BIBLIOTEKI", TEXT_HI, 2, 1)
    centred(s, 320, 38, "użyte do zbudowania i uruchomienia portu", head)
    rows = [("SDL3", "Sam Lantinga i in.", "zlib"),
            ("libopenmpt", "OpenMPT Project Developers", "BSD-3"),
            ("stb_image", "Sean Barrett i in.", "MIT/PD"),
            ("WinUAE", "Toni Wilen i in. (UAE: B. Schmidt)", "GPL-2.0"),
            ("AROS ROM", "The AROS Development Team", "APL 1.1"),
            ("ProWizard", "Sylvain 'Asle' Chipaux", "MIT"),
            ("libxmp", "C. Matsuoka, H. Carraro Jr, A. Rowan", "MIT"),
            ("ancient", "Teemu Suutari", "BSD-2"),
            ("Capstone", "Nguyen Anh Quynh i in.", "BSD-3"),
            ("amitools", "Christian Vogelgsang", "GPL-2.0+"),
            ("Python", "Python Software Foundation", "PSF-2.0"),
            ("Pillow, NumPy", "Alex Clark i in., NumPy Devs", "MIT-CMU/BSD")]
    y = 56
    for name, who, lic in rows:
        text(s, 40, y, name, TEXT_HI)
        text(s, 160, y, who, TEXT)
        text(s, 600 - text_width(lic), y, lic, head)
        y += 10
    centred(s, 320, 210, "Pełne teksty licencji: THIRD_PARTY_LICENSES.txt", TEXT_HI)
    centred(s, 320, 222, "1/2   kliknij: dalej", TEXT)
    return s


def main():
    game = game_screen_station()
    outputs = {
        "1_widescreen_station.png": screen_with_panels(game, True),
        "1b_widescreen_station_no_vertical_words.png": screen_with_panels(game, False),
        "2_title_with_port_line.png": screen_with_panels(title_screen(), True),
        "3_credits_original.png": screen_with_panels(credits_original(), True),
        "4_credits_tools.png": screen_with_panels(credits_tools(), True),
    }
    for name, c in outputs.items():
        to_screen(c).save(OUT / name)
        print("wrote", name)


if __name__ == "__main__":
    main()
