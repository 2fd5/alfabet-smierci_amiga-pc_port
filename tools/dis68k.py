"""Disassemble a raw 68k blob: dis68k.py file offset length loadaddr"""
import sys

from capstone import CS_ARCH_M68K, CS_MODE_BIG_ENDIAN, CS_MODE_M68K_020, Cs


def main():
    path, off, length, base = sys.argv[1], *(int(x, 0) for x in sys.argv[2:5])
    code = open(path, "rb").read()[off:off + length]
    md = Cs(CS_ARCH_M68K, CS_MODE_BIG_ENDIAN | CS_MODE_M68K_020)
    md.skipdata = True
    for ins in md.disasm(code, base):
        print(f"{ins.address:08x}  {ins.bytes.hex():<20} {ins.mnemonic} {ins.op_str}")


if __name__ == "__main__":
    main()
