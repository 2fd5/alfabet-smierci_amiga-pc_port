# How Alfabet Śmierci works, and how the port runs it

This file is for anyone reading the code, and first of all for Maniak, who wrote the original. Addresses are the original absolute addresses (main binary loaded at `$3000`), so everything can be checked against the asm.

## 1. The original in one page

| Piece | Where | Notes |
|---|---|---|
| Boot | disk 1 bootblock -> loader at `$1FE400` | own MFM trackloader + CrunchMania decruncher |
| Intro | disk 1, sector 22, unpacked to `$3000` | Seven Stars, arte, title (8 planes, palette at intro `$76250`), credits, story pages |
| Main game | disk 1, sector 450, unpacked to `$3000`, ~1.9 MB | code `$3000`..`$1EC25`, then data |
| Data disks 2-4 | raw blobs of CrunchMania files from byte `$1600` | loaded whole (or 10 tracks of them) at `$10181A` |
| Screen | `$96738`, 8 bitplanes of `$5000`, 640x256 hires | colours 0-127 = scene, 128-255 = UI |
| Copper list | `$591DE` | bitplane + sprite pointers, all 256 AGA colours, WAIT at line `$F5` for the text colour |
| Scene frame | decrunched to `$610FE`, 464x169, 7 planes | blitted to (16,16) by `$193C0` |
| Palettes | 59 x 128 x 0RGB at `$59AFA`..`$60EFA` | 0 = UI stone, 1 = blue, 2 = gold, 3.. = scenes |
| Font | 8x8 sheet at `$95FAC` (and `$9672C`) | game charset: ą=E6 ć=E7 ę=EA ł=EE ń=F1 ó=F3 ś=F5 ź=FB ż=FE, capitals -$20 |
| Music | The Player 6.0A module at `$1EC26` | replayer patched to start at the order in `$7C0B6` |
| Game state | `$7BBD4`..`$7C26F` (`$69C` bytes) | location id, inventory, all story flags; this is what a save game is |

### Locations

Every location is a routine that starts with `move.b #id,$7BBD4` (65 of them, ids `$02`..`$3D`). The shape is always the same:

1. pick the music (`$15732`), clear text, make sure the right data disk is loaded (`$143C0` -> `$4E82E`),
2. decrunch the frame from the disk blob, blit it, fade in its palette,
3. set the hotspot table (`$1CEC2`) and the mouse limits,
4. loop: wait for the raster, run the right panel (`$16E54`: inventory slots, arrows, verb buttons, menu) and the item combinations (`$17C40`), hit-test the hotspots (`$1D7BA` -> `d2`), then a chain of `cmpi.l #n,d2` with the actions for each hotspot.

Actions are tests on the verb flags (`$1795A` look, `$1795C` talk, `$1795E` take, `$17960` give, `$17962` use, `$17964` open), on story flags in the state block, and on the left mouse button, followed by text output, flag changes and jumps to other locations.

### Dialogues

A conversation switches to the close-up frame, swaps the hotspot table for one whose rectangles are the lines of the text panel, and confines the mouse to the panel. Then: print the other person's line (`$1C67E`, right click to continue), print the options (`$1C6A8`), wait for a left click, hit-test which line was clicked, and branch. The whole tree is code, nested loops of exactly this pattern.

### Hotspots

Tables of `x1, x2, y1, y2` words ending with `$BACA`. `x` is in hires pixels, `y` in half-lines (the mouse counters are kept at twice the vertical resolution), so a screen line is `y / 2`.

### Text output

`$1C6C8` prints into the marble panel from line 203, column 2, ORing the glyphs into 6 bitplanes through the pointers at `$7A904`. The visible colour comes from colour 255, which the copper switches to `$CCC` (or `$FFF` after a `$B9` code) from line `$F5` down. `$1C7DA` prints in the scene area (line 20), `$1CA3C` at any byte offset (inventory names, verb bar).

## 2. The port

The port keeps the Amiga's memory layout and re-implements the machine only as far as the game uses it. Original data is never converted for the engine; it is read from the four ADF files at start-up.

```
data/disk1..4.adf  ->  CrunchMania (C)  ->  2 MB chip RAM image (same addresses as on the A1200)
                                              |
        scripts (data/scripts/*.alf)  <-------+------->  native routines (src/natives.c)
        the game logic, lifted from asm                  blitter, copper, sprites, fades,
        by tools/lifter.py                               text printing, disks, music
                                              |
                     video: copper list + bitplanes + sprites -> 640x256 RGB (src/video.c)
                     audio: P60A -> MOD in memory -> libopenmpt, A1200 Paula emulation (src/audio.c)
```

### Source files

| File | What |
|---|---|
| `src/amiga.c` | chip RAM, the few hardware registers the game reads (`$BFE001`, `$DFF016`), frame sync, mouse (`$1CAF8`), the blitter (both the copy helper and the register interface `$DFF040`..`$DFF074` that some lifted routines program directly) |
| `src/disk.c` | ADF loading, CrunchMania decruncher, intro loader |
| `src/video.c` | copper list interpreter (bitplane/sprite pointers, AGA colours with bank + LOCT, WAIT per line) and sprite drawing |
| `src/script.c` | `.alf` compiler and interpreter |
| `src/natives.c` | the routines that touch hardware, one C function per original routine, each commented with its address |
| `src/audio.c` | The Player 6.0A to ProTracker conversion and libopenmpt playback |
| `src/panels.c` | side panels, title screen with the port line, the two credits screens, save/load |
| `src/main.c` | window, 50 Hz timing, input, integer scaling, test driver |

