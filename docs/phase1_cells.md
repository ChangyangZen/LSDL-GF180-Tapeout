# Phase 1 — Cell Foundation: Detailed Plan

## Topology Anchor

**LSDL** (Limited Switch Dynamic Logic), per Belluomini et al.,
*Limited Switch Dynamic Logic Circuits for High-Speed Low-Power Circuit
Design* (IBM J. Res. & Dev. 50:2/3, 2006) —
[PDF](related/Limited switch dynamic logic circuits for high-speed low-power circuit design.pdf).

Each LSDL cell is a single-clock dynamic gate with an **integrated
latch** built into the predriver/output stage (paper Fig. 1). The same
`Clk` drives the precharge PMOS, foot NMOS, header NMOS, and cut-feedback
PMOS. There is no separate latch clock — the cell behaves semantically
like a positive-edge-triggered flop on `Clk`.

At the pipeline level, two interleaved global clocks `C1` and `C2`
alternate between consecutive stages (paper Fig. 2(a), L1/L2 pipeline).
Each cell instance is bound to one of the two clocks at synthesis time
based on pipeline-stage parity.

We adopt the paper's "pure LSDL" form (no keeper, no minder). The paper
states this is workable at 90 nm and larger so long as the evaluate
window is bounded — and we enforce that bound in the on-die clock
generator. No controlled-load (CL-LSDL) and no hybrid (HLSDL).

Complex output gates: **NAND form only** (paper Fig. 3a). Two evaluation
trees combine via a NAND-form predriver inside one cell. NOR form
(Fig. 3b) not built.

Primary topology references:

- Belluomini et al. (above) — Fig. 1 (basic LSDL cell), Fig. 2(a) (L1/L2
  pipeline), Fig. 3(a) (NAND complex output), Fig. 5(a) (footless —
  *not built*), Fig. 6 (keeper/minder — *not built*).
- Sivagnaname et al., *Wide Limited Switch Dynamic Logic Circuit
  Implementations* (VLSID 2006) —
  [PDF](related/Wide_limited_switch_dynamic_logic_circuit_implementations.pdf).
  Wide-cell layout guidance and the 64-way mux benchmark.

---

## Cell-interface specification

Every LSDL cell exposes the following pins:

| Pin | Direction | Function |
|---|---|---|
| `Clk` | input | Bound to `C1` or `C2` depending on pipeline-stage parity. |
| `IN[]` | input | Logic inputs feeding the n-FET evaluation tree(s). |
| `Out` | output | Driven by the cell's integrated Output driver. |
| `VPWR` | power | Per-domain 5 V supply. |
| `VGND` | ground | Shared ground. |

No separate latch clock. No scan pins.

Per-cell internal devices (every cell follows paper Fig. 1):

- **Precharge device** (PMOS, gate = `Clk`)
- **n-FET evaluation tree** (function-specific)
- **Foot device (1)** (NMOS, gate = `Clk`)
- **Predriver p** (PMOS, gate = `dyn`)
- **Predriver n** (NMOS, gate = `dyn`, source via Header device)
- **Header device** (NMOS, gate = `Clk`)
- **Cut feedback** (PMOS, gate = `Clk`) — included for n/p ratio
  robustness per paper
- **Feedback device p** (PMOS, gate = `Out`)
- **Feedback device n** (NMOS, gate = `Out`)
- **Output driver p** (PMOS, gate = `out_b`)
- **Output driver n** (NMOS, gate = `out_b`)

For `LSDL_NAND_CMPLX` (paper Fig. 3a): `dyn1` and `dyn2` each have their
own Precharge device and Foot device; both feed the NAND-form complex
output gate which replaces the simple predriver inverter.

**Paper sizing rule (p. 278):** the cell must be sized so that the
dynamic-node-to-predriver path switches fast enough to keep the glitch on
`out_b` below 10% VDD. This becomes a hard SPICE check in Task 1.

---

## Task 0 — Disproof gate (pre-Phase-1)

Verify pure-LSDL at GF180MCU 5V matches the paper's behavior on hand-
laid-out cells.

- Hand-design two reference cells in Magic: `LSDL_INV_X1` (single-NMOS
  evaluation tree) and `LSDL_NAND2_X1` (stack-of-2 evaluation tree).
  Both follow paper Fig. 1 verbatim.
