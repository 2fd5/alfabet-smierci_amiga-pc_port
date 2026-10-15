/* .alf script compiler and interpreter. */
#include "script.h"

#include "amiga.h"

#include <SDL3/SDL.h>
#include <ctype.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* ------------------------------------------------------------------ program */

enum { E_IMM, E_DREG, E_AREG, E_MEM };
enum { M_ABS, M_IND, M_DISP, M_POSTINC, M_PREDEC };

typedef struct {
    uint8_t kind, size, reg, mode;
    int32_t disp;
    uint32_t value;
} Expr;

enum { OP_SET, OP_ADD, OP_SUB, OP_AND, OP_OR, OP_EOR, OP_JMP, OP_JFALSE, OP_CALL, OP_CALLN, OP_RET, OP_VBL,
       OP_PUSH, OP_POP, OP_SHL, OP_SHR, OP_ASR, OP_SWAP, OP_EXT, OP_NOT, OP_NEG, OP_MULU, OP_MULS, OP_DIVU, OP_DIVS };
enum { C_CMP, C_LMB, C_RMB, C_FIRE, C_BIT };
enum { CMP_EQ, CMP_NE, CMP_LT, CMP_LE, CMP_GT, CMP_GE, CMP_ULT, CMP_ULE, CMP_UGT, CMP_UGE };

typedef struct {
    uint8_t op, cond, cmp, size, negate;
    Expr x, y;
    int target;          /* pc (jumps, calls) or native index; for labels resolved later */
    int line, file;
    char *label_ref;     /* unresolved label/routine name */
} Ins;

static Ins *prog;
static int nprog, capprog;

typedef struct { char *name; int pc; uint32_t addr; int program; } Sym;
static Sym *labels; static int nlabels;
static bool g_dbg;      /* ALF_DBG: diagnostic prints */
static Sym *routines; static int nroutines;
typedef struct { char *name; uint8_t size; uint32_t addr; } Var;
static Var *vars; static int nvars;
static const Native *g_natives; static int g_nnatives;
static char *files[128]; static int nfiles;
static char label_prefix[8] = "L";     /* "labels IL" in a file switches it (the intro) */

static Ins *emit(void)
{
    if (nprog == capprog) {
        capprog = capprog ? capprog * 2 : 4096;
        prog = realloc(prog, capprog * sizeof *prog);
    }
    memset(&prog[nprog], 0, sizeof *prog);
    return &prog[nprog++];
}

static void add_sym(Sym **tab, int *n, const char *name, int pc, uint32_t addr)
{
    *tab = realloc(*tab, (*n + 1) * sizeof **tab);
    (*tab)[*n].name = SDL_strdup(name);
    (*tab)[*n].pc = pc;
    (*tab)[*n].addr = addr;
    (*tab)[*n].program = strcmp(label_prefix, "L") != 0;
    (*n)++;
}

static Sym *find_sym(Sym *tab, int n, const char *name)
{
    for (int i = 0; i < n; i++)
        if (!strcmp(tab[i].name, name))
            return &tab[i];
    return NULL;
}

/* ------------------------------------------------------------------ lexer */

typedef struct { char text[96]; int line; } Tok;
static Tok *toks; static int ntoks, tpos;
static int cur_file;
static bool parse_error;

static void err(const char *fmt, ...)
{
    va_list ap;
    va_start(ap, fmt);
    fprintf(stderr, "%s:%d: ", files[cur_file], tpos < ntoks ? toks[tpos].line : -1);
    vfprintf(stderr, fmt, ap);
    fprintf(stderr, "\n");
    va_end(ap);
    parse_error = true;
}

