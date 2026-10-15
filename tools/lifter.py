"""Lift Alfabet Smierci's 68k game logic into readable .alf scripts.

    py tools/lifter.py            -> scripts/*.alf, work/lift_report.txt (reads orig/adf; scripts/README.md is hand-written)

The game logic (locations, dialogues, per-location tables) is hand-written asm that only
uses a small set of instruction shapes. Each instruction is translated exactly into one
script statement; the control flow graph is then structured into if/elseif/else blocks.
Branches that do not form a clean structure stay as `goto` to labels named after the
original address, so every line of a script can be traced back to the asm.
"""
import collections
import pathlib
import re
import sys

from capstone import CS_ARCH_M68K, CS_MODE_BIG_ENDIAN, CS_MODE_M68K_020, Cs

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from crunchmania import decrunch  # noqa: E402
from plchars import decode as pl_decode  # noqa: E402
from symbols import INTRO_LABELS, INTRO_NATIVE, INTRO_ROUTINES, NATIVE, ROUTINES, VAR_OF_ADDRESS, VARIABLES  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
LOAD = 0x3000
LOC_ID = 0x7BBD4
LABEL_PREFIX = "L"       # "IL" while lifting the intro (its addresses overlap the game's)
MAIN_LOAD = 0x3000
TEXT_RANGE = (0x7A900, 0x96500)

# hardware registers the scripts read
HW = {0xBFE001: "ciaa_pra", 0xDFF006: "vhpos", 0xDFF016: "potgor"}


class Unliftable(Exception):
    pass


# ---------------------------------------------------------------- decoding

class Code:
    def __init__(self, blob):
        self.blob = blob
        self.md = Cs(CS_ARCH_M68K, CS_MODE_BIG_ENDIAN | CS_MODE_M68K_020)
        self.cache = {}

    def insn(self, addr):
        if addr not in self.cache:
            o = addr - LOAD
            ins = next(self.md.disasm(self.blob[o:o + 12], addr), None)
            if ins is None:
                raise Unliftable(f"cannot decode ${addr:05X}")
            self.cache[addr] = ins
        return self.cache[addr]

    def text_at(self, addr):
        o = addr - LOAD
        end = self.blob.index(b"\0", o)
        return pl_decode(self.blob[o:end])


def hexval(s):
    s = s.strip()
    neg = s.startswith("-")
    s = s.lstrip("-#$").replace(".l", "").replace(".w", "")
    v = int(s, 16)
    return -v if neg else v


def parse_operand(op):
    """-> ('imm', v) | ('abs', addr) | ('d', n) | ('a', n) | ('postinc', n) | ('ind', n)"""
    op = op.strip()
    if op.startswith("#"):
        return ("imm", hexval(op))
    m = re.fullmatch(r"d([0-7])", op)
    if m:
        return ("d", int(m.group(1)))
    m = re.fullmatch(r"a([0-7])", op)
    if m:
        return ("a", int(m.group(1)))
    m = re.fullmatch(r"\(a([0-7])\)\+", op)
    if m:
        return ("postinc", int(m.group(1)))
    m = re.fullmatch(r"\(a([0-7])\)", op)
    if m:
        return ("ind", int(m.group(1)))
    m = re.fullmatch(r"(-?\$[0-9a-f]+)\(a([0-7])\)", op)
    if m:
        return ("disp", int(m.group(2)), hexval(m.group(1)))
    m = re.fullmatch(r"-\(a([0-7])\)", op)
    if m:
        return ("predec", int(m.group(1)))
    m = re.fullmatch(r"\$[0-9a-f]+(\.[lw])?", op)
    if m:
        return ("abs", hexval(op))
    raise Unliftable(f"operand {op!r}")


def split_ops(s):
    return [x for x in re.split(r",\s*(?![^()]*\))", s) if x] if s else []


# ---------------------------------------------------------------- IR

# Each instruction becomes one Op. kinds:
#   set(dst, src, size) add(dst, src, size) sub(dst, src, size)
#   cmp(lhs, rhs, size) btst(src, bit) tst(src, size)
#   call(target) jump(target) ret() goto(target) branch(cc, target)
#   wait_vbl() dbra(reg, target)
Op = collections.namedtuple("Op", "kind args addr size next")

SIZES = {"b": 1, "w": 2, "l": 4}


