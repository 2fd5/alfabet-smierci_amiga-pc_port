/*
 * Music: the game's The Player 6.0A module, converted in memory to a ProTracker M.K.
 * module (same notes, same sample bytes; port of tools/p60a.py, itself a port of the
 * ProWizard depacker from libxmp) and played by libopenmpt with its Amiga resampler
 * emulation set to the A1200 filter. Nothing is pre-rendered.
 *
 * The original replayer was patched by the authors to start at the order stored in
 * $7C0B6; music_start(order) does exactly that.
 */
#include "audio.h"

#include "amiga.h"

#include <SDL3/SDL.h>
#include <libopenmpt/libopenmpt.h>
#include <stdlib.h>
#include <string.h>

#define GAME_MODULE 0x1EC26u
#define RATE 48000

static openmpt_module *g_mod, *g_intro, *g_cur;
static SDL_AudioStream *g_stream;
static SDL_Mutex *g_lock;
static bool g_playing;
static uint64_t g_rendered;          /* sample frames rendered (tests) */
static float g_volume = 1.0f;

/* ------------------------------------------------------------------ P60A -> MOD */

static const uint16_t periods[60] = {
    1712, 1616, 1525, 1440, 1357, 1281, 1209, 1141, 1077, 1017, 961, 907,
    856, 808, 762, 720, 678, 640, 604, 570, 538, 508, 480, 453,
    428, 404, 381, 360, 339, 320, 302, 285, 269, 254, 240, 226,
    214, 202, 190, 180, 170, 160, 151, 143, 135, 127, 120, 113,
    107, 101, 95, 90, 85, 80, 76, 71, 67, 64, 60, 57,
};

static int put_event(uint8_t *x, uint8_t c1, uint8_t c2, uint8_t c3)
{
    int note = c1 / 2;
    uint16_t per = (note >= 1 && note <= 60) ? periods[note - 1] : 0;
    int eff = c2 & 0x0F;
    if (eff == 0x08) c2 -= 0x08;
    if (eff == 0x05 || eff == 0x06 || eff == 0x0A)
        c3 = c3 > 0x7F ? (uint8_t)((0x100 - c3) << 4) : c3;
    x[0] = (uint8_t)(((c1 << 4) & 0x10) | (per >> 8));
    x[1] = (uint8_t)per;
    x[2] = c2;
    x[3] = c3;
    return eff;
}

#define EV(p, ch, row) (pat + (p) * 1024 + (row) * 16 + (ch) * 4)

static void decode_patterns(const uint8_t *d, uint32_t base, int npat, const uint16_t (*taddr)[4], uint8_t *pat)
{
    for (int p = 0; p < npat; p++) {
        int max_row = 63;
        for (int ch = 0; ch < 4; ch++) {
            uint32_t pos = base + taddr[p][ch];
            int k = 0;
            while (k <= max_row) {
                uint8_t c1 = d[pos], c2 = d[pos + 1], c3 = d[pos + 2];
                pos += 3;
                if ((c1 & 0x80) && c1 != 0x80) {
                    uint8_t c4 = d[pos++];
                    c1 = (uint8_t)(0xFF - c1);
                    int eff = put_event(EV(p, ch, k), c1, c2, c3);
                    if (eff == 0x0D || eff == 0x0B) { max_row = k; break; }
                    if (c4 < 0x80) { k += c4 + 1; continue; }
                    for (int n = 0x100 - c4; n > 0; n--) {
                        if (++k >= 64) break;
                        put_event(EV(p, ch, k), c1, c2, c3);
                    }
                    k++;
                    continue;
                }
                if (c1 == 0x80) {
                    uint8_t c4 = d[pos++];
                    uint32_t resume = pos, rpos = pos - ((uint32_t)c3 << 8 | c4);
                    int lines = c2;
                    bool stop = false;
                    for (int l = 0; l <= lines && k < 64;) {
                        uint8_t r1 = d[rpos], r2 = d[rpos + 1], r3 = d[rpos + 2];
                        rpos += 3;
                        if ((r1 & 0x80) && r1 != 0x80) {
                            uint8_t r4 = d[rpos++];
                            r1 = (uint8_t)(0xFF - r1);
                            int eff = put_event(EV(p, ch, k), r1, r2, r3);
                            if (eff == 0x0D || eff == 0x0B) { max_row = k; stop = true; break; }
                            if (r4 < 0x80) { k += r4 + 1; l++; continue; }
                            for (int n = 0x100 - r4; n > 0; n--) {
                                if (++k >= 64) break;
                                put_event(EV(p, ch, k), r1, r2, r3);
                            }
                        }
                        if (k >= 64) break;
                        put_event(EV(p, ch, k), r1, r2, r3);
                        l++;
                        k++;
                    }
                    pos = resume;
                    if (stop) break;
                    continue;
                }
                int eff = put_event(EV(p, ch, k), c1, c2, c3);
                if (eff == 0x0D || eff == 0x0B) { max_row = k; break; }
                k++;
            }
        }
    }
}

