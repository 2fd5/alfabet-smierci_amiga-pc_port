"""Polish charset used by Alfabet Smierci (empirical, derived from in-game text)."""
LOWER = {0xE6: "ą", 0xE7: "ć", 0xEA: "ę", 0xEE: "ł", 0xF1: "ń", 0xF3: "ó", 0xF5: "ś", 0xFB: "ź", 0xFE: "ż"}
UPPER = {k - 0x20: v.upper() for k, v in LOWER.items()}  # verified: Ł=CE, Ś=D5, Ż=DE
TABLE = {**LOWER, **UPPER}


def decode(b: bytes) -> str:
    return "".join(TABLE.get(c, chr(c)) for c in b)