def translate(code, addr):
    ins = code.insn(addr)
    mn = ins.mnemonic
    nxt = addr + ins.size
    base = mn.partition(".")[0]
    if base == "movem" and ("(a7)+" in ins.op_str or "-(a7)" in ins.op_str):
        pop = ins.op_str.startswith("(a7)+")
        regs = ins.op_str.split(",", 1)[1].strip() if pop else ins.op_str.split(",", 1)[0].strip()
        lst = []
        for part in regs.split("/"):
            if "-" in part:
                lo, hi = part.split("-")
                if lo[0] == hi[0]:
                    lst += [f"{lo[0]}{i}" for i in range(int(lo[1]), int(hi[1]) + 1)]
                else:   # d0-a6 style range across register files
                    lst += [f"d{i}" for i in range(int(lo[1]), 8)] + [f"a{i}" for i in range(0, int(hi[1]) + 1)]
            else:
                lst.append(part)
        return Op("pop" if pop else "push", (tuple(lst),), addr, 4, nxt)
    ops = [parse_operand(x) for x in split_ops(ins.op_str)]
    nxt = addr + ins.size
    base, _, sz = mn.partition(".")
    size = SIZES.get(sz, 4)

    def op(kind, *args, size=size):
        return Op(kind, args, addr, size, nxt)

    if mn == "cmpi.b" and ops[1] == ("abs", 0xDFF006):
        # raster wait loop: L: cmpi.b #n,$dff006 ; bne L
        follow = code.insn(nxt)
        if follow.mnemonic.startswith("bne") and hexval(follow.op_str) == addr:
            return Op("wait_vbl", (ops[0][1],), addr, 1, nxt + follow.size)
    if base in ("jsr",):
        if ops[0][0] != "abs":
            raise Unliftable(f"${addr:05X} library call {ins.op_str}")
        return op("call", ops[0][1])
    if base == "bsr":
        return op("call", ops[0][1])
    if base == "jmp":
        return op("jump", ops[0][1])
    if base == "rts":
        return op("ret")
    if base == "bra":
        return op("goto", ops[0][1])
    if base in ("beq", "bne", "bhi", "bls", "bcc", "bcs", "bge", "blt", "bgt", "ble", "bmi", "bpl"):
        return op("branch", base[1:], ops[0][1])
    if base == "dbra":
        return op("dbra", ops[0], ops[1][1])
    if base == "lea" and ops[0][0] == "disp":
        return op("set", ops[1], ("areg_plus", ops[0][1], ops[0][2]), size=4)
    if base == "lea" and ops[0][0] != "abs":
        raise Unliftable(f"${addr:05X} lea {ins.op_str}")
    if base in ("lea", "movea"):
        return op("set", ops[1], ops[0] if base == "movea" else ("imm", ops[0][1]), size=4)
    if base in ("move", "moveq"):
        if base == "moveq":
            size = 4
        return op("set", ops[1], ops[0], size=size)
    if base == "clr":
        return op("set", ops[0], ("imm", 0))
    if base in ("cmpi", "cmp", "cmpa"):
        return op("cmp", ops[1], ops[0])
    if base == "btst":
        return op("btst", ops[1], ops[0][1])
    if base == "tst":
        return op("tst", ops[0])
    if base in ("addi", "addq", "add", "adda"):
        return op("add", ops[1], ops[0])
    if base in ("subi", "subq", "sub", "suba"):
        return op("sub", ops[1], ops[0])
    if base in ("andi", "and"):
        return op("and", ops[1], ops[0])
    if base in ("ori", "or"):
        return op("or", ops[1], ops[0])
    if base in ("eori", "eor"):
        return op("eor", ops[1], ops[0])
    if base in ("lsl", "lsr", "asl", "asr"):
        if len(ops) == 1:                      # memory shift by one
            ops = [("imm", 1), ops[0]]
        kind = {"lsl": "shl", "asl": "shl", "lsr": "shr", "asr": "asr"}[base]
        return op(kind, ops[1], ops[0])
    if base == "swap":
        return op("swap", ops[0], size=4)
    if base in ("ext", "extb"):
        return op("ext", ops[0], size=size if base == "ext" else 4)
    if base in ("not", "neg"):
        return op(base, ops[0])
    if base in ("mulu", "muls", "divu", "divs"):
        return op(base, ops[1], ops[0])
    raise Unliftable(f"${addr:05X} {mn} {ins.op_str}")