static void lex(const char *src)
{
    ntoks = tpos = 0;
    int line = 1, cap = 0;
    const char *p = src;
    while (*p) {
        if (*p == '\n') { line++; p++; continue; }
        if (isspace((unsigned char)*p)) { p++; continue; }
        if (p[0] == '-' && p[1] == '-') { while (*p && *p != '\n') p++; continue; }
        if (ntoks == cap) { cap = cap ? cap * 2 : 8192; toks = realloc(toks, cap * sizeof *toks); }
        Tok *t = &toks[ntoks++];
        t->line = line;
        int n = 0;
        static const char *ops[] = {"::", "u<=", "u>=", "u<", "u>", "==", "~=", "<=", ">=", "+=", "-=",
                                    "&=", "|=", "++", "--", "<", ">", "=", "[", "]", "(", ")", ",", "+", "-", "@", NULL};
        bool matched = false;
        if (!(p[0] == 'u' && isalnum((unsigned char)p[1]) && p[1] != '<' && p[1] != '>')) {
            for (int i = 0; ops[i]; i++) {
                size_t l = strlen(ops[i]);
                if (!strncmp(p, ops[i], l)) {
                    memcpy(t->text, p, l);
                    t->text[l] = 0;
                    p += l;
                    matched = true;
                    break;
                }
            }
        }
        if (matched)
            continue;
        while (*p && (isalnum((unsigned char)*p) || *p == '_' || *p == '$' || *p == '.') && n < 95)
            t->text[n++] = *p++;
        if (n == 0) { t->text[0] = *p++; n = 1; }
        t->text[n] = 0;
    }
}

static const char *peek(void) { return tpos < ntoks ? toks[tpos].text : ""; }
static const char *next(void) { return tpos < ntoks ? toks[tpos++].text : ""; }
static bool accept(const char *s) { if (!strcmp(peek(), s)) { tpos++; return true; } return false; }
static void expect(const char *s) { if (!accept(s)) err("expected '%s', got '%s'", s, peek()); }

static bool parse_number(const char *s, uint32_t *out)
{
    if (s[0] == '$') { char *e; *out = (uint32_t)strtoul(s + 1, &e, 16); return *e == 0 && s[1]; }
    if (isdigit((unsigned char)s[0])) { char *e; *out = (uint32_t)strtoul(s, &e, 10); return *e == 0; }
    return false;
}

static int size_of(char c) { return c == 'b' ? 1 : c == 'w' ? 2 : 4; }

/* ------------------------------------------------------------------ parser */

static Expr parse_expr(void)
{
    Expr e = {0};
    const char *t = next();
    uint32_t v;
    if (!strcmp(t, "-")) {                     /* -1 */
        if (!parse_number(next(), &v)) err("bad number");
        e.kind = E_IMM; e.size = 4; e.value = (uint32_t)-(int32_t)v;
        return e;
    }
    if (parse_number(t, &v)) { e.kind = E_IMM; e.size = 4; e.value = v; return e; }
    if ((t[0] == 'd' || t[0] == 'a') && t[1] >= '0' && t[1] <= '7' && (t[2] == 0 || t[2] == '.')) {
        e.kind = t[0] == 'd' ? E_DREG : E_AREG;
        e.reg = (uint8_t)(t[1] - '0');
        e.size = t[2] == '.' ? (uint8_t)size_of(t[3]) : 4;
        /* "a1 + $8": lea 8(a1),... (only as a value, never as a target) */
        if (e.kind == E_AREG && (!strcmp(peek(), "+") || !strcmp(peek(), "-")) &&
            tpos + 1 < ntoks && toks[tpos + 1].text[0] == '$') {
            bool neg = !strcmp(next(), "-");
            parse_number(next(), &v);
            e.mode = M_DISP;
            e.disp = neg ? -(int32_t)v : (int32_t)v;
        }
        return e;
    }
    if ((t[0] == 'b' || t[0] == 'w' || t[0] == 'l') && t[1] == 0 && !strcmp(peek(), "[")) {
        next();
        e.kind = E_MEM; e.size = (uint8_t)size_of(t[0]);
        if (accept("--")) {
            const char *r = next(); e.mode = M_PREDEC; e.reg = (uint8_t)(r[1] - '0');
        } else {
            const char *r = next();
            if (parse_number(r, &v)) { e.mode = M_ABS; e.value = v; }
            else {
                e.reg = (uint8_t)(r[1] - '0');
                if (accept("++")) e.mode = M_POSTINC;
                else if (accept("+")) { parse_number(next(), &v); e.mode = M_DISP; e.disp = (int32_t)v; }
                else if (accept("-")) { parse_number(next(), &v); e.mode = M_DISP; e.disp = -(int32_t)v; }
                else e.mode = M_IND;
            }
        }
        expect("]");
        return e;
    }
    for (int i = 0; i < nvars; i++)
        if (!strcmp(vars[i].name, t)) {
            e.kind = E_MEM; e.mode = M_ABS; e.size = vars[i].size; e.value = vars[i].addr;
            return e;
        }
    static const struct { const char *n; uint32_t a; } hw[] = {{"ciaa_pra", 0xBFE001}, {"vhpos", 0xDFF006}, {"potgor", 0xDFF016}};
    for (int i = 0; i < 3; i++)
        if (!strcmp(hw[i].n, t)) { e.kind = E_MEM; e.mode = M_ABS; e.size = 1; e.value = hw[i].a; return e; }
    err("unknown operand '%s'", t);
    return e;
}

