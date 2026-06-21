#!/usr/bin/env python3
"""draw_adder_slice.py — schematic PDF of the LSDL adder bit-slice.

Page 1: bit-slice i schematic (7 logic cells + rail staging, 2 stages)
Page 2: signal glossary + the full-adder identities used
Page 3: how slices chain into the W-bit adder + C1/C2 timing

Run inside the IIC-OSIC-TOOLS container (has matplotlib):
    run_in_container.sh "python3 .../draw_adder_slice.py"
Outputs adder_slice_schematic.pdf (+ per-page PNGs) next to this script.
"""

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.patches import Rectangle, FancyArrow
from pathlib import Path

OUT_DIR = Path(__file__).resolve().parent

# net colors
C_A = 'tab:blue'      # operand a rails
C_B = 'tab:green'     # operand b rails
C_C = 'tab:red'       # carry rails
C_X = 'tab:purple'    # x / nx (propagate)
C_S = 'black'         # sum
TRUE_LS, COMP_LS = '-', (0, (4, 2))   # solid = true rail, dashed = complement


def draw_cell(ax, x, y, w, h, title, pins, out_net, clk, formula=None,
              title_fs=10, pin_fs=8):
    """Box with left input pins, one right output, CLK wedge at bottom.
    pins: list of (pin_name, net_label, color, linestyle). Returns pin/out xy."""
    ax.add_patch(Rectangle((x, y), w, h, fill=True, facecolor='#f4f4f4',
                           edgecolor='black', lw=1.2, zorder=2))
    ax.text(x + w / 2, y + h - 0.16, title, ha='center', va='top',
            fontsize=title_fs, fontweight='bold', zorder=3)
    # clock wedge (flop-style) bottom-left + label
    ax.plot([x + 0.12, x + 0.30, x + 0.12], [y, y + 0.13, y + 0.26],
            color='black', lw=1.0, zorder=3)
    ax.text(x + 0.38, y + 0.13, clk, fontsize=7.5, va='center',
            color='dimgray', zorder=3)
    coords = {}
    n = len(pins)
    for k, (pname, net, col, ls) in enumerate(pins):
        py = y + h * (n - k) / (n + 1)
        ax.plot([x - 0.28, x], [py, py], color=col, ls=ls, lw=1.6, zorder=1)
        ax.text(x + 0.07, py, pname, fontsize=pin_fs, va='center', zorder=3)
        ax.text(x - 0.36, py, net, fontsize=pin_fs, va='center', ha='right',
                color=col, style='italic', zorder=3)
        coords[pname] = (x - 0.28, py)
    oy = y + h / 2
    ax.plot([x + w, x + w + 0.28], [oy, oy], color='black', lw=1.6, zorder=1)
    ax.text(x + w - 0.07, oy, 'OUT', fontsize=pin_fs, va='center', ha='right',
            zorder=3)
    coords['OUT'] = (x + w + 0.28, oy)
    if formula:
        ax.text(x + w / 2, y - 0.16, formula, ha='center', va='top',
                fontsize=8.5, style='italic', color='dimgray', zorder=3)
    return coords


def wire(ax, pts, color, ls='-', lw=1.6):
    xs, ys = zip(*pts)
    ax.plot(xs, ys, color=color, ls=ls, lw=lw, zorder=1)


def dot(ax, x, y, color):
    ax.plot([x], [y], marker='o', ms=5, color=color, zorder=2)


