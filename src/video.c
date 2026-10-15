/*
 * Display: walks the game's copper list like the Amiga does each frame, then turns the
 * planar screen and the sprites into a 640x256 RGB image.
 *
 * Handled copper moves: bitplane pointers, BPLCON0 (plane count), BPLCON3 (AGA colour
 * bank + LOCT), BPLCON4 (sprite colour banks), COLOR00-31 (12+12 bit AGA colours) and
 * sprite pointers. WAIT is honoured per scanline, which the game uses to switch the text
 * colour (colour 255) from line $F5 down.
 */
#include "amiga.h"

#include <string.h>

#define DIW_VSTART 0x2C

typedef struct {
    uint32_t rgb[256];        /* 0x00RRGGBB */
} Palette;

static uint32_t agacol_set(uint32_t old, uint16_t v, bool loct)
{
    uint32_t r = (old >> 16) & 0xFF, g = (old >> 8) & 0xFF, b = old & 0xFF;
    uint32_t nr = (v >> 8) & 0xF, ng = (v >> 4) & 0xF, nb = v & 0xF;
    if (loct) {
        r = (r & 0xF0) | nr; g = (g & 0xF0) | ng; b = (b & 0xF0) | nb;
    } else {
        /* writing the high nibbles also copies them into the low nibbles (AGA rule) */
        r = nr << 4 | nr; g = ng << 4 | ng; b = nb << 4 | nb;
    }
    return r << 16 | g << 8 | b;
}

typedef struct {
    uint32_t bplpt[8];
    int planes;
    bool hires;
    uint16_t bplcon3, bplcon4;
    uint32_t sprpt[8];
} CopState;

static void copper_move(CopState *st, Palette *pal, uint16_t reg, uint16_t val)
{
    if (reg >= 0x0E0 && reg <= 0x0FE) {
        int i = (reg - 0x0E0) >> 2;
        if (reg & 2) st->bplpt[i] = (st->bplpt[i] & 0xFFFF0000u) | val;
        else         st->bplpt[i] = (st->bplpt[i] & 0x0000FFFFu) | (uint32_t)val << 16;
    } else if (reg >= 0x120 && reg <= 0x13E) {
        int i = (reg - 0x120) >> 2;
        if (reg & 2) st->sprpt[i] = (st->sprpt[i] & 0xFFFF0000u) | val;
        else         st->sprpt[i] = (st->sprpt[i] & 0x0000FFFFu) | (uint32_t)val << 16;
    } else if (reg == 0x100) {
        int n = (val >> 12) & 7;
        if (val & 0x10) n = 8;
        st->planes = n;
        st->hires = (val & 0x8000) != 0;
    } else if (reg == 0x106) {
        st->bplcon3 = val;
    } else if (reg == 0x10C) {
        st->bplcon4 = val;
    } else if (reg >= 0x180 && reg <= 0x1BE) {
        int idx = ((st->bplcon3 >> 13) & 7) * 32 + ((reg - 0x180) >> 1);
        pal->rgb[idx] = agacol_set(pal->rgb[idx], val, (st->bplcon3 & 0x200) != 0);
    }
}

/* Sprites: 16 pixels wide (lores), attached pairs give 15 colours. */
static void draw_sprites(const CopState *st, const Palette *pal, uint32_t *out, int line)
{
    int esprm = (st->bplcon4 >> 4) & 0xF, osprm = st->bplcon4 & 0xF;
    for (int pair = 0; pair < 4; pair++) {
        uint32_t pe = st->sprpt[pair * 2], po = st->sprpt[pair * 2 + 1];
        if (!pe || pe + 4 >= MEM_SIZE)
            continue;
        uint8_t c3o = po ? (uint8_t)rd8(po + 3) : 0;
        bool attached = po && (c3o & 0x80);
        for (int s = 0; s < 2; s++) {
            uint32_t p = s ? po : pe;
            if (!p || (s == 1 && attached))
                continue;
            int vstart = rd8(p) | ((rd8(p + 3) & 4) << 6);
            int vstop = rd8(p + 2) | ((rd8(p + 3) & 2) << 7);
            int hstart = (rd8(p + 1) << 1) | (rd8(p + 3) & 1);
            int vline = line + DIW_VSTART;
            if (vline < vstart || vline >= vstop)
                continue;
            int row = vline - vstart;
            uint16_t a = rd16(p + 4 + row * 4), b = rd16(p + 6 + row * 4);
            uint16_t oa = 0, ob = 0;
            if (attached) {
                oa = rd16(po + 4 + row * 4);
                ob = rd16(po + 6 + row * 4);
            }
            int x0 = (hstart - 0x80) * 2;   /* measured against WinUAE: HSTART $80 = first hires column */
            for (int k = 0; k < 16; k++) {
                int bit = 15 - k;
                int v = ((a >> bit) & 1) | ((b >> bit) & 1) << 1;
                int col;
                if (attached) {
                    v |= ((oa >> bit) & 1) << 2 | ((ob >> bit) & 1) << 3;
                    if (!v) continue;
                    col = osprm * 16 + v;
                } else {
                    if (!v) continue;
                    col = (s ? osprm : esprm) * 16 + pair * 4 + v;
                }
                for (int dx = 0; dx < 2; dx++) {
                    int x = x0 + k * 2 + dx;
                    if (x >= 0 && x < SCREEN_W)
                        out[x] = 0xFF000000u | pal->rgb[col & 255];
                }
            }
        }
    }
}