static void parse_cond(Ins *in)
{
    bool neg = accept("not");
    if (accept("lmb")) { in->cond = C_LMB; in->negate = neg; return; }
    if (accept("rmb")) { in->cond = C_RMB; in->negate = neg; return; }
    if (accept("fire")) { in->cond = C_FIRE; in->negate = neg; return; }
    if (accept("bit")) {
        expect("(");
        in->x = parse_expr();
        expect(",");
        uint32_t n; parse_number(next(), &n);
        in->y.value = n;
        expect(")");
        const char *op = next();
        next(); /* 0 */
        in->cond = C_BIT;
        in->negate = !strcmp(op, "==");        /* "== 0": true when the bit is clear */
        return;
    }
    in->cond = C_CMP;
    in->x = parse_expr();
    const char *op = next();
    static const char *names[] = {"==", "~=", "<", "<=", ">", ">=", "u<", "u<=", "u>", "u>="};
    in->cmp = 255;
    for (int i = 0; i < 10; i++) if (!strcmp(op, names[i])) in->cmp = (uint8_t)i;
    if (in->cmp == 255) err("bad comparison '%s'", op);
    in->y = parse_expr();
    in->size = in->x.kind == E_IMM ? in->y.size : in->x.size;
}

static void parse_block(const char *const *terminators);

static void parse_if(void)
{
    /* if C then B (elseif C then B)* (else B)? end */
    int ends[64], nends = 0;
    for (;;) {
        Ins *j = emit();
        int jpc = nprog - 1;
        j->op = OP_JFALSE; j->line = toks[tpos].line; j->file = cur_file;
        parse_cond(&prog[jpc]);
        expect("then");
        static const char *const term[] = {"elseif", "else", "end", NULL};
        parse_block(term);
        const char *t = peek();
        if (!strcmp(t, "end")) { next(); prog[jpc].target = nprog; break; }
        Ins *jj = emit(); jj->op = OP_JMP; ends[nends++] = nprog - 1;
        prog[jpc].target = nprog;
        if (accept("elseif")) continue;
        expect("else");
        static const char *const term2[] = {"end", NULL};
        parse_block(term2);
        expect("end");
        break;
    }
    for (int i = 0; i < nends; i++) prog[ends[i]].target = nprog;
}