# ---------------------------------------------------------------- CFG

class Block:
    def __init__(self, start):
        self.start = start
        self.ops = []
        self.succ = []      # successor block addresses (cond: [target, fallthrough])
        self.exit = None    # 'ret' | 'jump' | 'goto' | 'branch' | 'fall'


def build_cfg(code, entry, stop, entry_labels=()):
    """Blocks reachable from entry. `stop(addr)` says when an address belongs to
    another routine (then a branch there becomes a cross-routine goto).
    `entry_labels` are addresses that must start a block (the engine jumps there)."""
    leaders = {entry}
    seen = set()
    work = [entry]
    while work:
        a = work.pop()
        while a not in seen:
            seen.add(a)
            op = translate(code, a)
            if op.kind in ("branch", "dbra"):
                tgt = op.args[-1]
                leaders.update((tgt, op.next))
                if not stop(tgt):
                    work.append(tgt)
                work.append(op.next)
                break
            if op.kind == "goto":
                tgt = op.args[0]
                leaders.add(tgt)
                if not stop(tgt):
                    work.append(tgt)
                break
            if op.kind in ("ret", "jump"):
                break
            if op.kind == "wait_vbl":
                leaders.add(a)
            a = op.next
            if stop(a):
                leaders.add(a)
                break
    leaders.update(a for a in entry_labels if a in seen)
    blocks = {}
    for start in sorted(leaders):
        if start not in seen:
            continue
        b = Block(start)
        a = start
        while True:
            op = translate(code, a)
            b.ops.append(op)
            if op.kind in ("branch", "dbra"):
                b.exit = "branch"
                b.succ = [op.args[-1], op.next]
                break
            if op.kind == "goto":
                b.exit = "goto"
                b.succ = [op.args[0]]
                break
            if op.kind in ("ret", "jump"):
                b.exit = op.kind
                break
            a = op.next
            if a in leaders:
                b.exit = "fall"
                b.succ = [a]
                break
        blocks[start] = b
    return blocks


def postdominators(blocks, exit_node="EXIT"):
    """Immediate post-dominators via the iterative dataflow algorithm."""
    nodes = list(blocks) + [exit_node]
    succ = {n: [s for s in blocks[n].succ if s in blocks] or [exit_node] for n in blocks}
    for n in blocks:  # edges leaving the routine also lead to EXIT
        if any(s not in blocks for s in blocks[n].succ):
            succ[n] = succ[n] + [exit_node]
    succ[exit_node] = []
    pdom = {n: set(nodes) for n in nodes}
    pdom[exit_node] = {exit_node}
    changed = True
    while changed:
        changed = False
        for n in blocks:
            new = {n} | set.intersection(*(pdom[s] for s in succ[n]))
            if new != pdom[n]:
                pdom[n] = new
                changed = True
    ipdom = {}
    for n in blocks:
        strict = pdom[n] - {n}
        # the immediate one is post-dominated by all the others
        for c in strict:
            if all(c == o or o in pdom[c] for o in strict):
                ipdom[n] = c
                break
    return ipdom


# ---------------------------------------------------------------- emission

CMP_OPS = {  # cc -> (operator, unsigned?)
    "eq": "==", "ne": "~=", "hi": "u>", "ls": "u<=", "cc": "u>=", "cs": "u<",
    "ge": ">=", "lt": "<", "gt": ">", "le": "<=", "mi": "<", "pl": ">=",
}
NEGATE = {"eq": "ne", "ne": "eq", "hi": "ls", "ls": "hi", "cc": "cs", "cs": "cc",
          "ge": "lt", "lt": "ge", "gt": "le", "le": "gt", "mi": "pl", "pl": "mi"}


