/* Side panels (options left, decoration right) and the two credits screens. */
#ifndef PANELS_H
#define PANELS_H
#include <stdbool.h>
#include <stdint.h>
#include "amiga.h"

#define PANEL_W  160                      /* hires units per side panel */
#define CANVAS_W (SCREEN_W + 2 * PANEL_W)

void panels_init(void);
void panels_compose(uint32_t *canvas, const uint32_t *game, bool panels);
void panels_click(int cx, int cy, bool panels, bool down);
void panels_hover(int cx, int cy, bool panels);
bool panels_quit_requested(void);
bool panels_overlay_active(void);         /* title / credits cover the game (game paused) */
bool panels_overlay_click(void);          /* a click on the game area while an overlay is up */
int  panels_scale_choice(void);           /* 0 = auto, else integer window scale */
bool panels_fullscreen_wanted(void);
void panels_set_fullscreen(bool fs);
void panels_quick_save(void);             /* same as the panel buttons (ALF_SAVE overrides the file) */
void panels_quick_load(void);
#endif