# ════════════════════════════════ PAGE 1 ════════════════════════════════
def page1():
    fig, ax = plt.subplots(figsize=(16, 10.5))
    ax.set_xlim(0, 16); ax.set_ylim(0, 10.8); ax.axis('off')

    ax.text(8, 10.55, 'LSDL adder — bit-slice $i$  (dual-rail pipelined '
            'ripple-carry, gen_lsdl_adder.py)',
            ha='center', fontsize=15, fontweight='bold')

    # stage bands
    for xb in (3.6, 9.7):
        ax.axvline(xb, color='gray', ls=':', lw=1)
    ax.text(1.8, 10.05, 'STAGE 2i\n(previous-stage outputs)', ha='center',
            fontsize=10, color='gray')
    ax.text(6.65, 10.05, 'STAGE 2i+1 — all cells on C1\n(evaluate at C1$\\uparrow$)',
            ha='center', fontsize=10, color='gray')
    ax.text(12.8, 10.05, 'STAGE 2i+2 — all cells on C2\n(evaluate at C2$\\uparrow$)',
            ha='center', fontsize=10, color='gray')
    ax.annotate('', xy=(9.7, 9.55), xytext=(3.6, 9.55),
                arrowprops=dict(arrowstyle='->', color='gray'))
    ax.text(6.65, 9.62, 'one half period = 500 ps @ 1 GHz', ha='center',
            fontsize=8.5, color='gray')

    # ── stage 2i+1 cells ────────────────────────────────────────────────
    ux = draw_cell(ax, 4.3, 7.7, 2.5, 1.55, 'U_x  (aoi22)',
                   [('A1', 'aT', C_A, TRUE_LS), ('A2', 'bT', C_B, TRUE_LS),
                    ('B1', 'aF', C_A, COMP_LS), ('B2', 'bF', C_B, COMP_LS)],
                   'x', 'C1',
                   'x = !(aT·bT + aF·bF) = a $\\oplus$ b   (propagate)')
    unx = draw_cell(ax, 4.3, 5.55, 2.5, 1.55, 'U_nx  (aoi22)',
                    [('A1', 'aT', C_A, TRUE_LS), ('A2', 'bF', C_B, COMP_LS),
                     ('B1', 'aF', C_A, COMP_LS), ('B2', 'bT', C_B, TRUE_LS)],
                    'nx', 'C1',
                    'nx = !(aT·bF + aF·bT) = !(a $\\oplus$ b)')
    stg = draw_cell(ax, 4.3, 3.5, 2.5, 1.45, '4 × lsdl_inv_x1',
                    [('A', 'aT', C_A, TRUE_LS), ('A', 'aF', C_A, COMP_LS),
                     ('A', 'bT', C_B, TRUE_LS), ('A', 'bF', C_B, COMP_LS)],
                    '', 'C1',
                    "rail staging: out = !in $\\Rightarrow$ T/F roles swap "
                    "(aT$\\rightarrow$aF', aF$\\rightarrow$aT', ...)")
    # staging outputs (4 labeled stubs on the right edge)
    for k, (lbl, col, ls) in enumerate([("aF'", C_A, COMP_LS), ("aT'", C_A, TRUE_LS),
                                        ("bF'", C_B, COMP_LS), ("bT'", C_B, TRUE_LS)]):
        py = 3.5 + 1.45 * (4 - k) / 5
        ax.plot([6.8, 7.08], [py, py], color=col, ls=ls, lw=1.6)
        ax.text(7.16, py, lbl, fontsize=8, va='center', color=col, style='italic')

    ucst = draw_cell(ax, 4.3, 2.35, 2.5, 0.7, 'U_cst (inv)',
                     [('A', 'cF$_i$', C_C, COMP_LS)], 'cTs', 'C1',
                     'cTs = !cF$_i$ = c  (true carry, restaged)')
    ucsf = draw_cell(ax, 4.3, 1.1, 2.5, 0.7, 'U_csf (inv)',
                     [('A', 'cT$_i$', C_C, TRUE_LS)], 'cFs', 'C1',
                     'cFs = !cT$_i$ = !c')

    # carry inputs from the left, crossing (invert the OPPOSITE rail)
    ax.text(0.7, 3.25, 'cT$_i$', fontsize=10, color=C_C, va='center')
    ax.text(0.7, 1.25, 'cF$_i$', fontsize=10, color=C_C, va='center')
    ax.text(0.55, 2.25, 'carry rails\nfrom bit i−1\n(stage-2i outputs;\n'
            'bit 0: cin/cinn ports)', fontsize=7.5, color='dimgray', va='center')
    wire(ax, [(1.25, 3.25), (3.3, 3.25), (3.3, 1.45), (ucsf['A'][0], 1.45)],
         C_C, TRUE_LS)
    wire(ax, [(1.25, 1.25), (2.9, 1.25), (2.9, 2.81), (ucst['A'][0], 2.81)],
         C_C, COMP_LS)

    # operand-rail note
    ax.text(1.8, 8.6, 'operand rails @ stage 2i\n(taps of the 4 inverter\n'
            'chains for a[i], b[i]:\naT aF bT bF)', fontsize=8.5,
            color='dimgray', ha='center')

    # ── stage 2i+2 cells ────────────────────────────────────────────────
    ucoF = draw_cell(ax, 10.6, 7.5, 2.5, 1.55, 'U_coF  (aoi22)',
                     [('A1', "aT'", C_A, TRUE_LS), ('A2', "bT'", C_B, TRUE_LS),
                      ('B1', 'cTs', C_C, TRUE_LS), ('B2', 'x', C_X, TRUE_LS)],
                     'cF$_{i+1}$', 'C2',
                     'cF$_{i+1}$ = !(a·b + c·x)   (complement carry-out)')
    ucoT = draw_cell(ax, 10.6, 5.3, 2.5, 1.55, 'U_coT  (aoi22)',
                     [('A1', "aF'", C_A, COMP_LS), ('A2', "bF'", C_B, COMP_LS),
                      ('B1', 'cFs', C_C, COMP_LS), ('B2', 'x', C_X, TRUE_LS)],
                     'cT$_{i+1}$', 'C2',
                     'cT$_{i+1}$ = !(!a·!b + !c·x) = maj(a,b,c)   (true carry-out)')
    us = draw_cell(ax, 10.6, 2.7, 2.5, 1.55, 'U_s  (aoi22)',
                   [('A1', 'x', C_X, TRUE_LS), ('A2', 'cTs', C_C, TRUE_LS),
                    ('B1', 'nx', C_X, COMP_LS), ('B2', 'cFs', C_C, COMP_LS)],
                   'sum[i]', 'C2',
                   's = !(x·c + !x·!c) = x $\\oplus$ c = a $\\oplus$ b $\\oplus$ c')

    # ── routed nets in the channel ──────────────────────────────────────
    # x: U_x.OUT -> track x=7.6 -> U_coF.B2, U_coT.B2, U_s.A1
    xo = ux['OUT']
    wire(ax, [xo, (7.6, xo[1]), (7.6, us['A1'][1]), (us['A1'][0], us['A1'][1])],
         C_X)
    wire(ax, [(7.6, ucoF['B2'][1]), ucoF['B2']], C_X)
    wire(ax, [(7.6, ucoT['B2'][1]), ucoT['B2']], C_X)
    dot(ax, 7.6, ucoF['B2'][1], C_X); dot(ax, 7.6, ucoT['B2'][1], C_X)
    ax.text(7.6, xo[1] + 0.12, 'x', fontsize=9, color=C_X, ha='center')

    # nx: U_nx.OUT -> track 8.0 -> U_s.B1
    nxo = unx['OUT']
    wire(ax, [nxo, (8.0, nxo[1]), (8.0, us['B1'][1]), us['B1']], C_X, COMP_LS)
    ax.text(8.0, nxo[1] + 0.12, 'nx', fontsize=9, color=C_X, ha='center')

    # cTs: U_cst.OUT -> track 8.5 -> U_coF.B1 and U_s.A2
    cto = ucst['OUT']
    wire(ax, [cto, (8.5, cto[1]), (8.5, ucoF['B1'][1]), ucoF['B1']], C_C)
    wire(ax, [(8.5, us['A2'][1]), us['A2']], C_C)
    dot(ax, 8.5, us['A2'][1], C_C)
    ax.text(8.5, 2.55, 'cTs', fontsize=9, color=C_C, ha='center')

    # cFs: U_csf.OUT -> track 8.95 -> U_coT.B1 and U_s.B2
    cfo = ucsf['OUT']
    wire(ax, [cfo, (8.95, cfo[1]), (8.95, ucoT['B1'][1]), ucoT['B1']],
         C_C, COMP_LS)
    wire(ax, [(8.95, us['B2'][1]), us['B2']], C_C, COMP_LS)
    dot(ax, 8.95, us['B2'][1], C_C)
    ax.text(8.95, 1.3, 'cFs', fontsize=9, color=C_C, ha='center')

    # ── outputs on the right ────────────────────────────────────────────
    for cell_, lbl in ((ucoF, 'cF$_{i+1}$  $\\rightarrow$ bit i+1 slice'),
                       (ucoT, 'cT$_{i+1}$  $\\rightarrow$ bit i+1 slice')):
        o = cell_['OUT']
        ax.annotate('', xy=(o[0] + 0.7, o[1]), xytext=o,
                    arrowprops=dict(arrowstyle='->', color=C_C))
        ax.text(o[0] + 0.8, o[1], lbl, fontsize=9.5, va='center', color=C_C)
    o = us['OUT']
    ax.annotate('', xy=(o[0] + 0.7, o[1]), xytext=o,
                arrowprops=dict(arrowstyle='->', color=C_S))
    ax.text(o[0] + 0.8, o[1], 'sum[i]  $\\rightarrow$ output port\n'
            '(valid 2i+2 half-cycles after inputs)', fontsize=9.5,
            va='center', color=C_S)

    # legend + footer
    lg_y = 0.55
    ax.plot([4.3, 5.0], [lg_y, lg_y], color='gray', ls=TRUE_LS, lw=1.6)
    ax.text(5.1, lg_y, 'true rail', fontsize=8.5, va='center')
    ax.plot([6.2, 6.9], [lg_y, lg_y], color='gray', ls=COMP_LS, lw=1.6)
    ax.text(7.0, lg_y, 'complement rail', fontsize=8.5, va='center')
    ax.text(9.4, lg_y, 'colors:  a-rails  b-rails  carry  x/nx  sum',
            fontsize=8.5, va='center')
    for k, col in enumerate((C_A, C_B, C_C, C_X, C_S)):
        ax.plot([10.27 + 0.555 * k], [lg_y - 0.25], marker='s', ms=7, color=col)
    ax.text(8, 0.05, 'Every box is an LSDL flop: samples inputs at its CLK '
            'rising edge, OUT = !(n-tree function), value latched through '
            'the following precharge.', ha='center', fontsize=9,
            style='italic', color='dimgray')
    return fig


