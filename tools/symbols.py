"""Names for the game's variables and routines, shared by the lifter and the docs.

Every name maps to the original absolute address, so a script line can always be
traced back to the asm. Unknown addresses simply stay as $XXXXX in the scripts.
"""

# Variables: name -> (size, address). Size: b = byte, w = word, l = long.
VARIABLES = {
    # game state block $7BBD4..$7C26F (saved as a whole, like the original)
    "loc_id":            ("b", 0x7BBD4),
    "music_order":       ("l", 0x7C0B6),   # start order in the game module ($15732)
    "inv_scroll":        ("l", 0x7C0BE),   # inventory scroll offset (bytes, 4 per slot)
    "train_rides":       ("b", 0x7C0CF),
    # verb selected in the right panel (exactly one is 1)
    "verb_look":         ("w", 0x1795A),   # Oglądaj
    "verb_talk":         ("w", 0x1795C),   # Rozmawiaj
    "verb_take":         ("w", 0x1795E),   # Weź/Daj (take)
    "verb_give":         ("w", 0x17960),   # Weź/Daj (give)
    "verb_use":          ("w", 0x17962),   # Użyj
    "verb_open":         ("w", 0x17964),   # Otwórz
    "panel_mode":        ("w", 0x17966),   # 1 = verbs, else menu (Zapisz/Wczytaj/...)
    "inv_click_armed":   ("w", 0x17958),
    "hover_mode":        ("w", 0x7A928),   # 1 = nothing selected, hovering
    "label_shown":       ("w", 0x7A92A),   # a hotspot name is shown in the text panel
    "quip_person":       ("w", 0x7A92E),   # 0 = object quips, 1 = person quips ($16980)
    "hotspot_table":     ("l", 0x1CEC2),
    "mouse_min_y":       ("w", 0x1CC04),
    "mouse_max_y":       ("w", 0x1CC06),
    "mouse_max_x":       ("w", 0x1CC08),
    "disk_in_drive":     ("b", 0x4EA36),
}

# Readable names for routines: address -> name. Whether a routine is lifted to script or
# implemented natively is decided by the lifter (NATIVE below forces native).
ROUTINES = {
    0x1953C: "clear_text",          # restore the marble text panel from its backup
    0x1C6C8: "print",               # print text at a2 into the text panel
    0x1C67E: "say",                 # clear_text + print + wait for right click
    0x1C696: "say_restore_cursor",  # clear_text + print + wait right click + hand cursor
    0x1C6A8: "show",                # clear_text + print + hand cursor
    0x1C68C: "clear_print",         # clear_text + print
    0x1C7DA: "print_alt",
    0x1CA3C: "print_at",            # print text a2 at screen offset d1
    0x1C6B6: "text_white",
    0x1C960: "wait_right_click",
    0x16956: "wait_right_click_fast",
    0x1C9B2: "delay_200",
    0x1C9C6: "delay_c9c6",
    0x1C9E2: "delay_c9e2",
    0x1917A: "reset_verbs",
    0x191C0: "label_mode",          # hover_mode = 0, label_shown = 1
    0x191D2: "draw_inventory",
    0x19FC0: "draw_verb_bar",       # restore the pink verb bar
    0x1CC2A: "cursor_off",
    0x1CC70: "cursor_hand",
    0x1C90A: "wait_right_click_hand",
    0x1CCCA: "cursor_busy",
    0x1CD2C: "cursor_anim_cd2c",
    0x1CD88: "cursor_anim_cd88",
    0x1CDE4: "cursor_exit_a",
    0x1CE3E: "cursor_exit_b",
    0x1D7BA: "hit_test",            # d2 = hotspot under the mouse, -1 if none
    0x1D7E0: "hit_test_ui",         # d3 = right panel element under the mouse
    0x16E54: "ui_panel",            # inventory slots, arrows, verb buttons, menu
    0x17C40: "ui_combine",          # use-item-on-item combinations
    0x16980: "quip_if_verb",        # random "wrong action" line for take/give/use/open/talk
    0x169CA: "quip_if_verb_b",
    0x169AA: "quip_if_verb_c",
    0x4E5DC: "decrunch",            # CrunchMania a0 -> a1
    0x193C0: "show_frame",          # blit the decrunched frame at $610FE to the screen
    0x19332: "set_palette",         # fade target = 128 x 0RGB at a0
    0x1C050: "fade_in",
    0x1C0DA: "fade_out",
    0x1D884: "music_start",
    0x1D8A8: "music_stop",
    0x4E722: "random",              # d0 = 1..d5
    0x143C0: "ensure_disk",         # loads the location's data disk if needed (lifted)
    0x4E82E: "load_disk",           # "Włóż dysk N" screen + load disk blob at $10181A
    0x14382: "show_disk_picture",   # the A1200 drive photo shown while disks change (lifted)
    0x19610: "blit",                # generic blitter copy with parameters at $196A8..$196BE
    0x19226: "inventory_add",       # item name pointer in $1932A (lifted)
    0x19252: "inventory_remove",
    0x1928E: "inventory_scroll_up",
    0x192D4: "inventory_scroll_down",
    0x19374: "clear_disk_band",
    0x13E92: "game_over",           # music $3D + one of four random death screens
    0x14006: "game_over_b",
    0x13E8C: "halt",                # bra.s *: the program stops here
    0x15318: "resume_location",     # jump back into the routine of loc_id (after load / menu)
    0x173F0: "restore_after_load",
    0x15732: "select_music",        # per-location start order of the game module (lifted)
}

# Routines the engine implements in C even though parts of them might lift.
NATIVE = {
    0x1953C, 0x1C6C8, 0x1C7DA, 0x1CA3C, 0x1C960, 0x16956, 0x1C9B2, 0x1C9C6, 0x1C9E2,
    0x1CC2A, 0x1CC70, 0x1CCCA, 0x1CD2C, 0x1CD88, 0x1CDE4, 0x1CE3E, 0x1D7BA,
    0x1D7E0, 0x4E5DC, 0x193C0, 0x19332, 0x1C050, 0x1C0DA,
    0x1D884, 0x1D8A8, 0x4E722, 0x4E82E, 0x19610,
    0x13E8C,               # halt: the port waits for a click and returns to the title
    0x1C90A,               # wait_right_click_hand: speech wait (left/right/fire in the port)
}

VAR_OF_ADDRESS = {addr: name for name, (_size, addr) in VARIABLES.items()}


# ---------------------------------------------------------------- intro program
INTRO_ROUTINES = {
    0x035D0: "intro_print",          # text page printer (story pages)
    0x0366C: "intro_set_bitplanes",
    0x039DA: "intro_palette_current_to_copper",
    0x03A4C: "intro_palette_target_to_copper",
    0x042C2: "intro_decrunch",
    0x043E0: "intro_music_start",
    0x04404: "intro_music_stop",
    0x1FE4B0: "intro_end_load_game",   # jump into the loader: load and start the main game
}
# intro routines the engine implements natively (decruncher, replayer, loader)
INTRO_NATIVE = {0x042C2, 0x043E0, 0x04404, 0x1FE4B0}
# intro addresses that get a label even if no branch goes there: the engine jumps to them
INTRO_LABELS = {0x031BA}           # start of the title section (after the ending, see n_halt)
