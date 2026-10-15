# Alfabet Śmierci: walkthrough derived from the lifted scripts

Derived from `scripts/loc_XX.alf` and `scripts/common.alf`, then played through in the port by `tools/playthrough.py`. Machine-readable twin: `tests/walkthrough.json` (same step numbers). Inventory slot numbers here come from a simulation; the playthrough bot picks items by name from the real inventory instead (one simulated slot was wrong at step 140).

Result: **263 steps** from the first frame of loc_04 (railway station, after the intro) to the ending (loc_3D), about 120 of them plain walks. No deaths on the main path. Phase 1 = real world (`$7C0CE`=1, steps 1-55), phase 2 = dream world (`$7C0CE`=2, steps 56-263).

## 0. How the game reads input (needed for autoplay)

Coordinates: x = hires pixel 0..639, y = half-line (screen line = y/2), same as the mouse registers and the hotspot tables. Every rect is `[x1,x2,y1,y2]`, inclusive. `hit_test` returns the **first** rect that contains the mouse (`src/natives.c:256`), so overlapping rects are resolved by order (the generator checked that no chosen centre falls in an earlier rect).

Right panel (UI table `$1D716`, d3), centres (x, y half-line):

| d3 | what | rect | centre |
|---|---|---|---|
| 1-6 | inventory slots 1-6 | x 519-624, y 35-52 / 59-77 / 83-102 / 107-125 / 131-149 / 155-173 | (571, 43 / 68 / 92 / 116 / 140 / 164) |
| 7 | status line | [510,630,179,197] | (do not use) |
| 8 / 9 | inventory up / down | [523,566,204,233] / [576,620,204,233] | (544,218) / (598,218) |
| 10 / 11 | Oglądaj / Rozmawiaj | [523,566,240,282] / [576,620,240,282] | (544,261) / (598,261) |
| 12 / 13 | Użyj / Otwórz | [523,566,290,333] / [576,620,290,333] | (544,311) / (598,311) |
| 14 / 15 | Weź/Daj / Menu | [523,566,340,382] / [576,620,340,382] | (544,361) / (598,361) |

Dialogue options: table `$1D790`, row n = `[15,620, 404+21(n-1), 417+21(n-1)]`, centre (317, 410/431/452/473/494). **Row = screen line of the option list, not option number**: an option that wraps over two lines occupies two rows (both work). The step table always gives rows. While an option list is up the mouse is clamped to y 402..495.

Rules that matter for a bot:
- `panel_mode` starts at 1 = verbs. Button 15 (Menu) toggles to the menu page where 10-14 mean Zapisz / Wczytaj / Muzyka / **Restart** / "?" (credits) (`common.alf` ui_panel, `panel_mode ~= 1` branches). Never click Menu.
- Verb buttons set `verb_*` (14 sets take AND give). Verbs stay set until an action calls `reset_verbs`.
- **Item selection**: inventory slots react only with Use or Weź/Daj active, and only when `inv_click_armed`==1, which is re-armed when the pointer is over no UI rect (d3 == -1). Before every slot click move to a neutral point, e.g. (495,300): outside every scene rect (max scene x2 is 479) and every UI rect. A slot click with Use sets the item's USE word `w[$7C1F0+2*id]` (`sub_187C6`, common.alf:3901), with Weź/Daj the GIVE word `w[$7C172+2*id]` (`sub_18266`, common.alf:3613). Several words are only armed in one location (noted per step).
- **Combinations** (`ui_combine`, common.alf:3309-3612): Use, slot A, neutral point, slot B. The game checks both words every frame.
- **Hotspot verbs**: most handlers act only if `hover_mode`==1, which is set on any frame where the pointer is over no scene hotspot (the panel counts). Clicking a verb/slot first and then the hotspot satisfies this. Walk exits (no verb) only need lmb while over the exit.
- **Off-hotspot actions** (`talk_panel`, `use_panel`, `give_panel` in the table): many rooms run Talk, or Use/Give + item, in the `d2 == -1` branch. Since the pointer is on the panel when you click, the action fires immediately; do not click the scene.
- **Speech** (`say`, common.alf:6863) waits for a right click (press + release), full-screen pages (`print_alt` + `wait_right_click_fast`) too. Right clicks at any other time are ignored (rmb is only read in those waits), so a bot can simply right-click every ~10 frames until the expected screen appears.
- **Inventory order**: `inventory_add` (common.alf:4455) inserts at the FRONT, removals close the gap. Slot numbers in the table come from simulating this. Three steps need an item beyond slot 6 (151, 246, 248): click the down arrow k times (lmb held exactly one frame each, the arrow scrolls every frame lmb is down, common.alf:2738-2760), use slot 6, then click up k times.
- **Rest the pointer between actions**: some rooms (e.g. loc_33) set `hover_mode` = 1 only on a frame where the pointer is over no scene hotspot AND no verb is chosen. After an action that leaves the pointer on a hotspot, choosing the next verb straight away leaves `hover_mode` at 0 and the next hotspot click does nothing. A player moves the mouse away naturally; the bot rests at (495,300) before every step.
- **Joystick FIRE**: three steps (179, 182, 187) require the port-2 fire button (CIA-A PRA bit 7, e.g. `loc_2D.alf:33-35`). In the port: space, middle mouse button or any pad button; autoplay `fire` / `fireup`.
- **Death = full restart**: every game_over path ends in `sub_142CA` (common.alf:642), which copies the boot snapshot `$7C270` back over the whole state and jumps to loc_04. Use the panel quick save before risky steps.

Verbs in the step table: `walk` (lmb on an exit, no verb), `look`/`talk`/`open`/`take`/`use`/`give` (verb button, item slot if any, then the hotspot), `talk_panel` / `use_panel` / `give_panel` (verb button [+ slot], fires off-hotspot), `combine` (Use + two slots), `dialogue` (a forced conversation: just click the rows), `fire` (joystick), `wait` (cutscene: right-click through).

## 1. Location graph

Disk = data disk the frame comes from (`ensure_disk` table, common.alf:701; value 1/2/3 = ADF disk2/3/4, 4/5 = partial loads of disk2/disk4, see `load_disk` in src/natives.c). "none" = frame inside the main binary, no disk access.