static uint32_t g_spr0;          /* SPR0PT at the top of the last frame: which pointer is up */
uint32_t video_pointer_sprite(void) { return g_spr0; }

/* The hand pointer straight from the game data (sprites $58E7E + $58EC6, attached, 16 lines,
 * colours 128+ = the UI palette, table entry 0 at $59AFA). Used by the port as its cursor
 * before the game has shown its own pointer. img: 32 x 16 hires pixels, 0 = transparent. */
void video_hand_image(uint32_t *img)
{
    for (int row = 0; row < 16; row++) {
        uint16_t a = rd16(0x58E7E + 4 + row * 4), b = rd16(0x58E7E + 6 + row * 4);
        uint16_t oa = rd16(0x58EC6 + 4 + row * 4), ob = rd16(0x58EC6 + 6 + row * 4);
        for (int k = 0; k < 16; k++) {
            int bit = 15 - k;
            int v = ((a >> bit) & 1) | ((b >> bit) & 1) << 1 | ((oa >> bit) & 1) << 2 | ((ob >> bit) & 1) << 3;
            uint32_t a4 = 0x59AFA + v * 4;
            uint32_t c = v ? 0xFF000000u | rd8(a4 + 1) << 16 | rd8(a4 + 2) << 8 | rd8(a4 + 3) : 0;
            img[row * 32 + k * 2] = img[row * 32 + k * 2 + 1] = c;
        }
    }
}

void video_render(uint32_t *rgba, uint32_t *sprites)
{
    CopState st;
    Palette pal;
    memset(&st, 0, sizeof st);
    memset(&pal, 0, sizeof pal);

    uint32_t pc = amiga_cop1lc();
    st.hires = true;
    int pending_wait = -1;
    /* run the copper up to the first visible line */
    for (int guard = 0; guard < 4096; guard++) {
        uint16_t w1 = rd16(pc), w2 = rd16(pc + 2);
        if (w1 & 1) {
            if (w1 == 0xFFFF && w2 == 0xFFFE)
                break;
            int vp = w1 >> 8;
            if (vp > DIW_VSTART) {     /* wait inside the picture: resume during the scan */
                pending_wait = vp;
                pc += 4;
                break;
            }
            pc += 4;
            continue;
        }
        copper_move(&st, &pal, w1 & 0x1FE, w2);
        pc += 4;
    }
    g_spr0 = st.sprpt[0];
    if (sprites)
        memset(sprites, 0, SCREEN_W * SCREEN_H * 4);

    for (int y = 0; y < SCREEN_H; y++) {
        int vline = y + DIW_VSTART;
        while (pending_wait >= 0 && vline >= pending_wait) {
            pending_wait = -1;
            for (int guard = 0; guard < 4096; guard++) {
                uint16_t w1 = rd16(pc), w2 = rd16(pc + 2);
                if (w1 & 1) {
                    if (w1 == 0xFFFF && w2 == 0xFFFE)
                        break;
                    pending_wait = w1 >> 8;
                    pc += 4;
                    break;
                }
                copper_move(&st, &pal, w1 & 0x1FE, w2);
                pc += 4;
            }
        }
        uint32_t *out = rgba + y * SCREEN_W;
        int row_bytes = st.hires ? 80 : 40, px = st.hires ? 1 : 2;   /* lores pixels are 2 hires wide */
        for (int xb = 0; xb < row_bytes; xb++) {
            uint8_t bytes[8] = {0};
            for (int p = 0; p < st.planes; p++)
                bytes[p] = (uint8_t)rd8(st.bplpt[p] + y * row_bytes + xb);
            for (int k = 0; k < 8; k++) {
                int idx = 0;
                for (int p = 0; p < st.planes; p++)
                    idx |= ((bytes[p] >> (7 - k)) & 1) << p;
                uint32_t c = 0xFF000000u | pal.rgb[idx];
                for (int d = 0; d < px; d++)
                    out[(xb * 8 + k) * px + d] = c;
            }
        }
        if (sprites)
            draw_sprites(&st, &pal, sprites + y * SCREEN_W, y);
    }
}
