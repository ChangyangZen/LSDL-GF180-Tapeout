#!/usr/bin/env python3
"""LSDL priority encoder generator — composed from signed-off Wave-1 cells.

Highest-index-priority encoder. Outputs: vld (any request) + pos[ceil(log2 W)-1:0]
(binary index of the highest set input bit).

All wide ORs are composed from the signed-off NOR4 + NAND4 (and NOR2/3, NAND2/3
for remainders) — NMOS-only evaluate in every stage (the LSDL showcase), with
ZERO use of the quarantined wide NOR8/NOR16 (see EXPERIMENTAL_lsdl_nor8_x1.md).

Logic:
    hi[i]      = OR(in[i+1 .. W-1])        # a higher-priority bit is set
    one_hot[i] = in[i] & ~hi[i]            # i is the leading one
    pos[k]     = OR( one_hot[i] : bit k of i == 1 )
    vld        = OR(in[0 .. W-1])

Pipeline: each LSDL cell is a clocked flop; consecutive logical stages alternate
C1/C2 (paper L1/L2, same scheme as the adder). Multi-input cells get their inputs
balanced to a common stage with INV-pair delays (polarity-preserving).

    gen_lsdl_priencoder.py --width 32 --selftest        # functional check
    gen_lsdl_priencoder.py --width 32 --out enc.v        # emit Verilog
"""
import argparse, random

def clk_of(stage):  # stage 1,3,5..->c1 ; 0,2,4..->c2  (matches gen_lsdl_adder)
    return 'c1' if stage % 2 == 1 else 'c2'

class Netlist:
    """Records emitted LSDL cells and an executable model of each, for both
    structural Verilog emission and a combinational selftest."""
    def __init__(self):
        self.cells = []            # (name, ctype, pins{pin:net}, stage)
        self.func = {}             # net -> (op, [in_nets])  for selftest eval
        self.stage = {}            # net -> ready stage (0 = primary input)
        self._n = 0

    def _new(self, tag):
        self._n += 1
        return f"n{self._n}_{tag}"

    def primary(self, net):
        self.stage[net] = 0
        self.func[net] = ('IN', [])
        return net

    def _cell(self, ctype, ins, op, tag):
        st = max((self.stage[a] for a in ins), default=0) + 1
        out = self._new(tag)
        # pin map: A/A1.. for inputs, OUT for output, CLK by stage
        if len(ins) == 1:
            pins = {'A': ins[0]}
        else:
            pins = {f'A{i+1}': a for i, a in enumerate(ins)}
        pins['OUT'] = out
        self.cells.append((out, ctype, pins, st))
        self.func[out] = (op, list(ins))
        self.stage[out] = st
        return out

    # --- primitive inverting cells ---
    def inv(self, a):                 return self._cell('lsdl_inv_x1',  [a], 'INV', 'inv')
    def nor(self, ins):               # 2..4-input NOR
        t = {2:'lsdl_nor2_x1',3:'lsdl_nor3_x1',4:'lsdl_nor4_x1'}[len(ins)]
        return self._cell(t, ins, 'NOR', 'nor')
    def nand(self, ins):              # 2..4-input NAND
        t = {2:'lsdl_nand2_x1',3:'lsdl_nand3_x1',4:'lsdl_nand4_x1'}[len(ins)]
        return self._cell(t, ins, 'NAND', 'nand')

    # --- balancing: delay a net to >= target stage, preserving polarity (INV pairs) ---
    def delay_to(self, net, target):
        while self.stage[net] + 2 <= target:
            net = self.inv(self.inv(net))
        return net

    def align(self, nets):
        target = max(self.stage[n] for n in nets)
        return [self.delay_to(n, target) for n in nets], target

    # --- composite OR (true-OR), built from NOR groups + NAND combine ---
    def OR(self, ins):
        ins = list(ins)
        if len(ins) == 1:
            return ins[0]
        # split into groups of <=4; NOR each group (= ~OR of group)
        groups = [ins[i:i+4] for i in range(0, len(ins), 4)]
        gnor = []
        for g in groups:
            if len(g) == 1:
                gnor.append(self.inv(g[0]))           # ~g = NOR of one input
            else:
                ga, _ = self.align(g)
                gnor.append(self.nor(ga))             # ~OR(group)
        if len(gnor) <= 4:
            if len(gnor) == 1:
                return self.inv(gnor[0])              # OR = ~(~OR)
            ga, _ = self.align(gnor)
            return self.nand(ga)                      # NAND(group-nors) = OR(all)  (e.g. OR16=NAND4(NOR4x4))
        # >4 groups: OR the group-ORs recursively
        gor = [self.inv(gn) for gn in gnor]           # OR of each group
        return self.OR(gor)

    def AND2(self, a, b):                              # a & b = ~NAND2
        (a, b), _ = self.align([a, b])
        return self.inv(self.nand([a, b]))

