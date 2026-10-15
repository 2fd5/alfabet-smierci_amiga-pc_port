/*
 * The original disks: ADF images, the CrunchMania decruncher and the data-disk blobs.
 *
 * Disk 1 holds the bootblock, the trackloader and two CrunchMania files: the intro
 * (sector 22) and the main game (sector 450), both unpacked to $3000. Disks 2-4 are
 * raw blobs of concatenated CrunchMania files starting at byte $1600; the game loads
 * a whole blob at $10181A ("Wczytuję dane...") and finds its files by offset.
 */
#include "amiga.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define ADF_SIZE 901120u

static uint8_t *g_adf[5];
static int g_loaded_disk;
static bool g_main_loaded;

bool amiga_main_loaded(void) { return g_main_loaded; }


/* ------------------------------------------------------------------ CrunchMania
 * 'CrM!' | u16 | u32 raw_len | u32 packed_len | stream. The stream is read backwards
 * in big-endian words, LSB first; the output is written backwards. Same algorithm as
 * tools/crunchmania.py. */

typedef struct {
    const uint8_t *start, *pos;
    uint64_t bits;
    int nbits;
} BitReader;

static int br_refill(BitReader *br)
{
    if (br->pos - 2 < br->start)
        return 0;
    br->pos -= 2;
    br->bits |= (uint64_t)((br->pos[0] << 8) | br->pos[1]) << br->nbits;
    br->nbits += 16;
    return 1;
}

static uint32_t br_read(BitReader *br, int n)
{
    while (br->nbits < n)
        if (!br_refill(br))
            return 0;
    uint32_t v = (uint32_t)(br->bits & ((1u << n) - 1));
    br->bits >>= n;
    br->nbits -= n;
    return v;
}

static uint32_t be32(const uint8_t *p) { return (uint32_t)p[0] << 24 | p[1] << 16 | p[2] << 8 | p[3]; }

/* Huffman codes of the non-LZH 'CrM!' format, read MSB first */
static int read_len_index(BitReader *br)
{
    if (!br_read(br, 1)) return 0;            /* 0   */
    if (!br_read(br, 1)) return 1;            /* 10  */
    return br_read(br, 1) ? 3 : 2;            /* 110 / 111 */
}

static int read_dist_index(BitReader *br)
{
    if (!br_read(br, 1)) return 0;            /* 0  */
    return br_read(br, 1) ? 2 : 1;            /* 10 / 11 */
}

uint32_t crunchmania_decrunch(const uint8_t *src, uint8_t *dst, uint32_t dst_cap)
{
    static const int len_bits[4] = {1, 2, 4, 8}, len_add[4] = {2, 4, 8, 24};
    static const int dist_bits[3] = {9, 5, 14}, dist_add[3] = {32, 0, 544};
    if (memcmp(src, "CrM!", 4) != 0)
        return 0;
    uint32_t raw = be32(src + 6), packed = be32(src + 10);
    if (raw > dst_cap)
        return 0;
    BitReader br = {src + 14, src + 14 + packed - 6, 0, 0};
    uint32_t content = be32(br.pos);
    int shift = (br.pos[4] << 8) | br.pos[5];
    br.bits = content >> (16 - shift);
    br.nbits = shift + 16;

    uint32_t op = raw;
    while (op > 0) {
        if (br_read(&br, 1)) {
            dst[--op] = (uint8_t)br_read(&br, 8);
            continue;
        }
        int li = read_len_index(&br);
        uint32_t count = br_read(&br, len_bits[li]) + len_add[li];
        if (count == 23) {
            count = br_read(&br, 1) ? br_read(&br, 5) + 15 : br_read(&br, 14) + 15;
            for (uint32_t i = 0; i < count && op > 0; i++)
                dst[--op] = (uint8_t)br_read(&br, 8);
            continue;
        }
        if (count > 23)
            count--;
        int di = read_dist_index(&br);
        uint32_t dist = br_read(&br, dist_bits[di]) + dist_add[di];
        for (uint32_t i = 0; i < count && op > 0; i++) {
            op--;
            dst[op] = dst[op + dist];
        }
    }
    return raw;
}

/* ------------------------------------------------------------------ disks */

static uint8_t *read_file(const char *path, size_t want)
{
    FILE *f = fopen(path, "rb");
    if (!f)
        return NULL;
    uint8_t *buf = malloc(want);
    size_t got = fread(buf, 1, want, f);
    fclose(f);
    if (got != want) {
        free(buf);
        return NULL;
    }
    return buf;
}

const uint8_t *amiga_disk_image(int n) { return (n >= 1 && n <= 4) ? g_adf[n] : NULL; }

bool amiga_load_disks(const char *dir)
{
    char path[1024];
    for (int n = 1; n <= 4; n++) {
        snprintf(path, sizeof path, "%s/disk%d.adf", dir, n);
        g_adf[n] = read_file(path, ADF_SIZE);
        if (!g_adf[n]) {
            fprintf(stderr, "cannot read %s\n", path);
            return false;
        }
    }
    g_loaded_disk = 0;
    return amiga_load_main();
}

/* main game: CrunchMania file at disk 1 sector 450, unpacked to $3000 (cleared memory) */
bool amiga_load_main(void)
{
    memset(mem, 0, MEM_SIZE);
    uint32_t n = crunchmania_decrunch(g_adf[1] + 0x38400, mem + MAIN_LOAD, MEM_SIZE - MAIN_LOAD);
    if (n != 1979176) {
        fprintf(stderr, "main binary decrunch failed (%u)\n", n);
        return false;
    }
    g_loaded_disk = 0;
    g_main_loaded = true;
    return true;
}

/* intro program: disk 1 sector 22, unpacked to $3000 (cleared memory) */
bool amiga_load_intro_program(void)
{
    g_main_loaded = false;
    memset(mem, 0, MEM_SIZE);
    return crunchmania_decrunch(g_adf[1] + 0x2C00, mem + MAIN_LOAD, MEM_SIZE - MAIN_LOAD) == 576608;
}

void amiga_note_disk(int n) { g_loaded_disk = n; }

int amiga_disk_loaded(void) { return g_loaded_disk; }

/* The intro is a separate program (disk 1, sector 22) that the engine unpacks on demand. */
uint8_t *amiga_load_intro(uint32_t *size)
{
    uint8_t *buf = malloc(576608);
    *size = crunchmania_decrunch(g_adf[1] + 0x2C00, buf, 576608);
    return buf;
}
