/*
 * .alf scripts: the game logic lifted from the original asm (see scripts/README.md).
 *
 * All script files are compiled into one flat program. Labels are global and named after
 * the original addresses (L035DC), so `goto` and `jump` work across files exactly like the
 * asm's branches did. Execution runs on the game thread; `wait_vbl` hands the frame over.
 */
#ifndef SCRIPT_H
#define SCRIPT_H

#include <stdbool.h>
#include <stdint.h>

typedef struct VM {
    uint32_t d[8], a[8];
    int pc;
    int stack[256];
    int sp;
    bool jumped;            /* set by a native that moved pc somewhere else (stack cleared) */
} VM;

typedef void (*NativeFn)(VM *vm);

typedef struct {
    const char *name;
    uint32_t addr;          /* original routine address */
    NativeFn fn;
} Native;

bool script_load_dir(const char *dir, const Native *natives, int n_natives);
int  script_routine_pc(uint32_t addr);         /* -1 if the address is not a lifted routine */
int  script_routine_pc_by_name(const char *name);
int  script_label_pc(const char *name);        /* a `::label::` inside a routine, -1 if none */
const char *script_routine_name(uint32_t addr);
void vm_run(VM *vm, int pc);                   /* runs until the routine at pc returns */
void vm_call_addr(VM *vm, uint32_t addr);      /* call a routine (lifted or native) by address */
const char *script_where(int pc);              /* "file.alf:123" for diagnostics */
const char *vm_where_now(void);                /* diagnostics: where the game thread is */
void vm_request_jump(uint32_t addr);
void vm_request_jump_pc(int pc);           /* at the next wait_vbl: clear the stack, continue there */

#endif