class Emitter:
    def __init__(self, code, lifted_names):
        self.code = code
        self.names = lifted_names      # addr -> routine name (lifted or native)

    # operands --------------------------------------------------------
    def var(self, addr, size):
        if addr in VAR_OF_ADDRESS and SIZES[VARIABLES[VAR_OF_ADDRESS[addr]][0]] == size:
            return VAR_OF_ADDRESS[addr]
        if addr in HW:
            return HW[addr]
        return f"{'?bwxl'[size]}[${addr:05X}]"

    def operand(self, o, size, value_hint=True):
        kind, v = o[0], o[1]
        if kind == "imm":
            v &= (1 << (8 * size)) - 1
            if v == (1 << (8 * size)) - 1 and size > 1:
                return "-1"
            return f"${v:X}" if v >= 10 else str(v)
        if kind == "abs":
            return self.var(v, size)
        if kind == "d":
            return f"d{v}" + {1: ".b", 2: ".w", 4: ""}[size]
        if kind == "a":
            return f"a{v}"
        if kind == "postinc":
            return f"{'?bwxl'[size]}[a{v}++]"
        if kind == "ind":
            return f"{'?bwxl'[size]}[a{v}]"
        if kind == "disp":
            off = o[2]
            return f"{'?bwxl'[size]}[a{v}{'+' if off >= 0 else '-'}${abs(off):X}]"
        if kind == "areg_plus":
            off = o[2]
            return f"a{v} {'+' if off >= 0 else '-'} ${abs(off):X}"
        if kind == "predec":
            return f"{'?bwxl'[size]}[--a{v}]"
        raise Unliftable(str(o))

    def text_comment(self, value):
        if TEXT_RANGE[0] <= value < TEXT_RANGE[1]:
            t = self.code.text_at(value).replace("\n", " / ")
            if len(t) < 2 or sum(ch.isalpha() for ch in t) < len(t) // 2:
                return ""
            if len(t) > 70:
                t = t[:67] + "..."
            return f'  -- "{t}"'
        return ""

    def target(self, addr):
        return self.names.get(addr, f"${addr:05X}")

    # statements ------------------------------------------------------
    def stmt(self, op):
        k, a = op.kind, op.args
        if k == "wait_vbl":
            return f"wait_raster ${a[0]:02X}"
        if k == "call":
            return f"call {self.target(a[0])}"
        if k == "jump":
            return f"jump {self.target(a[0])}"
        if k == "ret":
            return "return"
        if k == "push":
            return "push " + ", ".join(a[0])
        if k == "pop":
            return "pop " + ", ".join(a[0])
        if k in ("shl", "shr", "asr"):
            return f"{k} {self.operand(a[0], op.size)}, {self.operand(a[1], 1)}"
        if k in ("swap", "not", "neg"):
            return f"{k} {self.operand(a[0], op.size)}"
        if k == "ext":
            return f"ext {self.operand(a[0], op.size)}"
        if k in ("mulu", "muls", "divu", "divs"):
            return f"{k} {self.operand(a[0], 4)}, {self.operand(a[1], 2)}"
        if k == "set":
            dst, src = a
            line = f"{self.operand(dst, op.size)} = {self.operand(src, op.size)}"
            if src[0] == "imm":
                line += self.text_comment(src[1])
            return line
        if k in ("add", "sub", "and", "or", "eor"):
            sym = {"add": "+=", "sub": "-=", "and": "&=", "or": "|=", "eor": "^="}[k]
            return f"{self.operand(a[0], op.size)} {sym} {self.operand(a[1], op.size)}"
        if k in ("cmp", "btst", "tst"):
            return None  # folded into the following branch
        raise Unliftable(k)

    def condition(self, flag_op, cc):
        if flag_op is None:
            raise Unliftable("branch without a flag-setting instruction in the same block")
        if flag_op.kind == "btst":
            src, bit = flag_op.args
            if src == ("abs", 0xBFE001) and bit == 6:
                return "lmb" if cc == "eq" else "not lmb"
            if src == ("abs", 0xDFF016) and bit == 10:
                return "rmb" if cc == "eq" else "not rmb"
            if src == ("abs", 0xBFE001) and bit == 7:
                return "fire" if cc == "eq" else "not fire"
            val = self.operand(src, 1)
            return f"bit({val}, {bit}) {'== 0' if cc == 'eq' else '~= 0'}"
        if flag_op.kind == "tst":
            return f"{self.operand(flag_op.args[0], flag_op.size)} {CMP_OPS[cc]} 0"
        lhs, rhs = flag_op.args
        return f"{self.operand(lhs, flag_op.size)} {CMP_OPS[cc]} {self.operand(rhs, flag_op.size)}"