static uint8_t *p60a_to_mod(const uint8_t *d, size_t *out_len)
{
    uint16_t sdata = (uint16_t)(d[0] << 8 | d[1]);
    int npat = d[2], flags = d[3], nins = flags & 0x3F;
    bool delta = (flags & 0x80) != 0;
    uint32_t sizes[31] = {0}, addrs[31] = {0}, isize[31] = {0};
    uint8_t hdr[1084];
    memset(hdr, 0, sizeof hdr);
    uint32_t pos = 4;
    for (int i = 0; i < nins; i++, pos += 6) {
        uint16_t size = (uint16_t)(d[pos] << 8 | d[pos + 1]);
        uint8_t fine = d[pos + 2], vol = d[pos + 3];
        uint16_t loop = (uint16_t)(d[pos + 4] << 8 | d[pos + 5]);
        if (size > 0xFF00) {
            int src = 0xFFFF - size;
            sizes[i] = sizes[src]; isize[i] = isize[src]; addrs[i] = addrs[src];
        } else {
            addrs[i] = i ? addrs[i - 1] + sizes[i - 1] : 0;
            sizes[i] = size * 2u; isize[i] = size;
        }
        uint8_t *s = hdr + 20 + i * 30;
        uint32_t words = sizes[i] / 2;
        s[22] = (uint8_t)(isize[i] >> 8); s[23] = (uint8_t)isize[i];
        s[24] = fine & 0x3F; s[25] = vol;
        uint32_t ls = loop == 0xFFFF ? 0 : loop, ll = loop == 0xFFFF ? 1 : words - loop;
        s[26] = (uint8_t)(ls >> 8); s[27] = (uint8_t)ls; s[28] = (uint8_t)(ll >> 8); s[29] = (uint8_t)ll;
    }
    for (int i = nins; i < 31; i++) hdr[20 + i * 30 + 29] = 1;
    uint16_t (*taddr)[4] = calloc(npat, sizeof *taddr);
    for (int p = 0; p < npat; p++, pos += 8)
        for (int c = 0; c < 4; c++)
            taddr[p][c] = (uint16_t)(d[pos + c * 2] << 8 | d[pos + c * 2 + 1]);
    int len = 0;
    while (len < 128 && d[pos] != 0xFF) hdr[952 + len++] = d[pos++];
    pos++;
    hdr[950] = (uint8_t)len;
    hdr[951] = 0;     /* restart byte 0: OpenMPT then plays with ProTracker rules */
    memcpy(hdr + 1080, "M.K.", 4);

    uint32_t smp_total = 0;
    for (int i = 0; i < nins; i++) smp_total += sizes[i];
    size_t total = 1084 + (size_t)npat * 1024 + smp_total;
    uint8_t *out = calloc(1, total);
    memcpy(out, hdr, 1084);
    decode_patterns(d, pos, npat, (const uint16_t (*)[4])taddr, out + 1084);
    uint8_t *smp = out + 1084 + npat * 1024;
    for (int i = 0; i < nins; i++) {
        memcpy(smp, d + sdata + addrs[i], sizes[i]);
        if (delta)
            for (uint32_t j = 1; j < sizes[i]; j++)
                smp[j] = (uint8_t)(0x100 - smp[j] + smp[j - 1]);   /* out[j] = out[j-1] - raw[j] */
        smp += sizes[i];
    }
    free(taddr);
    *out_len = total;
    return out;
}

/* ------------------------------------------------------------------ playback */