### The intro

The intro is its own program (disk 1, sector 22) and runs first, exactly like on the floppy: `tools/lifter.py` lifts it into `scripts/intro.alf` (labels prefixed `IL`, because both programs live at `$3000`). Only its decruncher, its music replayer and the final jump into the loader are native. When it ends, memory is cleared, the main game is unpacked to `$3000` and `boot` runs. While the title picture is on screen the presentation layer adds the port line under it. `ALF_SKIP_INTRO=1` starts the game directly.

### Threads and time

The game logic runs on its own thread and stops at every place where the asm waited for the raster (`wait_vbl` in the scripts, or the natives' own waits). The main thread lets it run one PAL frame at a time (50 Hz), then draws memory as it is. The beam position is modelled from the instructions executed (50,000 per frame, 312 PAL lines), so `wait_raster $n` waits for the next line whose low byte is `n`, exactly like `cmpi.b #n,$dff006 / bne`: two waits for different lines can fall into the same frame, and a wait for the line the beam is already on passes at once. Code that busy-waits on the mouse buttons without waiting for the raster gets its frames the same way. Fades take 255 steps with no raster wait in the original; their speed per frame (9 in, 8 out) was measured on the original running in WinUAE.

### What is lifted and what is native

`tools/lifter.py` turned 394 routines into scripts: all locations, all dialogues, the right panel, inventory handling, item combinations, the per-location music, disk and palette tables, and the many small palette and blit wrappers. About 35 routines are native because they talk to hardware or the OS: text printing, blits, palette fades, pointer sprites, hit tests, decrunching, music start/stop, the disk change, random numbers, and the save disk. The game's own menu (Zapisz / Wczytaj, slots "Stan gry 1-3", "Zrób dysk") works unchanged: its track reads and writes (`$4F232`, `$4F2B8`) go to `saves/stan_gry.adf`, a formatted save disk created on first use. The HD-install path through dos.library (`$4E92A`..) is not used, because the port runs the floppy version (`$30EE` = 1).

### Things done differently on purpose

| Original | Port | Why |
|---|---|---|
| "Włóż dysk N", wait until the disk is in | the prompt stays 2 s, then the disk "goes in" by itself | requested; the screens are kept |
| relative mouse counters | absolute host mouse, same clamping limits | no mouse capture needed |
| save to a formatted save disk | the game's menu writes to `saves/stan_gry.adf`; the side panel also has a quick save (`saves/stan.sav`, the same `$69C`-byte state block) | same data, no physical disk |

## 3. Verification so far

- Every CrunchMania file decrunches to its exact size with no input left over.
- Scene frames, UI and the title screen were compared pixel by pixel with WinUAE captures (A1200 config, AROS ROM): all colours match exactly, and all differences are explained by WinUAE's non-integer window scaling.
- The scene -> palette mapping comes from the code (the palette wrapper called after each decrunch) and was confirmed on screen.
- Pointer position was measured against WinUAE (HSTART `$80` = first hires column).
- A random-click test drove the game for 30,000 frames through locations 3-7 with no unimplemented routine and no script error.
- `tools/test_locations.py` warps into every location routine (`ALF_WARP`), fills the inventory with every item (`ALF_ITEMS`) and clicks around for 4,000 frames, collecting unimplemented routines, script errors and hangs. All locations pass. Death screens (`loc_02`, `loc_02_2`, `loc_07_2`, `loc_08_2`, `loc_12_3`, `loc_1F_2`, `loc_22_2`, `loc_23_2`, `loc_27_2`, `loc_35_2`) are subroutines of `game_over`, so warping straight into them ends the game thread by design.
- Input as in the original, plus: speech moves on with the left button and space/fire too (the original waits for the right button only, `$1C960`, and hides the pointer, checked in WinUAE); a left click on an empty spot of the picture is joystick fire in the three rooms that read it for the power (loc_2D, loc_34, loc_35). The game's sprites are not drawn into the picture: they go to their own layer and become the window's hardware cursor at the current scale, also over the side panels. After the original end credits the port adds one page in the same style (the port line and the port author), then a click returns to the title.
- The whole game plays through: `tools/playthrough.py` drives the engine live (`ALF_CONTROL=1`, commands on stdin, `state`/`inv`/`peek` answers on stdout) through the 263 steps of `tests/walkthrough.json` (derived from the scripts, `docs/WALKTHROUGH.md`), from the station to the last card of the ending in one run, checking the location and the state flags each step sets. It right-clicks only while the game waits for a right click, picks dialogue rows only while the option list is polled, and picks items by name from the real inventory.
- The ending (`loc_3D`) was run through: final picture, congratulations, the authors' thanks and beta testers. The original then stops for good (`bra.s *` at `$13E8C`). The port keeps the last page on screen until a click or a key, then reloads the intro program and runs it from the title (`halt` native in `natives.c`; the intro's setup runs as usual, the logo pictures are skipped by jumping to the label `IL031BA`, which the lifter emits from `INTRO_LABELS` in `tools/symbols.py`). Checked with autoplay: the last page holds, a key brings up the title, then the story pages and a new game.
- Scripted tests (tools are in `src/main.c`: `ALF_AUTOPLAY`, `ALF_FAST`, `ALF_TRACE`) cover: boot and disk change, station hover/look/exit, the train dialogue, taking an item into the inventory, the side panel, both credits screens, quick save/load across locations, and saving through the game's own menu.