static void parse_statement(void)
{
    int line = toks[tpos].line;
    const char *t = peek();
    if (!strcmp(t, "::")) {
        next();
        add_sym(&labels, &nlabels, next(), nprog, 0);
        expect("::");
        return;
    }
    if (accept("if")) { parse_if(); return; }
    Ins *in = NULL;
    if (accept("wait_vbl")) { in = emit(); in->op = OP_VBL; in->y.value = 0xFF; }
    else if (accept("wait_raster")) {
        /* L: cmpi.b #n,$dff006 / bne L: wait until the beam's line (low byte) equals n */
        in = emit();
        in->op = OP_VBL;
        uint32_t n;
        parse_number(next(), &n);
        in->y.value = n & 0xFF;
    }
    else if (accept("return")) { in = emit(); in->op = OP_RET; }
    else if (!strcmp(t, "push") || !strcmp(t, "pop")) {
        /* register list as a bit set: bit k = d(k), bit 8+k = a(k) */
        in = emit();
        in->op = !strcmp(next(), "push") ? OP_PUSH : OP_POP;
        do {
            const char *r = next();
            in->x.value |= 1u << ((r[0] == 'a' ? 8 : 0) + (r[1] - '0'));
        } while (accept(","));
    } else if (!strcmp(t, "shl") || !strcmp(t, "shr") || !strcmp(t, "asr") || !strcmp(t, "mulu") ||
               !strcmp(t, "muls") || !strcmp(t, "divu") || !strcmp(t, "divs")) {
        const char *k = next();
        in = emit();
        in->op = !strcmp(k, "shl") ? OP_SHL : !strcmp(k, "shr") ? OP_SHR : !strcmp(k, "asr") ? OP_ASR :
                 !strcmp(k, "mulu") ? OP_MULU : !strcmp(k, "muls") ? OP_MULS : !strcmp(k, "divu") ? OP_DIVU : OP_DIVS;
        in->x = parse_expr();
        expect(",");
        in->y = parse_expr();
        in->size = in->x.size;
    } else if (!strcmp(t, "swap") || !strcmp(t, "ext") || !strcmp(t, "not") || !strcmp(t, "neg")) {
        const char *k = next();
        in = emit();
        in->op = !strcmp(k, "swap") ? OP_SWAP : !strcmp(k, "ext") ? OP_EXT : !strcmp(k, "not") ? OP_NOT : OP_NEG;
        in->x = parse_expr();
        in->size = in->x.size;
    }
    else if (accept("goto") || accept("jump")) {
        in = emit(); in->op = OP_JMP; in->label_ref = SDL_strdup(next());
    } else if (accept("call")) {
        in = emit(); in->op = OP_CALL; in->label_ref = SDL_strdup(next());
    } else {
        in = emit();
        in->x = parse_expr();
        const char *op = next();
        if (!strcmp(op, "=")) in->op = OP_SET;
        else if (!strcmp(op, "+=")) in->op = OP_ADD;
        else if (!strcmp(op, "-=")) in->op = OP_SUB;
        else if (!strcmp(op, "&=")) in->op = OP_AND;
        else if (!strcmp(op, "|=")) in->op = OP_OR;
        else if (!strcmp(op, "^=")) in->op = OP_EOR;
        else err("unknown statement near '%s'", op);
        in->y = parse_expr();
        in->size = in->x.size;
    }
    in->line = line;
    in->file = cur_file;
}

static void parse_block(const char *const *terminators)
{
    while (tpos < ntoks && !parse_error) {
        for (int i = 0; terminators[i]; i++)
            if (!strcmp(peek(), terminators[i]))
                return;
        parse_statement();
    }
}

static void parse_file(void)
{
    while (tpos < ntoks && !parse_error) {
        if (accept("labels")) {
            SDL_strlcpy(label_prefix, next(), sizeof label_prefix);
            continue;
        }
        if (accept("var")) {
            const char *name = next();
            const char *sz = next();
            uint32_t a; parse_number(next(), &a);
            vars = realloc(vars, (nvars + 1) * sizeof *vars);
            vars[nvars].name = SDL_strdup(name); vars[nvars].size = (uint8_t)size_of(sz[0]); vars[nvars].addr = a;
            nvars++;
            continue;
        }
        expect("routine");
        const char *name = next();
        expect("@");
        uint32_t addr; parse_number(next(), &addr);
        char lab[16];
        SDL_snprintf(lab, sizeof lab, "%s%05X", label_prefix, addr);
        add_sym(&routines, &nroutines, name, nprog, addr);
        add_sym(&labels, &nlabels, lab, nprog, addr);
        static const char *const term[] = {"end", NULL};
        parse_block(term);
        expect("end");
        Ins *r = emit(); r->op = OP_RET; r->file = cur_file;  /* asm falls off the end only by bugs */
    }
}

