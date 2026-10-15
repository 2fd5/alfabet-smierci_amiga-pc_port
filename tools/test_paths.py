"""Reach the optional locations and the death screens the normal way, from playthrough saves.

    py tools/test_paths.py            (needs work/play/step_NNN.sav from tools/playthrough.py)

Each scenario starts from a save of the full playthrough where the entry conditions hold
(found by reading the state block in the save files), plays a few actions and records
every location the game passes through. Death scenarios must pass a death screen and end
in the full restart at loc_04. Report: work/paths/report.txt, screenshots next to it.
"""
import copy
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import playthrough as pt  # noqa: E402

ROOT = pt.ROOT
OUT = ROOT / "work" / "paths"
SAVES = ROOT / "work" / "play"
STATE = 0x7BBD4
VERB = {"look": (544, 261), "talk": (598, 261), "use": (544, 311), "open": (598, 311), "take": (544, 361)}
ROW_Y = (410, 431, 452, 473, 494)
DEATH_MUSIC = 0x3D          # every death routine starts module order $3D


def flags(path):
    data = path.read_bytes()
    return lambda addr: data[addr - STATE]


def find_save(cond):
    """First playthrough save whose state satisfies cond(byte_at)."""
    for p in sorted(SAVES.glob("step_*.sav")):
        if cond(flags(p)):
            return p
    return None


def watch(g, seen, limit=3000):
    """Play on (right clicks while the game waits for them) until it waits for the player."""
    calm = 0
    for _ in range(limit):
        st = g.state(8)
        seen.append(st["loc"])
        if g.peek(0x7C0B9) == DEATH_MUSIC:
            seen.append("death music")
        if st["rwait"]:
            g.send("0 rclick", "4 rup")
            calm = 0
        elif g.options_up(st):
            return st
        elif not g.busy(st):
            calm += 1
            if calm >= 4:
                return st
        else:
            calm = 0
    raise RuntimeError("did not settle")


def walk(g, seen, x, y):
    g.move(*pt.NEUTRAL)
    g.state(6)
    g.click(x, y)
    return watch(g, seen)


def verb_on(g, seen, verb, x, y, item=None):
    g.move(*pt.NEUTRAL)
    g.state(6)
    g.click(*VERB[verb])
    if item:
        g.move(*pt.NEUTRAL)
        g.select_item(item)
    if x is not None:
        g.click(x, y)
    return watch(g, seen)


def row(g, seen, n):
    g.click(317, ROW_Y[n - 1])
    return watch(g, seen)


def steps():
    return {s["n"]: s for s in json.loads((ROOT / "tests" / "walkthrough.json").read_text(encoding="utf-8"))}


def unique(seq):
    out = []
    for x in seq:
        if not out or out[-1] != x:
            out.append(x)
    return out


# ---------------------------------------------------------------- scenarios
# each returns (save used or None, play function g, seen -> None, check seen -> message or None)

def optional(loc, cond, *walks):
    def play(g, seen):
        for w in walks:
            walk(g, seen, *w)

    def check(seen):
        return None if loc in seen else f"never reached loc {loc:02X}"
    return find_save(cond), play, check


def death(save, play, screens):
    def check(seen):
        hit = [s for s in screens if s in seen]
        if "death music" not in seen:
            return "death music never started"
        if not hit:
            return f"no death screen of {[hex(s) for s in screens]}"
        last = [x for x in seen if isinstance(x, int)][-1]
        if last != 0x04:
            return f"did not restart at loc_04 (ended in {last:02X})"
        return None
    return save, play, check


def scenarios():
    S = steps()
    game_over = [0x02, 0x07, 0x08]                 # random pick in game_over (loc_02, _02_2, _07_2, _08_2)
    game_over_b = [0x12, 0x23, 0x22, 0x1F]
    yield "loc_07 sklep", optional(
        0x07, lambda b: b(STATE) == 0x05 and b(0x7C0CE) != 2 and b(0x7C0D1) != 1, (297, 159), (140, 336))
    yield "loc_0A slepy zaulek", optional(
        0x0A, lambda b: b(STATE) == 0x06 and b(0x7C0C7) == 1 and b(0x7C0CF) == 1, (289, 192), (38, 246))
    yield "loc_17 wizja", optional(
        0x17, lambda b: b(STATE) == 0x06 and b(0x7C0CE) != 2 and b(0x7C0F0) == 1 and b(0x7C0CD) == 1 and b(0x7C0DA) != 1,
        (316, 342), (286, 163))
    yield "loc_18 akta parafii", optional(
        0x18, lambda b: b(STATE) == 0x06 and b(0x7C0E6) == 1 and b(0x7C0CB) == 1, (250, 311), (47, 193))

    def d1(g, seen):                                # loc_0B first visit, row 1: "Lenia? To ja, Tomek!"
        pt.run_step(g, S[5], S[6])
        row(g, seen, 1)
    yield "smierc: loc_0B wiersz 1 (game_over)", death(SAVES / "step_004.sav", d1, game_over)

    def d2(g, seen):                                # loc_21: look at the mirror before painting it
        verb_on(g, seen, "look", 213, 203)
    yield "smierc: loc_21 lustro (game_over_b)", death(SAVES / "step_055.sav", d2, game_over_b)

    def d3(g, seen):                                # loc_35: wrong missing piece, then build the puzzle
        wrong = copy.deepcopy(S[192])
        for a in wrong["actions"]:
            if "dialogue row" in a.get("what", ""):
                a["y"] = ROW_Y[0]
        pt.run_step(g, wrong, S[193])
        verb_on(g, seen, "use", None, None, item=S[193]["item"])    # build the puzzle
    yield "smierc: loc_35 zly klocek (sub_1418C)", death(SAVES / "step_191.sav", d3, [0x35, 0x27])

    def d4(g, seen):                                # loc_2B: the scene ends before the powder is in the beer
        g.move(*pt.NEUTRAL)
        g.state(6)
        g.click(*VERB["talk"])                      # talk off-hotspot ends the scene
        watch(g, seen)
    yield "smierc: loc_2B bez proszku (sub_1425A)", death(SAVES / "step_094.sav", d4, [0x31])


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    lines = []
    for name, (save, play, check) in scenarios():
        if save is None or not pathlib.Path(save).exists():
            lines.append(f"{name:42s} SKIP  no save with the entry conditions")
            print(lines[-1], flush=True)
            continue
        seen = []
        g = pt.Game(save)
        try:
            seen.append(g.state(2)["loc"])
            play(g, seen)
            err = check(seen)
        except RuntimeError as e:
            err = str(e)
        tag = name.split()[0].replace(":", "")
        g.shot((OUT / f"{tag}_{len(lines):02d}.bmp").as_posix())
        g.close()
        path = " ".join(f"{x:02X}" for x in unique([x for x in seen if isinstance(x, int)]))
        if "death music" in seen:
            path += " (death music)"
        lines.append(f"{name:42s} {'FAIL ' + err if err else 'ok'}  [{pathlib.Path(save).stem}] {path}")
        print(lines[-1], flush=True)
    (OUT / "report.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