# ---------- reference model ----------
def ref_encode(vec, W, K):
    pos = 0; vld = 0
    for i in range(W - 1, -1, -1):
        if vec & (1 << i):
            pos = i; vld = 1; break
    return vld, (pos & ((1 << K) - 1))

# ---------- build ----------
def build(W):
    import math
    K = max(1, (W - 1).bit_length())     # output width
    nl = Netlist()
    inb = [nl.primary(f"in{i}") for i in range(W)]

    hi = [None] * W                       # hi[i] = OR(in[i+1..W-1])
    for i in range(W):
        higher = inb[i + 1:]
        hi[i] = nl.OR(higher) if higher else None     # hi[W-1] = const 0

    one_hot = [None] * W
    for i in range(W):
        if hi[i] is None:
            one_hot[i] = inb[i]                        # no higher bit -> winner iff in[i]
        else:
            nhi = nl.inv(hi[i])                        # ~hi
            one_hot[i] = nl.AND2(inb[i], nhi)

    pos = []
    for k in range(K):
        members = [one_hot[i] for i in range(W) if (i >> k) & 1]
        pos.append(nl.OR(members) if members else None)

    vld = nl.OR(inb)
    return nl, inb, one_hot, pos, vld, K

# ---------- selftest (combinational eval of the emitted netlist) ----------
def eval_net(nl, net, vals, in_map):
    if net in in_map:
        return in_map[net]
    if net in vals:
        return vals[net]
    op, ins = nl.func[net]
    iv = [eval_net(nl, a, vals, in_map) for a in ins]
    if op == 'INV':  r = 1 - iv[0]
    elif op == 'NOR':  r = 0 if any(iv) else 1
    elif op == 'NAND': r = 0 if all(iv) else 1
    else: raise ValueError(op)
    vals[net] = r
    return r

def selftest(W, vectors=400):
    nl, inb, one_hot, pos, vld, K = build(W)
    rng = random.Random(42)
    tests = list(range(0, min(W, 32)))            # one-hots
    tests = [1 << i for i in range(W)] + [0, (1 << W) - 1]
    tests += [rng.randrange(0, 1 << W) for _ in range(vectors)]
    fails = 0
    for vec in tests:
        in_map = {inb[i]: (vec >> i) & 1 for i in range(W)}
        vals = {}
        got_vld = eval_net(nl, vld, vals, in_map)
        got_pos = 0
        for k in range(K):
            if pos[k] is not None:
                got_pos |= eval_net(nl, pos[k], vals, in_map) << k
        exp_vld, exp_pos = ref_encode(vec, W, K)
        if got_vld != exp_vld or (exp_vld and got_pos != exp_pos):
            fails += 1
            if fails <= 5:
                print(f"  FAIL vec={vec:#0{W//4+2}x} got(vld={got_vld},pos={got_pos}) exp(vld={exp_vld},pos={exp_pos})")
    ncell = len(nl.cells)
    from collections import Counter
    by = Counter(c[1] for c in nl.cells)
    print(f"  W={W} K={K}: {len(tests)} vectors, {fails} fail   |  cells={ncell} {dict(by)}")
    return fails == 0