static char *read_text(const char *path)
{
    size_t len;
    return SDL_LoadFile(path, &len);
}

bool script_load_dir(const char *dir, const Native *natives, int n_natives)
{
    g_natives = natives;
    g_nnatives = n_natives;
    int count;
    char **list = SDL_GlobDirectory(dir, "*.alf", 0, &count);
    if (!list) return false;
    /* symbols first, so variable names resolve in every file */
    for (int pass = 0; pass < 2; pass++) {
        for (int i = 0; i < count; i++) {
            bool is_sym = !strcmp(list[i], "symbols.alf");
            if ((pass == 0) != is_sym) continue;
            char path[1024];
            SDL_snprintf(path, sizeof path, "%s/%s", dir, list[i]);
            char *src = read_text(path);
            if (!src) { fprintf(stderr, "cannot read %s\n", path); return false; }
            cur_file = nfiles;
            files[nfiles++] = SDL_strdup(list[i]);
            SDL_strlcpy(label_prefix, "L", sizeof label_prefix);
            lex(src);
            SDL_free(src);
            parse_file();
            if (parse_error) return false;
        }
    }
    SDL_free(list);
    /* resolve names */
    for (int i = 0; i < nprog; i++) {
        Ins *in = &prog[i];
        if (!in->label_ref) continue;
        const char *n = in->label_ref;
        Sym *s;
        uint32_t addr;
        bool by_addr = parse_number(n, &addr);
        if (in->op == OP_CALL) {
            int native = -1;
            for (int k = 0; k < g_nnatives; k++)
                if ((!by_addr && !strcmp(g_natives[k].name, n)) || (by_addr && g_natives[k].addr == addr)) native = k;
            if (native >= 0) { in->op = OP_CALLN; in->target = native; continue; }
            s = by_addr ? NULL : find_sym(routines, nroutines, n);
            if (by_addr) for (int k = 0; k < nroutines; k++) if (routines[k].addr == addr && !routines[k].program) s = &routines[k];
            if (!s) {
                /* unknown native: keep it as a call that reports itself at runtime */
                in->op = OP_CALLN; in->target = -1;
                continue;
            }
            in->target = s->pc;
        } else {
            s = find_sym(labels, nlabels, n);
            if (!s) s = find_sym(routines, nroutines, n);
            if (!s) {
                /* jump to a native routine (e.g. the intro's jmp into the loader): the native
                 * itself moves on, so it is called like any other */
                int native = -1;
                for (int k = 0; k < g_nnatives; k++) if (!strcmp(g_natives[k].name, n)) native = k;
                if (native >= 0) { in->op = OP_CALLN; in->target = native; continue; }
                fprintf(stderr, "%s:%d: unknown label %s\n", files[in->file], in->line, n);
                return false;
            }
            in->target = s->pc;
        }
    }
    fprintf(stderr, "scripts: %d files, %d routines, %d instructions\n", nfiles, nroutines, nprog);
    return true;
}

int script_routine_pc(uint32_t addr)
{
    for (int k = 0; k < nroutines; k++) if (routines[k].addr == addr && !routines[k].program) return routines[k].pc;
    return -1;
}

int script_routine_pc_by_name(const char *name)
{
    Sym *s = find_sym(routines, nroutines, name);
    return s ? s->pc : -1;
}

int script_label_pc(const char *name)
{
    Sym *s = find_sym(labels, nlabels, name);
    return s ? s->pc : -1;
}

const char *script_routine_name(uint32_t addr)
{
    for (int k = 0; k < nroutines; k++) if (routines[k].addr == addr && !routines[k].program) return routines[k].name;
    return NULL;
}

const char *script_where(int pc)
{
    static char buf[160];
    if (pc < 0 || pc >= nprog) return "?";
    SDL_snprintf(buf, sizeof buf, "%s:%d", files[prog[pc].file], prog[pc].line);
    return buf;
}

/* ------------------------------------------------------------------ interpreter */

static uint32_t mask(int size) { return size == 1 ? 0xFFu : size == 2 ? 0xFFFFu : 0xFFFFFFFFu; }