| loc | routine | disk | entered from | exits (hotspot, rect [x1,x2,y1,y2], centre in hires x / half-line y; screen line = y/2) | notes |
|---|---|---|---|---|---|
| loc_02 | $13EF6 (+ loc_02_2 $13F3A) | disk2 | game_over random pick |  | death screen, then full restart at loc_04 |
| loc_03 | $030F0 | disk2 | loc_04 hs1 while train_rides==0 |  | Talk (panel) -> dialogue -> loc_04 |
| loc_04 | $035DC | disk2 | start of game (boot jumps here after the intro), every death/restart, loc_1D talk row 1, loc_1E bad visit | hs1 [254,464,139,173] c(359,156) walk -> loc_03 if train_rides==0; loc_1D if $7C0E2~=1 and $7C0E1==1 and $7C145==0 and $7C139==0; else nothing<br>hs5 [16,468,316,354] c(242,335) walk -> loc_05 |  |
| loc_05 | $0390A | none (main binary frame) | loc_04, loc_06, loc_07, loc_08, loc_0A, loc_0B, loc_0D, loc_16, loc_17, loc_18, loc_19, loc_1C, loc_0C (phase 2), loc_27 | hs4 [277,317,144,174] c(297,159) walk -> loc_07 (shop) (layout A ($7C0CE~=2), only while $7C0D1~=1)<br>hs6 [16,32,173,246] c(24,209) walk -> loc_04 (layout A)<br>hs8 [433,466,214,355] c(449,284) walk -> loc_06 (map) (layout A)<br>hs4 [445,472,190,262] c(458,226) walk -> loc_09 if $7C144~=1 else loc_18 (layout B ($7C0CE==2), only while $7C0FC~=1)<br>hs6 [16,175,312,354] c(95,333) walk -> loc_27 (layout B)<br>hs7 [320,466,312,354] c(393,333) walk -> loc_19 (layout B, only while $7C12D~=1) | layout A hs7 = papierosy (take, optional) |
| loc_06 | $04028 | none (main binary frame) | loc_05 hs8 | hs1 [402,466,32,354] c(434,193) walk -> loc_05<br>hs10 [249,258,278,288] c(253,283) walk -> loc_05<br>hs2 [305,315,163,174] c(310,168) walk -> loc_08 ($7C0C6==1)<br>hs3 [285,294,186,198] c(289,192) walk -> loc_0A ($7C0C7==1 and train_rides==1)<br>hs4 [191,200,186,197] c(195,191) walk -> loc_0B ($7C0C8==1 and train_rides==1)<br>hs5 [222,231,215,224] c(226,219) walk -> loc_1B ($7C0C9==1)<br>hs6 [255,263,239,249] c(259,244) walk -> loc_0D ($7C0CA==1)<br>hs7 [246,255,307,316] c(250,311) walk -> loc_18 if $7C0E6==1 else loc_09 ($7C0CB==1)<br>hs8 [229,237,317,327] c(233,322) walk -> loc_19 ($7C0CC==1)<br>hs9 [311,321,337,347] c(316,342) walk -> loc_11 ($7C0CD==1) | markers are tiny (about 9x10 px), aim at the centres |
| loc_07 | $044FA | disk2 | loc_05 layout A hs4 | hs1 [18,263,318,354] c(140,336) walk -> loc_05 | shop, optional |
| loc_08 | $04CE4 | disk2 | loc_06 hs2 | hs1 [17,49,32,354] c(33,193) walk -> loc_05 |  |
| loc_09 | $0527A | disk2 | loc_06 hs7, loc_05 layout B hs4 | hs1 [17,91,32,354] c(54,193) walk -> loc_05 (phase 1) | phase 1: Talk (panel) with $7C150==0 -> loc_0C; phase 2: forced cutscene -> loc_0C |
| loc_0A | $05A62 | disk2 | loc_06 hs3 | hs1 [16,60,208,284] c(38,246) walk -> loc_05 | dead end, optional |
| loc_0B | $05C3C | disk2 | loc_06 hs4, loc_0F exit (2nd ride) | hs1 [17,466,315,354] c(241,334) walk -> loc_05 | first-visit dialogue -> loc_16 (rows 2-4) or loc_0E death (row 1); $7C0E9==1 and $7C0F0~=1 -> auto loc_16; Talk later can -> loc_0E (death) |
| loc_0C | $06252 | disk2 | loc_09 |  | phase 1: exit hs1 or look hs3 both fall into the phone dialogue: row 1 -> loc_0F, row 2 -> loc_18; phase 2 ($1D08C): scripted, -> loc_05 |
| loc_0D | $067A8 | disk2 | loc_06 hs6, loc_27 hs2, loc_15, loc_31, loc_2C | hs1 [16,39,279,347] c(27,313) walk -> loc_05 (phase 1)<br>hs4 [178,191,83,116] c(184,99) use sznur(7), later walk -> loc_31 (phase 1, needs $7C0F0==1 (walk once $7C0F2==1))<br>hs1 [16,39,279,347] c(27,313) walk -> loc_27 (phase 2)<br>hs4 [178,191,83,116] c(184,99) use sznur(12), later walk -> loc_31 (phase 2, needs $7C0F7==1; blocked once $7C147 and $7C146 are both 0)<br>hs5 [191,214,161,170] c(202,165) use mały klucz, then walk -> loc_2C (phase 2, needs $7C133==1, $7C12D~=1, $7C13C~=0) |  |
| loc_0E | $071B2 | disk2 | loc_0B (wrong row / talk trap) |  | death cutscene -> game_over |
| loc_0F | $07214 + loc_0F_2 $072E2 | disk2 | loc_0C row 1, loc_11 hs3 | hs1 [154,468,32,104] c(311,68) walk -> loc_11 if $7C0E4==1; loc_0B if $7C0DA~=1 and $7C0E9~=0; else loc_05 | hs3 Schowek: open, take sznur(7) |
| loc_10 | $075AC | disk3 | loc_11 hs1, loc_13 (parasol) | hs1 [446,475,32,226] c(460,129) walk -> loc_11 | Talk (panel) -> doctor -> loc_12 -> loc_13 |
| loc_11 | $07D32 | disk3 | loc_0F, loc_06 hs9, loc_27 hs9, loc_10, loc_13 | hs1 [239,333,39,287] c(286,163) walk -> loc_17 if $7C0F0==1; loc_10 if $7C0E9~=1 (phase 1, needs $7C0DA~=1)<br>hs3 [435,466,234,356] c(450,295) walk -> $7C0E9==0: loc_05 (or loc_0F if $7C0E4==1); $7C0E9~=0: loc_05 if $7C0DA==1 else loc_0F (phase 1)<br>hs1 [239,333,39,287] c(286,163) walk -> loc_32 if $7C147==0; loc_13 if $7C16D==0 (phase 2, needs $7C15D~=1, $7C12D~=1, $7C132~=1, $7C16E~=0)<br>hs3 [435,466,234,356] c(450,295) walk -> loc_27 (phase 2) |  |
| loc_12 | $082FC (+ loc_12_2 $1395C ending, loc_12_3 death) | disk3 | loc_10 dream (phase 1), loc_2D hs2 use/look (phase 2), loc_19 boss win (loc_12_2) | hs1 [427,466,256,356] c(446,306) walk -> loc_2D (phase 2) | phase 1 -> loc_13 automatically; loc_12_2 -> loc_3C |
| loc_13 | $08720 | disk3 | loc_12 (phase 1), loc_11 / loc_32 (phase 2) | hs1 [17,82,32,354] c(49,193) walk -> loc_11 (phase 2, needs $7C16E==0) | phase 1: parasol -> loc_10; phase 2 FIRE -> loc_11 (sets $7C132, avoid) |
| loc_15 | $08D34 | disk2 | loc_31 hs4 | hs1 [17,117,32,354] c(67,193) walk -> loc_0D |  |
| loc_16 | $0917C | disk2 | loc_0B | hs1 [20,54,32,261] c(37,146) walk -> loc_05 |  |
| loc_17 | $09952 | disk2 (partial) | loc_11 hs1 with $7C0F0==1 |  | vision cutscene, sets $7C0DA=1 -> loc_05 (optional) |
| loc_18 | $099D6 | disk2 | loc_06 hs7 ($7C0E6==1), loc_05 B hs4 ($7C144==1), loc_0C row 2 | hs1 [17,78,32,354] c(47,193) walk -> loc_05 | parish records, story only |
| loc_19 | $09E40 | disk2 | loc_06 hs8, loc_05 layout B hs7 | hs1 [288,468,310,354] c(378,332) walk -> loc_05 (phase 1)<br>hs1 [288,468,310,354] c(378,332) walk -> loc_05 (phase 2 (boss)) | boss win -> loc_12_2 -> loc_3C |
| loc_1B | $0A676 | disk2 | loc_06 hs5 | hs1 [50,358,319,356] c(204,337) walk -> loc_06 | Talk (panel) -> loc_1C -> loc_05 |
| loc_1C | $0A946 | disk2 | loc_1B |  | cutscene, $7C0E1=1 -> loc_05 |
| loc_1D | $0A9B4 | disk3 | loc_04 hs1 (second ride) |  | no walk exit: Talk -> loc_1E (rows 2-4) or loc_04 (row 1, soft-lock) |
| loc_1E | $0AC3E | disk3 | loc_1D, loc_1F hs1 | hs1 [401,474,333,356] c(437,344) walk -> loc_1F | hs4 potion -> loc_21; phase 2 entry redirects to loc_21; bad visit -> loc_04 |
| loc_1F | $0B558 | disk3 | loc_1E, loc_21, loc_20, loc_22 hs3 | hs1 [433,468,294,354] c(450,324) walk -> loc_1E (phase 1)<br>hs1 [433,468,102,274] c(450,188) walk -> loc_1E (-> loc_21) (phase 2)<br>hs6 [237,420,332,356] c(328,344) walk -> loc_22 (phase 2)<br>hs7 [16,64,102,356] c(40,229) walk -> loc_20 (phase 2, only while $7C0EC==0) |  |
| loc_20 | $0BBDE | disk3 | loc_1F hs7 | hs1 [16,54,32,356] c(35,194) walk -> loc_1F | deer + loaded pistol -> loc_1F |
| loc_21 | $0B080 | disk3 | loc_1E (dream) | hs1 [401,474,333,356] c(437,344) walk -> loc_1F |  |
| loc_22 | $0BF1A | disk3 | loc_1F hs6, loc_23, loc_24, loc_34 hs3 | hs1 [450,473,160,291] c(461,225) walk -> loc_24<br>hs2 [17,39,139,361] c(28,250) walk -> loc_23 if $7C155~=0 else loc_34<br>hs3 [97,255,341,366] c(176,353) walk -> loc_1F |  |
| loc_23 | $0CDA0 | disk3 | loc_22 hs2 | hs1 [116,278,340,356] c(197,348) walk -> loc_22 | give jabłko -> loc_34 |
| loc_24 | $0D2B2 | disk3 | loc_22 hs1, loc_25 | hs1 [151,326,332,349] c(238,340) walk -> loc_22<br>hs2 [21,28,272,356] c(24,314) walk -> loc_25 |  |
| loc_25 | $0D706 | disk3 | loc_24 hs2 | hs1 [375,457,337,356] c(416,346) walk -> loc_24 |  |
| loc_27 | $0DA7A | disk3 | loc_05 B hs6, loc_0D B hs1, loc_11 B hs3, loc_2D hs3, loc_28, loc_2B, loc_39 | hs1 [192,245,195,244] c(218,219) walk -> loc_05<br>hs2 [20,27,301,344] c(23,322) walk -> loc_0D if $7C0DF==1, loc_39 if $7C0E0==1 (only when $7C105~=0)<br>hs9 [445,471,229,355] c(458,292) walk -> loc_11<br>hs10 [163,302,332,345] c(232,338) walk -> loc_2D<br>hs11 [98,150,133,170] c(124,151) walk -> loc_28 (only while $7C102~=1) | ENTRY DEATH if $7C12D~=1 and $7C126==1 and $7C16D~=0 (loc_27.alf:25-37) |
| loc_28 | $0EA88 | disk3 | loc_27 hs11 |  | 1st visit Talk -> loc_27; 2nd visit forced dialogue -> loc_2B, loc_27 or death |
| loc_2B | $0F15E | disk4 | loc_28 (dialogue 3,2,2,4) |  | event -> loc_27 (powder in beer) or death |
| loc_2C | $0F51C | disk4 | loc_0D B hs5 | hs6 [266,367,331,359] c(316,345) walk -> loc_0D |  |
| loc_2D | $0F91A | disk3 | loc_27 hs10, loc_34 hs5, loc_12 | hs2 [379,415,170,228] c(397,199) use / look -> loc_12 (use = jump, $7C126=1; look = visit)<br>hs3 [185,240,171,194] c(212,182) walk -> loc_27<br>hs4 [204,304,336,351] c(254,343) walk -> loc_34 |  |
| loc_2E | $0FC78 | disk4 | loc_34 hs4, loc_2F, loc_30 | hs2 [67,392,337,347] c(229,342) walk -> loc_34<br>hs3 [306,338,172,208] c(322,190) walk -> loc_30<br>hs4 [19,66,226,275] c(42,250) walk -> loc_2F (only while $7C12D~=1) |  |
| loc_2F | $0FE8C | disk4 | loc_2E hs4 | hs2 [17,65,32,354] c(41,193) walk -> loc_2E |  |
| loc_30 | $10880 | disk4 | loc_2E hs3, loc_33 | hs3 [19,47,282,358] c(33,320) walk -> loc_2E<br>hs4 [388,465,161,203] c(426,182) walk -> loc_33 (only when $7C151==0) |  |
| loc_31 | $10B64 (+ loc_31_2 $14282 death screen) | disk4 (partial) | loc_0D hs4 | hs3 [16,163,331,349] c(89,340) walk -> loc_0D<br>hs4 [438,469,275,364] c(453,319) walk -> loc_15 |  |
| loc_32 | $112F4 | disk3 | loc_11 B hs1 | hs3 [17,236,319,352] c(126,335) walk -> loc_13 |  |
| loc_33 | $1158C | disk4 | loc_30 hs4, loc_37 | hs3 [17,65,229,356] c(41,292) walk -> loc_30 ($7C100==0)<br>hs2 [365,417,160,241] c(391,200) walk -> loc_37 ($7C100==1)<br>hs3 [17,65,229,356] c(41,292) walk -> loc_30 ($7C100==1) |  |
| loc_34 | $11C06 | none (main binary frame) | loc_23 (jabłko), loc_22 hs2, loc_2D hs4, loc_2E hs2, loc_35 | hs3 [92,260,331,349] c(176,340) walk -> loc_22<br>hs4 [16,33,244,307] c(24,275) walk -> loc_2E (only while $7C16C~=1)<br>hs5 [162,194,193,227] c(178,210) walk -> loc_2D<br>hs6 [427,467,185,255] c(447,220) walk -> loc_35 (only when $7C101==1) |  |
| loc_35 | $1224C (+ loc_35_2 $141DE death screen) | disk3 | loc_34 hs6 | hs3 [18,100,325,356] c(59,340) walk -> loc_34 |  |
| loc_37 | $12E9E | disk4 | loc_33 ($7C100==1), loc_38 | hs2 [144,331,170,365] c(237,267) use -> loc_38 (needs $7C0FD==1)<br>hs3 [366,475,329,359] c(420,344) walk -> loc_33 |  |
| loc_38 | $1316A | disk4 | loc_37 hs2 | hs3 [42,65,123,284] c(53,203) walk -> loc_37 |  |
| loc_39 | $13392 | disk2 | loc_27 hs2 ($7C0E0==1), loc_3A | hs3 [326,371,179,261] c(348,220) walk -> loc_3A<br>hs4 [36,50,209,243] c(43,226) walk -> loc_27 |  |
| loc_3A | $1366C | disk2 | loc_39 hs3 | hs3 [16,309,329,356] c(162,342) walk -> loc_39 |  |
| loc_3C | $13A84 | disk4 | loc_12_2 |  | use buteleczka on Marlena (hs1) -> loc_3D |
| loc_3D | $13CFA | (whatever is loaded, disk4) | loc_3C |  | ending cards, then halt |

## 2. Story route in short

