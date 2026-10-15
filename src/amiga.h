/*
 * The slice of the Amiga that Alfabet Śmierci actually uses.
 *
 * The game's data lives exactly where the original put it: a 2 MB chip-RAM image
 * with the main binary at $3000, data disks loaded at $10181A, the screen in planar
 * bitplanes at $96738 and the copper list at $591DE. The engine re-implements the
 * game's helper routines on top of this, so text, palettes, graphics and tables are
 * always read from the original bytes.
 */
#ifndef AMIGA_H
#define AMIGA_H

#include <stdbool.h>
#include <stdint.h>

#define MEM_SIZE    0x200000u          /* 2 MB chip RAM (A1200) */
#define MAIN_LOAD   0x3000u
#define BLOB_BASE   0x10181Au          /* where a data disk is loaded */
#define SCREEN_W    640
#define SCREEN_H    256

extern uint8_t mem[MEM_SIZE];

/* big-endian memory access, with the few hardware registers the game reads */
uint32_t rd8(uint32_t a);
uint32_t rd16(uint32_t a);
uint32_t rd32(uint32_t a);
void wr8(uint32_t a, uint32_t v);
void wr16(uint32_t a, uint32_t v);
void wr32(uint32_t a, uint32_t v);

/* input as the hardware sees it (filled by the main thread every frame) */
typedef struct {
    int mouse_x, mouse_y;   /* host mouse in Amiga coordinates: hires pixels, half-lines */
    bool lmb, rmb, fire;
    bool key;               /* any key held (not the port's own F11, Alt+Enter, Tab) */
} AmigaInput;

/* ---- boot / disks (disk.c) ---- */
bool amiga_load_disks(const char *dir);       /* reads disk1..4.adf, decrunches the main binary */
int  amiga_disk_loaded(void);                 /* which data disk is in memory (0 = none) */
void amiga_note_disk(int n);
bool amiga_load_main(void);                   /* main game binary into cleared memory */
bool amiga_main_loaded(void);                 /* false while the intro program runs */
bool amiga_load_intro_program(void);          /* intro program into cleared memory */
uint8_t *amiga_load_intro(uint32_t *size);
uint32_t crunchmania_decrunch(const uint8_t *src, uint8_t *dst, uint32_t dst_cap);
const uint8_t *amiga_disk_image(int n);       /* raw 901120-byte ADF */

/* ---- frame sync (amiga.c): the game thread calls vbl() where the asm waited for the raster ---- */
void amiga_vbl(void);
void amiga_sync_init(void);
bool amiga_run_frame(int timeout_ms);         /* main thread: run the game for one frame */
void amiga_wait_first_vbl(void);
void amiga_set_vbl_hook(void (*fn)(void));    /* runs on the game thread right after each vbl */
void amiga_set_input(const AmigaInput *in);
const AmigaInput *amiga_input(void);
void amiga_set_fire_hook(bool (*fn)(void));   /* more ways to press joystick fire (port 2) */
uint32_t amiga_frame_count(void);
void amiga_note_lmb_poll(void);               /* the game polled for player input (tests) */
uint32_t amiga_last_lmb_poll(void);           /* frame of that */
void amiga_mouse_update(void);                /* the level-3 interrupt's mouse code ($1CAF8) */

/* ---- blitter (A->D copies only, which is all the game uses) ---- */
void blit_copy(uint32_t src, uint32_t dst, uint16_t bltsize, int16_t amod, int16_t dmod);

/* ---- video (video.c): copper + bitplanes + sprites -> 640x256 RGB ---- */
#define COPPER_LIST 0x591DEu
uint32_t amiga_cop1lc(void);                  /* last value written to COP1LC ($DFF080) */
void amiga_reset_custom(void);
void video_render(uint32_t *rgba, uint32_t *sprites);  /* SCREEN_W x SCREEN_H, 0xAARRGGBB; sprites:
                                              the pointer on its own layer (NULL: skip) */
uint32_t video_pointer_sprite(void);          /* SPR0PT of the last frame (which pointer) */
void video_hand_image(uint32_t *img);         /* hand pointer from the game data, 32 x 16 */

#endif