static int32_t sext(uint32_t v, int size)
{
    if (size == 1) return (int8_t)v;
    if (size == 2) return (int16_t)v;
    return (int32_t)v;
}

static uint32_t ea_addr(VM *vm, const Expr *e)
{
    switch (e->mode) {
    case M_ABS: return e->value;
    case M_IND: return vm->a[e->reg];
    case M_DISP: return vm->a[e->reg] + (uint32_t)e->disp;
    case M_POSTINC: { uint32_t a = vm->a[e->reg]; vm->a[e->reg] += e->size; return a; }
    case M_PREDEC: vm->a[e->reg] -= e->size; return vm->a[e->reg];
    }
    return 0;
}

static uint32_t mem_read(uint32_t a, int size)
{
    return size == 1 ? rd8(a) : size == 2 ? rd16(a) : rd32(a);
}

static void mem_write(uint32_t a, int size, uint32_t v)
{
    if (size == 1) wr8(a, v); else if (size == 2) wr16(a, v); else wr32(a, v);
}

static uint32_t read_expr(VM *vm, const Expr *e, int size)
{
    switch (e->kind) {
    case E_IMM: return e->value & mask(size);
    case E_DREG: return vm->d[e->reg] & mask(size);
    case E_AREG: return (vm->a[e->reg] + (e->mode == M_DISP ? (uint32_t)e->disp : 0)) & mask(size);
    case E_MEM: return mem_read(ea_addr(vm, e), e->size);
    }
    return 0;
}

static void write_expr(VM *vm, const Expr *e, uint32_t v)
{
    switch (e->kind) {
    case E_DREG: { uint32_t m = mask(e->size); vm->d[e->reg] = (vm->d[e->reg] & ~m) | (v & m); break; }
    case E_AREG: vm->a[e->reg] = v; break;
    case E_MEM: mem_write(ea_addr(vm, e), e->size, v); break;
    }
}

static bool eval_cond(VM *vm, const Ins *in)
{
    const AmigaInput *ip = amiga_input();
    bool r;
    switch (in->cond) {
    case C_LMB: amiga_note_lmb_poll(); r = ip->lmb; if (r && g_dbg) fprintf(stderr, "lmb true at %s\n", script_where(vm->pc)); break;
    case C_RMB: r = ip->rmb; break;
    case C_FIRE: r = ip->fire; break;
    case C_BIT: {
        /* btst: bit number modulo 8 on memory, modulo 32 on a data register */
        uint32_t bit = in->x.kind == E_MEM ? in->y.value & 7 : in->y.value & 31;
        r = (read_expr(vm, &in->x, in->x.size) >> bit) & 1;
        break;
    }
    default: {
        int sz = in->size;
        uint32_t a = read_expr(vm, &in->x, sz), b = read_expr(vm, &in->y, sz);
        int32_t sa = sext(a, sz), sb = sext(b, sz);
        switch (in->cmp) {
        case CMP_EQ: r = a == b; break;
        case CMP_NE: r = a != b; break;
        case CMP_LT: r = sa < sb; break;
        case CMP_LE: r = sa <= sb; break;
        case CMP_GT: r = sa > sb; break;
        case CMP_GE: r = sa >= sb; break;
        case CMP_ULT: r = a < b; break;
        case CMP_ULE: r = a <= b; break;
        case CMP_UGT: r = a > b; break;
        default: r = a >= b; break;
        }
        return r;
    }
    }
    return in->negate ? !r : r;
}

static volatile int pending_jump = -1;

void vm_request_jump(uint32_t addr)
{
    pending_jump = script_routine_pc(addr);
}

void vm_request_jump_pc(int pc)
{
    pending_jump = pc;
}

/* The 68020 runs roughly this many of the game's instructions per 50 Hz frame. Code that
 * busy-waits on the mouse buttons without waiting for the raster gets its frames this way,
 * so time passes (and input changes) exactly as it would on the machine. */
#define INSNS_PER_FRAME 50000
#define PAL_LINES 312

static VM *volatile g_vm_diag;

