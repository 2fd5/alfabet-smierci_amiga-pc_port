/* Chip RAM, the hardware registers the game reads, frame sync, mouse and blitter. */
#include "amiga.h"

#include <SDL3/SDL.h>
#include <string.h>

uint8_t mem[MEM_SIZE];

static AmigaInput g_input;
static SDL_Mutex *g_input_lock;
static SDL_Semaphore *g_tick;      /* main -> game: a new frame may start */
static SDL_Semaphore *g_done;      /* game -> main: the game reached its next vbl */
static uint32_t g_frames;
static void (*g_vbl_hook)(void);

void amiga_set_vbl_hook(void (*fn)(void)) { g_vbl_hook = fn; }

/* ------------------------------------------------------------------ memory */

static bool (*g_fire_hook)(void);           /* extra fire sources (natives_lmb_is_fire) */
void amiga_set_fire_hook(bool (*fn)(void)) { g_fire_hook = fn; }

static uint32_t hw_read8(uint32_t a)
{
    AmigaInput in;
    SDL_LockMutex(g_input_lock);
    in = g_input;
    SDL_UnlockMutex(g_input_lock);
    switch (a) {
    case 0xBFE001: /* CIA-A PRA: bit 6 = left mouse (port 1), bit 7 = fire (port 2), active low */
        amiga_note_lmb_poll();
        return 0x3F | (in.lmb ? 0 : 0x40) | (in.fire || (g_fire_hook && g_fire_hook()) ? 0 : 0x80);
    case 0xDFF016: /* POTGOR high byte: bit 10 (= bit 2 here) right mouse, active low */
        return 0xF0 | (in.rmb ? 0 : 0x04) | 0x01;
    case 0xDFF017:
        return 0x00;
    case 0xDFF006: case 0xDFF007: case 0xDFF008: case 0xDFF026:
        /* beam position and pot counters: the game reads them only as a source of randomness
         * (seed at $4E6E4, $4E722); raster waits are handled by wait_raster */
        return (uint32_t)SDL_rand(256);
    default:
        return 0;
    }
}

uint32_t rd8(uint32_t a)
{
    if (a < MEM_SIZE)
        return mem[a];
    return hw_read8(a);
}

uint32_t rd16(uint32_t a) { return (rd8(a) << 8) | rd8(a + 1); }
uint32_t rd32(uint32_t a) { return (rd16(a) << 16) | rd16(a + 2); }

/* ------------------------------------------------------------------ custom chips
 * Lifted code programs the blitter directly ($DFF040..$DFF074). Writes land in a register
 * file; writing BLTSIZE ($DFF058) runs the blit, as on the Amiga (area mode only, which is
 * all the game uses). Other custom registers are accepted and ignored. */
static uint8_t custom[0x200];
uint32_t amiga_cop1lc(void);

void amiga_reset_custom(void) { memset(custom, 0, sizeof custom); }

uint32_t amiga_cop1lc(void)
{
    uint32_t v = ((uint32_t)custom[0x80] << 24 | (uint32_t)custom[0x81] << 16 | (uint32_t)custom[0x82] << 8 | custom[0x83]) & 0x1FFFFE;
    return v ? v : 0x591DE;
}

static uint16_t creg(uint32_t off) { return (uint16_t)(custom[off] << 8 | custom[off + 1]); }
static uint32_t cptr(uint32_t off) { return ((uint32_t)creg(off) << 16 | creg(off + 2)) & 0x1FFFFE; }

static void blitter_run(void)
{
    uint16_t con0 = creg(0x40), con1 = creg(0x42), size = creg(0x58);
    uint16_t fwm = creg(0x44), lwm = creg(0x46);
    uint32_t apt = cptr(0x50), bpt = cptr(0x4C), cpt = cptr(0x48), dpt = cptr(0x54);
    int16_t amod = (int16_t)creg(0x64), bmod = (int16_t)creg(0x62), cmod = (int16_t)creg(0x60), dmod = (int16_t)creg(0x66);
    uint16_t adat = creg(0x74), bdat = creg(0x72), cdat = creg(0x70);
    int h = size >> 6, w = size & 0x3F;
    if (!h) h = 1024;
    if (!w) w = 64;
    bool useA = con0 & 0x800, useB = con0 & 0x400, useC = con0 & 0x200, useD = con0 & 0x100;
    int ash = con0 >> 12, bsh = con1 >> 12;
    bool desc = con1 & 2;
    int step = desc ? -2 : 2;
    uint8_t mt = (uint8_t)con0;
    uint16_t aold = 0, bold = 0;
    for (int y = 0; y < h; y++) {
        for (int x = 0; x < w; x++) {
            uint16_t a = useA ? (uint16_t)rd16(apt) : adat;
            uint16_t b = useB ? (uint16_t)rd16(bpt) : bdat;
            uint16_t c = useC ? (uint16_t)rd16(cpt) : cdat;
            if (useA) apt += step;
            if (useB) bpt += step;
            if (useC) cpt += step;
            uint16_t am = a;
            if (x == 0) am &= fwm;
            if (x == w - 1) am &= lwm;
            uint16_t as, bs;
            if (desc) {
                as = (uint16_t)((((uint32_t)am << 16) | aold) >> (16 - ash));
                bs = (uint16_t)((((uint32_t)b << 16) | bold) >> (16 - bsh));
            } else {
                as = (uint16_t)((((uint32_t)aold << 16) | am) >> ash);
                bs = (uint16_t)((((uint32_t)bold << 16) | b) >> bsh);
            }
            if (ash == 0) as = am;
            if (bsh == 0) bs = b;
            aold = am;
            bold = b;
            uint16_t d = 0;
            for (int m = 0; m < 8; m++) {
                if (!(mt & (1 << m))) continue;
                uint16_t t = (m & 4 ? as : (uint16_t)~as) & (m & 2 ? bs : (uint16_t)~bs) & (m & 1 ? c : (uint16_t)~c);
                d |= t;
            }
            if (useD) { wr16(dpt, d); dpt += step; }
        }
        if (useA) apt += desc ? -amod : amod;
        if (useB) bpt += desc ? -bmod : bmod;
        if (useC) cpt += desc ? -cmod : cmod;
        if (useD) dpt += desc ? -dmod : dmod;
        aold = bold = 0;
    }
}