Phase 1 (real world):
1. Station: board the train (loc_03), talk to Gerwazy: Janina's address. Walk to town, map, Marlena (fake name!), talk: parasol + police/parish/cemetery on the map.
2. Parish: tell the priest about the parasol, phone call, drive to the hospital (take the rope from the glovebox), talk to the doctor, dream: hit the nurse with the parasol at once. Get the knife, ride back, Marlena's news.
3. Police: rope through the window, the doctor in the cell sends you to the shelf: akta. Janina's house: threaten Stryczyński with the knife: Urylewscy address. Old woman: Gerwazy's daughter. Cemetery: old key.
4. Second train ride, Marysia, use the akta, throw the key into the well, drink the potion. Inventory is wiped, the dream begins.

Phase 2 (dream):
5. Bucket, hammer, pistol, brush, cup. Holy water in the cup wakes the man on the bench. Nail, table, fix it with the hammer, apple, give it to the aunties: textbook. Swap the textbook for the herbarium: herbs appear. Take Ślepik.
6. Market: steal the watch, trade it for the old grinder, grind Ślepik into powder. Butcher: talk once, then lure him into the inn (3,2,2,4), powder into his beer: small key. Handlarz tells you where the butcher lived: police basement with the small key: bullet. Load the pistol.
7. River spirit (look through the railing): old grinder for a new one. Shoot the deer: glasses open the forest road. Witch: give the new grinder (palm reading). Scarecrow rope, police window, doctor: kluczyk; camera from the shelf. Hospital: ether + gauze on the witch, photograph her: fotka Xanadu. Spirit: bracelet, the scarecrow lets you pass.
8. Cellar: fill the bucket, splash the cellar, photograph the force field, spirit: crystal ball, witch: potion, drink it, take the space suit, the witch seals it. Jump into the river: the power ($7C101).
9. FIRE on the bridge, crossroads and forest: 5 blocks, Valence, pick the right missing piece (row 3), assemble, hang the puzzle on the nail. Cellar opens: fridge, secret room, old book. Witch: czar zamiany.
10. Transformed (czar zamiany), pass the market where Bercer waits: parish, priest gives the church key. Back to normal (re-enter loc_35), open the church, kropidło, fill it, move the book right. Transform again, market, "Do masarza" now leads to loc_39/3A: fishing rod and paint. Fish the second old key from the well (market is now safe). Paint the mirror, take it.
11. Re-enter loc_35 (back to normal), market, cemetery: mirror, kropidło, mirror. Spirit's farewell, buteleczka, Marlena drinks it: ending.

## 3. Step table

Columns: n, location, verb, target hotspot (index, rect `[x1,x2,y1,y2]`, centre in hires x / half-line y, and screen point x, line), item (address, inventory slot at that moment), dialogue rows in click order, notes with required (`needs`) and set (`sets`) state and the next location. Flags are bytes `b[$7Cxxx]` unless noted; initial values: inventory empty, `$7C134..$7C172` = 1 except `$7C14C`, plus `$7C0BC $7C0C7 $7C0C8 $7C0CE $7C0DD $7C0DF $7C113` = 1, all else 0 (read from the binary).