const char *vm_where_now(void)
{
    VM *vm = g_vm_diag;
    return vm ? script_where(vm->pc) : "?";
}

void vm_run(VM *vm, int pc)
{
    g_vm_diag = vm;
    g_dbg = SDL_getenv("ALF_DBG") != NULL;
    int base = vm->sp;
    int budget = INSNS_PER_FRAME;
    vm->pc = pc;
    for (;;) {
        const Ins *in = &prog[vm->pc];
        if (--budget <= 0) {
            amiga_vbl();
            budget = INSNS_PER_FRAME;
        }
        switch (in->op) {
        case OP_SET: {
            uint32_t v = read_expr(vm, &in->y, in->x.kind == E_AREG ? 4 : in->size);
            write_expr(vm, &in->x, v);
            vm->pc++;
            break;
        }
        case OP_ADD: case OP_SUB: case OP_AND: case OP_OR: case OP_EOR: {
            int sz = in->x.kind == E_AREG ? 4 : in->size;
            Expr x = in->x;
            uint32_t addr = 0;
            uint32_t cur;
            if (x.kind == E_MEM) { addr = ea_addr(vm, &x); cur = mem_read(addr, x.size); x.mode = M_ABS; x.value = addr; }
            else cur = read_expr(vm, &x, sz);
            uint32_t v = read_expr(vm, &in->y, sz);
            uint32_t res = in->op == OP_ADD ? cur + v : in->op == OP_SUB ? cur - v : in->op == OP_AND ? cur & v :
                           in->op == OP_OR ? cur | v : cur ^ v;
            if (x.kind == E_AREG) vm->a[x.reg] = (in->y.kind == E_IMM && in->y.size == 4) ? res : res;
            else write_expr(vm, &x, res);
            vm->pc++;
            break;
        }
        case OP_JMP: vm->pc = in->target; break;
        case OP_JFALSE: vm->pc = eval_cond(vm, in) ? vm->pc + 1 : in->target; break;
        case OP_CALL:
            if (vm->sp >= 255) { fprintf(stderr, "script stack overflow at %s\n", script_where(vm->pc)); return; }
            vm->stack[vm->sp++] = vm->pc + 1;
            vm->pc = in->target;
            if (g_dbg) fprintf(stderr, "f%u call %s -> %s sp=%d d7=%08X\n", amiga_frame_count(), in->label_ref ? in->label_ref : "?", script_where(vm->pc), vm->sp, vm->d[7]);
            break;
        case OP_CALLN:
            if (in->target < 0) {
                fprintf(stderr, "unimplemented routine %s at %s\n", in->label_ref, script_where(vm->pc));
            } else {
                int here = vm->pc;
                uint32_t frame = amiga_frame_count();
                vm->jumped = false;
                g_natives[in->target].fn(vm);
                if (amiga_frame_count() != frame)  /* the native waited: the beam is in a new frame */
                    budget = INSNS_PER_FRAME;
                if (vm->jumped) {          /* e.g. the intro handing over to the game */
                    vm->jumped = false;
                    vm->sp = 0;
                    break;
                }
                vm->pc = here;
            }
            vm->pc++;
            break;
        case OP_RET:
            if (vm->sp <= base) return;
            vm->pc = vm->stack[--vm->sp];
            break;
        case OP_VBL: {
            /* The beam moves with the code: INSNS_PER_FRAME instructions = 312 PAL lines.
             * Wait for the next line whose low byte is the value; only if it has already
             * passed in this frame does the wait run into the next frame (vertical blank). */
            int used = INSNS_PER_FRAME - budget;
            int line = used * PAL_LINES / INSNS_PER_FRAME;
            int v = (int)in->y.value, target = -1;
            for (int cand = v; cand < PAL_LINES; cand += 256)
                if (cand >= line) { target = cand; break; }
            if (target < 0) {
                amiga_vbl();
                target = v;
            }
            if (target != line)                /* already on that line: no time passes */
                budget = INSNS_PER_FRAME - target * INSNS_PER_FRAME / PAL_LINES - 1;
            vm->pc++;
            if (pending_jump >= 0) {           /* e.g. "Wczytaj" from the side panel */
                vm->pc = pending_jump;
                vm->sp = 0;
                pending_jump = -1;
            }
            break;
        }
        case OP_PUSH:                          /* movem.l regs,-(a7): highest register first */
            for (int r = 15; r >= 0; r--)
                if ((in->x.value & (1u << r)) && vm->sp < 255)
                    vm->stack[vm->sp++] = (int)(r < 8 ? vm->d[r] : vm->a[r - 8]);
            vm->pc++;
            break;
        case OP_POP:                           /* movem.l (a7)+,regs (also pops return addresses) */
            for (int r = 0; r < 16; r++)
                if (in->x.value & (1u << r)) {
                    uint32_t v = vm->sp > 0 ? (uint32_t)vm->stack[--vm->sp] : 0;
                    if (r < 8) vm->d[r] = v; else vm->a[r - 8] = v;
                }
            vm->pc++;
            break;
        case OP_SHL: case OP_SHR: case OP_ASR: {
            int sz = in->size;
            uint32_t n = read_expr(vm, &in->y, 4) & 63, v = read_expr(vm, &in->x, sz), m = mask(sz), res;
            if (in->op == OP_SHL) res = n >= 32 ? 0 : v << n;
            else if (in->op == OP_SHR) res = n >= 32 ? 0 : (v & m) >> n;
            else res = (uint32_t)(sext(v, sz) >> (n > 31 ? 31 : n));
            write_expr(vm, &in->x, res & m);
            vm->pc++;
            break;
        }
        case OP_SWAP: {
            uint32_t v = read_expr(vm, &in->x, 4);
            write_expr(vm, &in->x, v << 16 | v >> 16);
            vm->pc++;
            break;
        }
        case OP_EXT: {                         /* ext.w: byte -> word, ext.l: word -> long */
            uint32_t v = read_expr(vm, &in->x, 4);
            write_expr(vm, &in->x, in->size == 2 ? (uint32_t)(int32_t)(int8_t)v : (uint32_t)(int32_t)(int16_t)v);
            vm->pc++;
            break;
        }
        case OP_NOT: case OP_NEG: {
            uint32_t v = read_expr(vm, &in->x, in->size);
            write_expr(vm, &in->x, in->op == OP_NOT ? ~v : (uint32_t)-(int32_t)v);
            vm->pc++;
            break;
        }
        case OP_MULU: case OP_MULS: {
            uint32_t a = read_expr(vm, &in->x, 4), b = read_expr(vm, &in->y, 2);
            uint32_t r = in->op == OP_MULU ? (a & 0xFFFF) * (b & 0xFFFF) : (uint32_t)((int16_t)a * (int16_t)b);
            write_expr(vm, &in->x, r);
            vm->pc++;
            break;
        }
        case OP_DIVU: case OP_DIVS: {
            uint32_t a = read_expr(vm, &in->x, 4), b = read_expr(vm, &in->y, 2) & 0xFFFF;
            if (b) {
                if (in->op == OP_DIVU) {
                    uint32_t q = a / b, r = a % b;
                    if (q <= 0xFFFF) write_expr(vm, &in->x, r << 16 | q);
                } else {
                    int32_t q = (int32_t)a / (int16_t)b, r = (int32_t)a % (int16_t)b;
                    if (q >= -32768 && q <= 32767) write_expr(vm, &in->x, (uint32_t)(r & 0xFFFF) << 16 | (uint32_t)(q & 0xFFFF));
                }
            }
            vm->pc++;
            break;
        }
        }
    }
}

void vm_call_addr(VM *vm, uint32_t addr)
{
    for (int k = 0; k < g_nnatives; k++)
        if (g_natives[k].addr == addr) { g_natives[k].fn(vm); return; }
    int pc = script_routine_pc(addr);
    if (pc < 0) { fprintf(stderr, "vm_call_addr: no routine at $%05X\n", addr); return; }
    int saved = vm->pc;
    vm_run(vm, pc);
    vm->pc = saved;
}
