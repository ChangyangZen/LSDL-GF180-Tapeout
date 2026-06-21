# First Tapeout — Wafer.space GF180MCU (180 nm)

First-tapeout-specific plan layered on [phase1_cells.md](phase1_cells.md).
Only deltas and tapeout-specific work appear here.

Architecture follows Belluomini et al., *Limited Switch Dynamic Logic
Circuits for High-Speed Low-Power Circuit Design* (IBM J. Res. & Dev.
50:2/3, 2006) —
[PDF](related/Limited switch dynamic logic circuits for high-speed low-power circuit design.pdf).
The LSDL cell topology is Fig. 1 of that paper; the pipeline structure
is Fig. 2(a) (L1/L2); complex output gates are Fig. 3(a) (NAND form only).

---

## Why GF180MCU for the first tapeout

[Wafer.space](https://wafer.space) shuttle runs on GlobalFoundries
GF180MCU — a 180 nm mixed-signal process with an open-source PDK and an
open-flow toolchain (LibreLane).

- **180 nm forgives pure LSDL.** Paper notes that at 90 nm and larger,
  LSDL works without keeper or minder so long as the evaluate window
  is bounded. We enforce that bound in the on-die clock generator.
- **Open PDK** ([gf180mcu-pdk.readthedocs.io](https://gf180mcu-pdk.readthedocs.io)) —
  no NDA, fully reproducible.
- **5 metal layers** — sufficient for dynamic-node shielding via stacked
  metal.
- **Stock 9T 5V static-cell library** (`gf180mcu_fd_sc_mcu9t5v0`, SITE
  `GF018hv5v_green_sc9`, 5.04 µm row height) is the static-CMOS
  comparison baseline and the host library for all non-LSDL on-die
  infrastructure (clock generator, LFSRs, capture registers, pad ring).
- **MIM caps available** — on-die decoupling per power domain.
- **Cost:** $4,000–$7,500 per slot, ~1000 dies per slot.
- **Slot decision (A64, 2026-06-03): 1×1 slot** — 3.93 × 5.12 mm,
  19.65 mm² usable silicon, 56 default pads (up to 168 custom),
  $7,000–7,500 (re-verify pricing at submission; the early-bird date on
  the price page has passed). Area budget against it:

  | Block | Cells | Placed est. |
  |---|---|---|
  | LSDL adder64 (ripple, dual-rail) | 16,832 | ~2.2 mm² |
  | CMOS adder64 (matched arch) | 4,224 | ~0.5 mm² |
  | mux32 + priencoder32 pairs | TBD (Wave 2) | ~1–1.5 mm² |
  | 6× testers + clkgen + glue | ~1,500 | ~0.2 mm² |
  | **Total core** | | **~4–4.5 mm²** |

  vs ~14–16 mm² core inside the default pad ring → ~3× margin.

---

## Tapeout scope

Three benchmark circuits, each implemented twice — once in LSDL, once in
static GF180MCU cells — for direct frequency/power comparison. All six
instances on one die, each in its own power domain.

### Benchmark circuits

1. **64-bit adder** (systolic ripple-carry, architecture-matched pair).
   Library proof-of-concept. Both flavors implement the SAME dataflow —
   skewed pipeline, carry advancing one bit per cycle, sum[i] valid at
   cycle i+1 — so the comparison isolates the logic family:
   - LSDL: dual-rail, `gen_lsdl_adder.py --width 64` — 16,832 cells
     (16,512 inv + 320 aoi22), 128 C1/C2 half-cycle stages, ~1.40 mm²
     cell area (~2.2 mm² placed), closes 1 GHz with +0.134 ns slack
     (OpenSTA, measured-PVT Liberty, TT).
   - CMOS: single-rail, `gen_cmos_adder.py --width 64` — 4,224 cells
     (4,160 dffq_1 + 64 addf_1), 0.334 mm² cell area (~0.5 mm² placed),
     f_max ≈ 634 MHz (pre-PnR, ideal clock, TT).
   Upgraded from 16 bits 2026-06-03 (decision A64); 16-bit generators kept
   as regression vehicles. If this doesn't tape out clean, the library
   has a fundamental problem.
2. **32-way rotator / mux** (scaled-down Sivagnaname 2006 example). LSDL
   power-advantage demonstrator with published comparison numbers. Tests
   wide-cell layout, dynamic-node length budget, segmented-mux drive
   sizing.
3. **32-bit priority encoder** with leading-zero-count output. LSDL
   delay-advantage demonstrator. Deep OR-chain — domino wins structurally
   here because the CMOS counterpart needs either many series-OR stages
   or wide PMOS stacks.

Per the role split: adder is the proof-of-concept; priority encoder is
the headline delay-advantage result; rotator reproduces the paper-canonical
power-advantage measurement.

### Per-instance requirements

For each benchmark, both versions:

- **Ring oscillator mode** with output looped back through an enable-mux
  to the input, output frequency divided (÷256) to an output pad.
  Cleanest frequency/delay measurement; no input vector setup.
- **Functional mode** driven by an on-die LFSR (static-CMOS), with
  outputs sampled into a capture register and serialized to a pad. No
  scan chain.
- **Dedicated `VDD_<benchmark>` pad** for current measurement.

---

## Power gating strategy

Each of 6 instances has an independent power domain.

- **PMOS header switch** per domain, controlled by a dedicated enable
  pad (1 pad per domain).
- **Shared ground** across domains (single Gnd plane); only Vdd is gated.
- **Always-on domain** for I/O ring, clock generator, LFSRs, capture
  registers. Powers up first; everything else gated until selected.
- **Gating policy:** exactly one benchmark domain powered at a time
  during measurement. Others contribute only gated-Vdd leakage.
- **LSDL wake-up:** dynamic nodes start unknown after re-power. The
  master clock must run for ≥10 cycles after a domain enables before its
  LFSR is started, ensuring all dynamic nodes have precharged at least
  once. Encoded in bench bring-up procedure.
- **Header switch sizing.** Domain-on Vdd droop must stay below 100 mV
  at full activity (paper sizing rule for noise margin headroom).
- **On-die decoupling cap per domain** using GF180MCU MIM caps.

---

## Measurement infrastructure

### Adder testers (decision TST, 2026-06-03 — replaces LFSR/capture/RO
### for the two adder instances)

Each 64-bit adder gets an identical static-CMOS go/no-go tester
(`lsdl_lib/blocks/adder/tester/adder_tester.v`, one module, two
instances; the LSDL flavor's extra `c2` pin only forwards to its adder):

- ROM of 10 vectors (carry-ripple worst cases + PRNG), comparator,
  and two LED pads per tester: **correct** / **incorrect**.
- FSM on clock 1 internally divided by 6 (self-starting Johnson counter,
  no reset). Vector held 96 cycles; result sampled at cycle 66 — the
  exact first arrival in both adder flavors, so at-speed corruption is
  caught while the tester logic itself runs ≥5× slower per evaluation.
- f_max measurement: sweep the external clock until **incorrect** lights;
  the adder is the limiter (tester is flop-limited at ~1.1 GHz, FSM
  paths run at clk/6). The previous RO-loopback method does not apply to
  the adder pair.
- Each tester is placed at the SAME distance from its adder
  (mirrored floorplan) for a fair comparison.

### LFSR input driver (one per remaining benchmark, ×4)

- 32-bit maximum-length LFSR built in static CMOS
  (`gf180mcu_fd_sc_mcu9t5v0`), drives the benchmark's primary inputs.
- Seeded from 2 shared input pads (serial seed + load enable) at reset;
  16-bit seed per LFSR loaded into a 16-bit chain wrapping all 6 LFSRs
  through bank-select bits in the seed stream.
- Clocked by the chip master clock; advances one step per chip cycle.
- LFSR lives in the always-on domain and crosses the power-domain
  boundary into the benchmark via isolation buffers.

### Output capture register (one per remaining benchmark, ×4)

- Static-CMOS shift register at the benchmark's primary outputs.
- Parallel-loaded each functional cycle, serialized out to one pad per
  benchmark (×4 capture-output pads — mux32 and priencoder32 pairs).
- Capture controlled by a 2-bit mode register in the always-on domain:
  capture-and-shift, capture-only (frozen for inspection), or bypass.

### Ring-oscillator mode

- Per-benchmark enable-mux loops the output back to the input.
- ÷256 divider on the RO output to bring frequency to a pad-measurable
  range.
- 4 RO-output pads (mux/encoder pairs; adders use tester clock sweep).

### Two-phase clock generator (single instance, always-on domain)

- External clock pad → divide-by-2 → produces 50% duty C1 and C1_bar →
  programmable delay-chain inserts a non-overlap gap at every transition
  to produce C1 and C2 with non-overlap.
- 5-bit non-overlap control register, ~10 ps step at TT 5V 25°C,
  range 10–320 ps. Bits delivered via dedicated pads.
- Both C1 and C2 are 50% duty, 180° apart in phase, with the
  programmable non-overlap gap.
- Built entirely in static CMOS. No PLL, no on-die oscillator —
  confirmed against wafer.space and GF180MCU PDK that no clock-gen IP
  is available.

### Process monitor

- Ring oscillator from stock `gf180mcu_fd_sc_mcu9t5v0` cells
  (inverter chain) in the always-on domain, ÷256 to a dedicated pad.
  Normalizes per-die measurements against silicon process corner.

---

## Pad budget (56 default; up to 122 on 0.5×1 slot)

| Function | Count |
|---|---|
| `VDD_<domain>` × 7 (6 benchmark + always-on) | 7 |
| `GND` | 6 |
| External clock in | 1 |
| Reset | 1 |
| LFSR seed input (serial data + load enable) | 2 |
| Domain enables × 6 | 6 |
| Clock-gen non-overlap control bits × 5 | 5 |
| Capture-register serial outputs × 4 (mux/encoder pairs) | 4 |
| Ring-oscillator outputs × 4 (mux/encoder pairs) | 4 |
| Adder tester LEDs (correct + incorrect) × 2 testers | 4 |
| Process-monitor RO output | 1 |
| Spare / future | 6 |
| **Total** | **47** |

Fits the default 56-pad ring with 9 pads of slack. Headroom on the 0.5×1
slot (up to 122 IO) for Kelvin-sensing on `VDD_<benchmark>` and for
additional debug taps.

---

## Deltas to Phase 1 ([phase1_cells.md](phase1_cells.md))

### Task 0 — disproof gate

- Run on GF180MCU 5V. Per paper, 180 nm tolerates leakage without
  keeper or minder.
- Disproof cells: `LSDL_INV_X1` and `LSDL_NAND2_X1` (paper Fig. 1
  topology, single-Clk, integrated latch). These hand-cells become
  the literal cells in the tapeout.
- Plus the two-phase clock generator (static CMOS).

### Task 1 — SPICE fitness function

- GF180MCU backend (ngspice + open PDK models).
- Characterize at 5 V ± 5%, three temperatures (−40, 25, 125 °C),
  five process corners (TT/SS/FF/SF/FS).
- Hard sizing check: glitch on `out_b` must stay below 10% VDD
  (paper, p. 278).

### Task 3 — cell family

- **Per paper Fig. 1.** Single-clock LSDL latch with integrated
  Predriver, Header device, Cut feedback, Feedback p/n, Output driver
  p/n.
- **Cut feedback included** per paper recommendation (n/p ratio
  robustness).
- **Footed only.** Foot device (1) in every cell.
- **No keeper, no minder.** Paper supports this at 180 nm.
- **Complex output gates: NAND form only** (Fig. 3a). Two evaluation
  trees feed the NAND-form predriver in a single cell.
- **No scan-related cells.** No SDFFRS variant; no scan latches.
- **No power-gate-aware precharge driver.** Domain enable is via pad-
  controlled header PMOS in the always-on power switch; LSDL cells
  don't need internal back-drive protection.

### Task 4 — synthesis loop

- Compute budget shifts toward GF180MCU; ASAP7 deferred.
- 5 V GF180MCU may admit larger stack heights (verify in Task 1
  sweeps before locking the cell-family stack budget).

### Task 5 — Liberty/LEF

- Target the **LibreLane** flow (wafer.space-supported). Test against
  the [project template](https://github.com/wafer-space/gf180mcu-project-template)
  early.
- **Row height 5.04 µm** (verified from upstream LEF — see Decisions
  Captured below). LSDL cells share SITE `GF018hv5v_green_sc9` with the
  stock 9T static library.
- LSDL cells ship as a separate library, suggested name
  `lsdl_fd_sc_9t5v0`. Stock `gf180mcu_fd_sc_mcu9t5v0` is consumed
  unchanged for the CMOS-baseline benchmark and for the LFSR /
  capture / clock-gen infrastructure.
- **Liberty pattern:** each LSDL cell modeled as a positive-edge
  flop on `Clk`. Single `ff (IQ, IQN) { clocked_on: "Clk"; }` group.
  Setup of inputs measured from `Clk` rising. C1 and C2 declared as
  two separate clocks in SDC.

### Task 6 — sanity benchmark

- Tapeout chip *is* the sanity benchmark.
- **64-bit adder** is the library proof-of-concept (Wave 1 gate;
  upgraded from 16-bit per decision A64 — netlists + STA done, see
  `lsdl_lib/blocks/adder/`).
- Place + route through **LibreLane**, not OpenROAD-flow-scripts.

### Cross-cutting

- **No scan.** Removed entirely.
- **Two-phase clock generator** (static CMOS) is a Phase 1 deliverable.
- **LFSR + capture register infrastructure** is a Phase 1 deliverable.

---

## Decisions captured

1. **Clock model:** single `Clk` per cell, two interleaved global trees
   C1/C2 (paper Fig. 2a, L1/L2 pipeline).
2. **Layout tool:** Magic + Netgen authoritative; KLayout informational.
3. **Row site:** `GF018hv5v_green_sc9`, row height 5.04 µm (verified
   from upstream `gf180mcu_fd_sc_mcu9t5v0__inv_1.lef`).
4. **Separate LSDL library** `lsdl_fd_sc_9t5v0` sharing the site.
5. **Complex output gates:** NAND form only (Fig. 3a).
6. **C1/C2 generator:** 50% duty, programmable non-overlap, 5-bit
   register from pads.
7. **No scan;** LFSR + capture register + ring oscillator for
   measurement.
8. **Footed n-trees only.**
9. **No keeper, no minder** (paper supports this at 180 nm).
10. **Cut feedback device included** (paper recommends).
11. **Liberty pattern:** positive-edge flop on Clk rising.

---

## Run scheduling

[Wafer.space pricing, accessed May 2026:](https://wafer.space/price.html)

| Milestone | Date |
|---|---|
| Run 2 early bird deadline | 30 April 2026 (past) |
| Run 2 submission deadline | 30 June 2026 |
| Run 2 parts shipped | Early Q4 2026 |

Run 2 (June 30 2026) is unrealistic. Target is **Run 3** or later.

Working backward from a hypothetical Run 3 submission ~Q4 2026:

- Task 0 (disproof) — 4 weeks
- Phase 1 Tasks 1–5 — 12–16 weeks
- Tapeout chip design (RTL + flow + sign-off) — 8 weeks
- LibreLane DRC/LVS clean — 2–4 weeks
- Buffer for fab-rejected DRC issues — 2 weeks

Total ~7 months. Tight; doable if Task 0 starts soon.

---

## Tapeout-specific risks

- **First-time LibreLane bring-up.** The wafer.space template repo
  ([wafer-space/gf180mcu-project-template](https://github.com/wafer-space/gf180mcu-project-template))
  is the path of least resistance.
- **Custom cell LEF acceptance by LibreLane.** Biggest unknown. Run one
  hand-designed LSDL cell from Task 0 through the full LibreLane flow
  early.
- **OpenSTA acceptance of LSDL Liberty.** Pattern is "flop on Clk
  rising" — much simpler than the prior dual-clock approach — but a
  spike test on `LSDL_NAND2_X1` is still a Wave-0 gate.
- **Pad ring choice.** Default 56-pad ring is enough; sticking with it
  avoids custom pad-ring generation and enables the optional
  chip-on-board packaging add-on.
- **DRC on dynamic-node shielding.** GF180MCU DRC rules may not
  recognize shielding patterns as standard cells expect. Budget
  iteration time on the wide-mux family.
- **Shielding budget at 5.04 µm row height** is tighter than originally
  scoped. Wave 0 must verify a real LSDL layout fits with adequate
  shielding around the dynamic node; if not, multi-row cells for wide
  muxes only is the Plan B.
- **Yield expectation.** First dynamic-logic tapeout, no prior silicon
  experience — expect ~50% functional dies. 1000 dies/slot absorbs this.
- **Bring-up plan.** Bench needs: external clock source, programmable
  supply per `VDD_<benchmark>`, current meter, serial pattern loader
  (for LFSR seed), serial-out capture. Budget bench equipment before
  tapeout, not after.

---

## Out of scope for this document

- Cell-by-cell sizing for GF180MCU (Phase 1 Task 4 output).
- LibreLane configuration files (project template handles defaults).
- Post-silicon characterization test program (separate doc once bench
  setup is finalized).
- Package selection beyond chip-on-board option.

---

## References

- Belluomini et al., [*Limited Switch Dynamic Logic Circuits for
  High-Speed Low-Power Circuit Design*](related/Limited switch dynamic logic circuits for high-speed low-power circuit design.pdf) (IBM J. Res. & Dev. 50:2/3, 2006).
- [GF180MCU PDK documentation](https://gf180mcu-pdk.readthedocs.io/)
- [Wafer.space project template](https://github.com/wafer-space/gf180mcu-project-template)
- [Wafer.space Run 1 density report](https://github.com/wafer-space/ws-run1/blob/density-report/reticle_density_report.md)
- [LibreLane / OpenLane2 flow](https://github.com/librelane/librelane)
- [gf180mcu_fd_sc_mcu9t5v0 (9T 5V library)](https://github.com/google/globalfoundries-pdk-libs-gf180mcu_fd_sc_mcu9t5v0)
- Phase 1 references — see [phase1_cells.md](phase1_cells.md).
