#!/usr/bin/env python3
"""gen_lsdl_adder.py — structural LSDL pipelined ripple-carry adder generator.

Why a generator instead of Yosys: every LSDL cell is a positive-edge flop
(precharge on CLK=0, evaluate on CLK=1), so combinational technology mapping
(Yosys/ABC) cannot target this library. The adder is built structurally as a
deeply pipelined design with alternating C1/C2 stages (Belluomini Fig. 2a
L1/L2 scheme).

Architecture — dual-rail pipelined ripple-carry, 2 stages per bit:

  * Every cell inverts, so a single-rail signal flips polarity each stage.
    Operands enter dual-rail (a, an) and each rail pair is staged through a
    pair of lsdl_inv_x1 chains; the true/false roles swap every stage.
  * XOR in one cell:   x  = aoi22(a, b, an, bn)  = !(ab + na*nb) = a^b
    XNOR:              nx = aoi22(a, bn, an, b)  = !(a*nb + na*b)
  * Carry rails (majority is self-dual, maj(a,b,c) = !maj(na,nb,nc), and
    na^nb = a^b = x):
    nc[i+1] = aoi22(a, b, c, x)    = !(ab + cx)
    c[i+1]  = aoi22(an, bn, nc, x) = !(na*nb + nc*x) = maj(a,b,c)
  * Sum:  s = aoi22(x, c, nx, nc) = !(xc + nx*nc) = x^c

  Stage schedule for bit i (stage 0 = primary inputs / block ports):
    stage 2i+1 : x_i, nx_i, carry-rail staging inverters
    stage 2i+2 : c_{i+1} rails, sum_i
  Carry rails c_i are outputs of stage 2i. Operand rails for bit i are
  tapped from the staging chains at stages 2i and 2i+1, so each chain has
  2i+1 cells per rail.

  Clocking: odd stages -> C1, even stages -> C2 (rising edges 180 deg
  apart). Each stage-to-stage transfer gets one half period.

  Latency: sum[i] is launched by stage 2i+2 (a C2 stage); cout by stage 2W.
  Outputs are deliberately time-skewed (no on-die realignment); per-bit
  latency is documented in the generated header.

Cell count: 4*W^2 + 7*W  (W=4: 92, W=16: 1136).

Usage:
    gen_lsdl_adder.py --width 4  --out adder4_lsdl.v
    gen_lsdl_adder.py --width 16 --out adder16_lsdl.v
    gen_lsdl_adder.py --width 16 --selftest   # functional check, no file
"""

from __future__ import annotations
import argparse
import random
import sys


def clk_of(stage: int) -> str:
    return 'c1' if stage % 2 == 1 else 'c2'


class Netlist:
    def __init__(self, width: int):
        self.w = width
        self.wires: list[str] = []
        self.cells: list[tuple] = []  # (name, type, {pin: net}, stage)

    def wire(self, name: str) -> str:
        self.wires.append(name)
        return name

    def inv(self, name: str, a: str, out: str, stage: int) -> str:
        self.cells.append((name, 'lsdl_inv_x1', {'A': a, 'OUT': out}, stage))
        return out

    def aoi22(self, name: str, a1: str, a2: str, b1: str, b2: str,
              out: str, stage: int) -> str:
        self.cells.append((name, 'lsdl_aoi22_x1',
                           {'A1': a1, 'A2': a2, 'B1': b1, 'B2': b2,
                            'OUT': out}, stage))
        return out


