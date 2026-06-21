# T5 Signoff — 64-bit Adder Pair PnR (OpenROAD)

**Date:** 2026-06-03 · **Tool:** OpenROAD 26Q2 (IIC-OSIC-TOOLS) · TT corner

## Results

| | LSDL adder64 | CMOS adder64 (matched arch.) |
|---|---|---|
| Netlist | `adder64_lsdl.v` — 16,832 LSDL cells | `adder64_cmos.v` — 4,224 + repair cells |
| Site / rows | custom `unit` 11T (0.56×6.16), 247 rows | `GF018hv5v_green_sc9` 9T |
| Die / core | 1.55 × 1.55 mm, util 60.3% | 0.75 × 0.75 mm, util 60.2% |
| Clocks | C1 + C2 @ 1 GHz, 180° flat (no buffers) | CLK 500 MHz, CTS clkbuf_2/4/8+16 |
| Worst setup | **+0.078 ns** (1 GHz, est. wire RC) | **+0.003 ns** (500 MHz, repaired) |
| Worst hold | +0.50 ns | +0.135 ns |
| TNS | 0.0 | 0.0 |
| Route DRC | **0** | **0** |
| Output | `lsdl_adder64.def` | `cmos_adder64.def` |

**Frequency comparison (same systolic ripple architecture, TT post-route):
LSDL 1 GHz vs CMOS 500 MHz = 2.0×.**

## Implementation notes
- LSDL collateral: `make_pnr_collateral.py` lowercases macros, maps
  met1/met2/via1→Metal1/Metal2/Via1, snaps pins to 5 nm grid (DRT-0320),
  declares custom 11T site.
- Tracks per PDK tracks.info (0.28/0.56; M5 0.45/0.90).
- PDN: M1 followpins 0.48 µm + M4/M5 straps (LSDL VPWR/VGND, stock VDD/VSS).
- LSDL run: no CTS (no LSDL clock buffers) — C1/C2 routed flat (8.5k pins);
  skew absorbed by 500 ps half-period; hold +0.5 ns.
- CMOS: repair_timing setup+hold; I/O multicycle 2/1 (tester /6 ticks).

---

# T5b — GDS streamout, fillers/taps, DRC convergence, tester macro

**Date:** 2026-06-05

## Tester macro — HARDENED
`adder_tester.def/.gds` (stock 9T, 278×278 µm): worst setup **+0.012 ns @
0.9 ns (1.11 GHz)**, hold +0.49, TNS 0, route DRC 0. OpenROAD
`repair_design` closed the fanout paths the raw Yosys netlist failed at
(−6 ns) — validates the f_max-sweep methodology (tester outlasts both
adders: LSDL 1 GHz, CMOS 500 MHz).

## Physical completion of lsdl_adder64
- 11T support LEF written (`lsdl_support_11t.lef`): tap (CORE WELLTAP),
  endcap, fill 1/2/4.
- tapcell: 25 µm pitch + **tap-as-endcap** (DF.13/14 violations were only
  at row ends); ~8k taps. (12 µm pitch experiment over-fragmented rows —
  detailed placement failed; reverted.)
- filler_placement: ~70k fills. Timing unchanged (+0.08 ns @ 1 GHz).
- PDN: followpins on **Metal2 only** + M4/M5 mesh. Cells' internal rail
  vias bond M1↔M2, so no PDN via1 stacks — avoids 15k V1.1/V1.2a unions
  with cell-internal cuts. Signal routing restricted to Metal2–Metal5 for
  the same reason.

## Streamout (`def2gds.py`, KLayout)
- Official PDK map file (`gf180mcu.map`) for routing layers.
- Gotchas burned in: LEFDEF reader ignores configured dbu when the LEF
  declares DATABASE MICRONS (force `ly.dbu = 0.0005` post-read for the
  LSDL tech LEF; do NOT force for the stock LEF — `def2gds_cmos.py`);
  merge cell GDS via dbu-aware `copy_tree`, not OverwriteCell.
- **Implant-band extension at streamout**: cells were signed off
  standalone with NPLUS/PPLUS bands 0.1 µm short of top/bottom edges and
  0.42 µm short of left/right — stacked rows leave same-layer gaps at
  every seam (NP.2/PP.2, 21k markers). Fix: bands (≥80% cell width)
  extended flush to all cell edges → continuous row-length stripes,
  stock-library style; tap islands untouched.