| n | loc | verb | target | item | dialogue rows | notes |
|---|---|---|---|---|---|---|
| 1 | loc_04 | walk | hs1 [254, 464, 139, 173] c(359,156) scr(359,78) |  |  | Pociąg. First click goes into the compartment because train_rides == 0 (loc_04.alf:66); -> loc_03 |
| 2 | loc_03 | talk_panel |  |  | 2,2 | Talk button starts the chat with Gerwazy (loc_03.alf:53). Q1 $84538 row 2, Q3 $84E0C row 2 (any row of Q3 works); sets train_rides=1 (loc_03.alf:69), $7C0C6=1 Janina on map (sub_035CA); -> loc_04 |
| 3 | loc_04 | walk | hs5 [16, 468, 316, 354] c(242,335) scr(242,167) |  |  | Droga do miasteczka; -> loc_05 |
| 4 | loc_05 | walk | hs8 [433, 466, 214, 355] c(449,284) scr(449,142) |  |  | Plan miasta; -> loc_06 |
| 5 | loc_06 | walk | hs4 [191, 200, 186, 197] c(195,191) scr(195,95) |  |  | Marlena Żyhoniuk; needs train_rides==1, $7C0C8==1 (initial); -> loc_0B |
| 6 | loc_0B | dialogue |  |  | 2 | Forced on first visit, $87A20. Row 1 ('Lenia? To ja, Tomek!') leads to loc_0E = DEATH. Rows 2-4 are one option (fake name); sets $7C0F4=1, $7C0D5=1; -> loc_16 |
| 7 | loc_16 | talk_panel |  |  | 1,2 | Marlena: $8A63C row 1 (any of 1-4), then $8A800 row 2 (row 1 also gives the parasol); sets $7C150=0, $7C0CA=1 (Policja), $7C0CB=1 (Parafia), $7C0CC=1 (Cmentarz) (loc_16.alf:178-196) |
| 8 | loc_16 | walk | hs1 [20, 54, 32, 261] c(37,146) scr(37,73) |  |  | Wyjście; -> loc_05 |
| 9 | loc_05 | walk | hs8 [433, 466, 214, 355] c(449,284) scr(449,142) |  |  | -> loc_06 |
| 10 | loc_06 | walk | hs7 [246, 255, 307, 316] c(250,311) scr(250,155) |  |  | Parafia św. Wojciecha; needs $7C0CB==1; $7C0E6==0 so it is loc_09 and not loc_18; -> loc_09 |
| 11 | loc_09 | talk_panel |  |  | 1,1 | Priest: $86ED0 row 1 ('Zapomniał ksiądz PARASOLA'), then $8711B any row (1 used); needs $7C150==0 (parasol taken), otherwise only small talk; sets $7C0E8=1; loc_0C sets $7C0E6=1; -> loc_0C |
| 12 | loc_0C | look | hs3 [265, 387, 272, 316] c(326,294) scr(326,147) |  | 1 | Look at Księga: record page (right click), then the phone call falls through to dialogue $88104: row 1 'Mogę nawet poprowadzić' -> car. Row 2 sets $7C0E7=1 and goes to loc_18 (avoid: $7C0E7 arms the loc_0B talk death); -> loc_0F |
| 13 | loc_0F | wait |  |  |  | loc_0F ride cutscene (timed, ~4 x delay_200), then loc_0F_2 interactive; sets $7C0E4 += 1 |
| 14 | loc_0F | open | hs3 [303, 378, 186, 212] c(340,199) scr(340,99) |  |  | Schowek; sets $7C0E3=1 |
| 15 | loc_0F | take | hs3 [303, 378, 186, 212] c(340,199) scr(340,99) |  |  | Schowek: sznur (id 7); needs $7C0E3==1; sets $7C13A=0 |
| 16 | loc_0F | walk | hs1 [154, 468, 32, 104] c(311,68) scr(311,34) |  |  | Wyjście; goes to the hospital because $7C0E4==1 (loc_0F.alf:164); -> loc_11 |
| 17 | loc_11 | walk | hs1 [239, 333, 39, 287] c(286,163) scr(286,81) |  |  | Wejście; needs $7C0DA~=1, $7C0F0~=1, $7C0E9~=1; -> loc_10 |
| 18 | loc_10 | talk_panel |  |  | 1,1,1 | Doctor (common sub_07816): $88884 row 1, $88A3C any (1), $897B4 any (1). Tomek falls asleep: loc_12 cutscene (river spirit) then loc_13; -> loc_13 |
| 19 | loc_13 | use_panel |  | parasol $7B5DE (slot 2) |  | TIMED DEATH ROOM. Immediately: Use, then the parasol slot. Look/Talk/Open/Give with the cursor off the nurse = game_over_b; idle timeout (1000 calls of delay_c9e2, ~20 s) = game_over_b (loc_13.alf:55-80); sets $7C0E9=1 (loc_13.alf:63); -> loc_10 |
| 20 | loc_10 | wait |  |  |  | Entry cutscene with the doctor (loc_10.alf:16-41): nóż added; sets $7C14E=0 |
| 21 | loc_10 | walk | hs1 [446, 475, 32, 226] c(460,129) scr(460,64) |  |  | Wyjście; -> loc_11 |
| 22 | loc_11 | walk | hs3 [435, 466, 234, 356] c(450,295) scr(450,147) |  |  | Wyjście; with $7C0E9~=0 and $7C0DA~=1 it goes to the car (loc_11.alf:97-131); -> loc_0F |
| 23 | loc_0F | wait |  |  |  | ride cutscene again ($7C0E4=2) |
| 24 | loc_0F | walk | hs1 [154, 468, 32, 104] c(311,68) scr(311,34) |  |  | Wyjście; $7C0E4~=1, $7C0DA~=1, $7C0E9~=0 -> loc_0B, which says 'Wskakuj!' and jumps to loc_16 (loc_0B.alf:83); -> loc_0B |
| 25 | loc_16 | dialogue |  |  | 1,1 | Forced entry cutscene (repeats on every entry while $7C0E9==1): $8AC27 any row (1-5), then $8B210 row 1 or 3 (2/4 = 'Idiota!', harmless); sets $7C0F0=1 (loc_16.alf:24) |
| 26 | loc_16 | walk | hs1 [20, 54, 32, 261] c(37,146) scr(37,73) |  |  | -> loc_05 |
| 27 | loc_05 | walk | hs8 [433, 466, 214, 355] c(449,284) scr(449,142) |  |  | -> loc_06 |
| 28 | loc_06 | walk | hs6 [255, 263, 239, 249] c(259,244) scr(259,122) |  |  | Policja; needs $7C0CA==1; -> loc_0D |
| 29 | loc_0D | use | hs4 [178, 191, 83, 116] c(184,99) scr(184,49) | sznur (id 7) $7B450 (slot 2) |  | Okno + sznur (id 7). Needs $7C0F0==1 (else 'Nie sądzę żebym miał tu jakiś interes'); sets $7C0F2=1 (loc_0D.alf:120-145); loc_31 first entry: doctor says 'Przeszukaj półkę i zmykaj!' ($7C0DC=1); -> loc_31 |
| 30 | loc_31 | walk | hs4 [438, 469, 275, 364] c(453,319) scr(453,159) |  |  | Do półki; -> loc_15 |
| 31 | loc_15 | look | hs2 [140, 319, 175, 266] c(229,220) scr(229,110) |  |  | Szafka: 'O! Tu coś jest!'; sets $7C0D6=1 |
| 32 | loc_15 | take | hs3 [245, 292, 284, 300] c(268,292) scr(268,146) |  |  | Akta; needs $7C0D6==1; sets $7C145=0 (needed by the train) |
| 33 | loc_15 | walk | hs1 [17, 117, 32, 354] c(67,193) scr(67,96) |  |  | Na zewnątrz; -> loc_0D |
| 34 | loc_0D | walk | hs1 [16, 39, 279, 347] c(27,313) scr(27,156) |  |  | Do centrum; -> loc_05 |
| 35 | loc_05 | walk | hs8 [433, 466, 214, 355] c(449,284) scr(449,142) |  |  | -> loc_06 |
| 36 | loc_06 | walk | hs2 [305, 315, 163, 174] c(310,168) scr(310,84) |  |  | Janina Stachura; needs $7C0C6==1; -> loc_08 |
| 37 | loc_08 | dialogue |  |  | 1,1,1 | Forced first-visit dialogue with Stryczyński: $85B2A any, $85BED row 1 or 2 (3/4 = thrown out, no knife chance this visit), $85D5B any; sets $7C0D2=1, $7C0CB=1, $7C0CC=1 |
| 38 | loc_08 | use_panel |  | nóż $7B5C2 (slot 2) | 1 | Use + nóż (selection word $7C226 is only set in loc 8): threat dialogue $863A2, any option; needs $7C0D3==0; sets $7C0D3=1, $7C0C9=1 (R.P. Urylewscy on map) (loc_08.alf:70-127) |
| 39 | loc_08 | walk | hs1 [17, 49, 32, 354] c(33,193) scr(33,96) |  |  | Do centrum; -> loc_05 |
| 40 | loc_05 | walk | hs8 [433, 466, 214, 355] c(449,284) scr(449,142) |  |  | -> loc_06 |
| 41 | loc_06 | walk | hs5 [222, 231, 215, 224] c(226,219) scr(226,109) |  |  | R.P. Urylewscy; needs $7C0C9==1; -> loc_1B |
| 42 | loc_1B | talk_panel |  |  | 1,1 | Old woman: $8BC73 row 1, then $8BD8D any (rows 2-3 or 4 of $8BC73 skip the second menu). Then loc_1C cutscene, then loc_05; sets $7C0E1=1 (loc_1C); -> loc_05 |
| 43 | loc_05 | walk | hs8 [433, 466, 214, 355] c(449,284) scr(449,142) |  |  | -> loc_06 |
| 44 | loc_06 | walk | hs8 [229, 237, 317, 327] c(233,322) scr(233,161) |  |  | Cmentarz komunalny; needs $7C0CC==1; -> loc_19 |
| 45 | loc_19 | take | hs3 [269, 276, 229, 245] c(272,237) scr(272,118) |  |  | Kluczyk (stary klucz, id 6); sets $7C139=0 |
| 46 | loc_19 | walk | hs1 [288, 468, 310, 354] c(378,332) scr(378,166) |  |  | Wyjście do miasta; -> loc_05 |
| 47 | loc_05 | walk | hs6 [16, 32, 173, 246] c(24,209) scr(24,104) |  |  | Do stacji PKP; -> loc_04 |
| 48 | loc_04 | walk | hs1 [254, 464, 139, 173] c(359,156) scr(359,78) |  |  | Pociąg (second ride); needs train_rides>=1, $7C0E2~=1, $7C0E1==1, $7C145==0, $7C139==0 (loc_04.alf:66-84); -> loc_1D |
| 49 | loc_1D | talk_panel |  |  | 4 | Marysia: $8C15B row 4 (rows 2-3 also OK). Row 1 sends you back to loc_04 with the train blocked ($7C0E2=1): SOFT-LOCK; sets $7C0E2=1 (on entry); -> loc_1E |
| 50 | loc_1E | wait |  |  |  | First entry: 'Przygotuj się do długiej podróży. Przedtem jednak musisz użyć akt!'. Do NOT press Talk before using the akta (soft-lock, $7C0F6=1); sets $7C0EF=1 |
| 51 | loc_1E | use_panel |  | akta $7B50A (slot 2) |  | Use + akta (word $7C214, loc $1E only): page + explanation; sets $7C0EE=1 |
| 52 | loc_1E | walk | hs1 [401, 474, 333, 356] c(437,344) scr(437,172) |  |  | Wyjście do studni; -> loc_1F |
| 53 | loc_1F | use | hs2 [158, 218, 225, 241] c(188,233) scr(188,116) | stary klucz (id 6) $7B42A (slot 1) |  | Otwór w studni + stary klucz (word $7C1FC, loc $1F only): 'Plum i nie ma klucza'; sets $7C0ED=1 |
| 54 | loc_1F | walk | hs1 [433, 468, 294, 354] c(450,324) scr(450,162) |  |  | Do domu Gerwazego; on re-entry the sleep speech plays (sub_0B512); needs $7C0ED~=0 (else bounced to loc_04); -> loc_1E |
| 55 | loc_1E | use | hs4 [42, 64, 198, 235] c(53,216) scr(53,108) |  |  | Miksturka, plain Use (no item). Inventory is CLEARED (sub_0B05C), dream phase begins; needs $7C0F3==1; sets $7C0DD=0, $7C135=0, $7C138=0, $7C0F2=0, $7C0CE=2 (loc_1E.alf:160-174); -> loc_21 |
| 56 | loc_21 | take | hs5 [235, 349, 343, 367] c(292,355) scr(292,177) |  |  | Wiaderko. NEVER look at / take the Lustro (hs3) before painting it: death (loc_21.alf:93-129); sets $7C14D=0 |
| 57 | loc_21 | walk | hs1 [401, 474, 333, 356] c(437,344) scr(437,172) |  |  | Wyjście do studni; -> loc_1F |
| 58 | loc_1F | take | hs3 [133, 158, 248, 261] c(145,254) scr(145,127) |  |  | Młotek; sets $7C148=0 |
| 59 | loc_1F | walk | hs7 [16, 64, 102, 356] c(40,229) scr(40,114) |  |  | Na łąkę; needs $7C0EC==0; -> loc_20 |
| 60 | loc_20 | take | hs2 [104, 127, 297, 325] c(115,311) scr(115,155) |  |  | Pistolet; sets $7C15E=0 |
| 61 | loc_20 | walk | hs1 [16, 54, 32, 356] c(35,194) scr(35,97) |  |  | Do studni; -> loc_1F |
| 62 | loc_1F | walk | hs6 [237, 420, 332, 356] c(328,344) scr(328,172) |  |  | Do kościółka; -> loc_22 |
| 63 | loc_22 | take | hs5 [414, 442, 328, 336] c(428,332) scr(428,166) |  |  | Pędzel do golenia; sets $7C168=0 |
| 64 | loc_22 | take | hs7 [427, 438, 133, 145] c(432,139) scr(432,69) |  |  | Kubeczek; sets $7C169=0 |
| 65 | loc_22 | use | hs6 [235, 260, 101, 115] c(247,108) scr(247,54) | kubeczek $7BAAC (slot 1) |  | Holy water + kubeczek: 'Napełniłem!'; sets $7C115=1 |
| 66 | loc_22 | use | hs13 [270, 409, 261, 334] c(339,297) scr(339,148) | kubeczek $7BAAC (slot 1) | 3 | Gość na ławce + filled kubeczek: he wakes up; menu $8CDAB, row 3 ends it quickly (any row is harmless). Works only once; needs $7C115==1; sets $7C113=0, $7C119=1 |
| 67 | loc_22 | walk | hs2 [17, 39, 139, 361] c(28,250) scr(28,125) |  |  | Do drogi; needs $7C155~=0; -> loc_23 |
| 68 | loc_23 | take | hs2 [34, 48, 310, 317] c(41,313) scr(41,156) |  |  | Gwóźdź na drodze; sets $7C154=0 |
| 69 | loc_23 | walk | hs1 [116, 278, 340, 356] c(197,348) scr(197,174) |  |  | W stronę kościółka; -> loc_22 |
| 70 | loc_22 | walk | hs1 [450, 473, 160, 291] c(461,225) scr(461,112) |  |  | W stronę starego domu; -> loc_24 |
| 71 | loc_24 | walk | hs2 [21, 28, 272, 356] c(24,314) scr(24,157) |  |  | Na podwórko; -> loc_25 |
| 72 | loc_25 | take | hs3 [406, 479, 235, 294] c(442,264) scr(442,132) |  |  | Stolik; sets $7C159=0 |
| 73 | loc_25 | walk | hs1 [375, 457, 337, 356] c(416,346) scr(416,173) |  |  | Przed dom; -> loc_24 |
| 74 | loc_24 | combine |  | młotek $7B534 (slot 6) + stolik $7B7A6 (slot 1) |  | Use, młotek slot, then stolik slot (młotek word $7C21A is only armed in loc $24). common sub_17DA6: gwóźdź is used up; needs $7C154==0 (gwóźdź picked up); sets $7C11A=1, $7C11B=1 'Stolik jest jak nowy!' |
| 75 | loc_24 | use | hs5 [155, 192, 219, 264] c(173,241) scr(173,120) | stolik $7B7A6 (slot 1) |  | Jabłoń + stolik; needs $7C11B==1; sets $7C0D9=1 |
| 76 | loc_24 | take | hs4 [173, 179, 201, 211] c(176,206) scr(176,103) |  |  | Jabłko na drzewie; needs $7C0D9==1; sets $7C157=0 |
| 77 | loc_24 | walk | hs1 [151, 326, 332, 349] c(238,340) scr(238,170) |  |  | Do kościółka; -> loc_22 |
| 78 | loc_22 | walk | hs2 [17, 39, 139, 361] c(28,250) scr(28,125) |  |  | Do drogi; -> loc_23 |
| 79 | loc_23 | give | hs3 [102, 189, 170, 315] c(145,242) scr(145,121) | jabłko $7B722 (slot 1) |  | Give jabłko to the aunties (Postacie). After this loc_22 hs2 leads to loc_34 and loc_23 is gone; sets $7C155=0 (loc_23.alf:178-202); -> loc_34 |
| 80 | loc_34 | walk | hs3 [92, 260, 331, 349] c(176,340) scr(176,170) |  |  | Do kościółka; -> loc_22 |
| 81 | loc_22 | talk_panel |  |  | 1 | Talk to the woken man: $8D2C5 row 1 or 2 swaps podręcznik for zielnik (loc_22.alf:80-113); needs $7C113==0, $7C155==0, $7C16A==1; sets $7C16A=0 (herbs become visible) |
| 82 | loc_22 | walk | hs1 [450, 473, 160, 291] c(461,225) scr(461,112) |  |  | -> loc_24 |
| 83 | loc_24 | take | hs3 [429, 450, 343, 366] c(439,354) scr(439,177) |  |  | Ziółko: Ślepik. The other herbs (Florus Cudus loc_22 hs4, Ultramalina loc_25 hs2, Ziele Tereni/Jakuba loc_1F hs4/5) are not needed; needs $7C16A==0; sets $7C156=0 |
| 84 | loc_24 | walk | hs1 [151, 326, 332, 349] c(238,340) scr(238,170) |  |  | -> loc_22 |
| 85 | loc_22 | walk | hs2 [17, 39, 139, 361] c(28,250) scr(28,125) |  |  | Do drogi (now leads to the crossroads); -> loc_34 |
| 86 | loc_34 | walk | hs5 [162, 194, 193, 227] c(178,210) scr(178,105) |  |  | Na most; -> loc_2D |
| 87 | loc_2D | walk | hs3 [185, 240, 171, 194] c(212,182) scr(212,91) |  |  | Na targ (safe now: $7C126==0); -> loc_27 |
| 88 | loc_27 | take | hs6 [348, 356, 283, 288] c(352,285) scr(352,142) |  |  | Zegarek na ręce kolesia; sets $7C15B=0 |
| 89 | loc_27 | give | hs3 [81, 110, 182, 327] c(95,254) scr(95,127) | zegarek $7B8AC (slot 1) |  | Give zegarek to Handlarz z rowerkiem; needs $7C15C==1; sets $7C15C=0 |
| 90 | loc_27 | combine |  | Ślepik $7B714 (slot 2) + stary młynek $7B8BA (slot 1) |  | Use, Ślepik slot, then stary młynek slot -> proszek (common sub_1804A). ONLY ONE GRIND IS POSSIBLE ($7C172 goes to 0): grinding any other herb first makes the masarz puzzle unwinnable; needs $7C172~=0; sets $7C172=0, $7C11D=1 |
| 91 | loc_27 | walk | hs11 [98, 150, 133, 170] c(124,151) scr(124,75) |  |  | Budka rzeźnika; needs $7C102~=1; -> loc_28 |
| 92 | loc_28 | talk_panel |  |  | 1 | First visit: $8FABD any row; you are sent back to the market; sets $7C103=1; -> loc_27 |
| 93 | loc_27 | walk | hs11 [98, 150, 133, 170] c(124,151) scr(124,75) |  |  | Budka rzeźnika again; -> loc_28 |
| 94 | loc_28 | dialogue |  |  | 3,2,2,4 | Forced: $900FA row 3, $9038B row 2, $90461 row 2, $9060E row 4. Every other choice except rows 1-2 of the first menu = DEATH (game_over_b); sets $7C103=2; -> loc_2B |
| 95 | loc_2B | use | hs3 [139, 180, 263, 360] c(159,311) scr(159,155) | proszek $7BBBC (slot 1) |  | Piwo masarza + proszek (word $7C26E, loc $2B only). Do it fast: the idle timer (shared counter $1CA0C) or pressing Give/Talk/Open off-hotspot fires the ending of the scene; sets $7C11E=1 |
| 96 | loc_2B | talk_panel |  |  |  | Talk (cursor off-hotspot) fires the 'friend arrives' scene: masarz poisoned, story picture (right click). Without the powder = DEATH sub_1425A; needs $7C11E==1, $7C11D~=0; sets $7C102=1, $7C15D=0 (loc_2B.alf:138-162); -> loc_27 |
| 97 | loc_27 | talk | hs3 [81, 110, 182, 327] c(95,254) scr(95,127) |  | 1 | Talk to Handlarz: $8E6CB row 1 or 2; needs $7C102==1; sets $7C105=1 (opens hs2 'Do masarza') |
| 98 | loc_27 | walk | hs2 [20, 27, 301, 344] c(23,322) scr(23,161) |  |  | Do masarza: leads to loc_0D while the church book is on the left ($7C0DF==1, initial); needs $7C105~=0; -> loc_0D |
| 99 | loc_0D | use | hs5 [191, 214, 161, 170] c(202,165) scr(202,82) | mały klucz $7B948 (slot 1) |  | Okno w podmurówce + mały klucz: 'Otwarte!'; sets $7C133=1 |
| 100 | loc_0D | walk | hs5 [191, 214, 161, 170] c(202,165) scr(202,82) |  |  | Okno w podmurówce; needs $7C133==1, $7C12D~=1, $7C13C~=0; -> loc_2C |
| 101 | loc_2C | take | hs5 [233, 239, 322, 345] c(236,333) scr(236,166) |  |  | Nabój; sets $7C13C=0 |
| 102 | loc_2C | walk | hs6 [266, 367, 331, 359] c(316,345) scr(316,172) |  |  | Wyjście; -> loc_0D |
| 103 | loc_0D | combine |  | pistolet $7B972 (slot 6) + nabój $7B46A (slot 1) |  | Use, PISTOLET slot FIRST, then nabój slot (common sub_17C7E clears the nabój word within 2 frames unless the pistol is already selected): 'Nabiłeś pistolet.'; sets $7C0EB=1 |
| 104 | loc_0D | walk | hs1 [16, 39, 279, 347] c(27,313) scr(27,156) |  |  | Na targ; -> loc_27 |
| 105 | loc_27 | walk | hs10 [163, 302, 332, 345] c(232,338) scr(232,169) |  |  | Na most; -> loc_2D |
| 106 | loc_2D | look | hs2 [379, 415, 170, 228] c(397,199) scr(397,99) |  |  | Look at Dziura w poręczy: visits the river spirit WITHOUT jumping ($7C106=0); -> loc_12 |
| 107 | loc_12 | use | hs2 [17, 252, 32, 298] c(134,165) scr(134,82) | stary młynek $7B8BA (slot 1) |  | Duch rzeki + stary młynek -> nowy młynek (common sub_08570); sets $7C152=0 |
| 108 | loc_12 | walk | hs1 [427, 466, 256, 356] c(446,306) scr(446,153) |  |  | Most; -> loc_2D |
| 109 | loc_2D | walk | hs4 [204, 304, 336, 351] c(254,343) scr(254,171) |  |  | Do lasu; -> loc_34 |
| 110 | loc_34 | walk | hs3 [92, 260, 331, 349] c(176,340) scr(176,170) |  |  | -> loc_22 |
| 111 | loc_22 | walk | hs3 [97, 255, 341, 366] c(176,353) scr(176,176) |  |  | Do studni; -> loc_1F |
| 112 | loc_1F | walk | hs7 [16, 64, 102, 356] c(40,229) scr(40,114) |  |  | Na łąkę; -> loc_20 |
| 113 | loc_20 | use | hs3 [196, 355, 256, 364] c(275,310) scr(275,155) | pistolet $7B972 (slot 5) |  | Sarenka + loaded pistol (word becomes 2 only in loc $20 when $7C0EB==1). Vision page needs a right click; sets $7C16C=0, $7C0EC=1 (meadow closes); -> loc_1F |
| 114 | loc_1F | walk | hs6 [237, 420, 332, 356] c(328,344) scr(328,172) |  |  | -> loc_22 |
| 115 | loc_22 | walk | hs2 [17, 39, 139, 361] c(28,250) scr(28,125) |  |  | -> loc_34 |
| 116 | loc_34 | walk | hs4 [16, 33, 244, 307] c(24,275) scr(24,137) |  |  | Do leśnej drogi; needs $7C16C~=1 (okulary taken); -> loc_2E |
| 117 | loc_2E | walk | hs4 [19, 66, 226, 275] c(42,250) scr(42,125) |  |  | Do domku; needs $7C12D~=1; -> loc_2F |
| 118 | loc_2F | dialogue |  |  | 1,1 | Forced first-visit dialogue with Quefrete Xang: $9117A any, $91350 any; sets $7C122=1 |
| 119 | loc_2F | give_panel |  | nowy młynek $7B5FA (slot 2) | 2,1 | Take/Give, nowy młynek slot (fires off-hotspot). Palm reading: $915C6 any, $92450 any. NEVER give the STARY młynek: death (loc_2F.alf:202-218); sets $7C123=1, $7C0F7=1 (loc_2F.alf:231-237) |
| 120 | loc_2F | walk | hs2 [17, 65, 32, 354] c(41,193) scr(41,96) |  |  | Wyjście; -> loc_2E |
| 121 | loc_2E | walk | hs3 [306, 338, 172, 208] c(322,190) scr(322,95) |  |  | Strach na wróble; -> loc_30 |
| 122 | loc_30 | take | hs1 [222, 239, 207, 273] c(230,240) scr(230,120) |  |  | Sznur na strachu (id 12); sets $7C13F=0 |
| 123 | loc_30 | walk | hs3 [19, 47, 282, 358] c(33,320) scr(33,160) |  |  | Do leśnej drogi; -> loc_2E |
| 124 | loc_2E | walk | hs2 [67, 392, 337, 347] c(229,342) scr(229,171) |  |  | Do lasu; -> loc_34 |
| 125 | loc_34 | walk | hs5 [162, 194, 193, 227] c(178,210) scr(178,105) |  |  | -> loc_2D |
| 126 | loc_2D | walk | hs3 [185, 240, 171, 194] c(212,182) scr(212,91) |  |  | Na targ (still safe, no jump yet); -> loc_27 |
| 127 | loc_27 | walk | hs2 [20, 27, 301, 344] c(23,322) scr(23,161) |  |  | Do masarza; -> loc_0D |
| 128 | loc_0D | use | hs4 [178, 191, 83, 116] c(184,99) scr(184,49) | sznur (id 12) $7B492 (slot 1) | 3 | Okno + sznur (id 12) -> loc_31. Doctor's entry dialogue $93C9D: row 3 (or 4, same option) -> kluczyk; needs $7C0F7==1, $7C0F2==0; sets $7C0F2=1, $7C0F8=1, $7C147=0 (loc_31.alf:129-258); -> loc_31 |
| 129 | loc_31 | walk | hs4 [438, 469, 275, 364] c(453,319) scr(453,159) |  |  | Do półki; -> loc_15 |
| 130 | loc_15 | take | hs3 [233, 274, 157, 171] c(253,164) scr(253,82) |  |  | Aparat fotograficzny; sets $7C146=0 |
| 131 | loc_15 | walk | hs1 [17, 117, 32, 354] c(67,193) scr(67,96) |  |  | Na zewnątrz; -> loc_0D |
| 132 | loc_0D | walk | hs1 [16, 39, 279, 347] c(27,313) scr(27,156) |  |  | Na targ; -> loc_27 |
| 133 | loc_27 | walk | hs9 [445, 471, 229, 355] c(458,292) scr(458,146) |  |  | W stronę szpitala; -> loc_11 |
| 134 | loc_11 | walk | hs1 [239, 333, 39, 287] c(286,163) scr(286,81) |  |  | Wejście; $7C147==0 -> loc_32; needs $7C15D~=1, $7C12D~=1, $7C132~=1, $7C16E~=0; -> loc_32 |
| 135 | loc_32 | take | hs1 [33, 53, 177, 209] c(43,193) scr(43,96) |  |  | Buteleczka z eterem; sets $7C140=0 |
| 136 | loc_32 | take | hs2 [262, 291, 284, 302] c(276,293) scr(276,146) |  |  | Kawałek gazy; sets $7C141=0 |
| 137 | loc_32 | combine |  | gaza $7B4AC (slot 1) + eter $7B49F (slot 2) |  | Use, gaza slot, then eter slot: 'Nasączyłem gazę'; sets $7C10F=1 |
| 138 | loc_32 | walk | hs3 [17, 236, 319, 352] c(126,335) scr(126,167) |  |  | Wyjście; -> loc_13 |
| 139 | loc_13 | use | hs2 [321, 399, 208, 272] c(360,240) scr(360,120) | gaza $7B4AC (slot 1) |  | Twarz wiedźmy + soaked gaza (word = 2 only in loc $13 with $7C10F==1). NEVER take the Bransoletka hs3 here (death), never press FIRE here; sets $7C111=1 |
| 140 | loc_13 | use_panel |  | aparat $7B518 (slot 1) |  | Use + aparat with the cursor off-hotspot: photo -> fotka Xanadu. Before the gauze = DEATH; needs $7C111==1; sets $7C16E=0 |
| 141 | loc_13 | walk | hs1 [17, 82, 32, 354] c(49,193) scr(49,96) |  |  | Wyjście; needs $7C16E==0; -> loc_11 |
| 142 | loc_11 | walk | hs3 [435, 466, 234, 356] c(450,295) scr(450,147) |  |  | Na targ; -> loc_27 |
| 143 | loc_27 | walk | hs10 [163, 302, 332, 345] c(232,338) scr(232,169) |  |  | -> loc_2D |
| 144 | loc_2D | look | hs2 [379, 415, 170, 228] c(397,199) scr(397,99) |  |  | Visit the spirit without jumping; -> loc_12 |
| 145 | loc_12 | use | hs2 [17, 252, 32, 298] c(134,165) scr(134,82) | fotka Xanadu $7BB12 (slot 1) |  | Duch rzeki + fotka Xanadu -> bransoletka (common sub_085DC); sets $7C151=0 (scarecrow lets you pass) |
| 146 | loc_12 | walk | hs1 [427, 466, 256, 356] c(446,306) scr(446,153) |  |  | -> loc_2D |
| 147 | loc_2D | walk | hs4 [204, 304, 336, 351] c(254,343) scr(254,171) |  |  | -> loc_34 |
| 148 | loc_34 | walk | hs4 [16, 33, 244, 307] c(24,275) scr(24,137) |  |  | -> loc_2E |
| 149 | loc_2E | walk | hs3 [306, 338, 172, 208] c(322,190) scr(322,95) |  |  | -> loc_30 |
| 150 | loc_30 | walk | hs4 [388, 465, 161, 203] c(426,182) scr(426,91) |  |  | Do piwniczki; needs $7C151==0; -> loc_33 |
| 151 | loc_33 | use | hs1 [351, 476, 266, 363] c(413,314) scr(413,157) | wiaderko $7B57A (slot 9) |  | Strumyk + wiaderko; sets $7C165=0; ITEM BEYOND SLOT 6: scroll down 3x first, use slot 6, scroll back |
| 152 | loc_33 | use | hs2 [365, 417, 160, 241] c(391,200) scr(391,100) | wiadro wody $7B9E6 (slot 1) |  | Piwniczka + wiadro wody: force field visible; needs $7C120==0; sets $7C120=1 |
| 153 | loc_33 | use | hs2 [365, 417, 160, 241] c(391,200) scr(391,100) | aparat $7B518 (slot 2) |  | Piwniczka + aparat: fotka pola; needs $7C120==1, $7C16F==1; sets $7C16F=0 |
| 154 | loc_33 | walk | hs3 [17, 65, 229, 356] c(41,292) scr(41,146) |  |  | Do stracha na wróble; -> loc_30 |
| 155 | loc_30 | walk | hs3 [19, 47, 282, 358] c(33,320) scr(33,160) |  |  | -> loc_2E |
| 156 | loc_2E | walk | hs2 [67, 392, 337, 347] c(229,342) scr(229,171) |  |  | -> loc_34 |
| 157 | loc_34 | walk | hs5 [162, 194, 193, 227] c(178,210) scr(178,105) |  |  | -> loc_2D |
| 158 | loc_2D | look | hs2 [379, 415, 170, 228] c(397,199) scr(397,99) |  |  | -> loc_12 |
| 159 | loc_12 | use | hs2 [17, 252, 32, 298] c(134,165) scr(134,82) | fotka pola $7BB1F (slot 1) |  | Duch rzeki + fotka pola -> szklana kula (common sub_0864E); sets $7C153=0 |
| 160 | loc_12 | walk | hs1 [427, 466, 256, 356] c(446,306) scr(446,153) |  |  | -> loc_2D |
| 161 | loc_2D | walk | hs4 [204, 304, 336, 351] c(254,343) scr(254,171) |  |  | -> loc_34 |
| 162 | loc_34 | walk | hs4 [16, 33, 244, 307] c(24,275) scr(24,137) |  |  | -> loc_2E |
| 163 | loc_2E | walk | hs4 [19, 66, 226, 275] c(42,250) scr(42,125) |  |  | -> loc_2F |
| 164 | loc_2F | give_panel |  | szklana kula $7B63E (slot 1) |  | Give szklana kula -> napój; sets $7C15F=0, $7C124=1 |
| 165 | loc_2F | walk | hs2 [17, 65, 32, 354] c(41,193) scr(41,96) |  |  | -> loc_2E |
| 166 | loc_2E | walk | hs3 [306, 338, 172, 208] c(322,190) scr(322,95) |  |  | -> loc_30 |
| 167 | loc_30 | walk | hs4 [388, 465, 161, 203] c(426,182) scr(426,91) |  |  | -> loc_33 |
| 168 | loc_33 | use_panel |  | napój $7B992 (slot 1) |  | Use + napój off-hotspot (word $7C248, loc $33 only): drink it; needs $7C11F==0; sets $7C11F=1, $7C120=0 |
| 169 | loc_33 | take | hs2 [365, 417, 160, 241] c(391,200) scr(391,100) |  |  | Piwniczka: skafander; needs $7C166~=0, $7C11F==1; sets $7C166=0, $7C11F=0 |
| 170 | loc_33 | walk | hs3 [17, 65, 229, 356] c(41,292) scr(41,146) |  |  | -> loc_30 |
| 171 | loc_30 | walk | hs3 [19, 47, 282, 358] c(33,320) scr(33,160) |  |  | -> loc_2E |
| 172 | loc_2E | walk | hs4 [19, 66, 226, 275] c(42,250) scr(42,125) |  |  | -> loc_2F |
| 173 | loc_2F | give_panel |  | skafander $7B9F4 (slot 1) |  | Give skafander: the witch seals it (stays in inventory); needs $7C121==0; sets $7C121=1, $7C125=1 |
| 174 | loc_2F | walk | hs2 [17, 65, 32, 354] c(41,193) scr(41,96) |  |  | -> loc_2E |
| 175 | loc_2E | walk | hs2 [67, 392, 337, 347] c(229,342) scr(229,171) |  |  | -> loc_34 |
| 176 | loc_34 | walk | hs5 [162, 194, 193, 227] c(178,210) scr(178,105) |  |  | -> loc_2D |
| 177 | loc_2D | use | hs2 [379, 415, 170, 228] c(397,199) scr(397,99) |  |  | Use (no item) on Dziura w poręczy: 'Skaczę!'. With the sealed skafander the spirit grants the power. Without it = DEATH (loc_12.alf:125-132). FROM NOW ON loc_27 KILLS YOU ON ENTRY unless $7C16D==0 or $7C12D==1 (loc_27.alf:25-37); needs $7C121~=0; sets $7C106=1, $7C126=1, $7C128=1, $7C101=1 (loc_12.alf:29); -> loc_12 |
| 178 | loc_12 | walk | hs1 [427, 466, 256, 356] c(446,306) scr(446,153) |  |  | -> loc_2D |
| 179 | loc_2D | fire |  |  |  | Press JOYSTICK FIRE (CIA-A PRA bit 7, port 2), not a mouse button: 'Wyzwoliłeś moc!!!'; needs $7C101==1, $7C0FD~=1; sets $7C0FF=1, $7C0FD=1 |
| 180 | loc_2D | take | hs1 [161, 174, 343, 357] c(167,350) scr(167,175) |  |  | Klocek on the bridge; needs $7C0FF==1; sets $7C13D=0, $7C10E=1 |
| 181 | loc_2D | walk | hs4 [204, 304, 336, 351] c(254,343) scr(254,171) |  |  | Do lasu (NOT 'Na targ'); -> loc_34 |
| 182 | loc_34 | fire |  |  |  | Joystick fire: two klocki appear; needs $7C101==1, $7C107~=1; sets $7C107=1, $7C108=1, $7C109=1 |
| 183 | loc_34 | take | hs1 [43, 59, 340, 354] c(51,347) scr(51,173) |  |  | Klocek; sets $7C142=0, $7C10E=2 |
| 184 | loc_34 | take | hs2 [217, 227, 243, 252] c(222,247) scr(222,123) |  |  | Klocek; sets $7C143=0, $7C10E=3 |
| 185 | loc_34 | walk | hs6 [427, 467, 185, 255] c(447,220) scr(447,110) |  |  | Do lasu; needs $7C101==1; -> loc_35 |
| 186 | loc_35 | dialogue |  |  | 2,1 | Forced first visit with Valence: $949BE any, $9500E any; sets $7C12A=1 |
| 187 | loc_35 | fire |  |  |  | Joystick fire: two klocki appear; sets $7C10A=1, $7C10B=1, $7C10C=1 |
| 188 | loc_35 | take | hs1 [128, 143, 351, 364] c(135,357) scr(135,178) |  |  | Klocek; sets $7C163=0, $7C10E=4 |
| 189 | loc_35 | take | hs2 [163, 170, 119, 134] c(166,126) scr(166,63) |  |  | Klocek; sets $7C164=0, $7C10E=5 |
| 190 | loc_35 | walk | hs3 [18, 100, 325, 356] c(59,340) scr(59,170) |  |  | Do skrzyżowania; -> loc_34 |
| 191 | loc_34 | walk | hs6 [427, 467, 185, 255] c(447,220) scr(447,110) |  |  | re-enter with exactly 5 klocki; -> loc_35 |
| 192 | loc_35 | dialogue |  |  | 3 | Missing-piece dialogue $955FC: ROW 3 'wcięcie z dołu, dwie wypustki z góry i jedną z lewej' (hint: picture 3 in loc_2C). Rows 1, 2, 4 = DEATH later when combining; needs $7C10E==5; sets $7C12B=1, $7C170=0, $7C10E=6 |
| 193 | loc_35 | use_panel |  | 6 klocków $7BB2C (slot 1) |  | Use + 6 klocków off-hotspot -> układanka; needs $7C12B==1 (else DEATH game_over_c); sets $7C171=0 |
| 194 | loc_35 | use | hs4 [363, 379, 328, 338] c(371,333) scr(371,166) | układanka $7BBAF (slot 1) |  | Gwóźdź in the tree + układanka. This switches loc_33 to its exit-only table, so loc_33 must be finished before; sets $7C12C=1, $7C100=1 |
| 195 | loc_35 | walk | hs3 [18, 100, 325, 356] c(59,340) scr(59,170) |  |  | -> loc_34 |
| 196 | loc_34 | walk | hs4 [16, 33, 244, 307] c(24,275) scr(24,137) |  |  | -> loc_2E |
| 197 | loc_2E | walk | hs3 [306, 338, 172, 208] c(322,190) scr(322,95) |  |  | -> loc_30 |
| 198 | loc_30 | walk | hs4 [388, 465, 161, 203] c(426,182) scr(426,91) |  |  | -> loc_33 |
| 199 | loc_33 | walk | hs2 [365, 417, 160, 241] c(391,200) scr(391,100) |  |  | Wejście do piwniczki (only in the $7C100==1 table); -> loc_37 |
| 200 | loc_37 | fire |  |  |  | Joystick fire. NOTE: loc_37 shares the guard flag $7C0FD with loc_2D, which is already 1, so this does nothing and is not needed |
| 201 | loc_37 | use | hs2 [144, 331, 170, 365] c(237,267) scr(237,133) |  |  | Lodówka, plain Use; needs $7C0FD==1; -> loc_38 |
| 202 | loc_38 | take | hs1 [381, 408, 292, 310] c(394,301) scr(394,150) |  |  | Książka: stara księga; sets $7C144=0 |
| 203 | loc_38 | walk | hs3 [42, 65, 123, 284] c(53,203) scr(53,101) |  |  | Do środka; -> loc_37 |
| 204 | loc_37 | walk | hs3 [366, 475, 329, 359] c(420,344) scr(420,172) |  |  | Na zewnątrz; -> loc_33 |
| 205 | loc_33 | walk | hs3 [17, 65, 229, 356] c(41,292) scr(41,146) |  |  | -> loc_30 |
| 206 | loc_30 | walk | hs3 [19, 47, 282, 358] c(33,320) scr(33,160) |  |  | -> loc_2E |
| 207 | loc_2E | walk | hs4 [19, 66, 226, 275] c(42,250) scr(42,125) |  |  | -> loc_2F |
| 208 | loc_2F | talk_panel |  |  |  | Talk: the witch gives czar zamiany (loc_2F.alf:84-134); needs $7C123,$7C124,$7C125,$7C126 set, $7C101==1, $7C10E>=2, $7C144==0, $7C160~=0; sets $7C160=0 |
| 209 | loc_2F | walk | hs2 [17, 65, 32, 354] c(41,193) scr(41,96) |  |  | -> loc_2E |
| 210 | loc_2E | walk | hs2 [67, 392, 337, 347] c(229,342) scr(229,171) |  |  | -> loc_34 |
| 211 | loc_34 | walk | hs6 [427, 467, 185, 255] c(447,220) scr(447,110) |  |  | -> loc_35 |
| 212 | loc_35 | use_panel |  | czar zamiany $7B9A0 (slot 1) |  | Use + czar zamiany off-hotspot: transformation (item is NOT consumed); needs $7C12D~=1; sets $7C12D=1 (cleared again on the next entry to loc_35) |
| 213 | loc_35 | walk | hs3 [18, 100, 325, 356] c(59,340) scr(59,170) |  |  | -> loc_34 |
| 214 | loc_34 | walk | hs5 [162, 194, 193, 227] c(178,210) scr(178,105) |  |  | -> loc_2D |
| 215 | loc_2D | walk | hs3 [185, 240, 171, 194] c(212,182) scr(212,91) |  |  | Na targ: safe only because $7C12D==1; -> loc_27 |
| 216 | loc_27 | walk | hs1 [192, 245, 195, 244] c(218,219) scr(218,109) |  |  | Do centrum; -> loc_05 |
| 217 | loc_05 | walk | hs4 [445, 472, 190, 262] c(458,226) scr(458,113) |  |  | Na parafię: loc_09 because $7C144==0; needs $7C0FC~=1, $7C144~=1; -> loc_09 |
| 218 | loc_09 | dialogue |  |  | 1,4 | Forced: priest cutscene, $87384 any (1) -> loc_0C phase 2: book scene $883EF any (4) -> duży klucz -> loc_05; sets $7C0FC=1, $7C13B=0; -> loc_05 |
| 219 | loc_05 | walk | hs6 [16, 175, 312, 354] c(95,333) scr(95,166) |  |  | Na targ ($7C12D still 1); -> loc_27 |
| 220 | loc_27 | walk | hs10 [163, 302, 332, 345] c(232,338) scr(232,169) |  |  | -> loc_2D |
| 221 | loc_2D | walk | hs4 [204, 304, 336, 351] c(254,343) scr(254,171) |  |  | -> loc_34 |
| 222 | loc_34 | walk | hs6 [427, 467, 185, 255] c(447,220) scr(447,110) |  |  | entering loc_35 clears $7C12D (transform back); -> loc_35 |
| 223 | loc_35 | walk | hs3 [18, 100, 325, 356] c(59,340) scr(59,170) |  |  | -> loc_34 |
| 224 | loc_34 | walk | hs3 [92, 260, 331, 349] c(176,340) scr(176,170) |  |  | -> loc_22 |
| 225 | loc_22 | use | hs9 [309, 386, 32, 162] c(347,97) scr(347,48) | duży klucz $7B45D (slot 1) |  | Drzwi do kościółka + duży klucz; sets $7C0DE=1 |
| 226 | loc_22 | take | hs10 [363, 386, 186, 213] c(374,199) scr(374,99) |  |  | Kropidło; needs $7C0DE~=0; sets $7C16B=0 |
| 227 | loc_22 | use | hs6 [235, 260, 101, 115] c(247,108) scr(247,54) | kropidło $7BAC8 (slot 1) |  | Holy water + kropidło: 'Teraz mogę kogoś kropnąć!!!'; sets $7C116=1 |
| 228 | loc_22 | use | hs11 [320, 338, 241, 257] c(329,249) scr(329,124) |  |  | Książeczka (left), plain Use: moved right -> 'Do masarza' in loc_27 now leads to loc_39; needs $7C0DE~=0, $7C12D~=1, $7C0DF==1; sets $7C0DF=0, $7C0E0=1 |
| 229 | loc_22 | walk | hs2 [17, 39, 139, 361] c(28,250) scr(28,125) |  |  | -> loc_34 |
| 230 | loc_34 | walk | hs6 [427, 467, 185, 255] c(447,220) scr(447,110) |  |  | -> loc_35 |
| 231 | loc_35 | use_panel |  | czar zamiany $7B9A0 (slot 2) |  | Transform again for the market; sets $7C12D=1 |
| 232 | loc_35 | walk | hs3 [18, 100, 325, 356] c(59,340) scr(59,170) |  |  | -> loc_34 |
| 233 | loc_34 | walk | hs5 [162, 194, 193, 227] c(178,210) scr(178,105) |  |  | -> loc_2D |
| 234 | loc_2D | walk | hs3 [185, 240, 171, 194] c(212,182) scr(212,91) |  |  | -> loc_27 |
| 235 | loc_27 | walk | hs2 [20, 27, 301, 344] c(23,322) scr(23,161) |  |  | Do masarza -> loc_39 ($7C0E0==1); -> loc_39 |
| 236 | loc_39 | walk | hs3 [326, 371, 179, 261] c(348,220) scr(348,110) |  |  | Do środka; -> loc_3A |
| 237 | loc_3A | take | hs2 [377, 415, 212, 349] c(396,280) scr(396,140) |  |  | Wędka; sets $7C161=0 |
| 238 | loc_3A | take | hs4 [290, 314, 266, 286] c(302,276) scr(302,138) |  |  | Puszka w otwartej szafce; sets $7C162=0 |
| 239 | loc_3A | walk | hs3 [16, 309, 329, 356] c(162,342) scr(162,171) |  |  | Na zewnątrz; -> loc_39 |
| 240 | loc_39 | walk | hs4 [36, 50, 209, 243] c(43,226) scr(43,113) |  |  | Na targ; -> loc_27 |
| 241 | loc_27 | walk | hs10 [163, 302, 332, 345] c(232,338) scr(232,169) |  |  | -> loc_2D |
| 242 | loc_2D | walk | hs4 [204, 304, 336, 351] c(254,343) scr(254,171) |  |  | -> loc_34 |
| 243 | loc_34 | walk | hs3 [92, 260, 331, 349] c(176,340) scr(176,170) |  |  | -> loc_22 |
| 244 | loc_22 | walk | hs3 [97, 255, 341, 366] c(176,353) scr(176,176) |  |  | -> loc_1F |
| 245 | loc_1F | use | hs2 [158, 218, 225, 241] c(188,233) scr(188,116) | wędka $7B9AE (slot 2) |  | Otwór w studni + wędka: 'Jest! Nawet nie użyłem przynęty!' (loc_1F.alf:66-74); needs $7C16D~=0; sets $7C16D=0 (market safe again, boss can start) |
| 246 | loc_1F | combine |  | pędzel $7BA86 (slot 13) + puszka farby $7B9BC (slot 2) |  | Use, pędzel slot, then puszka farby slot: 'Nasączyłeś pędzel farbą.'; sets $7C129=1; ITEM BEYOND SLOT 6: scroll down 7x first, use slot 6, scroll back |
| 247 | loc_1F | walk | hs1 [433, 468, 102, 274] c(450,188) scr(450,94) |  |  | Do domu Gerwazego (loc_1E redirects to loc_21 in the dream); -> loc_21 |
| 248 | loc_21 | use | hs3 [205, 221, 193, 213] c(213,203) scr(213,101) | pędzel $7BA86 (slot 12) |  | Lustro + pędzel with paint: 'Zamalowałeś lusterko'; needs $7C129==1; sets $7C118=1; ITEM BEYOND SLOT 6: scroll down 6x first, use slot 6, scroll back |
| 249 | loc_21 | take | hs3 [205, 221, 193, 213] c(213,203) scr(213,101) |  |  | Lustro (now safe); needs $7C118==1; sets $7C14B=0 |
| 250 | loc_21 | walk | hs1 [401, 474, 333, 356] c(437,344) scr(437,172) |  |  | -> loc_1F |
| 251 | loc_1F | walk | hs6 [237, 420, 332, 356] c(328,344) scr(328,172) |  |  | -> loc_22 |
| 252 | loc_22 | walk | hs2 [17, 39, 139, 361] c(28,250) scr(28,125) |  |  | -> loc_34 |
| 253 | loc_34 | walk | hs6 [427, 467, 185, 255] c(447,220) scr(447,110) |  |  | clears $7C12D (needed for the cemetery exit); Valence: 'Idę pokonać Bercera'; -> loc_35 |
| 254 | loc_35 | walk | hs3 [18, 100, 325, 356] c(59,340) scr(59,170) |  |  | -> loc_34 |
| 255 | loc_34 | walk | hs5 [162, 194, 193, 227] c(178,210) scr(178,105) |  |  | -> loc_2D |
| 256 | loc_2D | walk | hs3 [185, 240, 171, 194] c(212,182) scr(212,91) |  |  | safe: $7C16D==0; -> loc_27 |
| 257 | loc_27 | walk | hs1 [192, 245, 195, 244] c(218,219) scr(218,109) |  |  | -> loc_05 |
| 258 | loc_05 | walk | hs7 [320, 466, 312, 354] c(393,333) scr(393,166) |  |  | Na cmentarz. Entry: Bercer intro (sub_0A612); needs $7C12D~=1; boss needs $7C16D==0, $7C14B==0, $7C118==1; -> loc_19 |
| 259 | loc_19 | use | hs3 [37, 103, 154, 342] c(70,248) scr(70,124) | lusterko (id 24) $7B55E (slot 1) |  | Bercer + lusterko (1st): 'kawałkiem szkiełka'; sets $7C12F=1 |
| 260 | loc_19 | use | hs3 [37, 103, 154, 342] c(70,248) scr(70,124) | kropidło $7BAC8 (slot 4) |  | Bercer + kropidło: paralysed. Using it before the mirror (or unfilled) = DEATH; needs $7C12F~=0, $7C116~=0; sets $7C130=1 |
| 261 | loc_19 | use | hs3 [37, 103, 154, 342] c(70,248) scr(70,124) | lusterko (id 24) $7B55E (slot 1) |  | Bercer + lusterko (2nd): victory -> loc_12_2 speech (buteleczka added, $7C14F=0) -> loc_3C; -> loc_3C |
| 262 | loc_3C | use | hs1 [191, 294, 107, 177] c(242,142) scr(242,71) | buteleczka $7B5D0 (slot 1) |  | Marlena + buteleczka (word $7C228, loc $3C only). Note picture needs a right click (loc_3C.alf:81); -> loc_3D |
| 263 | loc_3D | wait |  |  |  | Ending: 7 right clicks (loc_3D.alf:14..56), last card stays (original halts; port returns to title) |