void wr8(uint32_t a, uint32_t v)
{
    if (a < MEM_SIZE) {
        mem[a] = (uint8_t)v;
        return;
    }
    if (a >= 0xDFF000 && a < 0xDFF200) {
        custom[a - 0xDFF000] = (uint8_t)v;
        if (a == 0xDFF059)
            blitter_run();
    }
}

void wr16(uint32_t a, uint32_t v) { wr8(a, v >> 8); wr8(a + 1, v); }
void wr32(uint32_t a, uint32_t v) { wr16(a, v >> 16); wr16(a + 2, v); }

/* ------------------------------------------------------------------ frame sync */

void amiga_sync_init(void)
{
    g_input_lock = SDL_CreateMutex();
    g_tick = SDL_CreateSemaphore(0);
    g_done = SDL_CreateSemaphore(0);
}

/* Game thread: the place where the asm busy-waited for the vertical blank. */
void amiga_vbl(void)
{
    SDL_SignalSemaphore(g_done);
    SDL_WaitSemaphore(g_tick);
    g_frames++;
    amiga_mouse_update();
    if (g_vbl_hook)
        g_vbl_hook();          /* game-thread work requested by the UI (save / load) */
}

/* Main thread: let the game run one frame, wait until it parks at its next vbl. */
bool amiga_run_frame(int timeout_ms)
{
    SDL_SignalSemaphore(g_tick);
    return SDL_WaitSemaphoreTimeout(g_done, timeout_ms);
}

void amiga_wait_first_vbl(void) { SDL_WaitSemaphore(g_done); }

void amiga_set_input(const AmigaInput *in)
{
    SDL_LockMutex(g_input_lock);
    g_input = *in;
    SDL_UnlockMutex(g_input_lock);
}

const AmigaInput *amiga_input(void) { return &g_input; }
uint32_t amiga_frame_count(void) { return g_frames; }

/* tests: the game reads the left button and runs its hit tests only while it waits for the player */
static volatile uint32_t g_lmb_poll;
void amiga_note_lmb_poll(void) { g_lmb_poll = g_frames; }
uint32_t amiga_last_lmb_poll(void) { return g_lmb_poll; }

/* ------------------------------------------------------------------ mouse ($1CAF8)
 * The original accumulates JOY0DAT deltas into $1CC12 (x, hires pixels) and $1CC14
 * (y, half-lines), clamps them to the limits the location set, and writes the sprite
 * control words of the current pointer ($1CBFC / $1CC00). Here the host mouse gives the
 * position directly; the clamping and the sprite words are exactly the original's. */
void amiga_mouse_update(void)
{
    AmigaInput in;
    SDL_LockMutex(g_input_lock);
    in = g_input;
    SDL_UnlockMutex(g_input_lock);

    int x = in.mouse_x, y = in.mouse_y;
    int min_y = (int16_t)rd16(0x1CC04), max_y = (int16_t)rd16(0x1CC06), max_x = (int16_t)rd16(0x1CC08);
    if (x < 0) x = 0;
    if (max_x > 0 && x >= max_x) x = max_x;
    if (y < min_y) y = min_y;
    if (max_y > 0 && y >= max_y) y = max_y;
    wr16(0x1CC12, x);
    wr16(0x1CC14, y);
    wr16(0x1CC0E, x >> 1);
    wr16(0x1CC10, y >> 1);

    uint32_t s1 = rd32(0x1CBFC), s2 = rd32(0x1CC00);
    if (!s1 || !s2)
        return;
    int hx = (x >> 1) + 0x80, vy = (y >> 1) + 0x2C;
    uint8_t ctl = (uint8_t)(hx & 1);
    ctl |= (uint8_t)((vy & 0x100) >> 6);          /* VSTART bit 8 -> bit 2 */
    int ve = vy + 0x10;
    ctl |= (uint8_t)((ve & 0x100) >> 7);          /* VSTOP bit 8 -> bit 1 */
    wr8(s1, vy); wr8(s2, vy);
    wr8(s1 + 1, hx >> 1); wr8(s2 + 1, hx >> 1);
    wr8(s1 + 2, ve); wr8(s2 + 2, ve);
    wr8(s1 + 3, ctl); wr8(s2 + 3, ctl | 0x80);    /* odd sprite attached */
}

/* ------------------------------------------------------------------ blitter
 * A -> D copy with all masks set (BLTCON0 $09F0), the only blit the game performs. */
void blit_copy(uint32_t src, uint32_t dst, uint16_t bltsize, int16_t amod, int16_t dmod)
{
    int h = bltsize >> 6, w = bltsize & 0x3F;
    if (h == 0) h = 1024;
    if (w == 0) w = 64;
    for (int y = 0; y < h; y++) {
        for (int x = 0; x < w; x++) {
            wr16(dst, rd16(src));
            src += 2;
            dst += 2;
        }
        src += amod;
        dst += dmod;
    }
}