- Hand-design the two-phase clock generator in static CMOS using
  `gf180mcu_fd_sc_mcu9t5v0`. Produces C1, C2 with programmable
  non-overlap.
- Characterize across TT/SS/FF/SF/FS, 4.75–5.25 V, {−40, 25, 125 °C}.
  100 Monte Carlo points at TT 5V 25°C.
- Measure: dynamic noise margin, charge-sharing dip, leakage retention,
  evaluate delay, glitch magnitude on `out_b`.
- **Pass criterion:** meets paper sizing rule (glitch < 10% VDD) at all
  corners; behaves as a single-clock flop semantically. Fail at this
  gate = topology problem, not a downstream fix.
- Hand-cells double as bootstrap validation for Task 2 and the literal
  cells used in the tapeout chip.

**References:**

- Belluomini et al. (above) — Fig. 1 topology and sizing rule.
- Liu, Kursun — *Leakage Power Characteristics of Dynamic Circuits in
  Nanometer CMOS Technologies* (TCAS-II, 2006). Vector-dependent
  leakage and retention methodology.

---

## Task 1 — SPICE-in-the-loop fitness function

ngspice wrapper for GF180MCU returning a structured cost vector per
(cell, stimulus, corner).

- **Simulator:** ngspice with the open GF180MCU BSIM 4.x models.
- **Cost vector** (separate components, aggregated downstream):
  evaluate delay, precharge delay, dynamic-node noise margin,
  charge-sharing worst-case dip, glitch magnitude on `out_b`, static
  leakage, dynamic-node retention time, transistor count as area
  proxy.
- **Stimulus generators:**
  - Charge-sharing pattern enumerator (auto-generated, not
    hand-written).
  - Trapezoidal data-line noise pulse (LSDL paper Fig. 8/9 of
    Sivagnaname).
  - Power-rail bounce during precharge.
  - Vector-sweep for leakage/retention.
- **Corners:** TT/FF/SS/FS/SF; cross corners (FS, SF) often binding for
  dynamic.
- **Monte Carlo:** 100–500 points per characterization at the binding
  corner.
- **Surrogate model:** GP or small NN trained from a few hundred SPICE
  points; used between expensive SPICE calls. Refresh when proposals
  move outside trained region.
- **Caching** by (topology, sizing, corner) hash. ~10× warm speedup.
- **Logging:** record layout-stage features alongside SPICE results to
  enable future parasitic-aware modeling without re-running.
- **SPICE convergence on floating dynamic nodes:** wrapper must inject
  `.ic` statements; silent failure mode otherwise.
- **Hard gate:** glitch on `out_b` < 10% VDD across all corners (paper
  sizing rule).

**References:**

- Liu, Kursun (above) — vector-sweep leakage methodology.
- Sanabria-Borbón et al. — *Gaussian-Process-Based Surrogate for
  Optimization-Aided and Process-Variations-Aware Analog Circuit Design*
  (Electronics, 2020). Surrogate-layer methodology.
- Liu et al. — *Parasitic-Aware Analog Circuit Sizing with Graph Neural
  Networks and Bayesian Optimization* (DATE 2021). Motivates
  layout-feature logging.

---

## Task 2 — Extend SO3-Cell for dynamic cells

- https://github.com/ckchengucsd/SO3-Cell

LSDL anchoring narrows this task: only the n-stack pulldown is
synthesized; the precharge PMOS, foot NMOS, integrated latch, and
output driver are hand-templated from paper Fig. 1.

- **SMT scope:** n-stack topology (transistor ↔ Boolean literal) +
  per-transistor sizing.
- **Fixed templates:** Fig. 1 latch (precharge PMOS, foot NMOS, header,
  predriver p/n, cut feedback, feedback p/n, output driver p/n).
- **Clock-pin connectivity constraint:** precharge PMOS, foot NMOS,
  header NMOS, cut-feedback PMOS gates are all wired to the single
  `Clk` pin.
- **Internal-node identification:** every series-NMOS internal node
  exposed by name for charge-sharing probing (Task 1).
- **Bootstrap validation:** reproduce paper Fig. 1 LSDL NAND2 from its
  Boolean function. Mismatch = encoding bug.
- **Layout output gap:** SMT emits sized netlist; LibreLane needs a
  routable pin-accessible cell. Layout-from-netlist pass is likely the
  largest sub-task here.
