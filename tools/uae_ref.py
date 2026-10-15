"""Drive the untouched original in WinUAE (started with run_original.bat) for reference data.

Talks to WinUAE's IPC pipe through tools/uaeipc.ps1: debugger commands read and write
memory and save memory to files, CFG commands press the mouse button and change disks.
The mouse pointer is placed by writing the game's own pointer variables ($1CC12 x in hires
pixels, $1CC14 y in half-lines); the host mouse never moves, so the game adds no deltas.

    py tools/uae_ref.py peek 7bbd4 4
    py tools/uae_ref.py click 359 156
    py tools/uae_ref.py disk 2
    py tools/uae_ref.py dump work/ref/mem.bin
"""
import pathlib
import re
import subprocess
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
IPC = ROOT / "tools" / "uaeipc.ps1"


def ipc(*cmds):
    out = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(IPC), *cmds],
                         capture_output=True, text=True, timeout=60).stdout
    return [line.split(" -> ", 1)[1] if " -> " in line else line for line in out.splitlines() if line.strip()]


def peek(addr, n=1):
    """n words from addr (debugger 'm' prints 8 words per line)."""
    words = []
    a = addr
    while len(words) < n:
        reply = " ".join(ipc(f"DBG m {a:x} 1"))
        m = re.match(r"\s*([0-9A-F]{8})((?: [0-9A-F]{4}){1,8})", reply)
        if not m:
            raise RuntimeError(f"bad reply {reply!r}")
        words += [int(w, 16) for w in m[2].split()]
        a += 16
    return words[:n]


def poke_w(addr, value):
    ipc(f"DBG W {addr:x} {value:x}.w")


def point(x, y):
    poke_w(0x1CC12, x)
    poke_w(0x1CC14, y)


def button(down, which="JOY1_FIRE_BUTTON"):
    ipc(f"CFG {which} {1 if down else 0}")


def click(x, y, hold=0.15):
    point(x, y)
    time.sleep(0.1)
    button(True)
    time.sleep(hold)
    button(False)


def disk(n):
    ipc(f"CFG floppy0 {(ROOT / 'AlfabetSmierci' / 'data' / f'disk{n}.adf').as_posix()}")


def dump(path, addr=0, length=0x200000):
    pathlib.Path(path).parent.mkdir(parents=True, exist_ok=True)
    ipc(f"DBG S {pathlib.Path(path).resolve().as_posix()} {addr:x} {length:x}")


def main_loaded():
    return peek(0x3000, 3) == [0x4EB9, 0x0001, 0xD884]     # jsr $1D884: the main game's first line


def loc_id():
    return peek(0x7BBD4)[0] >> 8


def boot_to_game(log=print):
    """Click through the intro's story pages, then give the game disk 2 and wait for the station."""
    t0 = time.time()
    while peek(0x3000, 3) != [0x4EB9, 0x0000, 0x43E0]:     # the intro: no clicks during the boot
        if time.time() - t0 > 300:
            raise RuntimeError("intro never started")
        time.sleep(2)
    while not main_loaded():
        if time.time() - t0 > 1500:
            raise RuntimeError("main game never loaded")
        # click only on the story pages (BPLCON0 $9200): clicks during the logos and the
        # title hang the original under WinUAE/AROS
        if peek(0x3000, 3) == [0x4EB9, 0x0000, 0x43E0] and peek(0x29916)[0] == 0x9200:
            click(320, 200)
        time.sleep(3)
    log(f"main game loaded after {time.time() - t0:.0f} s")
    time.sleep(8)
    disk(2)
    while loc_id() != 0x04:
        if time.time() - t0 > 1200:
            raise RuntimeError("never reached the station")
        time.sleep(2)
    log(f"station after {time.time() - t0:.0f} s")


if __name__ == "__main__":
    cmd, args = sys.argv[1], sys.argv[2:]
    if cmd == "peek":
        print(" ".join(f"{w:04X}" for w in peek(int(args[0], 16), int(args[1]) if len(args) > 1 else 1)))
    elif cmd == "click":
        click(int(args[0]), int(args[1]))
    elif cmd == "point":
        point(int(args[0]), int(args[1]))
    elif cmd == "disk":
        disk(int(args[0]))
    elif cmd == "dump":
        dump(args[0])
    elif cmd == "boot":
        boot_to_game()
    elif cmd == "raw":
        print("\n".join(ipc(*args)))
