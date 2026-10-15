"""Same clicks in the port and in the original, a memory dump at each scene.

    py tools/ref_scenes.py uae      (WinUAE running, booted to the station: tools/uae_ref.py boot)
    py tools/ref_scenes.py port
    py tools/compare_ref.py work/ref/uae_<scene>.bin work/ref/port_<scene>.bin work/ref/<scene>

Scenes: the station (loc_04, disk 2), the town (loc_05, picture inside the main program),
the map (loc_06) and the hospital (loc_11, disk 3; the map marker is enabled by setting
$7C0CD = 1, as the story would). The pointer rests off every hotspot for each dump.
"""
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import playthrough as pt  # noqa: E402
import uae_ref  # noqa: E402

OUT = pt.ROOT / "work" / "ref"
NEUTRAL = (495, 300)
SCENES = [
    ("station", None, None, 0x04, None),
    ("town", (242, 335), None, 0x05, None),
    ("map", (449, 284), None, 0x06, None),
    ("hospital", (316, 342), (0x7C0CD, 1), 0x11, 3),
]


class Port:
    def __init__(self):
        self.g = pt.Game()

    def poke(self, addr, v):
        self.g.send(f"0 poke {addr:X} {v}")

    def click(self, x, y, disk):
        self.g.click(x, y)

    def settle(self, loc):
        self.g.move(*NEUTRAL)
        st = self.g.rclicks("idle")
        self.g.state(50)
        return self.g.state(2)["loc"]

    def dump(self, path):
        self.g.send(f"0 dump {pathlib.Path(path).resolve().as_posix()}")
        self.g.state(2)

    def close(self):
        self.g.close()


class Uae:
    def poke(self, addr, v):
        uae_ref.ipc(f"DBG W {addr:x} {v:x}")

    def click(self, x, y, disk):
        uae_ref.click(x, y)
        if disk:
            time.sleep(4)
            uae_ref.disk(disk)

    def settle(self, loc):
        """Wait for the location, then until the screen stops changing (disk loads, fades)."""
        t0 = time.time()
        while uae_ref.loc_id() != loc and time.time() - t0 < 180:
            time.sleep(2)
        uae_ref.point(*NEUTRAL)
        tmp, last, same = OUT / "uae_tmp.bin", None, 0
        while same < 2 and time.time() - t0 < 300:
            time.sleep(3)
            uae_ref.dump(tmp)
            time.sleep(1)
            screen = tmp.read_bytes()[0x96738:0x96738 + 8 * 0x5000]
            same = same + 1 if screen == last else 0
            last = screen
        return uae_ref.loc_id()

    def dump(self, path):
        uae_ref.dump(path)
        time.sleep(2)

    def close(self):
        pass


def main():
    side = sys.argv[1]
    OUT.mkdir(parents=True, exist_ok=True)
    d = Port() if side == "port" else Uae()
    try:
        for name, click, poke, loc, disk in SCENES:
            if poke:
                d.poke(*poke)
            if click:
                d.click(*click, disk)
            got = d.settle(loc)
            d.dump(OUT / f"{side}_{name}.bin")
            print(f"{side} {name}: loc {got:02X} (want {loc:02X})", flush=True)
    finally:
        d.close()


if __name__ == "__main__":
    main()