- **Solver runtime fallback:** timeout + hand-templated retry path for
  stacks ≥4.

**References:**

- Cheng et al. — *SO3-Cell: Standard Cell Layout Automation Framework
  for Simultaneous Optimization of Topology, Placement, and Routing*
  (ICCAD 2025). Defines what SO3-Cell exposes vs. what we have to
  extend.
- Cheng, Kahng, Lin, Wang, Yoon — *Gear-Ratio-Aware Standard Cell Layout
  Framework for DTCO Exploration* (SLIP 2023). Pin access, track/grid
  assumptions; closes the gap between SMT netlist and OpenROAD cell.

---

## Task 3 — Target cell family

Lock functional repertoire before sizing work in Task 4. All cells
follow paper Fig. 1 (basic) or Fig. 3a (NAND complex output gate). No
scan; no keeper/minder; footed only.

**Wave 0 — disproof cells:**

| Cell | n-tree | Purpose |
|---|---|---|
| `LSDL_INV_X1` | single NMOS | Smallest LSDL cell — Fig. 1 validation |
| `LSDL_NAND2_X1` | 2-NMOS series | Stack-of-2 validation, charge-sharing |
| Two-phase clock generator (static CMOS) | — | Wave 0 integration enabler |

**Wave 1 — mapper cells:**

| Cell | n-tree | For benchmark |
|---|---|---|
| `LSDL_AND2/3/4_X1` | 2/3/4 NMOS series | Adder, mux, encoder |
| `LSDL_OR2/3/4_X1` | 2/3/4 NMOS parallel | Adder, encoder |
| `LSDL_AOI21_X1` | (A·B) + C tree | Adder carry mapping |
| `LSDL_AOI22_X1` | (A·B) + (C·D) tree | Adder, mux |
| `LSDL_MUX2_X1` | one bit of wide mux | Mux building block |
| `LSDL_NAND_CMPLX_X1` | two single-NMOS trees, NAND output | Two-input gate with merged latch |
| `LSDL_NAND_CMPLX_AOI` | (A·B) and (C·D) trees, NAND output | Adder hot path |

**Wave 2 — benchmark cells:**

| Cell | Purpose |
|---|---|
| `LSDL_OR_TREE_4/8/16` | Wide-OR for priority-encoder chain |
| `LSDL_MUX_SEG_8/16` | Segmented wide-mux slice |
| `LSDL_PRI_ENC_CELL` | Priority-encoder stage with leading-zero output |
| `LSDL_C1_C2_TRANSFER` | C1↔C2 boundary transfer (if needed) |

**Design rules:**

- **Topology fixed:** paper Fig. 1 for basic, Fig. 3(a) for complex
  output.
- **Cut feedback device included** (paper recommends for robustness).
- **Footed only.** No footless variants (paper Fig. 5a not built).
- **No keeper, no minder.** Paper supports this at 180 nm.
- **Max stack height:** GF180MCU 5V → 4 (verify in Task 1 sweeps).
- **Drive strengths scale with stack height**, not uniform — paper used
  1.5× device width for the 64-way over 8-way (Sivagnaname).
- **Dynamic-node length budget per cell** controls long-wire noise;
  measured in Wave 0/1 and locked before Wave 2 segmentation.
- **Library coverage reporter:** given a benchmark RTL, list missing
  functions. Run before locking the family.

**Excluded:**

- Scan-related cells (per tapeout-specific decision).
- Dual-rail XOR/XNOR (Fig. 1 single-tree handles XOR via auxiliary
  inverter if needed).
- Wide NOR (AND-of-ORs preferred structurally).
- Footless variants.
- Keeper / minder variants.
- Power-gate-aware precharge driver (replaced by domain-level header
  PMOS in the always-on power-switch infrastructure).

**Per-cell precharge/evaluate semantics** in a single spec doc — input
setup relative to `Clk` rising edge, hold relative to `Clk` rising,
output valid window. These become Liberty timing arcs in Task 5. For
each cell, also document the worst-case evaluating input vector
(determines min evaluate window via Task 1).

**References:**

- Belluomini et al. (above) — Fig. 1, Fig. 3a, sizing rule.
- Zhao, Sapatnekar — *Technology Mapping Algorithms for Domino Logic*
  (ACM TODAES, 2002). Defines required functional coverage for a
  domino-mappable library.