def build(width: int) -> Netlist:
    nl = Netlist(width)
    w = width

    # Operand staging chains. p-chain roots at the true port, q-chain at the
    # complement port. After k inversions the p-chain carries the true value
    # iff k is even.
    chain: dict[tuple, str] = {}  # (op, bit, 'p'|'q', stage) -> net
    for op in ('a', 'b'):
        for i in range(w):
            depth = 2 * i + 1  # taps needed at stages 2i and 2i+1
            for rail, root in (('p', f'{op}[{i}]'), ('q', f'{op}n[{i}]')):
                prev = root
                chain[(op, i, rail, 0)] = root
                for k in range(1, depth + 1):
                    net = nl.wire(f'{rail}_{op}{i}_s{k}')
                    nl.inv(f'U_{rail}{op}{i}_s{k}', prev, net, k)
                    chain[(op, i, rail, k)] = net
                    prev = net

    def rails(op: str, i: int, stage: int) -> tuple[str, str]:
        """(true, false) rails of operand bit as outputs of `stage`."""
        p, q = chain[(op, i, 'p', stage)], chain[(op, i, 'q', stage)]
        return (p, q) if stage % 2 == 0 else (q, p)

    # Carry rails: (true, false) as outputs of stage 2i.
    carry: dict[int, tuple[str, str]] = {0: ('cin', 'cinn')}

    for i in range(w):
        s_x = 2 * i + 1   # xor / staging stage
        s_o = 2 * i + 2   # carry-out / sum stage
        aT, aF = rails('a', i, s_x - 1)
        bT, bF = rails('b', i, s_x - 1)
        cT, cF = carry[i]

        # Stage 2i+1: xor pair + carry-rail staging (inverters swap rails).
        x = nl.aoi22(f'U_x{i}', aT, bT, aF, bF, nl.wire(f'x{i}'), s_x)
        nx = nl.aoi22(f'U_nx{i}', aT, bF, aF, bT, nl.wire(f'nx{i}'), s_x)
        cTs = nl.inv(f'U_cst{i}', cF, nl.wire(f'c{i}_ts'), s_x)
        cFs = nl.inv(f'U_csf{i}', cT, nl.wire(f'c{i}_fs'), s_x)

        # Stage 2i+2: carry-out rails + sum.
        aT2, aF2 = rails('a', i, s_x)
        bT2, bF2 = rails('b', i, s_x)
        last = (i == w - 1)
        coF = 'coutn' if last else nl.wire(f'c{i + 1}_f')
        coT = 'cout' if last else nl.wire(f'c{i + 1}_t')
        nl.aoi22(f'U_coF{i}', aT2, bT2, cTs, x, coF, s_o)
        nl.aoi22(f'U_coT{i}', aF2, bF2, cFs, x, coT, s_o)
        carry[i + 1] = (coT, coF)

        nl.aoi22(f'U_s{i}', x, cTs, nx, cFs, f'sum[{i}]', s_o)

    return nl


def build_clock_tree(sink_cells: list[str], port: str, fanout: int,
                     pfx: str):
    """Balanced bottom-up fan-out tree of lsdl_clkbuf_x1 from `port` to the
    `sink_cells`' CLK pins. Returns (bufs, clk_net, nets):
      bufs    : list of [instname, a_net, z_net]  (a_net of the root = `port`)
      clk_net : {cell_name -> leaf buffer z_net it should clock on}
      nets    : list of new wire names to declare
    The LSDL adder routes c1/c2 flat to ~8500 cell CLK pins each (~30 pF, one
    driver) — unviable slew/skew for dynamic logic. CTS can't be used (the LSDL
    cells aren't CTS-synthesizable and OpenROAD won't accept a custom CTS
    buffer), so the tree is instantiated structurally here; the buffers are
    ordinary netlist cells the placer/router handle normally. Equal-depth tree
    keeps c1/c2 insertion delay matched (parity with the CMOS adder's CTS tree)."""
    bufs: list = []
    nets: list[str] = []
    clk_net: dict[str, str] = {}
    if not sink_cells:
        return bufs, clk_net, nets
    ctr = 0
    # items to be driven this level: ('cell', name) or ('buf', index in bufs)
    items = [('cell', c) for c in sink_cells]
    while len(items) > fanout:
        nxt = []
        for i in range(0, len(items), fanout):
            chunk = items[i:i + fanout]
            z = f'{pfx}_n{ctr}'
            nets.append(z)
            bufs.append([f'{pfx}_clkbuf{ctr}', None, z])  # a_net set by parent
            bi = len(bufs) - 1
            ctr += 1
            for kind, ref in chunk:
                if kind == 'cell':
                    clk_net[ref] = z
                else:
                    bufs[ref][1] = z          # child buffer's input
            nxt.append(('buf', bi))
        items = nxt
    # root buffer: driven by the clock port, drives the remaining (<=fanout) items
    z = f'{pfx}_n{ctr}'
    nets.append(z)
    bufs.append([f'{pfx}_clkbuf{ctr}', port, z])
    for kind, ref in items:
        if kind == 'cell':
            clk_net[ref] = z
        else:
            bufs[ref][1] = z
    return bufs, clk_net, nets