## 4. Deaths and soft-locks to avoid

Death routines: `game_over` ($13E92, common.alf:560, random screen loc_02 / loc_02_2 / loc_08_2 / loc_07_2), `game_over_b` ($14006, common.alf:583, loc_12_3 / loc_23_2 / loc_22_2 / loc_1F_2), `sub_1418C` (common.alf:611, loc_35_2 / loc_27_2), `sub_1425A` (common.alf:630, loc_31_2). All end in a full restart at loc_04 (`sub_142CA`, common.alf:642).

| where | what kills you | script |
|---|---|---|
| loc_0B | first-visit row 1 ("Lenia? To ja, Tomek!") -> loc_0E -> game_over | loc_0B.alf:56-60, loc_0E.alf:18 |
| loc_0B | pressing Talk on later visits ("GIŃ!") unless a narrow flag combination holds | loc_0B.alf:171-216 (goto at :208) |
| loc_13 phase 1 | Oglądaj / Rozmawiaj / Otwórz / Weź-Daj with the pointer off the nurse, or the idle timer (`delay_c9e2`, 1000 calls) | loc_13.alf:55-95 |
| loc_13 phase 2 | aparat before the soaked gauze; taking the Bransoletka (always) | loc_13.alf:142-169 (:156), :242-266 |
| loc_12 phase 2 | jumping from the bridge before the witch sealed the skafander ($7C121==0) | loc_12.alf:22, :125-132 |
| loc_21 | looking at or taking the mirror before painting it ($7C118==0) | loc_21.alf:93-129 |
| loc_27 | entering after the jump ($7C126==1) while $7C16D~=0 and not transformed ($7C12D~=1) | loc_27.alf:25-37 |
| loc_28 | 2nd visit: any row other than 3,2,2,4 (except rows 1/2 of the first menu, which just send you away) | loc_28.alf:174-306 |
| loc_2B | the scene ending fires (Give/Talk/Open off-hotspot or timeout) without powder in the beer | loc_2B.alf:109-176 |
| loc_2F | giving the witch the STARY młynek | loc_2F.alf:202-218 |
| loc_35 | combining the 6 klocków after picking a wrong piece (rows 1, 2, 4) | loc_35.alf:241-275 |
| loc_19 phase 2 | kropidło before the 1st mirror, or with an unfilled kropidło | loc_19.alf:298-319 |
| loc_19 phase 2 | entering without all boss conditions ($7C16D==0, $7C14B==0, $7C118==1) while $7C102==1 or $7C12D==1 | loc_19.alf:340-373 |

