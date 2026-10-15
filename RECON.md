# Alfabet Śmierci (Arte / Seven Stars, 1996, Amiga AGA): Phase 1 recon

## TL;DR

- **Not AMOS, not Blitz.** Hand-written 68k assembly by Maciej 'Maniak' Frontkiewicz, running on bare metal with a custom trackloader. The title screen literally says "100% AMOS FREE".
- **No filesystem.** None of the 4 disks is AmigaDOS (xdftool rejects all of them). Disk 1 boots a custom MFM trackloader, disks 2-4 are raw data blobs tagged `DSK2`/`DSK3`/`DSK4`.
- **Single packer: CrunchMania (`CrM!`).** I wrote a pure-Python decruncher (`tools/crunchmania.py`). All 61 packed files decrunch with exact size match and zero leftover input.
- **Assets are easy.** Scene images are raw planar bitplanes (464×169, 7 planes, 128 colours). Intro screens are 320×256 or 640×256 at 8 planes (AGA). Text is plain bytes with a simple Polish charset.
- **Logic is the hard part.** There is no script VM. Each location is a hand-coded asm routine that tests hotspot id, verb, mouse button and global byte flags, then calls "print text at address X". Hotspot rectangles *are* clean data tables, though.
- **Verdict: feasible.** A ScummVM-style Python reimplementation makes sense. Assets plus hotspots can be extracted automatically. The per-location logic must be lifted semi-automatically (pattern-matching the very repetitive asm idioms) and hand-checked.

## Source and working copy

| | |
|---|---|
| Originals (untouched) | `..\Alfabet-mierci_Amiga_EN\*.zip`, 4 zips, `[cr WT]` release |
| Working copy | `orig/zips` (copies), `orig/adf/disk1..4.adf` (901120 B each, standard DD) |
| Unpacked data | `work/unpacked/` (top level) and `work/unpacked/nested/` (files packed inside the binaries) |
| Tools | `tools/` (see bottom) |