def emit_verilog(nl: Netlist, clk_fanout: int = 32) -> str:
    w = nl.w
    lat = ', '.join(f'sum[{i}]@{2 * i + 2}' for i in range(w))
    lines = [
        f'// lsdl_adder{w} — {w}-bit dual-rail pipelined ripple-carry adder',
        f'// in LSDL cells. Generated by gen_lsdl_adder.py — do not edit.',
        f'//',
        f'// Clocking: odd stages on c1, even stages on c2 (180 deg apart);',
        f'// one half period per stage transfer.',
        f'// Cells: {len(nl.cells)} '
        f'({sum(1 for c in nl.cells if c[1] == "lsdl_inv_x1")} inv, '
        f'{sum(1 for c in nl.cells if c[1] == "lsdl_aoi22_x1")} aoi22)',
        f'// Output latency (half-cycles): {lat}, cout@{2 * w}',
        f'`timescale 1ns/1ps',
        f'module lsdl_adder{w} (',
        f'    input  c1,',
        f'    input  c2,',
        f'    input  [{w - 1}:0] a,',
        f'    input  [{w - 1}:0] an,',
        f'    input  [{w - 1}:0] b,',
        f'    input  [{w - 1}:0] bn,',
        f'    input  cin,',
        f'    input  cinn,',
        f'    output [{w - 1}:0] sum,',
        f'    output cout,',
        f'    output coutn',
        f');',
        '',
    ]
    # ── clock buffer trees (c1, c2) ─────────────────────────────────────
    c1_cells = [c[0] for c in nl.cells if clk_of(c[3]) == 'c1']
    c2_cells = [c[0] for c in nl.cells if clk_of(c[3]) == 'c2']
    b1, clk1, nets1 = build_clock_tree(c1_cells, 'c1', clk_fanout, 'c1t')
    b2, clk2, nets2 = build_clock_tree(c2_cells, 'c2', clk_fanout, 'c2t')
    clk_net = {**clk1, **clk2}
    all_bufs = b1 + b2

    for wn in nl.wires + nets1 + nets2:
        lines.append(f'    wire {wn};')
    lines.append('')
    lines.append(f'    // clock buffer trees: c1 {len(b1)} bufs / {len(c1_cells)} sinks, '
                 f'c2 {len(b2)} bufs / {len(c2_cells)} sinks, fanout<={clk_fanout}')
    for bname, a_net, z_net in all_bufs:
        lines.append(f'    lsdl_clkbuf_x1 {bname} (.A({a_net}), .Z({z_net}));')
    lines.append('')
    for name, ctype, pins, stage in nl.cells:
        conns = [f'.CLK({clk_net[name]})']
        conns += [f'.{p}({n})' for p, n in pins.items()]
        lines.append(f'    {ctype} {name} ({", ".join(conns)});  '
                     f'// stage {stage}')
    lines += ['', 'endmodule', '']
    return '\n'.join(lines)


def selftest(nl: Netlist, vectors: int = 200) -> bool:
    """Cycle-accurate functional check: every cell is a flop computing the
    inverting function of the previous stage's values. All cells update
    simultaneously per half-cycle tick; with inputs held constant the
    pipeline settles to the steady-state result."""
    w = nl.w
    rng = random.Random(42)
    ticks = 2 * w + 4
    ok = True
    for _ in range(vectors):
        a = rng.getrandbits(w)
        b = rng.getrandbits(w)
        ci = rng.getrandbits(1)
        val: dict[str, int] = {}
        for i in range(w):
            val[f'a[{i}]'] = (a >> i) & 1
            val[f'an[{i}]'] = 1 - ((a >> i) & 1)
            val[f'b[{i}]'] = (b >> i) & 1
            val[f'bn[{i}]'] = 1 - ((b >> i) & 1)
        val['cin'], val['cinn'] = ci, 1 - ci
        for _, _, pins, _ in nl.cells:
            val.setdefault(pins['OUT'], 0)
        for _ in range(ticks):
            nxt = dict(val)
            for _, ctype, pins, _ in nl.cells:
                if ctype == 'lsdl_inv_x1':
                    o = 1 - val[pins['A']]
                else:
                    o = 1 - ((val[pins['A1']] & val[pins['A2']]) |
                             (val[pins['B1']] & val[pins['B2']]))
                nxt[pins['OUT']] = o
            val = nxt
        got_sum = sum(val[f'sum[{i}]'] << i for i in range(w))
        exp = a + b + ci
        exp_sum, exp_co = exp & ((1 << w) - 1), exp >> w
        if got_sum != exp_sum or val['cout'] != exp_co or \
                val['coutn'] != 1 - exp_co:
            print(f'FAIL a={a:#x} b={b:#x} cin={ci}: '
                  f'got sum={got_sum:#x} cout={val["cout"]}, '
                  f'expected sum={exp_sum:#x} cout={exp_co}')
            ok = False
    return ok


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--width', type=int, default=16)
    ap.add_argument('--out', help='output Verilog file')
    ap.add_argument('--selftest', action='store_true')
    ap.add_argument('--clk-fanout', type=int, default=32,
                    help='max sinks per clock buffer in the c1/c2 trees')
    args = ap.parse_args()

    nl = build(args.width)
    n_inv = sum(1 for c in nl.cells if c[1] == 'lsdl_inv_x1')
    n_aoi = len(nl.cells) - n_inv
    print(f'lsdl_adder{args.width}: {len(nl.cells)} cells '
          f'({n_inv} inv, {n_aoi} aoi22), '
          f'{2 * args.width} stages, '
          f'sum[{args.width - 1}] latency {2 * args.width} half-cycles')

    if args.selftest:
        if selftest(nl):
            print(f'SELFTEST PASS (200 random vectors, width {args.width})')
        else:
            print('SELFTEST FAIL')
            return 1

    if args.out:
        with open(args.out, 'w') as f:
            f.write(emit_verilog(nl, args.clk_fanout))
        print(f'wrote {args.out}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