# ════════════════════════════════ PAGE 2 ════════════════════════════════
def page2():
    fig, ax = plt.subplots(figsize=(16, 10.5))
    ax.set_xlim(0, 16); ax.set_ylim(0, 10.8); ax.axis('off')
    ax.text(8, 10.45, 'Signal glossary & full-adder identities',
            ha='center', fontsize=15, fontweight='bold')

    rows = [
        ('a[i], an[i], b[i], bn[i]', 'ports',
         'Operand bits, DUAL-RAIL: true + complement versions. The static-CMOS '
         'driver (LFSR) supplies both; LSDL cannot make a complement at the same '
         'stage (every cell inverts).'),
        ('p_a{i}_s{k}, q_a{i}_s{k}', 'chain nets',
         'Physical staging-chain wires: k-th inverter output of the pair rooted '
         'at a[i] (p) and an[i] (q). After k inversions p carries a[i] iff k is '
         'even — so the PAIR always holds both polarities; only the roles swap.'),
        ('aT, aF / bT, bF  @ stage s', 'role names',
         'Whichever chain wire carries the true (T) / complement (F) value at '
         'stage s. rails() in the generator resolves role → physical wire.'),
        ('cin, cinn', 'ports', 'Carry-in rails = "stage-0 outputs" for bit 0.'),
        ('cT_i, cF_i', 'stage 2i',
         'Carry rails INTO bit i — true and complement of c_i, produced by bit '
         'i−1 cells U_coT / U_coF (or the cin ports).'),
        ('cTs, cFs', 'stage 2i+1',
         'Carry rails restaged one stage through U_cst/U_csf, so they arrive at '
         'stage 2i+2 together with x_i. Inverting the OPPOSITE rail keeps '
         'polarity: cTs = !cF_i = c_i.'),
        ('x_i', 'stage 2i+1',
         'Propagate: x = a⊕b, computed in ONE inverting cell via '
         'aoi22(aT,bT,aF,bF) = !(ab + !a!b). Used by sum AND both carry cells.'),
        ('nx_i', 'stage 2i+1', 'Complement propagate !(a⊕b), for the sum XOR.'),
        ('cT_{i+1}, cF_{i+1}', 'stage 2i+2',
         'Carry-out rails. cF = !(ab + c·x) directly; cT uses majority self-'
         'duality maj(a,b,c) = !maj(!a,!b,!c) and !a⊕!b = x, giving '
         '!(!a·!b + !c·x) — true carry from one inverting cell, no extra stage.'),
        ('sum[i]', 'stage 2i+2 / port',
         'Sum bit: s = x⊕c via aoi22(x,cTs,nx,cFs). Outputs are time-skewed: '
         'sum[i] valid 2i+2 half-cycles (= i+1 cycles) after its operands.'),
        ('cout, coutn', 'stage 2W / ports', 'Final carry rails of bit W−1.'),
    ]
    y = 9.7
    for name, st, desc in rows:
        ax.text(0.4, y, name, fontsize=10, fontweight='bold', va='top',
                family='monospace')
        ax.text(4.55, y, st, fontsize=9, va='top', color='dimgray')
        ax.text(6.3, y, desc, fontsize=9.5, va='top', wrap=True)
        # crude wrap: measure lines manually
        import textwrap
        nlines = len(textwrap.wrap(desc, 88))
        ax.texts[-1].set_text('\n'.join(textwrap.wrap(desc, 88)))
        y -= 0.28 * nlines + 0.26

    ax.text(0.4, y - 0.1, 'How the slices form an adder', fontsize=12.5,
            fontweight='bold', va='top')
    expl = (
        'Standard full-adder identities, restated for inverting-only cells:\n'
        '    sum_i  =  a ⊕ b ⊕ c  =  x ⊕ c                  '
        '(x computed once, shared by sum and carry)\n'
        '    cout_i =  a·b + c·(a⊕b)  =  a·b + c·x           '
        '(when a≠b the carry propagates; when a=b it is generated)\n'
        '\n'
        'Each bit needs the carry in BOTH polarities (the sum-XOR and the dual carry cells consume cT and\n'
        'cF), so the carry ripples as a rail pair. Bit i+1 consumes cT/cF_{i+1} at stage 2i+3 — the carry\n'
        'advances one bit per two stages = one bit per full clock cycle. Operands for bit i are delayed to\n'
        'stage 2i by their staging chains, so each slice sees its operands and its carry at the same\n'
        'pipeline depth — a classic systolic (skewed) ripple adder. Throughput: one full W-bit addition\n'
        'completes every cycle; latency of sum[i] is i+1 cycles.')
    ax.text(0.4, y - 0.45, expl, fontsize=9, va='top', family='monospace')
    return fig