## DRC convergence (KLayout full GF180 deck, deep mode) — **CLEAN**
| Run | Violated classes | Markers | Fix applied next |
|---|---|---|---|
| 1: raw merge, M1 PDN, no taps | 9 | ~37,000 | taps, M2-only PDN, M2+ routing |
| 2: +0.1 implant overshoot | 5 | 4,646 | flush (overshoot made slivers) |
| 3: flush vertical extension | 5 | 4,328 | + horizontal band extension |
| 4: horizontal bands | 5 | 1,478 | kiss corners ≠ gaps: close |
| 5–6: morphological close 0.2/0.4 | 5 | 1,478 | close adds measure-zero at a point — bite instead |
| 7: kiss-vertex bites (368) | 2 | 6 | opening pass + tap-contact M1 halo |
| 8: + opening + CO.6 halo | 1 (PP.1) | 5 | width-carve loop — DIVERGED (5→32, ate tap implant) |
| 10: cut patches at 5 necks | 3 | — | necks sit over tap COMP: fill, don't cut |
| 11: fill patches 0.45 | 1 (PP.2) | 1 | 0.04 um slot — widen to 0.55 |
| **12: fill patches 0.55** | **0** | **0** | — |

**Final verdict (2026-06-05): `Klayout DRC run is clean. GDS has no DRC
violations.`** All healing logic lives in `def2gds.py` (implant band
extension, kiss-vertex bites, opening, 5 placement-specific fill patches,
tap-contact M1 halo) — reproducible from DEF in one command.

Key physical-design lessons (feed back into the cell library, L5 follow-up):
- lclayout cells need implant bands drawn to the cell boundary (stock-cell
  convention) so rows merge; currently fixed at streamout.
- tapcell's row stagger creates same-layer checkerboard kisses at tap
  corners; geometrically unavoidable without aligned taps — bite resolution.
- PDN must hook at Metal2: cell-internal rail via1s collide with PDN via
  stacks (exact-size via rule V1.1 fails on merged unions).

## Magic-hang + off-grid fix (2026-06-12) — def2gds.py dbu + grid snap
The Phase B chip flow's Magic.DRC step "hung" ~21.7 h on `lsdl_adder64.gds`.
Root cause was TWO stacked problems, both fixed in `def2gds.py`:
1. **dbu 0.0005.** The LEFDEF reader leaves routing at DEF UNITS 2000 (dbu
   0.0005). Magic/GF180 hard-require 1e-9; a 0.0005 GDS forces Magic to rescale
   by a non-integer factor vs its 5 nm lambda grid and spin forever. **Fix:**
   convert the whole layout to dbu **0.001 up front** (`ICplxTrans(0.5)`, exact —
   DEF routing is on the 5 nm grid), *before* the cell merge + healing, so the
   native dbu-0.001 signoff cells merge **verbatim** (XOR-verified bit-identical
   on every real mask layer) and healing runs on the real grid. Magic now
   finishes in ~90 s.
2. **2 nm off-grid cells.** LibreCell emits poly/contact/metal/via with a
   systematic **+2 nm** offset vs the on-grid COMP/well (~8–13 % of cell coords
   at ≡2 mod 5 nm). KLayout DRC with `--no_offgrid` (our dev flag) hid it, but
   the **wafer.space precheck's gating KLayout DRC runs deck `all,…` with the
   off-grid check ON** → it *would have rejected the chip*. **Fix:** snap every
   cell to the 5 nm grid at streamout (round-to-nearest = lossless rigid +/-2 nm
   translate; routing/healed implants already on-grid → no-op; labels preserved).
   Verified: snapped cell + macro pass KLayout DRC with **off-grid ENABLED**
   (full deck) → *"Klayout DRC run is clean."*; standalone snapped cell Magic
   DRC = 0; macro is 0/754,612 off-grid at dbu 0.001.

**Note on Magic's 969,912 macro markers:** these are Magic-deck-only row-seam
complaints (DF.3a/DF.8/DF.1a/DF.9/PL.5a/DF.5) at cell abutment that the official
KLayout sign-off deck does **not** flag (and a *single* cell is Magic-clean).
The precheck sets `ERROR_ON_MAGIC_DRC: False` → Magic DRC is **non-gating**.
The gate is KLayout DRC (off-grid ON), which is clean. Not a submission blocker.

## Streamed artifacts
`lsdl_adder64.gds` (1549.4 µm² die, **dbu 0.001, 0 off-grid, KLayout-DRC clean
with off-grid ON**), `cmos_adder64.gds` (766 µm, stock cells, on-grid),
`adder_tester.gds` (278 µm, stock cells, on-grid).

## Remaining for T5b
DRC run 4 verdict (+ CO.6 singleton triage), block LVS vs netlist,
PEX glitch gate (W1-A3) on critical nets.