def emit_routine(code, name, entry, blocks, em, labels_needed):
    """Structured emission. Returns list of (indent, text)."""
    ipdom = postdominators(blocks)
    out = []
    emitted = set()

    def label(a):
        return f"{LABEL_PREFIX}{a:05X}"

    def emit_range(start, stop_at, depth):
        b_addr = start
        while b_addr is not None and b_addr != stop_at:
            if b_addr not in blocks:          # leaves the routine
                out.append((depth, f"goto {label(b_addr)}"))
                labels_needed.add(b_addr)
                return
            if b_addr in emitted:
                out.append((depth, f"goto {label(b_addr)}"))
                labels_needed.add(b_addr)
                return
            emitted.add(b_addr)
            blk = blocks[b_addr]
            out.append((depth, ("LABEL", b_addr)))
            flag = inherited.get(b_addr)
            for op in blk.ops:
                if op.kind in ("cmp", "btst", "tst"):
                    flag = op
                    continue
                if op.kind in ("branch", "goto", "dbra"):
                    break
                s = em.stmt(op)
                if s:
                    out.append((depth, s))
                if op.kind in ("set", "add", "sub", "and", "or", "eor", "shl", "shr", "asr", "swap", "ext", "not", "neg", "mulu", "muls") and op.args[0][0] != "a":
                    # 68k: data moves and arithmetic set N/Z from the result
                    flag = Op("tst", (op.args[0],), op.addr, op.size, op.next)
                elif op.kind == "call":
                    flag = None
            last = blk.ops[-1]
            if blk.exit in ("ret", "jump"):
                return
            if blk.exit == "fall":
                b_addr = blk.succ[0]
                continue
            if blk.exit == "goto":
                tgt = blk.succ[0]
                if tgt in blocks and tgt not in emitted and tgt != stop_at and is_only_pred(tgt, b_addr):
                    b_addr = tgt
                    continue
                if tgt == stop_at:
                    return
                out.append((depth, f"goto {label(tgt)}"))
                labels_needed.add(tgt)
                return
            # conditional branch
            if last.kind == "dbra":
                reg = em.operand(last.args[0], 2)
                out.append((depth, f"{reg} -= 1"))
                out.append((depth, f"if {reg} ~= -1 then goto {label(last.args[1])} end"))
                labels_needed.add(last.args[1])
                b_addr = last.next
                continue
            cc = last.args[0]
            taken, fall = blk.succ
            join = ipdom.get(b_addr)
            if join == "EXIT":
                join = None
            # body executed when the branch is NOT taken comes first in the asm
            cond_fall = em.condition(flag, NEGATE[cc])
            cond_taken = em.condition(flag, cc)
            if join is not None and join not in emitted:
                then_start, else_start, cond = fall, taken, cond_fall
                out.append((depth, f"if {cond} then"))
                emit_range(then_start, join, depth + 1)
                if else_start != join:
                    # fold `else if` chains
                    out.append((depth, "else"))
                    emit_range(else_start, join, depth + 1)
                out.append((depth, "end"))
                b_addr = join
                continue
            # no common join: both sides end in a goto/return/jump. Put the fall-through
            # side (the asm's "case body") inside the if and carry on with the branch
            # target, so hotspot tests read like a switch instead of nesting.
            if fall in emitted or fall not in blocks:
                out.append((depth, f"if {cond_taken} then"))
                emit_range(taken, None, depth + 1)
                out.append((depth, "end"))
                b_addr = fall
            else:
                out.append((depth, f"if {cond_fall} then"))
                emit_range(fall, None, depth + 1)
                out.append((depth, "end"))
                b_addr = taken
        return

    preds = collections.defaultdict(set)
    for a, b in blocks.items():
        for s in b.succ:
            preds[s].add(a)

    # flags survive a not-taken branch: `beq X / bne Y` tests the same compare twice
    inherited = {}
    for a in sorted(blocks):
        b = blocks[a]
        if b.exit != "branch" or b.ops[-1].kind != "branch":
            continue
        f = inherited.get(a)
        for op in b.ops:
            if op.kind in ("cmp", "btst", "tst"):
                f = op
            elif op.kind in ("set", "add", "sub", "and", "or", "eor", "shl", "shr", "asr", "swap", "ext", "not", "neg", "mulu", "muls") and op.args[0][0] != "a":
                f = Op("tst", (op.args[0],), op.addr, op.size, op.next)
            elif op.kind == "call":
                f = None
        fall = b.succ[1]
        if f is not None and preds.get(fall) == {a}:
            inherited[fall] = f

    def is_only_pred(tgt, src):
        return preds[tgt] == {src}

    emit_range(entry, None, 1)
    # leftovers (reached only through gotos from elsewhere)
    for a in sorted(blocks):
        if a not in emitted:
            emit_range(a, None, 1)
    return out