Soft-locks (no death, but the game cannot be finished):
- loc_1D: Talk row 1: back to loc_04 with the train blocked for good ($7C0E2=1). loc_1E: Talk before using the akta, or re-entering before the key is in the well: thrown out to loc_04 with $7C0F6=1 (loc_1E.alf, `L0AE0C`). No recovery path found (loc_0B.alf:183-189 only reads these flags for the talk trap).
- Herb grinding is one-shot (`b[$7C172]`, initial 1, cleared by every grind, common.alf:3440-3600). Only Ślepik sets `$7C11D`, which the butcher scene needs (loc_2B.alf:141). Grinding Florus Cudus / Ultramalina / Ziele Tereni / Ziele Jakuba first makes the game unwinnable. The route never picks those herbs up.
- loc_0C phase 1 row 2 sets `$7C0E7`=1 (arms the loc_0B talk death) and sends you to loc_18; probably recoverable but untested.
- loc_13 phase 2 FIRE sets `$7C132`=1 and closes the hospital entrance for good (loc_13.alf:110-136, loc_11.alf:182-235). Never press fire there.
- After the jump, "Na targ" (loc_2D hs3), "Do centrum"-type routes into loc_27 are deadly until the second stary klucz is fished ($7C16D=0) or while transformed. The route enters loc_27 after the jump only while transformed (steps 215, 219, 234, 240; czar used at 212 and 231) or after the key is fished at step 245 (step 256).