# ════════════════════════════════ PAGE 3 ════════════════════════════════
def page3():
    fig, ax = plt.subplots(figsize=(16, 10.5))
    ax.set_xlim(0, 16); ax.set_ylim(0, 10.8); ax.axis('off')
    ax.text(8, 10.45, '4-bit chaining and C1/C2 two-phase timing',
            ha='center', fontsize=15, fontweight='bold')

    # stage grid: stages 1..8, x = 1.5 + 1.55*(s-1)
    def sx(s):
        return 1.7 + 1.55 * (s - 1)

    for s in range(1, 9):
        ax.text(sx(s) + 0.65, 9.75, f'stage {s}\n({"C1" if s % 2 else "C2"})',
                ha='center', fontsize=9,
                color=('tab:orange' if s % 2 else 'tab:cyan'))
        ax.axvline(sx(s) - 0.08, ymin=0.30, ymax=0.88, color='lightgray',
                   ls=':', lw=0.8)

    # bit slices on a diagonal: bit i spans stages 2i+1..2i+2, row y
    for i in range(4):
        x0 = sx(2 * i + 1); x1 = sx(2 * i + 2) + 1.3
        y0 = 8.3 - 1.55 * i
        ax.add_patch(Rectangle((x0, y0), x1 - x0, 1.0, facecolor='#eef',
                               edgecolor='navy', lw=1.2))
        ax.text((x0 + x1) / 2, y0 + 0.5, f'bit {i} slice\n(7 cells)',
                ha='center', va='center', fontsize=9, color='navy')
        # operand chains feeding the slice
        if i > 0:
            ax.plot([sx(1) - 0.4, x0], [y0 + 0.78, y0 + 0.78], color=C_A, lw=2.4)
            ax.text(sx(1) - 0.5, y0 + 0.78,
                    f'a/b rail chains ({4 * (2 * i)} inv)', fontsize=7.5,
                    ha='right', va='center', color=C_A)
        else:
            ax.text(x0 - 0.15, y0 + 0.78, 'a[0],an[0],b[0],bn[0]', fontsize=7.5,
                    ha='right', va='center', color=C_A)
        ax.text(x0 - 0.15, y0 + 0.30,
                'cin,cinn' if i == 0 else '', fontsize=7.5, ha='right',
                va='center', color=C_C)
        # carry to next slice
        if i < 3:
            ny0 = 8.3 - 1.55 * (i + 1)
            wire(ax, [(x1, y0 + 0.25), (x1 + 0.25, y0 + 0.25),
                      (x1 + 0.25, ny0 + 0.3), (sx(2 * (i + 1) + 1), ny0 + 0.3)],
                 C_C, lw=2.2)
            ax.text(x1 + 0.34, ny0 + 0.62, f'cT$_{i + 1}$,cF$_{i + 1}$',
                    fontsize=8, color=C_C)
        # sum dropping out
        ax.annotate('', xy=(x1 - 0.45, y0 - 0.55), xytext=(x1 - 0.45, y0),
                    arrowprops=dict(arrowstyle='->', color='black'))
        ax.text(x1 - 0.6, y0 - 0.42, f'sum[{i}] @ cycle {i + 1}', fontsize=8,
                ha='right')
    ax.annotate('', xy=(sx(8) + 2.4, 8.3 - 1.55 * 3 + 0.25),
                xytext=(sx(8) + 1.3, 8.3 - 1.55 * 3 + 0.25),
                arrowprops=dict(arrowstyle='->', color=C_C))
    ax.text(sx(8) + 2.5, 8.3 - 1.55 * 3 + 0.25, 'cout, coutn', fontsize=8.5,
            va='center', color=C_C)

    # ── timing diagram ──────────────────────────────────────────────────
    ty = 1.9; period = 2.6; half = period / 2; t0 = 1.7
    ax.text(0.4, ty + 1.45, 'C1', fontsize=10, color='tab:orange')
    ax.text(0.4, ty + 0.45, 'C2', fontsize=10, color='tab:cyan')

    def square(y_lo, phase_off, color):
        pts = []
        t = t0 + phase_off
        ax.plot([t0, t], [y_lo, y_lo], color=color, lw=1.8)
        for k in range(5):
            pts += [(t, y_lo), (t, y_lo + 0.6), (t + half, y_lo + 0.6),
                    (t + half, y_lo)]
            t += period
        pts = [p for p in pts if p[0] <= t0 + 4.6 * period]
        wire(ax, pts, color, lw=1.8)

    square(ty + 1.1, 0.0, 'tab:orange')          # C1 rises at 0
    square(ty + 0.1, half, 'tab:cyan')           # C2 rises at T/2

    for k in range(4):
        tt = t0 + k * period
        ax.text(tt, ty - 0.25, f'{k:.1f} ns', fontsize=8, ha='center',
                color='gray')
        ax.text(tt + half, ty - 0.25, f'{k}.5', fontsize=8, ha='center',
                color='gray')
    # eval annotations
    ax.annotate('odd stages evaluate;\neven stages precharge\n(latches hold)',
                xy=(t0 + half / 2, ty + 1.75), fontsize=8, ha='center',
                color='tab:orange')
    ax.annotate('even stages evaluate,\nconsuming the just-latched\n'
                'odd-stage outputs',
                xy=(t0 + half + half / 2 + 0.4, ty - 0.85), fontsize=8,
                ha='center', color='tab:cyan')
    ax.annotate('', xy=(t0 + half, ty + 0.95), xytext=(t0 + 0.35, ty + 1.55),
                arrowprops=dict(arrowstyle='->', color='dimgray'))
    ax.text(9.6, 0.75,
            'Data advances one stage per half period.\n'
            'Budget per transfer: 500 ps = clk→out (266 ps aoi22)\n'
            '+ setup (100 ps) + 134 ps slack  [OpenSTA, TT/5V/25C].\n'
            'The internal latch holds each output through precharge,\n'
            'which is exactly when the opposite phase reads it.',
            fontsize=9, va='center', family='monospace')
    return fig


def main():
    pdf_path = OUT_DIR / 'adder_slice_schematic.pdf'
    figs = [page1(), page2(), page3()]
    with PdfPages(pdf_path) as pdf:
        for k, f in enumerate(figs, 1):
            pdf.savefig(f)
            f.savefig(OUT_DIR / f'adder_slice_p{k}.png', dpi=110)
    print(f'wrote {pdf_path}')


if __name__ == '__main__':
    main()
