#ifndef NATIVES_H
#define NATIVES_H
#include "script.h"
extern const Native natives[];
extern const int n_natives;
bool natives_waiting_rmb(void);           /* the game waits for a right click (tests) */
bool natives_lmb_is_fire(void);           /* a left click that counts as joystick fire */
bool natives_waiting_click(void);         /* the game waits for a click (speech, end pages): show the hand */
bool natives_title_shown(void);           /* the intro's title picture is on screen */
#endif