## 5. Disk changes and cutscenes

Disk changes along the route (computed from the `ensure_disk` table; the port shows the "Włóż dysk" band ~2 s, 100 frames on a real swap, 10 otherwise, then "Wczytuję dane...", `load_disk` in src/natives.c). Start state: disk2 (loc_04). `*` = partial reload of that disk (ensure_disk value 5, loc_31). Locations without a disk (loc_05, loc_06, loc_34) never trigger a swap.

- step 16: entering loc_11: disk2 -> disk3
- step 22: entering loc_0F: disk3 -> disk2
- step 29: entering loc_31: disk2 -> disk4*
- step 30: entering loc_15: disk4 -> disk2
- step 48: entering loc_1D: disk2 -> disk3
- step 94: entering loc_2B: disk3 -> disk4
- step 96: entering loc_27: disk4 -> disk3
- step 98: entering loc_0D: disk3 -> disk2
- step 100: entering loc_2C: disk2 -> disk4
- step 102: entering loc_0D: disk4 -> disk2
- step 104: entering loc_27: disk2 -> disk3
- step 116: entering loc_2E: disk3 -> disk4
- step 125: entering loc_2D: disk4 -> disk3
- step 127: entering loc_0D: disk3 -> disk2
- step 128: entering loc_31: disk2 -> disk4*
- step 129: entering loc_15: disk4 -> disk2
- step 132: entering loc_27: disk2 -> disk3
- step 148: entering loc_2E: disk3 -> disk4
- step 157: entering loc_2D: disk4 -> disk3
- step 162: entering loc_2E: disk3 -> disk4
- step 176: entering loc_2D: disk4 -> disk3
- step 196: entering loc_2E: disk3 -> disk4
- step 211: entering loc_35: disk4 -> disk3
- step 217: entering loc_09: disk3 -> disk2
- step 219: entering loc_27: disk2 -> disk3
- step 235: entering loc_39: disk3 -> disk2
- step 240: entering loc_27: disk2 -> disk3
- step 258: entering loc_19: disk3 -> disk2
- step 261: entering loc_12: disk2 -> disk3
- step 261: entering loc_3C: disk3 -> disk4

