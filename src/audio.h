#ifndef AUDIO_H
#define AUDIO_H
#include <stdbool.h>
#include <stdint.h>
bool audio_init(void);              /* after the main binary is in memory */
void audio_music_start(int order);  /* $1D884 with the start order from $7C0B6 */
void audio_music_stop(void);        /* $1D8A8 */
void audio_set_intro_module(const uint8_t *p60a);  /* the intro's own module (title screen music) */
void audio_play_intro(void);
void audio_stop_intro(void);
void audio_set_volume(float v);
float audio_volume(void);
void audio_position(int *module, int *order, int *row, uint64_t *samples);  /* 0 none, 1 intro, 2 game */
void audio_tempo(int *speed, double *tempo);

#endif