def fold_else_if(lines):
    """`else` + nested `if ... end` as the only content -> `elseif`."""
    changed = True
    while changed:
        changed = False
        for i, (d, t) in enumerate(lines):
            if t == "else" and i + 1 < len(lines):
                d2, t2 = lines[i + 1]
                if isinstance(t2, str) and t2.startswith("if ") and d2 == d + 1:
                    # find matching end of the nested if
                    j, depth = i + 2, 1
                    while j < len(lines):
                        dj, tj = lines[j]
                        if dj == d + 1 and isinstance(tj, str) and tj.startswith("if "):
                            depth += 1
                        if dj == d + 1 and tj == "end":
                            depth -= 1
                            if depth == 0:
                                break
                        j += 1
                    # the else block must contain only that if
                    if j + 1 < len(lines) and lines[j + 1] == (d, "end"):
                        new = lines[:i] + [(d, "elseif " + t2[3:])]
                        new += [(dd - 1, tt) for dd, tt in lines[i + 2:j]]
                        new += lines[j + 1:]
                        lines[:] = new
                        changed = True
                        break
    return lines


def render(lines, labels_needed):
    out = []
    for d, t in lines:
        if isinstance(t, tuple):
            if t[1] in labels_needed:
                out.append("  " * max(d - 1, 0) + f"::{LABEL_PREFIX}{t[1]:05X}::")
            continue
        out.append("  " * d + t)
    return out


# ---------------------------------------------------------------- driver

def location_entries(code):
    """Location routines start with `move.b #id,$7BBD4` (13FC 00id 0007 BBD4)."""
    blob = code.blob
    out = []
    for m in re.finditer(rb"\x13\xfc\x00(.)\x00\x07\xbb\xd4", blob, re.S):
        a = m.start() + LOAD
        if 0x30F0 <= a < 0x14300:
            out.append((a, m.group(1)[0]))
    return out


def discover(code, starts, todo, names, native, sub_prefix="", entry_labels=()):
    """Lift every routine reachable from `todo`. Returns (routines, native_needed, failures)."""
    routines = {}
    native_needed = collections.Counter()
    failures = {}
    owned = set()          # instruction addresses already inside a lifted routine

    def lift_all(todo):
        while todo:
            a = todo.pop()
            if a in routines or a in failures or a in native:
                continue
            region_end = min([s for s in starts if s > a] + [a + 0x10000])

            def stop(x, a=a, region_end=region_end):
                return x != a and (x in starts or x >= region_end or x < a - 0x10000 or x in owned)
            try:
                blocks = build_cfg(code, a, stop, entry_labels)
            except Unliftable as e:
                failures[a] = str(e)
                continue
            routines[a] = blocks
            for b in blocks.values():
                owned.update(op.addr for op in b.ops)
                for op in b.ops:
                    if op.kind in ("call", "jump"):
                        t = op.args[0]
                        if t in native:
                            native_needed[t] += 1
                        elif t not in routines:
                            todo.append(t)
            names.setdefault(a, f"{sub_prefix}sub_{a:05X}")

    lift_all(list(todo))
    # branch targets that no routine reaches from its own entry (e.g. a location jumping
    # into the middle of another one) become entry points of their own
    while True:
        block_starts = {b for r in routines.values() for b in r}
        extra = set()
        for r in routines.values():
            for b in r.values():
                for t in b.succ:
                    if t not in block_starts and t not in failures:
                        extra.add(t)
        extra -= set(routines)
        if not extra:
            break
        for t in extra:
            names.setdefault(t, f"{sub_prefix}part_{t:05X}")
        lift_all(sorted(extra))
    for a in failures:                      # anything that failed to lift is native
        names.setdefault(a, f"{sub_prefix}native_{a:05X}")
    for a in native:
        names.setdefault(a, f"{sub_prefix}native_{a:05X}")
    return routines, native_needed, failures