Cutscenes / scripted sequences on the route (right-click through the speech):
- step 2: loc_03 switches to the close-up frame $10C49C for the train talk.
- steps 13 and 23: loc_0F car ride (timed, ~4 x `delay_200`, no input).
- step 18: after the doctor dialogue Tomek falls asleep: loc_12 phase 1 (river spirit speech, no input) then loc_13 (timed room).
- step 20: loc_10 aftermath with the doctor, nóż added.
- step 24/25: loc_0B "Wskakuj!", then the loc_16 news dialogue.
- step 42: loc_1C "Oto chwila prawdy..." then loc_05.
- step 50/54: loc_1E first-entry prompt and the sleep speech (`sub_0B512`, common.alf:512).
- step 55: drinking the potion, inventory wiped, loc_21.
- step 96: loc_2B poisoning scene with a story picture (`sub_14360`, right click).
- step 113: loc_20 vision page after shooting the deer (right click).
- step 177: the jump, loc_12 spirit grants the power (loc_12.alf:29-33).
- steps 186 / 192: Valence in loc_35 (first meeting, missing piece).
- step 218: loc_09 phase 2 priest cutscene and loc_0C phase 2 book scene.
- step 258: Bercer's intro (`sub_0A612`, common.alf:482).
- step 261: `loc_12_2` farewell of the river spirit (buteleczka), then loc_3C.
- step 262: note picture in loc_3C (`wait_right_click_fast`, loc_3C.alf:81), drinking texts, loc_3D.
- step 263: loc_3D: picture + 6 text cards, 7 right clicks (loc_3D.alf:14-56), then the original halts (the port returns to the title screen).

Optional content skipped by the route (no effect on the ending, as far as the scripts show): shop and cigarettes (loc_07, loc_05 hs7), Prokopiewicz house (loc_0A), the hospital vision and parish letter (loc_17, loc_18, `$7C0DA`, `$7C0D8`), kwiatek (loc_0B), pomarańcza (loc_16), lusterko id 5 (loc_0D phase 1), the four other herbs, wieża (loc_27), kubek (loc_2F), Rex the dog (loc_34), Jumadi (loc_39), Valence small talk. Items never consumed by any script: kluczyk, okulary, bransoletka, stara księga, zielnik, skafander, kropidło, stary klucz (id 58); only picking them up (setting their flag) matters.

## 6. Uncertain points (check before relying on them)

1. **FIRE** (resolved): the port maps the port-2 fire button to space, the middle mouse button and any pad button; autoplay has `fire` / `fireup`.
2. Dialogue rows: assumed that the option list starts on row 1 of `$1D790` and each `\n`-separated line of the option text is one row. This matches every `d2` compare I checked (e.g. loc_22.alf:80 `d2 u<= 2`, loc_31 option 3 on rows 3-4, loc_0B rows 2-4), but was not tested on screen.
3. Inventory scrolling (steps 151, 246, 248): the arrows scroll once per frame while lmb is held and the limit counter `w[$7C0C4]` is only ever decremented (common.alf:2738-2760, :4494), so scrolling looks unbounded while the top slot is non-empty. Hold lmb exactly one frame per click. Untested.
4. Slot numbers come from a simulation of `inventory_add` / removal order; if any script adds or removes an item I did not model (e.g. a cutscene I treated as text only), later slot numbers shift. `inventory_after` in the JSON lets a bot verify by reading the panel.
5. loc_2B (step 95-96): the idle counter `$1CA0C` is shared with loc_13 and not reset on entry (src/natives.c:185-193, loc_2B.alf:15 only clears the flag), so the scene may end sooner than 20 s. With the powder already in the beer the timeout is harmless (it takes the success branch).
6. loc_13 phase 1 (step 19): act within a few seconds; the exact timeout depends on the same counter.
7. Combining pistolet + nabój (step 103): `sub_17C7E` (common.alf:3309-3345) clears the nabój word within ~2 frames unless the pistol word is already set, so the pistol must be selected first. Logic read from the script, untested.
8. loc_10 doctor dialogue (step 18, common sub_07816 at common.alf:157-385), loc_09 / loc_0C phase 2 (step 218, loc_09.alf:276-336, loc_0C.alf:141-218), loc_08 first visit (step 37, loc_08.alf:16-55, :234-250) and loc_2F palm reading (step 119, loc_2F.alf:220-320) were summarised by sub-readers; "any row works" is their reading, I only spot-checked loc_2F and loc_16.
9. czar zamiany as the way past Bercer at the market is inferred from the entry check (loc_27.alf:25-37) and the witch's hint ("Przy wejściu na targ czai się..."); it is the only flag that lets you into loc_27 between the jump and fishing the key, and the key needs the fishing rod from loc_3A, which is reachable only through loc_27. The item is not consumed (loc_35.alf:296-307) and the transformation ends on the next entry to loc_35 (loc_35.alf:25-36).
10. loc_37 (step 200): its fire check uses the same guard `$7C0FD` as loc_2D, so it does nothing after step 179 and the fridge opens because `$7C0FD`==1 already (loc_37.alf:26-41, :91-100). Harmless either way.
11. Hotspot rects come from `extracted/hotspots.json` (the tables the scripts load); none were checked against the rendered frames. Map markers in loc_06 and small items (loc_23 gwóźdź, loc_24 jabłko, loc_27 zegarek, loc_2C nabój, loc_34 klocki, loc_35 klocki) are 6-15 px wide.
12. loc_21 klej (hs4) is never visible (`$7C14C` starts at 0, nothing sets it; loc_21.alf:13, :148). Not needed.
13. Disk numbers: `ensure_disk` values 4 and 5 (loc_17, loc_31) are partial reloads of disk2 / disk4 (`load_disk` spec in src/natives.c); loc_3D has no `ensure_disk` entry and uses whatever is loaded (disk4 after loc_3C).