- Sivagnaname et al. (above). Cell sketches, 1.5× sizing scaling,
  stack-height guidance, wide-mux benchmark.

---

## Task 4 — Agent-driven synthesis + characterization loop

With topology fixed, search collapses to sizing + n-tree shape per
function.

- **Two-level search:** outer (openEvolve) proposes n-tree shape and
  drive-strength targets; inner (SMT + SPICE) sizes and characterizes.
- **Multi-objective handling:** Pareto front (NSGA-II-style dominance or
  top-K per metric). No weighted scalarization.
- **Robust-corner optimization:** cost = worst-corner cost, not TT cost.
- **Convergence:** Pareto-front stagnation, compute budget, or target
  spec met. No open-ended runs.
- **Agent prompt content:** current Pareto front, recent failure modes,
  delta from best cell of similar function. Always include the paper
  sizing rule explicitly.
- **Diversity:** penalize similarity to already-synthesized cells; force
  exploration across the family.
- **Wide cells:** extra axis is cell-width segmentation when
  dynamic-node-length budget is exceeded.
- **Logging:** every proposal, every SPICE result, every reject reason.
- **Agent reward hacking:** expect 2–3 cycles of loophole-finding (e.g.,
  topologies where precharge doesn't complete before next evaluate, or
  glitch sneaks under the 10% threshold by overshoot). Tighten
  constraints iteratively.

**References:**

- Sanabria-Borbón et al. (above). Surrogate-loop methodology.
- Cheng et al. SO3-Cell (above). Bounds the outer search space.

---

## Task 5 — Liberty/LEF emission

Library views LibreLane / OpenSTA accept. Each LSDL cell modeled as a
**positive-edge-triggered flop on `Clk`**.

```liberty
cell (LSDL_NAND2_X1) {
  pin (Clk) { direction: input; clock: true; }
  pin (A1)  { direction: input; ... }
  pin (A2)  { direction: input; ... }
  pin (Out) { direction: output; function: "!(A1 & A2)"; }
  ff (IQ, IQN) {
    clocked_on: "Clk";
    next_state: "!(A1 & A2)";
  }
  timing(Out) { related_pin: "Clk"; timing_type: rising_edge; ... }
  timing(A1)  { related_pin: "Clk"; timing_type: setup_rising; ... }
  timing(A1)  { related_pin: "Clk"; timing_type: hold_rising;  ... }
  min_pulse_width_high (Clk) ...
  min_pulse_width_low  (Clk) ...
  internal_power () { /* split: precharge_power + evaluate_power */ }
}
```

- **Setup time** of inputs to `Clk` rising = (worst-case eval delay for
  the evaluating vector) + (latch input setup margin).
