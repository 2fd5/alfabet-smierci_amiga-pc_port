# .alf scripts

These files are the game logic of Alfabet Śmierci, lifted from the original 68k asm by `tools/lifter.py`. Every line maps to one original instruction (compares and their branch are joined into one `if`). Do not edit them by hand. Change the lifter or `tools/symbols.py` and regenerate:

```
py tools/lifter.py
```

## Files

| File | Contents |
|---|---|
| `loc_XX.alf` | the location with id `$XX` (the value written to `loc_id`, `$7BBD4`) |
| `common.alf` | everything shared: boot, the right panel, inventory, item combinations, music and disk tables, palette and blit wrappers |
| `symbols.alf` | variable names (`var name size address`) |

## Language

```
routine loc_04 @ $035DC          -- name and original address
  loc_id = 4                     -- b/w/l size comes from symbols.alf
  call select_music              -- lifted routine or native routine
  a0 = $1160A0                   -- registers d0-d7, a0-a7 (d0.b / d0.w for byte/word)
::L0364E::                       -- label, named after the original address
  wait_raster $FF                -- the asm waited for the raster (line 255) here
  call hit_test                  -- natives put results in registers (d2 = hotspot)
  if d2 == 1 then
    if verb_look == 1 then
      a2 = $7FD90  -- "Stary dworzec kolejowy..."    (text shown as a comment)
      call print
    elseif b[$7C0E1] == 1 then   -- raw memory access: b[...], w[...], l[...]
      ...
    end
    goto L0364E                  -- branches the structuring could not express
  end
end
```

| Construct | Meaning |
|---|---|
| `x = y`, `x += y`, `x -= y`, `x &= y`, `x \|= y` | move / add / sub / and / or at the size of `x` |
| `b[$addr]`, `w[a1+$4]`, `l[a0++]` | memory: absolute, displacement, post-increment |
| `if ... then / elseif / else / end` | conditions: `==`, `~=`, `<`, `<=`, `>`, `>=` (signed), `u<`, `u<=`, `u>`, `u>=` (unsigned) |
| `lmb`, `rmb`, `fire`, `not lmb` | mouse buttons and fire button, as the hardware reports them |
| `bit(x, n) == 0` | `btst` |
| `call name` / `call $XXXXX` | subroutine call (`jsr` / `bsr`) |
| `jump name`, `goto Lxxxxx` | `jmp` / `bra`; labels are global, so jumps work across files like in the asm |
| `push d0, a1` / `pop d0, a1` | `movem.l regs,-(a7)` / `movem.l (a7)+,regs`; `pop` also drops return addresses (used before jumping back into a location) |
| `x ^= y` | `eor` |
| `shl x, n`, `shr x, n`, `asr x, n` | `lsl` / `lsr` / `asr` |
| `mulu x, y`, `muls x, y`, `divu x, y`, `divs x, y` | 68k multiply / divide (x = destination) |
| `swap x`, `ext x`, `not x`, `neg x` | `swap` / `ext` / `not` / `neg` |
| `return` | `rts` |
| `wait_raster $n` | `L: cmpi.b #n,$dff006 / bne L`: wait for the next raster line whose low byte is n (two waits in a row can be one frame) |