`orig/` and `work/` are git-ignored. Since version 1.0 the four disk images are committed in `AlfabetSmierci/data/` (the game is abandonware; Pete's decision), so the repo is playable as downloaded.

## Boot chain

1. **Bootblock** (disk 1, `DOS\0` header with a valid checksum, but no root block). It uses `trackdisk.device` `CMD_READ` to load `$1600` bytes from disk offset `$400` to `$1FE400`, sets DMACON, and jumps there. The rest of the bootblock is a credits text plus a taunt aimed at crackers ("make a HD version of this game...", signed Maniak, 22.01.96).
2. **Loader at `$1FE400`**: kills the OS (INTENA off, own copper list), has its own MFM track reader (`$1FE65E`: a6 = dest, d6 = byte length, d7 = start sector) and an embedded CrM! decruncher (`$1FE52E`). Two entry points:
   - Cold start: sector 22 (offset `$2C00`), `$34C78` bytes, unpacked to `$3000`, then `jmp $3000`. This is the **intro**.
   - `$1FE4B0` (called when the intro ends): sector 450 (offset `$38400`), `$85652` bytes, unpacked to `$3000`, then `jmp $3000`. This is the **main game**.
3. The main game is ~1.98 MB unpacked and loaded at `$3000`, so it needs the A1200's full 2 MB of chip RAM (AGA is mandatory anyway).
4. Data disks are read as **blobs of concatenated CrM! files** starting at offset `$1600`. The binary also has a dos.library path that opens `A:!dysk2`, `A:!dysk3`, `A:!dysk4` (blob sizes `$CC73A`, `$D73F6`, `$6F308`, matching the disks byte for byte) and `a:puchatek` (probably the save file). I don't know yet whether that path is original or part of the WT crack.

## File map

Offsets are absolute in the ADF. "frame" = 68614 B scene image (see Graphics).

### Disk 1 (boot + code)

| ADF offset | Packed | Unpacked | What |
|---|---|---|---|
| `$000000` | | 1024 | Bootblock (code + credits text) |
| `$000400` | | 5632 | Trackloader + CrM decruncher (runs at `$1FE400`) |
| `$002C00` | 216170 | 576608 | **Intro** executable + data (runs at `$3000`) |
| `$038400` | 546372 | 1979176 | **Main game** executable + data (runs at `$3000`) |
| `$0BDA52`..`$0BF200` | | | Unreferenced leftover bitplane data, probably junk from a previous write |
| rest | | | zeros (track 159 also zeros) |

Nested inside the **intro** (CrM!, all 0 leftover):

| Offset in intro | Unpacked | Guess (confirmed visually) |
|---|---|---|
| `$73DF8` | 81920 | 320×256×8 planar: "Seven Stars" logo |
| `$75430` | 143360 | 8-plane image, layout not pinned down yet (text/art strips) |
| `$7CC40` | 81920 | 320×256×8 |
| `$7D9DC` | 163840 | 640×256×8 planar: **title screen** ("Alfabet Śmierci", "100% AMOS FREE") |
| `$89EA6`, `$8ACA2`, `$8B8DC` | 61440 each | 320×256×6 or similar: credits text screens ("Programowanie: Maciej Frontkiewicz") |
| `$0271F4`..`$027F00` | | Intro story text (phone call, Wojtek, Marlena, train to Dęby) |

Nested inside the **main game**: 6 more frames (`$CD948`, `$D619C`, `$DC5BE`, `$E8E36`, `$EB53C`, `$EFB14`).

### Disks 2, 3, 4 (scene frames)

| Disk | Header | Contents | Blob end |
|---|---|---|---|
| 2 | `DSK2` | 20 frames, all CrM! | `$0CDD3A` |
| 3 | `DSK3` | 17 CrM! frames + 1 **stored raw** frame at `$C7DF0` | `$0D89F6` |
| 4 | `DSK4` | 10 CrM! frames + 1 **stored raw** frame at `$3DE38` (between files 5 and 6) | `$070908` |

Disk 2 tracks 158-159 contain ~11 KB of unreferenced data (starts `00000008 0000067e 0000004b ...`). Unknown for now, possibly leftovers or protection.

**Total: 55 scene frames** (20 + 18 + 11 + 6). The disk blobs have no offset table, so the game most likely finds file N by walking CrM headers.

## Tech stack

- **Language**: 68000/68020 assembly, absolute addressing (`jsr $1953c.l`, `lea $7fc76.l,a2`), flat binary loaded at a fixed address, no Hunk format. Assembler style suggests Asm-One or Devpac, though there's no way to be sure.
- **Hardware**: bare metal. Own copper lists, AGA registers written directly (BPLCON3 `$0106` bank switching for 256-colour palettes, FMODE `$01FC`), mouse via `$DFF00A` / CIA `$BFE001`.
- **Packer**: CrunchMania 1.x, `CrM!` (non-LZH) variant only.
- **Music**: a ProTracker-style replayer is present in both binaries (Amiga period table at intro `$19C6`/`$1C18`, main `$1AE46`/`$1B098`). No `M.K.` tag anywhere, so modules are stored with the tag stripped or in a converted format. To be located in phase 2. Composer: Michał 'Dixan05' Prochownik.
- **Graphics**: Ryszard 'Justus' Bagiński. Scenes are digitised B&W photographs of real locations and people from Żywiec and Jeleśnia (per the credits).

## Asset formats

### Scene frames (68614 bytes)
- 464 × 169 pixels, **7 bitplanes, non-interleaved** (plane 0 rows, then plane 1, ...), 58 bytes per row. 58 × 169 × 7 = 68614 exactly. No header, **no palette in the file**.
- Rendered with a linear grey ramp they already look right (`work/test/sheet.png`), so the real palette is probably a grey or sepia ramp. It lives in the main binary or in a copper list (phase 2).

### Full screens (intro)
- 320×256 and 640×256 at 8 planes (AGA 256 colours), non-interleaved. Palettes are again external, probably in copper lists. The intro has 16 BPLCON3 + COLOR00 copper sequences.

### UI, cursor, fonts, inventory icons
- Not yet located. They are inside the main binary (uncompressed), probably in the `$4C000`..`$77000` region, which sits between code and text.

### Text
- Plain byte strings, NUL-terminated, `\n` line breaks, embedded in the binaries and referenced by absolute address from code.
- **Polish charset** (empirical, verified against hundreds of words; uppercase = lowercase - `$20`):

  | ą | ć | ę | ł | ń | ó | ś | ź | ż |
  |---|---|---|---|---|---|---|---|---|
  | E6 | E7 | EA | EE | F1 | F3 | F5 | FB | FE |
  | **Ą** C6 | **Ć** C7 | **Ę** CA | **Ł** CE | **Ń** D1 | **Ó** D3 | **Ś** D5 | **Ź** DB | **Ż** DE |

  This is not the standard AmigaPL table (which has ą=E2, ł=EE, ś=F4 ...). Implemented in `tools/plchars.py`.
- Main game text block: offsets `$77900`..`$93500`, ~1345 strings, ~115 KB, ~619 dialogue lines starting with `- `. Contents: "wrong action" quips, inventory names (12-char padded, e.g. `' papierosy  '`), verb menu, save/load menu, hotspot names + descriptions per location, dialogue trees, several death endings, the good ending, credits.
- Verb menu: **Oglądaj, Rozmawiaj, Użyj, Otwórz, Weź/Daj**, plus Menu (Zapisz, Wczytaj, Muzyka, Restart). Saves: 3 slots on a separate formatted save disk.

### Hotspots (clean data)
- Tables of 8-byte records `x1, x2, y1, y2` (big-endian words, inclusive), terminated by the word `$BACA`. Hotspot ids are 1-based in table order.
- A location activates its table with `move.l #table, $1CEC2`. The hit test (`$1D7BA`) returns d2 = hotspot id or -1.
- Found: **104 table activations, 59 unique tables, ~253 hotspots** in total. Coordinates go up to x = 478, so they are screen coordinates (the frame is shown at some x offset on a wider screen). The exact mapping is still to be confirmed.

## How the game logic works (first look)

Location 1 (station, routine at `$35DC`), simplified:

```
move.b #4,$7bbd4          ; location / frame id
jsr    load+show frame    ; $15732, $1953c, ...
move.l #$1ced0,$1cec2     ; hotspot table (5 hotspots)
loop:
  wait VBL
  jsr  $1d7ba             ; d2 = hotspot under mouse
  cmpi.l #1,d2 / bne ...  ; per hotspot:
    cmpi.w #1,$7a928      ;   verb == Oglądaj?
    cmpi.b #1,$7c0e2      ;   flag checks
    lea    $7fd51,a2      ;   pick text
    jsr    $1c6c8         ;   print text
  btst #6,$bfe001         ; LMB
```

So the "script" is native code. On the plus side it is **extremely regular**: the same idioms (hotspot compare, verb compare, flag byte compare/set, `lea text`, `jsr print`, jump to another location routine) repeat throughout. That makes a semi-automatic **lifter** realistic. It would walk each location routine with capstone, recognise the idioms, and emit a readable per-location script (YAML/Python) that the new engine runs. Anything the lifter can't recognise gets flagged for manual reading.

## Feasibility verdict

**Feasible, and a good fit for the ScummVM-style approach.** Asset extraction is close to trivial now. The engine itself is small: a static scene image, rectangle hotspots, a verb bar, inventory, text boxes and multiple-choice dialogue. All of the real work is in recovering the per-location logic from asm.

Main risks:
1. **Logic lifting**: ~60 locations of hand-written asm. The idioms are regular, but there will be one-off special cases (minigames, the "6 klocków" puzzle, timed events, deaths).
2. **Palettes / UI art**: they have to be dug out of copper lists and the uncompressed data region. That's tedious, but low risk.
3. **Music**: the replayer is ProTracker-like, but the module format needs confirming. Worst case, convert or rip it via emulation.
4. **Ground truth**: some behaviour is only verifiable by watching the original run. A WinUAE session with your Kickstart would help a lot in phase 3, mainly to capture palettes, screen layout and coordinate offsets.

## Proposed plan and rough effort

Effort below is in focused working sessions (a few hours each, me driving, you reviewing).

| Phase | Work | Effort |
|---|---|---|
| 2a | Batch exporter: all frames and intro screens to PNG, all text to UTF-8 JSON (by address), hotspot tables to JSON | 1 session |
| 2b | Find palettes (copper lists / colour tables), cursor, font, UI bar, inventory icons. Re-export with real colours | 1-3 sessions |
| 2c | Locate and convert music + samples (MOD/WAV) | 1-2 sessions |
| 3a | Map the main loop, location dispatcher, frame-id to disk/file mapping, the print, dialogue and inventory routines, and the flag/variable map. Write ENGINE.md | 2-3 sessions |
| 3b | Asm-to-script lifter for location routines, iterated until most locations lift cleanly | 2-4 sessions |
| 3c | pygame-ce engine MVP: first location (station) fully playable with original art, cursor, hotspots, verbs, one dialogue | 2-3 sessions |
| 3d | Remaining locations, inventory, dialogues, endings, save/load, intro | 5-10+ sessions, mostly validation |

**MVP (station playable): roughly 8-12 sessions from now. Full game: roughly 20-30 sessions.** Only the lifter quality moves these numbers much.

## Tools written so far (`tools/`)

| Script | Purpose |
|---|---|
| `crunchmania.py` | Pure-Python CrM!/CrM2 decruncher (verified on all 61 files) |
| `scan_crm.py` | Find CrM headers in any blob |
| `unpack_disks.py` | Decrunch everything from the 4 ADFs into `work/unpacked/` |
| `diskmap.py` | Per-track entropy and magic-tag map of an ADF |
| `dis68k.py` | Capstone 68020 disassembler for raw blobs at a given load address |
| `planar.py` | Amiga planar/interleaved bitplanes to PNG |
| `plchars.py` | Game's Polish charset decoder |
| `strings.py` | Text dump with offsets and Polish decoding |

Dependencies installed (pip, user Python 3.14): `amitools`, `capstone`, `pillow`. Nothing heavy has been installed.

## Open questions for Pete

1. Is a WinUAE (or FS-UAE) install OK for phase 2/3? It would only be used to capture palettes and screen layout from the running original, and I would need your Kickstart 3.x ROM.
2. Script format for the lifted logic: YAML (data-like, easy to diff) or plain Python modules (more flexible for the odd special cases)? My recommendation is Python modules with a tiny DSL.
3. Output resolution: native 464×169 scene scaled up with the original layout (my default), or something modernised?