- **Hold time** = latch input hold (small).
- **`min_pulse_width_high`** = minimum evaluate window from Task 1.
- **`min_pulse_width_low`** = minimum precharge window (also bounded
  above by the paper's leakage-tolerance limit at 180 nm).
- **Power tables:** distinguish precharge energy, evaluate energy
  (pattern-dependent), leakage. Don't lump.
- **C1 and C2 declared as two separate clocks in SDC**, both derived
  from the master external clock; the L1/L2 pipeline structure means
  data crosses from C1 cells to C2 cells one stage at a time, which
  OpenSTA models cleanly with standard multi-clock setup/hold.

**LEF strategy:**

- **SITE `GF018hv5v_green_sc9`**, row height **5.04 µm** (verified from
  upstream `gf180mcu_fd_sc_mcu9t5v0__inv_1.lef`).
- **Library name:** `lsdl_fd_sc_9t5v0`. Separate library from stock
  `gf180mcu_fd_sc_mcu9t5v0`; both libraries co-exist in LibreLane
  config.
- **Mixed-row library** for wide muxes only if Wave 0 measures the
  dynamic-node-length budget too tight for 5.04 µm. Default: single-row.
- **Dynamic-node-length LEF constraint** prevents PnR from generating
  layouts exceeding the noise budget.
- **Pin placement:** dynamic node never appears as a pin (internal
  only). `Clk` pin on dedicated track.

**LibreLane integration:**

- Configure custom SCL bundle with LSDL `.lib`, `.lef`, `.gds`, Verilog
  wrappers.
- Use the [wafer.space project template](https://github.com/wafer-space/gf180mcu-project-template)
  as the base configuration.
- Validate with the LibreLane-bundled OpenSTA version specifically (not
  upstream OpenSTA), since Liberty quirks vary.

**STA-clean ≠ design-clean.** Charge-sharing and non-overlap-margin
checks live in Phase 3 Task 14 (parasitic-aware re-verification), not
STA. Flag clearly in deliverables.

**References:**

- Li et al. — *MCell: Multi-Row Cell Layout Synthesis with Resource
  Constrained MAX-SAT Based Detailed Routing* (ICCAD 2020). Multi-row
  precedent for the wide-mux row-height decision.
- Cheng, Kahng, Lin, Wang, Yoon (above). Pin access and track
  conventions.

---

## Task 6 — Sanity benchmark

End-to-end validation gating Phase 2. **The tapeout chip is the sanity
benchmark.**

- **First integration test:** 1-cell LibreLane smoke design with
  `LSDL_NAND2_X1` (Wave 0 gate).
- **Library proof-of-concept benchmark:** 16-bit adder, LSDL version,
  placed/routed in LibreLane (Wave 1 gate). Compare against the same
  function in stock `gf180mcu_fd_sc_mcu9t5v0` static CMOS.
- **Delay-advantage benchmark:** 32-bit priority encoder (Wave 2 gate).
- **Power-advantage benchmark (paper-canonical):** 32-way mux scaled
  from Sivagnaname et al. (Wave 2 gate).
- **Hand-routing constraints** on dynamic nodes (don't-touch nets,
  shielding). Document for Phase 3 integration.

**References:**

- Sivagnaname et al. (above). Canonical benchmark + comparison numbers.
- Belluomini et al. (above). Multiplier-design comparison numbers.

---

## Cross-Cutting Concerns

- **Process variability budget.** σVt tolerance up front. GF180MCU 5V
  ~50 mV. Drives Task 1 MC count, Task 5 Liberty margins, Task 3
  noise-margin spec.
- **Supply-noise modeling.** Dynamic nodes are Vdd-droop sensitive
  during evaluate. ±5% Vdd in Task 1 characterization.
- **Coupling-aware layout.** Dynamic nodes need aggressor isolation.
  LEF/layout constraint (Task 5) *and* characterization input (Task 1).
- **Glitch budget.** Paper sizing rule (glitch on `out_b` < 10% VDD)
  appears in Task 1 (SPICE check), Task 3 (cell sizing spec), and Task 4
  (synthesis loop objective).
- **Library coverage feedback loop.** RTL benchmark → missing functions
  list. Run before locking the cell family.
- **Documentation discipline.** Every cell's precharge/evaluate
  semantics + worst-case evaluating vector in one spec doc. Without it,
  Phase 2 mapper, Phase 3 verifier, and Phase 4 clock-gating logic
  will diverge silently.
- **Reproducibility.** Random seeds for SMT/openEvolve, version-locked
  SPICE models, pinned tool commits.
- **No-weak-cell tax.** Pure LSDL is more noise-sensitive than keeper-
  or minder-based variants. Layout effort recovers what a weak load
  gives for free. Shows up in Task 5, Phase 3 Task 14, Phase 2 Task 12.

**References:**

- Belluomini et al. (above) — multiplier-design measurements,
  voltage-frequency scaling.
- Sivagnaname et al. (above) — wide-mux benchmark and 1.5× scaling
  rule.

---

## Suggested Reading Order

1. Belluomini et al. (LSDL paper) — Fig. 1 cell topology, Fig. 2a
   pipeline, Fig. 3a NAND complex output, Fig. 6 keeper/minder
   discussion (we use neither).
2. Sivagnaname et al. — wide-cell layout, 1.5× scaling, 64-way mux
   benchmark.
3. Zhao & Sapatnekar — functional coverage for domino mapping (Task 3).
4. Cheng et al. SO3-Cell (ICCAD 2025) — inner tool (Task 2).
5. Liu, Kursun — Task 0 + Task 1 methodology (vector-dependent
   leakage).
6. Sanabria-Borbón et al. — Task 1 surrogate layer.
7. Remainder (MCell, Gear-Ratio, Liu GNN+BO) as their tasks come up.