static void SDLCALL feed(void *ud, SDL_AudioStream *stream, int additional, int total)
{
    (void)ud; (void)total;
    float buf[2048 * 2];
    while (additional > 0) {
        int frames = SDL_min(additional / (int)(sizeof(float) * 2), 2048);
        if (frames <= 0) frames = 1;
        SDL_LockMutex(g_lock);
        size_t got = 0;
        if (g_cur && g_playing) {
            got = openmpt_module_read_interleaved_float_stereo(g_cur, RATE, frames, buf);
            g_rendered += got;
        }
        SDL_UnlockMutex(g_lock);
        if (got < (size_t)frames)
            memset(buf + got * 2, 0, (frames - got) * 2 * sizeof(float));
        for (int i = 0; i < frames * 2; i++) buf[i] *= g_volume;
        SDL_PutAudioStreamData(stream, buf, frames * 2 * (int)sizeof(float));
        additional -= frames * 2 * (int)sizeof(float);
    }
}

static openmpt_module *open_p60a(const uint8_t *p60a)
{
    size_t len;
    uint8_t *mod = p60a_to_mod(p60a, &len);
    openmpt_module *m = openmpt_module_create_from_memory2(mod, len, NULL, NULL, NULL, NULL, NULL, NULL, NULL);
    free(mod);
    if (!m) return NULL;
    openmpt_module_ctl_set_boolean(m, "render.resampler.emulate_amiga", 1);
    openmpt_module_ctl_set_text(m, "render.resampler.emulate_amiga_type", "a1200");
    openmpt_module_set_repeat_count(m, -1);
    return m;
}

void audio_set_intro_module(const uint8_t *p60a)
{
    SDL_LockMutex(g_lock);
    g_intro = open_p60a(p60a);
    SDL_UnlockMutex(g_lock);
}

void audio_play_intro(void)
{
    SDL_LockMutex(g_lock);
    if (g_intro) {
        openmpt_module_set_position_order_row(g_intro, 0, 0);
        g_cur = g_intro;
        g_playing = true;
    }
    SDL_UnlockMutex(g_lock);
}

void audio_stop_intro(void)
{
    SDL_LockMutex(g_lock);
    if (g_cur == g_intro) g_playing = false;
    SDL_UnlockMutex(g_lock);
}

bool audio_init(void)
{
    g_lock = SDL_CreateMutex();
    g_mod = open_p60a(mem + GAME_MODULE);
    if (!g_mod) return false;
    SDL_AudioSpec spec = {SDL_AUDIO_F32, 2, RATE};
    g_stream = SDL_OpenAudioDeviceStream(SDL_AUDIO_DEVICE_DEFAULT_PLAYBACK, &spec, feed, NULL);
    if (!g_stream) return false;
    SDL_ResumeAudioStreamDevice(g_stream);
    return true;
}

void audio_music_start(int order)
{
    SDL_LockMutex(g_lock);
    if (g_mod) {
        openmpt_module_set_position_order_row(g_mod, order, 0);
        g_cur = g_mod;
        g_playing = true;
    }
    SDL_UnlockMutex(g_lock);
}

void audio_music_stop(void)
{
    SDL_LockMutex(g_lock);
    if (g_cur == g_mod) g_playing = false;
    SDL_UnlockMutex(g_lock);
}

/* tests: which module plays, where, and how many samples have gone to the device */
void audio_position(int *module, int *order, int *row, uint64_t *samples)
{
    SDL_LockMutex(g_lock);
    *module = !g_playing || !g_cur ? 0 : g_cur == g_intro ? 1 : 2;
    *order = g_cur ? openmpt_module_get_current_order(g_cur) : -1;
    *row = g_cur ? openmpt_module_get_current_row(g_cur) : -1;
    *samples = g_rendered;
    SDL_UnlockMutex(g_lock);
}

void audio_tempo(int *speed, double *tempo)
{
    SDL_LockMutex(g_lock);
    *speed = g_cur ? openmpt_module_get_current_speed(g_cur) : 0;
    *tempo = g_cur ? openmpt_module_get_current_tempo2(g_cur) : 0;
    SDL_UnlockMutex(g_lock);
}

void audio_set_volume(float v) { g_volume = v; }
float audio_volume(void) { return g_volume; }
