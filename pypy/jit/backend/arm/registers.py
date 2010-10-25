r0, r1, r2, r3, r4, r5, r6, r7, r8, r9, r10, r11, r12, r13, r14, r15 = range(16)
# aliases for registers
fp = 11
ip = 12
sp = 13
lr = 14
pc = 15

all_regs = range(12)
callee_resp = [r4, r5, r6, r7, r8, r9, r10, r11]
callee_saved_registers = callee_resp+[lr]
callee_restored_registers = callee_resp+[pc]