def emit_verilog(W):
    """Structural Verilog. Flat C1/C2 clock (each cell on c1/c2 per its stage);
    CTS/buffering is a hardening/timing follow-up — not needed for DRC/LVS/area."""
    nl, inb, one_hot, pos, vld, K = build(W)
    # net -> port renames
    rename = {inb[i]: f"req[{i}]" for i in range(W)}
    rename[vld] = "vld"
    for k in range(K):
        if pos[k] is not None:
            rename[pos[k]] = f"pos[{k}]"
    def m(net): return rename.get(net, net)
    port_nets = set(rename.values())
    # internal wires = every cell-output net not mapped to a port
    wires = [c[0] for c in nl.cells if m(c[0]) not in port_nets]

    L = [f"// lsdl_priencoder{W} (rev: simple) — {W}-bit priority encoder, highest-index.",
         f"// {len(nl.cells)} LSDL cells, composed from signed-off NOR4/NAND4/etc. (no NOR8).",
         f"// Flat c1/c2 clock (alternating per stage). Generated — do not edit.",
         f"`timescale 1ns/1ps",
         f"module lsdl_priencoder{W} (",
         f"    input  c1, c2,",
         f"    input  [{W-1}:0] req,",
         f"    output vld,",
         f"    output [{K-1}:0] pos,",
         f"    inout  VPWR, VGND",
         f");", ""]
    for wn in wires:
        L.append(f"    wire {wn};")
    L.append("")
    for name, ctype, pins, stage in nl.cells:
        conns = [f".CLK({clk_of(stage)})"]
        conns += [f".{p}({m(n)})" for p, n in pins.items()]
        conns += [".VPWR(VPWR)", ".VGND(VGND)"]
        L.append(f"    {ctype} U_{name} ({', '.join(conns)});")  # U_ prefix: instance != net name
    L += ["", "endmodule", ""]
    return "\n".join(L)

def emit_spice(W):
    """Golden SPICE for LVS: encoder .subckt with POSITIONAL cell instances.
    Cell subckt pin order (matches the hand-source .spice): <inputs..> Clk Out VPWR VGND.
    Port names use bus brackets req[i]/pos[k] to match Magic's extracted port names."""
    nl, inb, one_hot, pos, vld, K = build(W)
    rn = {inb[i]: f"req[{i}]" for i in range(W)}
    rn[vld] = "vld"
    for k in range(K):
        if pos[k] is not None: rn[pos[k]] = f"pos[{k}]"
    def m(net): return rn.get(net, net)
    ports = ["c1", "c2"] + [f"req[{i}]" for i in range(W)] + ["vld"] \
            + [f"pos[{k}]" for k in range(K)] + ["VPWR", "VGND"]
    L = [f".subckt lsdl_priencoder{W} {' '.join(ports)}"]
    for j, (name, ctype, pins, stage) in enumerate(nl.cells):
        ins = [pins[k] for k in sorted(pins) if k != "OUT"]   # A or A1,A2,..
        nets = [m(x) for x in ins] + [clk_of(stage), m(pins["OUT"]), "VPWR", "VGND"]
        L.append(f"X{j} {' '.join(nets)} {ctype}")
    L.append(f".ends lsdl_priencoder{W}")
    return "\n".join(L) + "\n"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--width', type=int, default=32)
    ap.add_argument('--selftest', action='store_true')
    ap.add_argument('--out')
    ap.add_argument('--spice')
    a = ap.parse_args()
    if a.selftest:
        ok = selftest(a.width)
        print("  SELFTEST", "PASS" if ok else "FAIL")
        return 0 if ok else 1
    if a.spice:
        s = emit_spice(a.width)
        with open(a.spice, 'w') as f: f.write(s)
        print(f"wrote {a.spice} ({len(s.splitlines())} lines)")
        return 0
    v = emit_verilog(a.width)
    if a.out:
        with open(a.out, 'w') as f:
            f.write(v)
        print(f"wrote {a.out} ({len(v.splitlines())} lines)")
    else:
        print(v)
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