def emit_files(code, routines, names, failures, group_of, entry_labels=()):
    em = Emitter(code, names)
    labels_needed = set(entry_labels)
    rendered = {}
    for a in sorted(list(routines)):
        try:
            rendered[a] = emit_routine(code, names[a], a, routines[a], em, labels_needed)
        except Unliftable as e:
            failures[a] = f"emit: {e}"
            del routines[a]
    files = collections.defaultdict(list)
    for a in sorted(routines):
        name = names[a]
        lines = [(d, t) for d, t in rendered[a] if not (isinstance(t, tuple) and t[1] not in labels_needed)]
        files[group_of(name)].extend([f"routine {name} @ ${a:05X}"] + render(fold_else_if(lines), labels_needed) + ["end", ""])
    return files


def write_report(path, routines, native_needed, failures, names):
    with path.open("w", encoding="utf-8") as f:
        f.write(f"lifted routines: {len(routines)}\n")
        f.write(f"native routines needed: {len(native_needed)}\n")
        for t, n in native_needed.most_common():
            f.write(f"  ${t:05X} {names.get(t, '?'):24s} x{n}\n")
        f.write(f"unliftable (must be native): {len(failures)}\n")
        for a, why in sorted(failures.items()):
            f.write(f"  ${a:05X} {names.get(a, '?'):24s} {why}\n")
    print(path.read_text(encoding="utf-8")[:3000])


def lift_game(adf1, outdir):
    global LABEL_PREFIX
    LABEL_PREFIX = "L"
    code = Code(decrunch(adf1, 0x38400)[0])
    entries = location_entries(code)
    names = dict(ROUTINES)
    seen_ids = collections.Counter()
    for a, lid in entries:
        seen_ids[lid] += 1
        names.setdefault(a, f"loc_{lid:02X}" if seen_ids[lid] == 1 else f"loc_{lid:02X}_{seen_ids[lid]}")
    starts = sorted({a for a, _ in entries})
    names[MAIN_LOAD] = "boot"
    todo = list(starts) + [MAIN_LOAD, 0x143C0, 0x15732, 0x14A60]
    routines, native_needed, failures = discover(code, starts, todo, names, NATIVE)

    def group_of(name):
        return name.split("_")[0] + "_" + name.split("_")[1] if name.startswith("loc_") else "common"
    files = emit_files(code, routines, names, failures, group_of)
    for group, lines in files.items():
        (outdir / f"{group}.alf").write_text("\n".join(lines), encoding="utf-8", newline="\n")
    sym = ["-- Variable names used by the scripts: name, size (b/w/l), original address.",
           "-- Generated from tools/symbols.py by tools/lifter.py.", ""]
    for name, (size, addr) in sorted(VARIABLES.items(), key=lambda kv: kv[1][1]):
        sym.append(f"var {name} {size} ${addr:05X}")
    (outdir / "symbols.alf").write_text("\n".join(sym) + "\n", encoding="utf-8", newline="\n")
    write_report(ROOT / "work" / "lift_report.txt", routines, native_needed, failures, names)


def lift_intro(adf1, outdir):
    """The intro is a separate program also loaded at $3000; its labels get the IL prefix."""
    global LABEL_PREFIX
    LABEL_PREFIX = "IL"
    code = Code(decrunch(adf1, 0x2C00)[0])
    names = dict(INTRO_ROUTINES)
    names[MAIN_LOAD] = "intro"
    routines, native_needed, failures = discover(code, [MAIN_LOAD], [MAIN_LOAD], names, set(INTRO_NATIVE),
                                                 sub_prefix="intro_", entry_labels=INTRO_LABELS)
    files = emit_files(code, routines, names, failures, lambda n: "intro", entry_labels=INTRO_LABELS)
    head = ["-- The intro program (disk 1, sector 22), lifted like the game. It is loaded at $3000",
            "-- before the main game, so its labels use the IL prefix.", "labels IL", ""]
    (outdir / "intro.alf").write_text("\n".join(head + files["intro"]), encoding="utf-8", newline="\n")
    LABEL_PREFIX = "L"
    write_report(ROOT / "work" / "lift_report_intro.txt", routines, native_needed, failures, names)


def main():
    adf1 = (ROOT / "AlfabetSmierci" / "data" / "disk1.adf").read_bytes()
    outdir = ROOT / "scripts"
    outdir.mkdir(exist_ok=True)
    lift_game(adf1, outdir)
    lift_intro(adf1, outdir)


if __name__ == "__main__":
    main()
