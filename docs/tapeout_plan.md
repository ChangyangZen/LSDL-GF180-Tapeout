# TPL — Migrate the LSDL tapeout into the wafer.space project template

## Phase A DRC triage (322 KLayout markers) + flow refinement
First full-chip run reached sign-off: routing DRC 0, antenna 0, **Netgen LVS
"Circuits match uniquely"**, Magic DRC ran (non-blocking). KLayout DRC = **322
markers**, triaged by the lyrdb `cell` attribution:
- **231 (72%) inside the `adder_tester` macro GDS**: NP.2 73, PP.2 64, NW.2a 41,
  NW.2b 38, DV.5 15. Root cause: the tester is **stock 9T cells** hardened by our
  `run_pnr_tester.tcl` + `def2gds_cmos.py`, which does NO implant/well healing and
  was only ever checked for *route* DRC — never the full GF180 deck. A block of
  abutted stock cells still needs row-level implant/nwell/dualgate continuity
  (fillers + welltaps + continuous NPLUS/PPLUS/NWELL). It isn't there → implant
  islands <0.4 µm (NP.2/PP.2), nwell gaps (NW.2), dualgate slivers (DV.5).
- **91 (28%) `DF.13/14_MV` tap-distance** in top-level 7T glue cells (dffq/dlyc/
  clkbuf/…): the "satisfied by tapcells at PnR" rule; check vs baseline template +
  tapcell coverage.

**Flow refinement (decision, PROVEN): harden STOCK-CELL macros (adder_tester,
cmos_adder64) THROUGH LibreLane** (their own Classic-flow sub-build under
`blocks/<name>/config.yaml`) instead of our hand OpenROAD + `def2gds_cmos.py` —
LibreLane does correct tapcell + filler + DRC-clean streamout automatically. Only
the **LSDL** adder keeps our custom `def2gds` implant-healing (LibreLane can't heal
lclayout cells). Recipe: `librelane blocks/<n>/config.yaml --scl <9t or 7t>
--save-views-to blocks/<n>/views`, then copy views/{gds,lef,vh,lib/*} into
`ip/<n>/`. **RESULT: re-hardening adder_tester this way took Phase A KLayout DRC
from 322 → 0** (block standalone: DRC+LVS clean; full chip: DRC 0, LVS match,
flow complete, final/chip_top.gds saved). Note the tester RTL hardcodes 9T cells
(dffq_4/inv_4), so it must harden at 9T.

## ✅ Phase A (TPL-3) SIGNED OFF
Full chip (tester macro + glue) on the 1x1 template: KLayout DRC **0**, Magic DRC
clear, Netgen LVS **"Circuits match uniquely"**, setup+hold MET, Flow complete,
`final/chip_top.gds` (166 MB) saved. Macro-integration path proven end-to-end.
NEXT: TPL-4 Phase B — integrate the lsdl_adder64 + cmos_adder64 pair (LSDL via
custom def2gds, CMOS via the same LibreLane-Classic recipe).

## Env gotcha — `pmap` missing in the LibreLane Nix image (KLayout DRC/antenna)
The GF180 KLayout deck `gf180mcu.drc` (line ~50) builds its log prefix from
`` `pmap <pid> | tail -1` ``[10,40].strip — purely a memory-usage string. The
LibreLane Nix image has no `procps`, so the backtick returns `""`, `""[10,40]`
is `nil`, and `nil.strip` raises `NoMethodError` → the deck crashes before any
geometry check (KLayout DRC *and* Antenna steps). Fix: a `pmap` stub on PATH —
`.pmap_stub/pmap` in the template (prints one ≥50-char line); `run_librelane_docker.sh`
prepends `/design/.pmap_stub` to PATH. (Our IIC-OSIC-TOOLS container has procps,
which is why standalone cell DRC worked there.)

## Sign-off TODO (do NOT forget at final tapeout)
- **Re-enable `OpenROAD.IRDropReport`** (disabled in `config.yaml` meta for Phase A)
  **and set `VSRC_LOC_FILES`** to the pad ring's VDD/VSS source-pad coordinates.
  Root cause of the Phase-A hang: with `VSRC_LOC_FILES` unset, `irdrop.tcl` calls
  `analyze_power_grid` with no `-vsrc`, so PSM has no anchored voltage source →
  degenerate solve (avg VDD "drop" = 4.99999 V on a 5 V rail = floating grid) →
  the 258k-node PSM solve spins at 100% CPU forever (CSVs+metrics written, but no
  `state_out.json`, `irdrop.rpt` 0 bytes). IR-drop is a sign-off quality check, NOT
  a wafer.space submission gate (precheck = DRC/antenna/density/LVS only).

## Context

The chip must be submitted through the wafer.space **`gf180mcu-project-template`
v1.5.0** (LibreLane "Chip" flow), cloned at
`~/projects/lsdl_tapeout_wafer.space/gf180mcu-project-template`. Our work so
far lives in `brainstorm/domino` and was hardened with our **own** raw-OpenROAD
flow (`run_pnr.tcl` + `def2gds.py` LSDL implant-healing), not LibreLane —
because LibreLane cannot run the LSDL implant-healing pipeline and cannot
synthesize the flop-only LSDL cells. The template, in contrast, owns the
fixed pad ring (`chip_top.sv`, bonding contract — do NOT change pad
count/power pads), the wafer.space ID/logo IP, full-chip KLayout+Magic DRC,
Netgen LVS, and the PDN core ring. The job is to plug our pre-hardened blocks
into the template as **macros** and let LibreLane assemble + sign off the chip.

**Decided (this planning round):**
- **Macro integration** is forced: each benchmark block + tester is a
  pre-hardened GDS/LEF/lib/vh macro (mirrors how the template handles the
  foundry SRAM). Glue logic (pad wiring, dual-rail boundary inverters, domain
  fan-out), the two-phase clkgen, and measurement infra are synthesizable
  static CMOS that go through LibreLane normally in `chip_core.sv`.
- **Top-level SCL = `gf180mcu_fd_sc_mcu7t5v0`** (template default; user choice).
  Glue/clkgen/infra synthesize to 7T. Macros enter as fixed GDS regardless of
  their internal site (9T inside cmos/tester, 11T inside the LSDL adder), so
  the foreign site only matters at the macro boundary (handled by LEF
  obstruction + halo).
- **Repo strategy:** `brainstorm/domino` stays source-of-truth (cells,
  generators, hardening flow). An export step generates each macro's 4 views
  into the template's `ip/<macro>/`. The template holds only `chip_core.sv`,
  configs, and exported artifacts.
- **First scope:** tester-only de-risk, then the adder pair, then scaffold the
  rest.

Intended outcome: the existing adder benchmark runs end-to-end through the
template's Chip flow (synth → PnR → pad ring → streamout → DRC → LVS) on real
pads, establishing the repeatable macro-integration recipe for every
remaining block (mux, encoder, CMOS comparisons, clkgen, measurement infra,
power gating).

## The missing artifacts (critical path — build these FIRST, in domino)

Each macro needs 4 views; we have GDS but **not** block-level LEF or Liberty:

| View | lsdl_adder64 | cmos_adder64 | adder_tester | How to produce |
|---|---|---|---|---|
| `gds` | ✓ `pnr/lsdl_adder64.gds` | ✓ | ✓ | exists (healed, DRC-clean) |
| `lef` (block abstract) | **MISSING** | MISSING | MISSING | OpenROAD `write_abstract_lef` from the `.odb`/`.def` |
| `vh` (blackbox) | trivial | trivial | trivial | port-only module from each adder's header |
| `lib` (block timing) | **MISSING** | MISSING | MISSING | extend `scripts/gen_liberty.py` to emit a block-level interface `.lib`; later upgrade via OpenROAD `write_timing_model` |

- Block ports (for vh + lef + lib, must agree exactly, case-sensitive):
  - `lsdl_adder64`: `c1, c2, a[63:0], an[63:0], b[63:0], bn[63:0], cin, cinn, sum[63:0], cout, coutn` + PG `VPWR/VGND`.
  - `cmos_adder64`: `clk, a[63:0], b[63:0], cin, sum[63:0], cout` + PG `VDD/VSS`.
  - `adder_tester`: ports from `tester/adder_tester.v` + PG `VDD/VSS`.
- The `write_abstract_lef` must expose signal pins on **Metal2/Metal3** (where
  `run_pnr.tcl` already placed them) and the PG pins, and **fully obstruct M1
  + M2–M5 except at pins** so the top router treats the macro as opaque. Verify
  pins are not buried under an OBS rectangle (common failure → unroutable).
- `cmos_adder64` has no `cinn`/dual-rail; the LSDL dual-rail boundary
  (`an=~a, bn=~b, cinn=~cin` from `tester/lsdl_adder_wrap.v`) becomes
  **synthesizable glue in `chip_core.sv`** (mapped to top-level 7T cells), not
  part of the macro.

## Macro-integration recipe (per block, mirrors the template SRAM entry)

1. **Export 4 views** into the template: `ip/<macro>/{gds,lef,vh,lib}/`
   (build artifacts; generators stay in domino).
2. **`librelane/macros/macros_5v.yaml`** — add an entry shaped exactly like
   `gf180mcu_fd_ip_sram__sram512x8m8wm1` (macros_5v.yaml:82): `gds/lef/vh`,
   `lib` keyed `"*"` (single corner) or `"*_tt_025C_5v00"` (multi-corner), and
   `instances: {<hier.inst>: {location:[x,y], orientation:N}}`. The instance
   key MUST be the fully-qualified path (`i_chip_core.u_<macro>`).
3. **`PDN_MACRO_CONNECTIONS`** (macros_5v.yaml:106) — one line per instance,
   format `"<inst> <macroVpin> <macroGpin> <topVnet> <topGnet>"`. The LSDL
   adder maps its VPWR/VGND to the chip VDD/VSS:
   `"i_chip_core.u_lsdl_adder64 VPWR VGND VDD VSS"`; cmos/tester are
   `"... VDD VSS VDD VSS"`.
4. **`chip_core.sv`** — instantiate the macro with its blackbox port names,
   wire to the pad buses; hierarchical name = the `macros_5v.yaml` instance key.
5. **`instances.location`** = lower-left corner in µm within
   `CORE_AREA [442,442,3490,4680]` (1x1 slot). Footprints: lsdl_adder64
   ~1550², cmos_adder64 ~766², adder_tester ~278². Keep halos clear of each
   other, the core ring, and the corner IP.

## LVS / DRC handling for the custom-site macros

- **LVS:** use **black-box LVS** at the top level (like the SRAM — matched as a
  single instance by ports, not descended into). Needs the 4 views' ports to
  agree; does NOT need the LSDL-cell SPICE. Keep the per-cell extracted SPICE
  + GF180 device models as a fallback only if full hierarchical device-level
  LVS is later wanted.
- **DRC:** macro internals are already healed/clean under the same GF180 deck
  the Chip flow runs (`KLAYOUT_DRC_OPTIONS.decks "all,-antenna,-density,-cup"`).
  The new surface is the **macro boundary** (implant NP/PP.2, metal spacing)
  where the foreign site abuts top-level fill + core ring. Mitigate with a
  placement halo + full LEF obstruction; debug with the `debug-drc` skill.
  Add `lsdl_*` to `MAGIC_GDS_FLATGLOB` (config.yaml:113) for a clean
  (non-blocking) Magic DRC report. **Do not re-run `def2gds.py`** — its 5 neck
  fill coords are tied to the current placement; consume the existing GDS.

## Phased sequence

**Phase A — tester-only de-risk (first integration):**
1. Confirm the *unmodified* template builds end-to-end on this machine:
   `make clone-pdk` then `make librelane` (establish green baseline).
2. In domino: generate `adder_tester` block LEF (`write_abstract_lef`) + minimal
   `.lib` + blackbox `.v`; export to `ip/adder_tester/`.
3. Template: add the `adder_tester` macro entry + 1 PDN line + 1 instance;
   reduce `chip_core.sv` to pad wiring + one tester instance (clocks→clk,
   result/correct/incorrect→bidir pads). Remove demo counter + both SRAMs.
4. `make librelane`; iterate boundary DRC + macro PDN until full-chip clean.
   This validates LEF abstract, macro PDN, black-box LVS, and top DRC on the
   smallest block.

**Phase B — the done adder pair (first complete chip):**
5. Export LEF/lib/vh for `lsdl_adder64` (VPWR/VGND PG, 1.55 mm, 11T) and
   `cmos_adder64`.
6. `chip_core.sv`: tester drives both adders; LSDL adder fed through the
   dual-rail boundary inverters (now top-level glue). Add both macro entries +
   PDN lines + placements. Drive C1/C2 from two input pads directly (defer
   on-chip clkgen to Phase C).
7. Full PnR + signoff. Verify M4/M5 PG straps land on the LSDL macro's internal
   mesh within the halo.

**Phase C — the two remaining benchmark circuits (mux32 + encoder32):**
Each is built LSDL + matched-CMOS in domino, hardened through the SAME flow as
the adder (structural generator → `run_pnr.tcl` → `def2gds.py` healing for the
LSDL flavor; stock-SCL PnR for the CMOS flavor), exported as 4-view macros, and
instantiated in `chip_core.sv`. Detailed below in "The two remaining benchmark
circuits". This completes the 6-instance benchmark set (3 circuits × {LSDL,CMOS}).

**Phase D — infrastructure + chip assembly (T11–T13):**
9. clkgen (T11, two-phase C1/C2 w/ programmable non-overlap) and measurement
   infra (T12 LFSR/capture/RO for mux+encoder) as **synthesizable RTL in
   chip_core** (7T) — preferred over macros.
10. Power gating (T13, 6 domains + always-on) is **beyond the template's
    single-CORE-domain `pdn_cfg.tcl`** — needs custom multi-domain PDN tcl +
    floorplan; treat as a dedicated effort and confirm shuttle support for
    multi-domain PDN with wafer.space first.

## The two remaining benchmark circuits (T7–T10, T12)

Both reproduce the LSDL paper's headline results and round out the 3-circuit
benchmark. Neither exists yet — generators + Wave-2 cells must be built in
domino first, then they follow the proven adder macro path.

### Circuit 2 — 32-way mux / rotator (power-advantage demonstrator)
- **New LSDL cells (Wave 2, T7):** `MUX_SEG_8/16` (one slice of a segmented
  wide mux — bounded dynamic-node length per the Wave-0/1 length budget),
  reusing `AOI22`/`AND` where possible. Built through the existing
  `signoff_cell.sh` LibreCell flow (0 DRC, block LVS, pin-access, LEF audit).
- **LSDL block (T8):** new `gen_lsdl_mux.py` structural generator → `mux32_lsdl.v`
  (segmented 32:1, dual-rail select). Selftest vs bit-exact reference, STA at the
  benchmark's own f_max.
- **CMOS block (T10):** matched `gen_cmos_mux.py` → `mux32_cmos.v`, stock
  `gf180mcu_fd_sc_mcu9t5v0` (mux2/AOI tree + DFF pipeline), same dataflow.
- **Harden + export:** both flavors → `run_pnr.tcl` (LSDL uses custom 11T site +
  `def2gds.py` healing; CMOS uses stock SCL) → `write_abstract_lef` + block
  `.lib` + blackbox `.v` → `ip/mux32_lsdl/`, `ip/mux32_cmos/`.

### Circuit 3 — 32-bit priority encoder (delay-advantage demonstrator)
- **New LSDL cells (Wave 2, T7):** `OR_TREE_4/8/16` (wide parallel-NMOS OR —
  this is where domino structurally wins: no PMOS stack in the evaluate path on
  the deep OR chain) and `PRI_ENC_CELL` (encoder stage w/ leading-zero output).
  Same `signoff_cell.sh` flow. Watch the dynamic-node length budget on the
  widest OR tree (charge-share floor > 3.5 V with PEX, like the adder cells).
- **LSDL block (T9):** `gen_lsdl_priencoder.py` → `priencoder32_lsdl.v` (deep
  OR-chain + leading-zero count). Selftest + STA.
- **CMOS block (T10):** matched `gen_cmos_priencoder.py` → stock 9T (series-OR
  / wide-OR tree + DFF), same dataflow — CMOS pays the structural cost here.
- **Harden + export:** same as mux → `ip/priencoder32_lsdl/`, `ip/priencoder32_cmos/`.

### Measurement for these two (T12 — NOT go/no-go testers)
Unlike the adder pair (identical go/no-go testers), mux32 + encoder32 use the
**LFSR / capture / ring-oscillator** scheme, all **synthesizable static-CMOS RTL
in `chip_core.sv`** (7T, not macros):
- **LFSR input driver** per instance (×4): 32-bit max-length LFSR, 16-bit seed
  loaded serially (shared seed chain + load-enable), lives in the always-on
  domain, crosses the power-domain boundary into each benchmark.
- **Output capture register** per instance (×4): parallel-load + serialize to one
  pad each (4 capture-out pads); 2-bit mode (capture-shift / capture-only / bypass).
- **Ring-oscillator mode** per instance (×4): output looped back through an
  enable-mux to the input, ÷256 to a pad (4 RO-out pads) — clean f_max with no
  vector setup.
These integrate as ordinary RTL the Chip flow synthesizes + places around the
4 benchmark macros; they connect to the macros' boundary pins and to the pads.

### Integration into the template (per macro, ×4)
Each of the four blocks (mux LSDL/CMOS, encoder LSDL/CMOS) follows the
"Macro-integration recipe" above: 4 views under `ip/<block>/`, a `macros_5v.yaml`
entry, a `PDN_MACRO_CONNECTIONS` line (LSDL → `VPWR VGND VDD VSS`, CMOS →
`VDD VSS VDD VSS`), a placement `location/orientation` in `CORE_AREA`, and a
`chip_core.sv` instance wired to its LFSR/capture/RO and pads. Floorplan: the
1.55 mm LSDL adder dominates; mux/encoder LSDL blocks are ~1–1.5 mm² combined —
budget the 1x1 core (~3.0×4.2 mm) for 6 macros + infra and keep macro halos +
the corner IP keepouts clear.

### Tasks covered
T7 (Wave-2 cells: OR_TREE, MUX_SEG, PRI_ENC_CELL), T8 (mux32 LSDL), T9
(encoder32 LSDL), T10 (CMOS mux + encoder), T12 (LFSR/capture/RO for these two).

## Pad / IO mapping (1x1 slot: 12 input + 40 bidir + 2 analog + clk + rst_n)

Budget ~47 fits with margin. `clk_PAD`/`rst_n_PAD` are dedicated (separate from
the 12 inputs). Assign signals to `input_PAD[i]`/`bidir_PAD[i]`/`analog_PAD[i]`
inside `chip_core.sv` only — never change `slot_defines.svh` counts or the
`PAD_*` lists. Cross-reference `slot_1x1.yaml` `PAD_SOUTH/EAST/NORTH/WEST` to
group related signals on one physical edge (`inputs[0..11]`=WEST,
`bidir[0..13]`=SOUTH, `[14..25]`=EAST, `[26..39]`=NORTH).
- clk→`clk_PAD`, reset→`rst_n_PAD`; C1/C2→2 input pads (Phase B), later from clkgen.
- 6 domain enables→6 input pads. Tester correct/incorrect→bidir (oe=1, LED go/no-go).
- Block results→**serial scan-out** on a couple of bidir pads (not parallel).
- mux/encoder LFSR seed / capture-scanout / RO_en / RO_out→bidir (+ optional analog for RO).

## Critical files
- Template (edit): `src/chip_core.sv` (replace demo with macro insts + glue),
  `librelane/macros/macros_5v.yaml` (macro entries + `PDN_MACRO_CONNECTIONS`),
  `librelane/config.yaml` (clock period, `MAGIC_GDS_FLATGLOB += lsdl_*`).
  Build with `make librelane` (default SCL 7T). **Do NOT touch `chip_top.sv`**.
- Template (new, build artifacts): `ip/<macro>/{gds,lef,vh,lib}/...`.
- Domino (extend): `lsdl_lib/blocks/adder/pnr/run_pnr*.tcl` (+ `write_abstract_lef`
  from `.odb`), `lsdl_lib/scripts/gen_liberty.py` (emit block-level `.lib`),
  new export script copying the 4 views into `<template>/ip/`.
- Domino (consume read-only): `pnr/lsdl_adder64.{gds,def,odb}`,
  `pnr/cmos_adder64.*`, `pnr/adder_tester.*`, `pnr/def2gds.py` (do NOT re-run).

## Verification
- Baseline: unmodified template `make librelane` completes (synth→PnR→DRC→LVS).
- Phase A: full-chip `make librelane` with the tester macro → KLayout DRC clean,
  Netgen LVS "match", macro PG connected. `make sim` (cocotb) drives the tester
  through pads and observes correct/incorrect.
- Phase B: full chip with 3 macros → DRC/LVS clean; OpenROAD STA shows the
  macro interfaces constrained (C1/C2 as macro clocks, not timed against the
  slow top clock); `make sim`/`make sim-gl` exercise the adder go/no-go.
- Per-macro pre-check: `write_abstract_lef` output has PINs not buried under
  OBS; the 4 views' port lists agree (case-sensitive).

## Final submission gate — wafer.space gf180mcu-precheck

The authoritative pre-submission sign-off is the **wafer.space
`gf180mcu-precheck`**, cloned at `~/projects/wafer.space_precheck/gf180mcu-precheck/`
(has a Dockerfile as an alternative to host Nix), run on the streamed top GDS —
separate from and stricter than the in-flow LibreLane DRC. Set up its env
(Nix `nix-shell` + `make clone-pdk`, or the Dockerfile), then:
```
export PDK_ROOT=gf180mcu PDK=gf180mcuD
python3 precheck.py --input final/gds/chip_top.gds --top chip_top --slot 1x1 --cob
```
It must pass with **zero violations** before submission. Its checks (and what
each implies for our LSDL design):
- **Structural** — exactly one top cell named `chip_top` (the Chip flow already
  produces this).
- **Layout params** — origin at (0,0), dbu **0.001 µm**, **Metal5 = max layer**,
  die dimensions match the `1x1` slot. *Watch:* our `def2gds.py` forces
  `dbu=0.0005` for the LSDL macro internally — confirm the merged top GDS is
  emitted at 0.001 µm (KLayout streamout in the Chip flow handles this, but
  verify after the macro is merged) and that nothing in the LSDL macro uses a
  layer above Metal5.
- **CoB** (`--cob`) — QR code / shuttle ID / project ID / marker present and
  positioned (supplied by the template IP, untouched).
- **Density** — fill density within bounds (template's density fill + the
  `Metal2_ignore_active` setting handle this; the large LSDL macro is opaque so
  its area counts as filled).
- **Zero-area polygon** elimination — *watch:* the `def2gds.py` healing
  (bites/fills) could in principle leave degenerate slivers; run a polygon
  cleanup on the macro GDS if flagged.
- **Antenna** (KLayout) and **DRC** (Magic + KLayout) — same decks as the flow,
  re-run independently as the final word.

This precheck is the gate for **T15 (full-chip verification + submission)** and
must be green on the final merged GDS, not just per-macro.

## Final: end-to-end verification order
- Baseline → Phase A (tester) → Phase B (adder pair): `make librelane` clean +
  `make sim`/`make sim-gl` at each phase.
- Then the **gf180mcu-precheck** gate above on `final/gds/chip_top.gds` →
  zero violations → submit.

---

# GF180MCU LSDL Tapeout — Paper-Aligned Build Plan

---

# TST — Identical tester circuits for the 64-bit adder pair

## Context

User spec (2026-06-03): both adders get a **completely identical tester**
(copy-paste). Tester pins — LSDL flavor: `clock1, clock2, result-of-adder,
correct, incorrect`. CMOS flavor: same minus `clock2` (4 pins). The tester
drives a fixed sequence of **10 numbers** into its adder; if the adder's
output matches the precomputed sum, the **correct** LED pad lights, else
the **incorrect** LED pad lights. Testers must be much faster than both
adders, run on clock 1, and each tester must sit at the **same physical
distance from its adder** so the comparison is fair.

This replaces the LFSR + capture + RO measurement infrastructure **for the
adder pair** (mux32/priencoder32 keep the LFSR/capture plan unchanged).
f_max measurement method: sweep the external clock; the adder fails first
(tester has ≥5× cycle margin); incorrect LED = past f_max.

## Design decisions

- **One RTL module, two instances.** `adder_tester.v` (static CMOS, stock
  9T cells, behavioral RTL → Yosys). LSDL instance pin `c2` exists per spec
  but is only routed onward to the LSDL adder, not used internally — keeps
  the testers gate-identical.
- **Dual-rail boundary in a wrapper, not the tester.** `lsdl_adder_wrap.v`
  holds adder64_lsdl + 129 stock inverters (an/bn/cinn); CMOS wrapper is
  the bare adder. Testers stay identical.
- **Hold-and-settle + ÷5 internal divider on clock 1.** GF180 5V flops cap
  near ~1.2-1.3 GHz, so no static-CMOS tester can cycle at 1.57 GHz. The
  FSM runs at clk1/5, holds each vector 16 ticks (80 cycles), advances
  vectors at tick 0, samples at **tick 13 = cycle 65 = exact first-arrival
  of the result** (verified: works identically for LSDL 2W+2 half-cycles
  and CMOS W+1 cycles). Exact-arrival sampling catches at-speed setup
  corruption (a settled-only comparison would mask it); LSDL pulse-width
  failures persist in steady state, also caught.
- **Frequency margin:** tester FSM at clk/5 closes trivially; full-rate
  elements = divider + sampling flops (~1.2 GHz cap), adders fail at ~1.0
  GHz (LSDL pulse-width SS) / ~634 MHz (CMOS TT) → tester is never the
  bottleneck up to the divider's ~1.2 GHz ceiling. Measured sweep is bounded
  there; LSDL's 1.57 GHz SPICE ceiling stays a simulation-only claim.
- **Vectors:** 10 numbers: carry-ripple worst cases (FFFF…+1, alternating
  AAAA…/5555…, max+max), zero, and 5 PRNG vectors; `gen_vectors.py`
  precomputes expected {sum,cout} → `vectors.vh` localparams (ROM in logic).
- **LEDs:** `correct` = all 10 pass in a loop, refreshed per loop;
  `incorrect` = latched within a failing loop. Pads: +2 per tester
  (LED via board resistor); removes adder LFSR-seed/capture/RO pads (−4).
- **Placement (T14):** tester↔adder distance identical for both pairs.

## Work items

1. **TST-1 — RTL + vectors**: `tester/gen_vectors.py` → `vectors.vh`;
   `tester/adder_tester.v` (param W=64, DIV=5, HOLD_TICKS=16);
   `tester/lsdl_adder_wrap.v`.
2. **TST-2 — Simulation**: iverilog — tester + adder64_cmos.v (stock
   gf180mcu verilog models, real netlist) end-to-end: correct LED on;
   negative test (corrupt one expected sum → incorrect LED on);
   tester + behavioral LSDL latency model.
3. **TST-3 — Synthesis + STA**: Yosys → stock-cell netlist; OpenSTA:
   divider/sampler ≥ 1.2 GHz; FSM at clk/5; record margins vs adders.
4. **TST-4 — Docs**: phase1_cells_tapeout.md measurement + pad-budget
   sections (testers for adders; LFSR/capture remain for mux/encoder);
   update task T12.

## Critical files
- New: `lsdl_lib/blocks/adder/tester/{gen_vectors.py, vectors.vh,
  adder_tester.v, lsdl_adder_wrap.v, tb_tester_cmos.v, tb_tester_lsdl.v,
  synth_tester.ys, run_sta_tester.tcl}`
- Edit: `phase1_cells_tapeout.md` (measurement, pad budget)

## Verification
- iverilog: correct LED asserts on real CMOS netlist; corrupted vector
  asserts incorrect LED (negative control); LSDL behavioral model passes.
- OpenSTA on synthesized tester: full-rate elements close at ~1.2 GHz;
  FSM paths close at clk/5 with 5x margin.

---

# A64 — Upgrade adder benchmark to 64 bits (ripple, LSDL + matched CMOS)

## Context

Decisions locked with the user (2026-06-03):
- **Chip scope**: full 3-benchmark tapeout retained (adder + 32-way mux + 32-bit priority
  encoder, each LSDL vs CMOS); the **adder benchmark goes 16 → 64 bits**.
- **Architecture**: **systolic ripple** for both flavors — the CMOS adder mirrors the LSDL
  dataflow (same skewed pipeline, same per-bit schedule) so the comparison is
  architecture-matched. The LSDL-64 ripple netlist already exists and passes selftest
  (`gen_lsdl_adder.py --width 64`: 16,832 cells, 128 stages, sum[i] @ cycle i+1).
- **Slot**: wafer.space **1×1** (3.93 × 5.12 mm, 19.65 mm² usable, 56 default pads,
  $7,000–7,500; the early-bird date on the price page has passed — re-verify price at
  submission time).
- **Area check (done)**: LSDL ripple-64 = 1.40 mm² cells ≈ 2.2 mm² placed; matched CMOS
  ≈ 0.8–1.4 mm²; testers + clkgen ≈ 0.1 mm²; full 3-benchmark core ≈ 5 mm² → fits the
  ~14–16 mm² core inside the default pad ring with ~3× margin.
- Kogge-Stone-64 (≈3,000 cells, 0.4 mm², 4.5-cycle latency, fanout ≤2; dual-rail prefix
  formulas already derived and verified this session — see conversation notes: combine
  node = aoi21/aoi22/nand2/nor2, 4 cells/node) is **documented as a future optimization,
  not in scope** — area does not force it and ripple needs zero new LSDL netlist work.

## Work items

### A64-1 — LSDL ripple-64: generate + STA closure
- Move the adder workspace `lsdl_lib/blocks/adder16/` → `lsdl_lib/blocks/adder/`
  (it now hosts 4/16/64-bit variants; update paths in `run_sta_adder.tcl`, README,
  `draw_adder_slice.py`).
- `gen_lsdl_adder.py --width 64 --selftest --out adder64_lsdl.v` (already proven to pass).
- G5 @ 64 b: `ADDER_W=64 sta -no_init -exit run_sta_adder.tcl` — expect the same
  +0.134 ns worst setup slack (per-stage timing is width-independent); confirm OpenSTA
  copes with 16.8k instances.

### A64-2 — Matched-architecture CMOS-64 generator
- New `lsdl_lib/blocks/adder/gen_cmos_adder.py`: emits the **same systolic dataflow**
  in stock `gf180mcu_fd_sc_mcu9t5v0` cells, single-rail (CMOS inverts freely — no
  dual-rail tax): one DFF pipeline stage (`dffq_1`) per LSDL stage-pair + FA gates;
  carry advances 1 bit/cycle; outputs skewed identically (sum[i] @ cycle i+1).
- Reuse the cycle-accurate selftest pattern from `gen_lsdl_adder.py` (model DFF + gate
  update per tick; 200 random vectors).
- STA against the stock liberty
  (`/soe/czeng14/software/pdk/gf180mcuD/libs.ref/gf180mcu_fd_sc_mcu9t5v0/liberty/`):
  record CMOS f_max — the benchmark compares each flavor at its own measured speed
  (RO mode), so CMOS does not need to hit 1 GHz.

### A64-3 — Tester scale-up spec (T12 delta; spec only in this plan)
- Per adder instance: LFSR widened to 128 bits (a, b operands; dual-rail complements
  for the LSDL flavor produced by static inverters at the domain boundary),
  capture register 65 bits (sum + cout), RO-loopback mapping defined for the 64-bit
  datapath, cin/cinn driven from an LFSR bit.

### A64-4 — Plan-doc + task-list updates
- `phase1_cells_tapeout.md`: benchmark table (adder 16→64), area-budget table with the
  slot numbers above, slot decision recorded; pad budget unchanged (56 default suffices).
- Tasks: retitle T5 (PnR target = adder64), T6 (64-bit bit-exact reference, skewed-output
  aware), T10 (CMOS adder = matched generator, not behavioral synthesis), T12 (128-bit
  LFSR / 65-bit capture).

After A64, the existing roadmap resumes at **T5** (LibreLane PnR of the LSDL adder64
block), now with the 64-bit netlists as input.

## Critical files
- Reuse unchanged: `lsdl_lib/blocks/adder16/gen_lsdl_adder.py` (relocated only),
  `adder_lsdl.sdc`, `run_sta_adder.tcl` (path/env tweaks).
- New: `lsdl_lib/blocks/adder/gen_cmos_adder.py`, `adder64_lsdl.v`, `adder64_cmos.v`,
  `adder_cmos.sdc`, `run_sta_cmos.tcl`.
- Edit: `phase1_cells_tapeout.md` (benchmark + area + slot tables).

## Verification
- Selftest: 200 random vectors, both flavors, W=64 (plus W=16 regression for the CMOS
  generator).
- OpenSTA: LSDL-64 @ 1 GHz → TNS = 0; CMOS-64 → report achievable clock.
- Area report: generator cell counts × LEF areas vs the budget table (LSDL ≤ 2.3 mm²
  placed estimate; CMOS ≤ 1.4 mm²).

---

# L5 Liberty Generation — Detailed Plan

## Context

9 Wave 1 BASIC cells are physically signed off (0 DRC, block LVS clean, LEF+GDS frozen).
The next blocker is **Liberty (`.lib`) generation** — without it, no synthesis tool or
OpenSTA can use the cells, and the 16-bit adder LibreLane block cannot be assembled.

**What exists already**:
- `descriptor/lsdl_inv_x1.yaml` + `lsdl_nand2_x1.yaml` — the descriptor schema is proven
- `pvt_sweep/lsdl_inv_x1_pvt.json` + `lsdl_nand2_x1_pvt.json` — 45-point PVT data for 2 cells
- `testbench/tb_lsdl_nand4_x1.sp`, `tb_lsdl_nor4_x1.sp`, `tb_lsdl_aoi22_x1.sp` — full testbenches
- `scripts/pvt_sweep.py` — automated PVT runner (5 corners × 3 T × 3 VDD → JSON)
- `TEMPLATE_lsdl_cell.sp` — testbench authoring template

**What's missing**:
- `scripts/gen_liberty.py` — does not exist yet
- `scripts/gen_verilog_wrapper.py` — does not exist yet
- Descriptors for 7 cells (NAND3/4, NOR2/3/4, AOI21/22)
- Testbenches for NAND3, NOR2, NOR3, AOI21
- PVT JSON for 7 cells (NAND3/4, NOR2/3/4, AOI21/22)

## LSDL Liberty model decisions

LSDL cells are **positive-edge-triggered sequential** (precharge on CLK=0, evaluate on CLK=1).
The Liberty model is an `ff` block with `clocked_on: "CLK"` rising.

| Liberty attribute | Value | Rationale |
|---|---|---|
| `clocked_on` | `"CLK"` | Positive-edge triggered |
| `next_state` | e.g. `"!(A1 & A2)"` | Inverting Boolean function from descriptor |
| `timing_type (CLK→OUT)` | `rising_edge` | Output resolves after CLK rises (evaluate phase) |
| `cell_fall` | measured `tpd_eval` from PVT JSON | The real timing arc: CLK↑ → OUT↓ when n-tree conducts |
| `cell_rise` | `0.050 ns` constant | Precharge brings OUT high during CLK=0; referenced to CLK rising it appears near-zero; 50 ps is conservative |
| `setup_rising (A* vs CLK)` | `0.100 ns` | Inputs must be stable before CLK rises (during precharge). Conservative placeholder. |
| `hold_rising (A* vs CLK)` | `0.050 ns` | Inputs held through start of evaluate. Conservative. |
| `min_pulse_width_high (CLK)` | From PVT: `tpd_eval` at worst-case (SS/125°C) | Minimum evaluate window = time for OUT to settle |
| `min_pulse_width_low (CLK)` | `0.250 ns` | Minimum precharge window for dyn to recover to VDD at SS/125°C |
| `function` on OUT pin | Same as `next_state` | Needed for synthesis mapping |

**Key timing values from PVT data (TT, 5 V, 25 °C)**:
- `lsdl_inv_x1` `cell_fall` ≈ **213 ps** (from `lsdl_inv_x1_pvt.json`, typical/25°C/5.0V entry)
- `lsdl_nand2_x1` `cell_fall` ≈ **216 ps** (from `lsdl_nand2_x1_pvt.json`, typical/25°C/5.0V entry)
- Worst case (SS/125°C/4.75V): ~330 ps (INV), ~416 ps (NAND2) — both < 500 ps, so 1 GHz closes

## Implementation — 4 ordered steps

### Step 1 — Write gen_liberty.py + gen_verilog_wrapper.py

**File**: `lsdl_lib/scripts/gen_liberty.py`

Inputs:
- `descriptor/<cell>.yaml` — function, pins, drive, area estimate
- `pvt_sweep/<cell>_pvt.json` — 45-point timing data (or absent → use conservative fallback)

Logic:
1. Read descriptor YAML. Extract: `name`, `library`, `function`, `pins`, `drive`.
2. Read PVT JSON. Extract `tpd_eval_*` for the TT/25°C/5.0V entry as `cell_fall_tt`.
   - If JSON is missing: use a fallback table: `{inv: 0.213, nand2: 0.216, nand3: 0.260, nand4: 0.310, nor2: 0.200, nor3: 0.240, nor4: 0.280, aoi21: 0.250, aoi22: 0.280}` (conservative scaled estimates for the 7 cells without data until their PVT runs complete).
3. Emit Liberty text. Template:

```
library(lsdl_fd_sc_9t5v0) {
  technology (cmos);
  delay_model : table_lookup;
  nom_process : 1;
  nom_voltage : 5.00;
  nom_temperature : 25.00;
  time_unit : "1ns";
  voltage_unit : "1V";
  current_unit : "1mA";
  pulling_resistance_unit : "1kohm";
  leakage_power_unit : "1nW";
  capacitive_load_unit (1,pf);
  input_threshold_pct_rise : 50.0;
  input_threshold_pct_fall : 50.0;
  output_threshold_pct_rise : 50.0;
  output_threshold_pct_fall : 50.0;

  cell (<name>) {
    area : <width_um × 5.04>;   /* from LEF SIZE line */
    pin (CLK) { direction : input; clock : true; }
    pin (<A*>) { direction : input; capacitance : 0.005; }
    pin (OUT) {
      direction : output;
      function : "<function>";
      timing () {
        related_pin : "CLK";
        timing_type : rising_edge;
        cell_fall (scalar) { values ("<cell_fall_tt>"); }
        cell_rise (scalar) { values ("0.050"); }
        fall_transition (scalar) { values ("0.040"); }
        rise_transition (scalar) { values ("0.040"); }
      }
    }
    ff ("IQ","IQN") {
      clocked_on : "CLK";
      next_state : "<function>";
    }
    /* setup / hold of each data input vs CLK */
    /* repeated for each A* pin: */
    timing () {
      related_pin : "CLK";
      timing_type : setup_rising;
      rise_constraint (scalar) { values ("0.100"); }
      fall_constraint (scalar) { values ("0.100"); }
    }
    timing () {
      related_pin : "CLK";
      timing_type : hold_rising;
      rise_constraint (scalar) { values ("0.050"); }
      fall_constraint (scalar) { values ("0.050"); }
    }
    cell_leakage_power : 0.100;
    pin (VPWR) { direction : inout; pg_type : primary_power; }
    pin (VGND) { direction : inout; pg_type : primary_ground; }
  }
}
```

After L5-A: combine all 9 cells into a single
`lsdl_lib/lib/lsdl_fd_sc_9t5v0__tt_5v_25c.lib` for OpenSTA.

**File**: `lsdl_lib/scripts/gen_verilog_wrapper.py`

Reads descriptor YAML → emits `cells/lsdl_basic/<cell>.v`:
```verilog
/* lsdl_nand2_x1 — OUT = !(A1 & A2) — GF180MCU 5V LSDL, X1 drive */
`timescale 1ns/1ps
module lsdl_nand2_x1 (CLK, A1, A2, OUT, VPWR, VGND);
  input  CLK, A1, A2;
  output OUT;
  inout  VPWR, VGND;
endmodule
```
No logic body — synthesis uses this as a blackbox; Liberty provides timing.

### Step 2 — Write descriptors for 7 remaining cells

Clone `descriptor/lsdl_nand2_x1.yaml` for each. Change only:

| Cell | `function` | `pins` | `n_tree expr` | `stack_height` | `worst_case_eval_vector` |
|---|---|---|---|---|---|
| `lsdl_nand3_x1` | `!(A1 & A2 & A3)` | +A3 | `A1 & A2 & A3` | 3 | `{A1:1, A2:1, A3:1}` |
| `lsdl_nand4_x1` | `!(A1 & A2 & A3 & A4)` | +A3,A4 | `A1 & A2 & A3 & A4` | 4 | all inputs=1 |
| `lsdl_nor2_x1` | `!(A1 \| A2)` | A1,A2 | `A1 \| A2` (parallel) | 1 | `{A1:1, A2:1}` |
| `lsdl_nor3_x1` | `!(A1 \| A2 \| A3)` | A1,A2,A3 | parallel | 1 | all inputs=1 |
| `lsdl_nor4_x1` | `!(A1 \| A2 \| A3 \| A4)` | A1..A4 | parallel | 1 | all inputs=1 |
| `lsdl_aoi21_x1` | `!((A1 & A2) \| B)` | A1,A2,B | `(A1 & A2) \| B` | 2 | `{A1:1,A2:1,B:1}` |
| `lsdl_aoi22_x1` | `!((A1 & A2) \| (B1 & B2))` | A1,A2,B1,B2 | `(A1&A2)\|(B1&B2)` | 2 | all inputs=1 |

Artifacts paths follow the same pattern as lsdl_nand2_x1.yaml.

### Step 3 — Write testbenches + run PVT sweep for all 7 cells

**Testbenches needed** (4 new files from TEMPLATE):

- `tb_lsdl_nand3_x1.sp`: clone `tb_lsdl_nand4_x1.sp`, remove A4, adjust IC and measurements
- `tb_lsdl_nor2_x1.sp`: clone `tb_lsdl_nor4_x1.sp`, keep A1/A2 only; no charge-share stress (parallel tree)
- `tb_lsdl_nor3_x1.sp`: clone NOR4, keep A1/A2/A3
- `tb_lsdl_aoi21_x1.sp`: clone `tb_lsdl_aoi22_x1.sp`, collapse to 3 inputs (A1,A2,B)

`pvt_sweep.py` must also be extended with `PASS_CRITERIA` entries for these 7 cells. Pattern from NAND2:
```python
'lsdl_nand3_x1': {
    'tpd_eval_hl': {'max': 2.0e-9},
    'v_dyn_low_min': {'max': 0.5},
    'v_dyn_share_min': {'min': 3.5},   # charge-share on nint1, nint2
    'v_out_cyc3_min': {'max': 1.0},
    'v_out_cyc5_final': {'max': 0.5},
},
```

NOR cells use `tpd_eval_hl` (parallel n-tree, any input=1 → evaluates). No charge-share stress
(single-device depth). Drop `v_dyn_share_min` for NOR2/3/4.

AOI21/22 have internal nodes (series sub-stack); include `v_dyn_share_min`.

**Run commands** (in container via `run_in_container.sh`):
```bash
for cell in lsdl_nand3_x1 lsdl_nand4_x1 lsdl_nor2_x1 lsdl_nor3_x1 lsdl_nor4_x1 lsdl_aoi21_x1 lsdl_aoi22_x1; do
    python3 lsdl_lib/scripts/pvt_sweep.py $cell
done
```
Each cell: 45 sims × ~20 s = ~15 min. Total: ~105 min for all 7.

After this step, `gen_liberty.py` uses real PVT data for all 9 cells instead of fallback estimates.

### Step 4 — Generate .lib for all 9 cells + OpenSTA validation

**Generate**:
```bash
for cell in lsdl_inv_x1 lsdl_nand2_x1 lsdl_nand3_x1 lsdl_nand4_x1 \
            lsdl_nor2_x1 lsdl_nor3_x1 lsdl_nor4_x1 lsdl_aoi21_x1 lsdl_aoi22_x1; do
    python3 lsdl_lib/scripts/gen_liberty.py lsdl_lib/descriptor/${cell}.yaml
    python3 lsdl_lib/scripts/gen_verilog_wrapper.py lsdl_lib/descriptor/${cell}.yaml
done
# Combine into one library file:
python3 lsdl_lib/scripts/gen_liberty.py --merge-all \
    --output lsdl_lib/lib/lsdl_fd_sc_9t5v0__tt_5v_25c.lib
```

**Evaluation standard — the 5 acceptance gates**:

| Gate | Command | Pass criterion |
|---|---|---|
| **G1: Liberty parse** | `opensta -exit -cmd "read_liberty lsdl_fd_sc_9t5v0__tt_5v_25c.lib; exit"` | 0 errors |
| **G2: Cell count** | `get_lib_cells lsdl_fd_sc_9t5v0 > /dev/null` | All 9 cells present |
| **G3: Function check** | `get_lib_cell_property lsdl_nand2_x1 function OUT` | `!(A1 & A2)` |
| **G4: Timing smoke** | Synthesize 1-bit `y = !(a & b)` → `report_timing -path_type full` | Slack reported (not "inf") |
| **G5: 1 GHz closure** | Synthesize 4-bit adder → `report_timing` with `create_clock -period 1.0 CLK` | No negative slack at TT corner |

G4 and G5 use OpenSTA's `-read_verilog` flow with the Verilog wrappers + Liberty + LEF.

**Deliverable**:
- `lsdl_lib/lib/lsdl_fd_sc_9t5v0__tt_5v_25c.lib` — 9 cells, scalar timing, TT 5V 25°C
- `lsdl_lib/cells/lsdl_basic/*.v` — Verilog blackbox wrappers for all 9 cells
- All 5 gates pass (documented in `lsdl_lib/lib/SIGNOFF_L5.md`)

## Critical files

| File | Status | Role |
|---|---|---|
| `scripts/gen_liberty.py` | **Write (new)** | Descriptor + PVT JSON → .lib |
| `scripts/gen_verilog_wrapper.py` | **Write (new)** | Descriptor → .v blackbox |
| `descriptor/lsdl_{nand3,nand4,nor2,nor3,nor4,aoi21,aoi22}_x1.yaml` | **Write (7 new)** | Cell descriptors |
| `testbench/tb_lsdl_{nand3,nor2,nor3,aoi21}_x1.sp` | **Write (4 new)** | PVT testbenches |
| `scripts/pvt_sweep.py` | **Edit** | Add PASS_CRITERIA for 7 cells |
| `lib/lsdl_fd_sc_9t5v0__tt_5v_25c.lib` | **Generated output** | Combined Liberty for OpenSTA |
| `cells/lsdl_basic/*.v` | **Generated output** | Verilog wrappers |
| `lib/SIGNOFF_L5.md` | **Write** | Gate results documentation |

## What L5 unblocks

After all 5 gates pass:
- **16-bit adder LibreLane block** can be assembled (Liberty + LEF + GDS all present)
- **OpenSTA** can report timing slack on the adder
- **Synthesis** (Yosys/OpenLane) can map RTL to LSDL cells

## Deferred to L5-B (after adder validation)

- Full lookup tables (replace scalars with 7×7 slew×cap tables) from the PVT data
- Measured setup/hold (dedicated testbench variant per cell)
- Accurate `cell_rise` delay (precharge characterization vs CLK falling)
- Per-corner Liberty files (SS, FF) for sign-off STA

---

## Context

The original build plan used a two-clock (PHI_E / PHI_L) cell model with an external static-latch stage and an LSSD-style scan network. After reading Belluomini et al., *Limited switch dynamic logic circuits for high-speed low-power circuit design* (IBM J. Res. & Dev. 50:2/3, 2006) — the original LSDL paper — the architecture must change to match what the paper actually defines:

- **Single clock per LSDL cell.** The latch is internal to the cell. The same `Clk` drives the precharge PMOS, foot NMOS, header NMOS, and cut-feedback PMOS. There is no separate latch clock.
- **L1/L2 pipeline (paper Fig. 2a).** Two interleaved chip-level clocks `C1` and `C2` alternate between consecutive pipeline stages. Each cell consumes one of the two; consecutive stages alternate.
- **Complex output gates (paper Fig. 3a, NAND form only).** Two evaluation trees feed a NAND-form predriver in one cell, replacing what would have been two separate cells with a static AND in between.
- **No scan.** Per user direction. Test pattern infrastructure becomes on-die LFSR + capture register per benchmark, read out through pads.

This brings the cell semantics in line with the original LSDL definition, makes Liberty modeling simple (each cell is a positive-edge flop on `Clk`), and removes ~25% of the cell count by dropping the SDFFRS_LSDL scan-latch family.

The intended outcome is a GF180MCU tapeout containing six benchmarks (three circuits × LSDL vs CMOS), each with a power-isolated domain, an LFSR-driven functional mode, and a ring-oscillator mode for frequency/power measurement.

## Paper alignment summary

| Paper element | Maps to in build plan |
|---|---|
| Fig. 1 — Basic LSDL latch | `LSDL_BASIC` cell template. Single Clk; integrated latch (Predriver p/n, Header device, Cut feedback, Feedback p/n, Output driver p/n). |
| Fig. 2(a) — L1/L2 pipeline | Two-phase clocking. Each cell instance bound to C1 *or* C2; alternating stages. |
| Fig. 3(a) — NAND complex output | `LSDL_NAND_CMPLX` cell template. Two evaluation trees combine via NAND in predriver. NOR form (Fig. 3b) **not** built. |
| Fig. 5(a) — Footless | **Not built.** All cells include Foot device (Fig. 1 form). |
| Fig. 6 — Keeper / Minder | **Not built.** Paper states 180 nm tolerates leakage without keeper/minder if evaluate period is bounded; we enforce that bound in the clock generator. |
| Fig. 4 — Domino front-end + delayed clock | **Wave 2 stretch only.** Not in initial library. |

## Cell-interface specification (replaces prior PHI_E/PHI_L spec)

Per-cell pins:

| Pin | Direction | Function |
|---|---|---|
| `Clk` | input | The cell's bound clock. At synthesis, instance is connected to C1 or C2 depending on pipeline stage parity. |
| `IN[]` | input | Logic inputs feeding the n-FET evaluation tree(s). For LSDL_NAND_CMPLX, split into two groups feeding two trees. |
| `Out` | output | Driven by Output driver p/n. Reflects evaluated value during evaluate, held by internal feedback during precharge. |
| `VPWR` | power | 5 V domain supply (per-domain gated). |
| `VGND` | ground | Shared ground. |

Internal devices (every cell):
- Precharge device (PMOS, gate = Clk)
- n-FET evaluation tree(s) (function-specific)
- Foot device (1) (NMOS, gate = Clk)
- Predriver p (PMOS, gate = dyn)
- Predriver n (NMOS, gate = dyn, source via Header device)
- Header device (NMOS, gate = Clk)
- Cut feedback (PMOS, gate = Clk) — **included** for n/p ratio robustness per paper
- Feedback device p (PMOS, gate = Out)
- Feedback device n (NMOS, gate = Out)
- Output driver p (PMOS, gate = out_b)
- Output driver n (NMOS, gate = out_b)

For LSDL_NAND_CMPLX: dyn1 and dyn2 each have their own Precharge device and Foot device; both feed into the NAND-form complex output gate per Fig. 3(a).

Sizing constraint (paper, page 278): cell must be sized so that dynamic-node predriver switches fast enough to keep the glitch on `out_b` below 10% of supply. This becomes a hard SPICE check in the characterization script.

## Two-phase clock generator

External clock pad → on-die two-phase generator → two global clock trees C1 and C2.

**Topology:** C1 and C2 both 50% duty cycle, 180° nominal phase relationship, with a programmable non-overlap gap inserted at every transition.

**Programmability:** 5-bit non-overlap control register (~10 ps step at TT, 5 V, 25 °C; range 10–320 ps). Bits delivered via pads, not scan. Latched at reset and held.

**Generator implementation:** input clock buffered → divide-by-2 to produce 50% duty raw C1 and C1_bar → each fed through a programmable delay-chain inserting falling-edge skew, producing C1 and C2 with the required non-overlap at both rising and falling edges. Built in static CMOS (gf180mcu_fd_sc_mcu9t5v0), not LSDL.

**No PLL, no on-die oscillator** — external clock pad is the sole reference. Confirmed against wafer.space and GF180MCU PDK that no clock generator IP is available.

## Cell library

### Wave 0 (disproof gate, ~4 weeks)

| Cell | n-tree function | Purpose |
|---|---|---|
| `LSDL_INV_X1` | single NMOS, gate = A | Smallest possible LSDL cell. Validates Fig. 1 topology in isolation. |
| `LSDL_NAND2_X1` | two NMOS in series | Validates stack-of-2 evaluate path + charge sharing on a 1-node internal stack. |
| Two-phase clock generator (static CMOS) | — | Wave 0 deliverable for early integration test. |

Wave 0 exit criteria:
- DRC clean (Magic + GF180MCU tech file)
- LVS clean (Netgen against hand-source SPICE)
- SPICE characterization: TT/SS/FF/SF/FS × 4.75–5.25 V × {-40, 25, 125} °C
- Glitch on `out_b` < 10% VDD across all corners (paper sizing rule)
- 1-cell LibreLane integration smoke test passes (place, route, GDS extracts cleanly)
- OpenSTA accepts the Liberty (Pattern: flop on Clk rising; spike test)

### Wave 1 (mapper cells, ~6–8 weeks after Wave 0)

LSDL_BASIC variants for common Boolean functions (each is a different n-tree):

| Cell | n-tree | For benchmark |
|---|---|---|
| `LSDL_AND2/3/4` | 2/3/4 NMOS in series | Adder, mux, encoder |
| `LSDL_OR2/3/4` | 2/3/4 NMOS in parallel | Adder, encoder |
| `LSDL_AOI21_X1` | (A·B) + C as AND-OR tree | Adder carry mapping |
| `LSDL_AOI22_X1` | (A·B) + (C·D) | Adder, mux |
| `LSDL_MUX2_X1` | one bit of a wide mux | Mux benchmark building block |

LSDL_NAND_CMPLX variants (Fig. 3a; two trees):

| Cell | tree1 / tree2 | For benchmark |
|---|---|---|
| `LSDL_NAND_CMPLX_X1` | both = single NMOS | Generic 2-input gate with merged latch |
| `LSDL_NAND_CMPLX_AOI` | tree1 = (A·B), tree2 = (C·D) | Adder hot path |

Wave 1 exit criteria: all Wave-0 criteria, plus a 16-bit adder netlist placed/routed in LibreLane against this library, DRC/LVS clean, post-PEX SPICE shows the adder meets the paper sizing rule across all corners.

### Wave 2 (benchmark cells, ~6–8 weeks after Wave 1)

| Cell | Purpose |
|---|---|
| `LSDL_OR_TREE_4/8/16` | wide-OR n-tree (parallel NMOS) for the priority-encoder chain |
| `LSDL_MUX_SEG_8/16` | one slice of the segmented wide-mux | 
| `LSDL_PRI_ENC_CELL` | priority-encoder stage with leading-zero output |
| Two-phase transfer cell | C1↔C2 boundary handling if any benchmark needs it |

Wave 2 segmentation gate: the wide-mux strategy (number of segments, drive sizing per segment) is locked using dynamic-node-length-budget numbers measured in Wave 0/1. No Wave-2 layout begins until that budget is in hand.

**Dropped from original plan:** dual-rail XOR, footless variants, scan-latch family, asymmetric precharge:evaluate clock driver, programmable PHI_E/PHI_L cells, power-gate-aware precharge driver (replaced — see Power-gating below).

## Liberty modeling (replaces Pattern β)

Each LSDL cell modeled as a **positive-edge-triggered flop on Clk**:

```liberty
cell (LSDL_NAND2_X1) {
  pin (Clk) { direction: input; clock: true; }
  pin (A1) { direction: input; ... }
  pin (A2) { direction: input; ... }
  pin (Out) { direction: output; function: "!(A1 & A2)"; }
  ff (IQ, IQN) {
    clocked_on: "Clk";
    next_state: "!(A1 & A2)";
  }
  timing(Out) { related_pin: "Clk"; timing_type: rising_edge; ... }
  timing(A1) { related_pin: "Clk"; timing_type: setup_rising; ... }
  timing(A1) { related_pin: "Clk"; timing_type: hold_rising; ... }
  min_pulse_width_high (Clk) ...
  min_pulse_width_low  (Clk) ...
  internal_power () { /* split: precharge_power + evaluate_power */ }
}
```

Setup time of inputs to Clk rising = (worst-case eval delay for the evaluating vector) + (latch input setup). Hold = latch input hold (small). `min_pulse_width_high` is the minimum evaluate window; `min_pulse_width_low` is the minimum precharge window — paper's leakage-tolerance limit at 180 nm goes here.

C1 and C2 are declared as **two separate clocks in SDC**, both derived from the master external clock. OpenSTA handles them as two independent clock domains; the L1/L2 pipeline structure means data crosses from C1-clocked cells to C2-clocked cells one stage at a time, which OpenSTA models cleanly with standard multi-clock setup/hold.

The Wave-0 Liberty/OpenSTA spike (issue #5 in the prior walkthrough) is dramatically simpler than under the dual-clock model. Spike still gates Wave 1.

## Measurement infrastructure (replaces scan)

Per benchmark (×6 instances total):

- **LFSR input driver:** ~32-bit LFSR built in static CMOS (gf180mcu_fd_sc_mcu9t5v0), seeded from 4 reset-time pads (16-bit seed × 2 banks), clocked by the chip's master clock. Drives the benchmark's primary inputs.
- **Output capture register:** static-CMOS shift register at the benchmark output, parallel-loaded each functional cycle, serialized out to a single pad (1 pad per benchmark × 6 = 6 capture-output pads).
- **Ring-oscillator mode:** each benchmark's output looped back through an enable-mux to its input, output frequency divided (÷256) to a pad. 6 RO-output pads.

LFSR and capture register are static CMOS, not LSDL — keeps test infrastructure independent of the cell library under test.

## Power gating

Still 6 domains (3 benchmarks × LSDL/CMOS). Domain control replaced:

- **6 enable pads** (one per domain). High = domain powered. Avoids the scan-loaded gating register from the prior plan.
- **Header-PMOS sizing** per domain, oversized to keep VDD droop under 100 mV at full activity.
- **One always-on domain** for clock generator, LFSRs, capture registers, and pad ring.
- **LSDL wake-up:** after a domain powers up, run the master clock for ≥10 cycles before enabling that domain's LFSR (ensures all dynamic nodes precharge to known state). Documented in bring-up procedure.

## Pad budget (revised, no scan)

| Function | Count |
|---|---|
| `VDD_<domain>` × 7 (6 benchmark + always-on) | 7 |
| `GND` | 6 |
| External clock in | 1 |
| Reset | 1 |
| LFSR seed in (16-bit serial load via shared signal + load enable) | 2 |
| Domain enables × 6 | 6 |
| Clock-gen non-overlap control bits × 5 | 5 |
| Capture-register serial out × 6 | 6 |
| Ring-oscillator outputs × 6 | 6 |
| **Total** | **40** |

Fits the default 56-pad ring with 16 pads of slack.

## Critical files to create / modify

Repository layout under `/mada/users/czeng14/projects/brainstorm/domino/`:

- `phase1_cells.md` — significant rewrite. Drop PHI_E/PHI_L language, drop scan, restate cell family in paper-Figure terms. Sections "Task 3 — cell family" and "Task 5 — Liberty/LEF" both substantially rewritten.
- `phase1_cells_tapeout.md` — drop scan infrastructure, replace with LFSR + capture; correct row-height numbers (7T=3.92 µm, 9T=5.04 µm); update measurement infrastructure section; update pad-budget table.
- `lsdl_lib/` (new directory) — cell library workspace.
  - `lsdl_lib/cells/lsdl_basic/lsdl_inv_x1.mag` — Wave 0 cell, hand layout
  - `lsdl_lib/cells/lsdl_basic/lsdl_nand2_x1.mag` — Wave 0 cell, hand layout
  - `lsdl_lib/cells/lsdl_basic/lsdl_nand2_x1.spice` — hand-source SPICE
  - `lsdl_lib/cells/lsdl_basic/lsdl_nand2_x1.lib` — Liberty
  - `lsdl_lib/cells/clkgen/two_phase_gen.mag` — static-CMOS two-phase generator
- `lsdl_lib/scripts/` —
  - `clk_ratio_characterize.py` — per-cell SPICE wrapper measuring (t_pre,min, t_eval,min, charge-sharing dip, glitch < 10% VDD)
  - `gen_liberty.py` — cell-descriptor → Liberty emitter
  - `gen_verilog_wrapper.py` — cell-descriptor → Verilog blackbox
- `lsdl_lib/descriptor/` — single-source-of-truth per cell (YAML), drives Liberty + Verilog + characterization

Existing patterns to reuse:
- Use **Magic + Netgen** (LibreLane sign-off path) for DRC/LVS.
- Use the **wafer.space project template** ([`wafer-space/gf180mcu-project-template`](https://github.com/wafer-space/gf180mcu-project-template)) as the LibreLane integration baseline. Drop our LSDL `.lib`, `.lef`, `.gds`, Verilog wrappers into its SCL config.
- Use the **upstream `gf180mcu_fd_sc_mcu9t5v0`** library unchanged for the CMOS comparison baseline and for the LFSR/capture/clock-gen static-CMOS infrastructure.
- LSDL cells live in a separate library `lsdl_fd_sc_9t5v0` sharing SITE `GF018hv5v_green_sc9` (row height 5.04 µm).

## Verification

End-to-end:

1. **Cell-level (per cell, per wave):**
   - Magic DRC clean (using `gf180mcu.tech`)
   - Netgen LVS clean against hand-source SPICE
   - ngspice characterization passes paper sizing rule (glitch < 10% VDD)
   - Liberty parses cleanly in OpenSTA
2. **Wave-0 gate:** 1-cell LibreLane smoke test (LSDL_NAND2_X1 in a trivial RTL design) places, routes, DRC/LVS clean, OpenSTA reports finite slack.
3. **Wave-1 gate:** 16-bit adder, LSDL version, placed+routed in LibreLane; post-PEX SPICE confirms paper sizing rule; functional simulation against bit-exact reference.
4. **Wave-2 gate:** all three benchmarks placed+routed for both LSDL and static CMOS; per-PEX dynamic-rule checker (charge sharing, non-overlap margin) clean.
5. **Tapeout sign-off:** full chip DRC/LVS through LibreLane; functional sim of full chip including LFSR + capture + ring-osc paths.

The two distinct outcomes the chip will demonstrate:
- **Library proof-of-concept:** the 16-bit adder works in both CMOS and LSDL flavors, placed and routed through LibreLane, with measurable functional correctness via LFSR/capture.
- **Domino advantage:** the 32-bit priority encoder demonstrates the structural delay advantage (no PMOS in the evaluate path on deep OR chains); the 32-way mux reproduces the paper's published power/area advantage on wide select logic.

## Decisions captured (this walkthrough)

1. Clock model: single `Clk` per cell, two interleaved global clock trees C1/C2 (Fig. 2a L1/L2).
2. Layout tool: Magic + Netgen authoritative; KLayout informational.
3. Row site: `GF018hv5v_green_sc9` (5.04 µm); separate library `lsdl_fd_sc_9t5v0`.
4. Complex output gates: NAND form only (Fig. 3a).
5. Non-overlap C1/C2 with 5-bit programmable register, fixed 50% duty.
6. No scan; LFSR + capture register + ring-osc for measurement.
7. Footed n-trees only.
8. No keeper, no minder (paper supports this at 180 nm).
9. Cut feedback device included (paper recommends for robustness).
10. Liberty pattern: positive-edge flop on Clk rising.

## Remaining decisions (deferred — can be locked at end of Wave 0)

- Wave 0 schedule pin (target date) — depends on staffing.
- Whether `LSDL_NAND_CMPLX_X2`, `_X4` drive strengths are needed or single-strength suffices (depends on Wave-1 16-bit-adder load profile).
- Whether the C1↔C2 transfer cell (Wave 2) is needed; only required if any benchmark has data crossing between C1- and C2-clocked stages within one logical operation.
- Whether to add Fig. 4 (delayed-clock domino front end) as a Wave-2 stretch goal — defer decision to end of Wave 1.

---

# DRC + LVS Fix Plan for `lsdl_inv_x1`

## Context

Current `lsdl_inv_x1.mag` is placement-only: 12 FETs at 1.8 µm pitch in PMOS-top/NMOS-bottom arrangement, unified n-well, VPWR/VGND M1 rails. **KLayout DRC reports 14 violated rule classes (47 Magic errors); Netgen LVS has not been run.** The structural skeleton is sound but is missing four things every working GF180MCU 5V standard cell requires:

1. **5V device marker** (`dualgate` layer) — without it the PDK assumes 3.3V devices, triggering DV.8 and the wrong well-stack rules.
2. **Well/substrate taps** for latch-up immunity (DF.13_MV / DF.14_MV require P+/N+ taps within 15 µm of every FET).
3. **M1 routing of all 12 internal nets** plus VPWR/VGND source connections.
4. **M1 pin labels** for `A`, `Clk`, `Out`, `VPWR`, `VGND` (required for LVS).

This plan eliminates all DRC violations and gets Netgen LVS clean against `lsdl_inv_x1.spice`. Restructures placement to **share diffusion between adjacent same-net FETs** (matching how stock GF180MCU 9T cells are built), shrinking the cell from ~12 µm to ~8 µm wide and auto-resolving most DF.3a_MV (MV diff spacing) violations.

The outcome is the first DRC+LVS-clean LSDL cell, closing Wave 0 for real and establishing the proven layout pattern for the ~25 cells to follow in Wave 1 / Wave 2.

## Authoritative DRC rules (from Phase 1 exploration of PDK rule decks)

| Rule | Limit | Means | Hit by us? |
|---|---|---|---|
| DV.8 | 0.4 µm Dualgate enclose Poly2 | 5V gate-oxide marker | yes |
| DF.3a_MV | ≥ 0.36 µm | MV diff spacing | yes — shared diff fixes |
| DF.4c_MV | ≥ 0.6 µm | N-well overlap of PCOMP | yes |
| DF.6_MV | ≥ 0.4 µm | COMP extends beyond poly (S/D overhang) | possibly |
| DF.13_MV | ≤ 15 µm | Max distance from PCOMP to N-well N+ tap | yes — taps needed |
| DF.14_MV | ≤ 15 µm | Max distance from NCOMP to P-substrate P+ tap | yes — taps needed |
| DF.16_MV | ≥ 0.6 µm | N-well to NCOMP spacing | yes |
| CO.2a | ≥ 0.25 µm | Min contact spacing | yes |
| M1.2a | ≥ 0.23 µm | Min M1 spacing | yes — routing fixes |
| M1.3 | ≥ 0.1444 µm² | Min M1 area | yes — routing fixes |
| NW.4 | LVPWELL must not overlap nwell outside DNWELL | Well-mixing | yes — likely Dualgate fix |
| LPW.12 | LVPWELL forbidden under nwell | Well-mixing | yes — likely Dualgate fix |
| PL.1a / PL.2_MV / PL.3a / PL.9 | Poly width / spacing / extension rules | Poly geometry | yes |

Source: `/soe/czeng14/software/pdk/gf180mcuD/libs.tech/klayout/drc/rule_decks/{comp,contact,metal1,nwell,lvpwell,dualgate}.drc`.

## Approach: 5-phase incremental fix

Each phase produces a renderable + DRC-runnable state. We iterate phase-by-phase, reading the rendered PNG after each one so I can spot wrong patterns visually before continuing.

### Phase A — 5V Dualgate marker (closes DV.8, likely LPW.12, NW.4)

Paint a single `dualgate` rectangle covering all transistors with ≥ 0.4 µm enclosure on every side. This marks the cell as 5V to the PDK. Likely also resolves the LV-PWell conflict (DV.8 / NW.4 / LPW.12) because the PDK auto-paints `lvpwell` only outside `dualgate`-marked regions.

Pattern:
```tcl
# Cover from 0.2um inside the cell on each side to 0.2um inside the other side.
paint_box dualgate \
    [expr {$X_MIN - 0.4}] [expr {$Y_NMOS - max_W_n/2 - 0.4}] \
    [expr {$X_MAX + 0.4}] [expr {$Y_PMOS + max_W_p/2 + 0.4}]
```

**Verification:** KLayout DRC, expect DV.8 / LPW.12 / NW.4 to disappear.

### Phase B — Restructure to shared-diff placement (closes DF.3a_MV, DF.6_MV, halves cell width)

Rebuild `lsdl_inv_x1_layout.tcl` so adjacent same-net FETs **share their abutting diffusion**, matching stock GF180MCU 9T cells. New FET ordering aims to maximize shared-diff opportunities.

**PMOS row reorder (left → right):**
| Slot | FET | left side net | right side net | shares left? | shares right? |
|---|---|---|---|---|---|
| 0 | XPRE | VPWR | dyn | — | dyn → XPDRVP |
| 1 | XPDRVP (2 fingers) | dyn | dyn | yes (dyn) | dyn → XCUTFB |
| 2 | XCUTFB | dyn | cut_fb_src | yes (dyn) | cut_fb_src → XFBP |
| 3 | XFBP | cut_fb_src | VPWR | yes | — |
| 4 | XODRVP | VPWR | Out | — | — |

Wait — XCUTFB's actual nets are different. Re-check from `lsdl_inv_x1.spice`:
- XCUTFB: drain=out_b, gate=Clk, source=cut_fb_src
- XFBP: drain=cut_fb_src, gate=Out, source=VPWR

So XCUTFB and XFBP share `cut_fb_src` — yes can merge. XPRE and XPDRVP share `dyn` (XPRE drain = dyn = XPDRVP gate, but gate is poly not diff). So XPRE↔XPDRVP can't share diff. Re-derive sharing pairs from actual spice during implementation.

**NMOS row reorder:** similar analysis from `lsdl_inv_x1.spice`. Pairs that share diff:
- XPDRVN ↔ XHDR (XPDRVN.source = hdr_src = XHDR.drain)
- XFOOT ↔ XNTREE (XFOOT.drain = foot_top = XNTREE.source)
- All VGND-tied sources can be in pairs

Layout: PMOS in n-well, NMOS in p-sub, gates aligned vertically where possible for cleaner clock routing. Place FETs without gaps where they share diffusion; insert 0.36 µm spacing only where they don't.

Expected: cell width drops from ~12 µm → ~8 µm; DF.3a_MV violations drop to zero on shared edges.

**Verification:** render PNG, visually confirm diffusion merges look correct. KLayout DRC; DF.3a_MV count should drop substantially.

### Phase C — Well + substrate taps (closes DF.13_MV, DF.14_MV, DF.4c_MV, DF.16_MV)

Add **N+ taps in n-well** (tied to VPWR) and **P+ taps in p-substrate** (tied to VGND). Pattern from stock `gf180mcu_fd_sc_mcu9t5v0__inv_1`:
- N-well taps: small mvndiff islands inside the n-well, just below the VPWR rail. Wired to rail via M1.
- P-substrate taps: small mvpdiff islands above the VGND rail. Wired to rail via M1.

For our ~8 µm cell, **2 taps of each type are sufficient** (15 µm DF.13_MV / DF.14_MV limit is well over the cell width). Place at:
- Left-end tap pair (x ≈ 0.5 µm)
- Right-end tap pair (x ≈ cell_width - 0.5 µm)

Adjust n-well rectangle to extend ≥ 0.6 µm beyond the rightmost PMOS diffusion (DF.4c_MV) and stay ≥ 0.6 µm from NMOS diffusion (DF.16_MV).

**Verification:** KLayout DRC, expect DF.7 / DF.8 / DF.13_MV / DF.14_MV / DF.4c_MV / DF.16_MV / NW.1a to disappear.

### Phase D — M1 routing of all internal nets (closes M1.2a, M1.3, CO.2a)

Route 9 internal nets in M1, sized to satisfy M1 minimum-area + spacing rules:

| Net | Connects | Routing strategy |
|---|---|---|
| VPWR | top rail ↔ PMOS sources, N-well taps | M1 stubs from rail down to each source diff contact |
| VGND | bottom rail ↔ NMOS sources, P-sub taps | M1 stubs from rail up to each source diff contact |
| Clk | gates of XPRE, XFOOT, XHDR, XCUTFB | M1 horizontal stripe spanning the gate-contact M1 of those 4 FETs |
| A | gate of XNTREE | short M1 stub to a pin patch on the cell-boundary track |
| dyn | drain XPRE, drain XNTREE, gates XPDRVP & XPDRVN | M1 wire spanning the column of these FETs vertically |
| out_b | drain XPDRVP, drain XPDRVN, drain XCUTFB, drain XFBN, gates XODRVP & XODRVN | M1 horizontal in the middle of the cell |
| cut_fb_src | XFBP.drain ↔ XCUTFB.source | short M1 between adjacent FETs (or shared diff if Phase B merged) |
| hdr_src | XPDRVN.source ↔ XHDR.drain | short M1 (or shared diff) |
| foot_top | XNTREE.source ↔ XFOOT.drain | short M1 (or shared diff) |
| Out | drain XODRVP, drain XODRVN, gates XFBP & XFBN, output pin | M1 spanning output column |

After routing, M1.3 (min-area) violations vanish (no more isolated gate patches) and M1.2a (spacing) needs only the rails-to-gate-contact gaps verified.

**Verification:** KLayout DRC clean. Cross-check by extracting and visually walking each net in the rendered PNG.

### Phase E — Pin labels + LVS (gets LVS clean)

Place Magic `port make` labels on M1 at appropriate positions:
- `A` on the A input M1 stub (left side of cell, at standard pin-access Y)
- `Clk` on the Clk M1 stripe (top access track)
- `Out` on the output M1 column (right side)
- `VPWR`, `VGND` on the rails (full-width labels)

Then:
1. Run Magic's `ext2spice` to produce extracted `.spice` netlist.
2. Run `netgen -batch lvs` comparing the extracted netlist against the hand-source `lsdl_inv_x1.spice`.
3. Iterate any mismatches per the project's `debug-lvs` skill (most likely: pin name mismatches, parallel-device merging, missing taps).

**Verification:** Netgen reports "Cell lsdl_inv_x1 -- Cells match" (or equivalent).

## Critical files to modify

- `lsdl_lib/cells/lsdl_basic/lsdl_inv_x1_layout.tcl` — main edit target across all 5 phases. Add procs for:
  - `paint_dualgate` (Phase A)
  - Reordered placement based on shared-diff analysis (Phase B)
  - `paint_tap` for N+ / P+ tap regions (Phase C)
  - `route_m1` for net wiring (Phase D)
  - `place_port` for M1 pin labels (Phase E)
- `lsdl_lib/scripts/build_layout.sh` — extend to also invoke Netgen LVS after Phase E
- `lsdl_lib/cells/lsdl_basic/lsdl_inv_x1.spice` — likely unchanged, but pin name capitalization may need to match Magic's extraction

## Files referenced (read-only)

- `/soe/czeng14/software/pdk/gf180mcuD/libs.ref/gf180mcu_fd_sc_mcu9t5v0/mag/gf180mcu_fd_sc_mcu9t5v0__inv_1.mag` — reference layout pattern (taps, rails, well structure)
- `/soe/czeng14/software/pdk/gf180mcuD/libs.tech/klayout/drc/run_drc.py` — DRC sign-off runner
- `/soe/czeng14/software/pdk/gf180mcuD/libs.tech/netgen/setup` — Netgen setup for GF180MCU
- `.claude/skills/lsdl-magic-headless-layout/SKILL.md` — gotchas (units, bbox parsing, getcell alignment, load -force)
- `.claude/skills/debug-drc/SKILL.md` — DRC triage methodology
- `.claude/skills/debug-lvs/SKILL.md` — LVS mismatch debugging

## Verification (end-to-end test)

After Phase E completes:

```bash
# Build the cell.
./lsdl_lib/scripts/build_layout.sh

# Run KLayout DRC sign-off.
./lsdl_lib/scripts/run_in_container.sh "
  python3 /soe/czeng14/software/pdk/gf180mcuD/libs.tech/klayout/drc/run_drc.py \
    --path=/mada/users/czeng14/projects/brainstorm/domino/lsdl_lib/cells/lsdl_basic/lsdl_inv_x1.gds \
    --topcell=lsdl_inv_x1 --variant=D --run_mode=flat --no_offgrid \
    --run_dir=/soe/czeng14/projects/brainstorm-domino-tmp/drc_runs --mp=4
"
# Expected: 'Klayout DRC run is clean.'

# Run Netgen LVS (after adding LVS step to build_layout.sh).
./lsdl_lib/scripts/run_in_container.sh "
  cd /mada/users/czeng14/projects/brainstorm/domino/lsdl_lib/cells/lsdl_basic && \
  magic -dnull -noconsole -rcfile /soe/czeng14/software/pdk/gf180mcuD/libs.tech/magic/gf180mcuD.magicrc \
    -T gf180mcuD <<EOF
load lsdl_inv_x1
extract all
ext2spice lvs
ext2spice -o lsdl_inv_x1_extracted.spice
quit -noprompt
EOF
"
./lsdl_lib/scripts/run_in_container.sh "
  netgen -batch lvs '/mada/users/czeng14/projects/brainstorm/domino/lsdl_lib/cells/lsdl_basic/lsdl_inv_x1_extracted.spice lsdl_inv_x1' \
                    '/mada/users/czeng14/projects/brainstorm/domino/lsdl_lib/cells/lsdl_basic/lsdl_inv_x1.spice lsdl_inv_x1' \
                    /soe/czeng14/software/pdk/gf180mcuD/libs.tech/netgen/gf180mcuD_setup.tcl
"
# Expected: 'Cells match uniquely.'
```

Estimated time: 4-6 hours of focused work, iterating phase by phase with PNG renders + DRC runs after each.

## Plan-doc edits to make (after this Track is complete)

Update `lsdl-magic-headless-layout` skill (`.claude/skills/lsdl-magic-headless-layout/SKILL.md`) with:
- "Phase A-E sequence for a DRC+LVS-clean cell" as a section
- Shared-diff placement TCL pattern (after Phase B is proven)
- Magic ext2spice + Netgen LVS one-liner (after Phase E is proven)

This skill becomes the template for the remaining ~25 cells in the library.

---

# Continued DRC iteration: Skill update + 9 remaining rule classes

## Context

The Phase A-E plan above produced a layout with 9 remaining KLayout DRC rule classes (down from 33 worst-case). The remaining rules each need specific knowledge that wasn't in the original plan: implant-layer naming, tap-cell strategy, well-overhang convention, the limit of subcell-based diff "sharing", and KLayout-vs-Magic DRC disagreement. This sub-plan captures every gotcha discovered during iteration and gives a concrete rule-by-rule attack to close the remaining 9 rule classes.

## Part 1 — Skill update (`lsdl-magic-headless-layout/SKILL.md`)

Add these sections to the skill:

### New section: "Hard-won lessons from the first cell"

**A. Subcell-based "shared diffusion" doesn't actually merge diffs.**
The subcell + `getcell` pattern places each FET as an independent instance. Each carries its own private diff polygon. At pitch < ~1.5 µm those polygons OVERLAP rather than MERGE — Magic treats them as electrically connected (good for LVS) but DRC sees separate polygons spaced impossibly close (bad for DF.3a_MV / DF.4c_MV). True diff sharing requires **painting diff at the top cell level**, not via subcells. For Wave 0 we accept ≥1.7 µm pitch (no real sharing) and revisit top-cell diff painting for Wave 1.

**B. The cell relies on neighbor cells for well continuity.**
Stock GF180MCU 9T cells have **n-well overhanging the cell top boundary** (y > 5.04 µm) and **p-well overhanging the bottom** (y < 0). Cells abutting in a row fuse their wells. For standalone-cell DRC, paint the wells extending past the cell boundary so the well-overlap rules (DF.4c_MV, DF.7) and well-spacing rules (DF.16_MV, DF.8) pass on the cell in isolation.

**C. Substrate / well taps are NOT in functional cells; they live in fillers + endcaps.**
The stock library has `__endcap` and `__fill_{1,2,4,...}` cells with tap regions. Functional cells like `__inv_1` have **no taps**. DF.13_MV / DF.14_MV (max 15 µm to nearest tap) **fail in standalone DRC** for any functional cell; they pass at chip level after PnR places fillers. Two project options:
   1. Replicate this — skip in-cell taps; treat DF.13_MV/14_MV as chip-level rules.
   2. Add in-cell taps for standalone sign-off. Requires the full implant-layer stack (see D).

**D. P+ / N+ implant layer names: `mvnsd` and `mvpsd`.**
For 5V devices, the medium-voltage implant markers are:
- `mvnsd` — N+ S/D implant (over n-active in p-well for NMOS S/D OR over n-active in n-well for N+ tap)
- `mvpsd` — P+ S/D implant (over p-active in n-well for PMOS S/D OR over p-active in p-well for P+ tap)
The `_draw` procs auto-paint these for FET S/D. For manual taps you must paint them explicitly; otherwise the implant rules (PP.3d, NP.5b, etc.) cascade — that's why my first tap attempt went from 12 → 33 violated rule classes.

**E. Dualgate is auto-derived from device layers, NOT paintable.**
Magic's tech file has `layer DUALGATE` only in the CIFOUTPUT section, with `bloat-or` rules deriving dualgate from `allndiffmv`/`allpdiffmv`. The grow amount (`grow 400` in the tech) may produce less than the required 0.4 µm enclosure for poly contacts that extend beyond diff. Two paths to satisfy DV.8:
   1. Ensure poly contacts don't extend beyond the active region (FET subcell modification — invasive).
   2. Paint a manual `mvactive` overlay that triggers extra dualgate. Untested but more contained.
Neither is pretty. For Wave 0 we may need to accept DV.8 marginal failures and document the tech-file gap.

**F. Magic's `drc list count total` is unreliable in batch mode.**
The count after `drc check ; drc catchup` differs between fresh-build runs (110+) and load-from-disk runs (0). KLayout DRC is the authoritative truth. Stop reading Magic's DRC count except as a smell test.

**G. `cellname create` collides with auto-loaded `.mag` files in CWD.**
Already in the skill. Restated: use `load <name> -force` for any cell that might be rebuilt.

**H. Magic units: always `units internal` + hardcoded 200 IU/µm.**
Already in the skill.

### Updated rule-by-rule first-aid table

Replace the existing DRC table with a more accurate one (limits verified from PDK rule decks):

| Rule | Limit | Cause we hit | Fix that worked |
|---|---|---|---|
| DV.8 | Dualgate ≥ 0.4 µm enclose Poly2 | Auto-derived dualgate insufficient | **Open** — needs investigation |
| DF.3a_MV | ≥ 0.36 µm MV diff spacing | Subcell-instanced FETs at < 1.7 µm pitch | Widen pitch to ≥ 1.7 µm OR rebuild with top-cell diff paint |
| DF.4c_MV | ≥ 0.6 µm n-well overlap of PCOMP | n-well doesn't extend past PMOS diff | Overhang n-well past cell boundary; cover all PMOS by 0.6 µm in all 4 directions |
| DF.13_MV | ≤ 15 µm PCOMP to N+ tap | No in-cell taps | **Chip-level rule** — pass via filler+endcap during PnR |
| DF.14_MV | ≤ 15 µm NCOMP to P+ tap | No in-cell taps | **Chip-level rule** — pass via filler+endcap |
| DF.16_MV | ≥ 0.6 µm n-well to NCOMP | NMOS-diff-top to n-well-bottom too close | Lower NMOS centerline, raise n-well bottom, paint p-well to override auto-lvpwell |
| LPW.12 | LVPWELL ∩ NW forbidden | Auto-derived LV-PWell from FET body markers overlaps our n-well at boundary | **Paint explicit pwell** under the NMOS half; suppresses the auto-derivation |
| NW.4 | LVPWELL space to NW (outside DNWELL) | Same as LPW.12 root cause | Same fix |
| NW.1a_MV | ≥ 0.86 µm n-well width | Cell n-well rectangle too narrow somewhere | Make n-well a single full-cell rectangle, overhanging cell boundaries |
| NW.2b_MV | ≥ 0.6 µm spacing between n-wells | Adjacent isolated n-wells from FET subcells | Paint unified cell-level n-well; let it override per-FET wells |
| CO.2a | ≥ 0.25 µm contact spacing | Contact-to-contact too close | Widen FET pitch OR re-template contacts |
| M1.2a | ≥ 0.23 µm M1 spacing | Power rail too close to gate-contact M1 | Add M1 routing connecting gate contacts to rails; OR move rail |
| M1.3 | ≥ 0.1444 µm² M1 min area | Isolated gate-contact M1 patches | Phase D routing: connect each gate to a wire |
| M1.1 | ≥ 0.23 µm M1 min width | Added M1 stubs were too narrow | Use ≥ 0.23 µm M1 stub width |
| PL.2_MV | ≥ 0.21 µm Poly2 space | Adjacent FET poly contacts too close | Either widen pitch or align poly contacts |
| PL.9 | Poly extension beyond active | Per-FET poly contacts extend past well in unsupported way | Investigate marker layout |
| PL.5a_MV / PL.5b_MV | Poly extension over active | Channel-length-related | Lengthen poly stripe (i.e., correct L) |
| DF.1a_MV | ≥ 0.3 µm MV diff width | Some diff drawn too narrow | Inspect markers |
| DF.17_MV | (varies) | (encountered briefly with bad taps) | Skip — only fires with malformed taps |
| DF.11 | (varies) | (encountered briefly with bad taps) | Skip |
| NP.3d/3e/4b/5b/5di/5dii/6, PP.3d/3e/4b/5b/5dii/6 | N+/P+ implant rules | Painted tap diff without `mvnsd`/`mvpsd` markers | **Don't paint manual taps**; rely on filler cells |

### New section: "Reading KLayout DRC `.lyrdb` markers programmatically"

Each `lsdl_<cell>_<rule>.lyrdb` file is XML with violation polygon coordinates. To extract violation locations without opening KLayout interactively:

```python
import xml.etree.ElementTree as ET
tree = ET.parse('/path/to/.lyrdb')
for item in tree.iter('item'):
    cat = item.findtext('category')
    val = item.find('values/value')
    print(f'{cat}: {val.text if val is not None else ""}')
```

This gives `(rule_category, polygon_coords)` per violation. Lets a script iterate fixes targeted at specific rules without opening the GUI.

### Updated "What's still TODO" section

Replace with the current 9-rule-class state:

**Closed by Phase A+B work:**
- DF.7, DF.8 (well-to-diff overlap/spacing) — fixed by well-overhang + lower NMOS
- LPW.12, NW.4 (LV-PWell conflict) — fixed by explicit `pwell` paint
- NW.1a, NW.2b (n-well width/spacing) — fixed by unified full-cell n-well

**Open at end of session (9 classes):**
- DF.4c_MV, DF.16_MV (well-overlap math) — needs nwell further extended
- DF.3a_MV (diff spacing) — needs true top-cell diff painting OR ≥1.7 µm pitch
- DF.13_MV, DF.14_MV (tap distance) — accept as chip-level
- DV.8 (dualgate enclose) — needs deeper investigation
- PL.2_MV, PL.9 (poly rules) — needs marker investigation
- M1.2a, M1.3 (M1 rules) — needs Phase D routing


## Part 2 — Concrete attack plan for the 9 remaining DRC rule classes

### Approach: parse-markers-first iteration

Add a Python helper that parses the per-rule `.lyrdb` files to extract violation coordinates. Use these coordinates to (a) understand which specific FET/edge is failing each rule, (b) target fixes at the exact geometry, (c) auto-verify after each fix.

Helper: `lsdl_lib/scripts/parse_drc.py`. Takes a DRC run directory, returns `{rule_name: [(x1,y1,x2,y2), ...]}` of failing polygons. Pretty-prints a summary keyed by FET name (matched by coordinate proximity).

### Rule-by-rule attack sequence

**Step 1 — accept DF.13_MV / DF.14_MV as chip-level.**
Document in the cell's README that these two rules require filler+endcap cells at PnR time. Strip them from the per-cell DRC sign-off criterion via a `--no_check_list` flag (or post-DRC filtering). **Estimated time: 15 min.**

**Step 2 — fix DF.4c_MV by extending n-well overhang in all directions.**
Currently n-well overhangs only top. Add lateral overhang (±0.5 µm beyond cell x-extent) and check that nwell covers every PMOS diff by ≥0.6 µm. Render PNG, verify visually. Re-run KLayout DRC, expect DF.4c_MV count = 0. **Estimated time: 30 min.**

**Step 3 — fix DF.16_MV by adjusting NMOS row Y position.**
Current Y_NMOS = 1.0; with W_max=0.9, NMOS_top_with_extension = 1.85. n-well bottom at WELL_BDY = 2.25 → gap = 0.40 µm. Need 0.6 µm. Lower Y_NMOS to 0.80 (top with ext = 1.65; gap = 0.60). Render, DRC. **Estimated time: 15 min.**

**Step 4 — fix PL.2_MV / PL.9 by inspecting markers and adjusting poly geometry.**
Run `parse_drc.py` to find which FET-pair edges fail PL.2_MV. Likely cause: poly contacts of adjacent FETs at 1.7 µm pitch are within 0.21 µm. Fix: increase pitch slightly OR shift one row's gate stubs to avoid overlap. **Estimated time: 30 min.**

**Step 5 — fix DV.8 via mvactive overlay.**
Investigate the Magic tech CIFOUTPUT rule for DUALGATE. If the issue is poly contacts extending past the auto-derived dualgate, paint a manual `mvactive` (or whichever Magic layer triggers DUALGATE growth) that covers the poly contact stubs. If no paintable Magic layer feeds DUALGATE, **accept DV.8 violations and document as known issue**. **Estimated time: 60 min (could be longer if tech inspection is needed).**

**Step 6 — Phase D routing.**
Add M1 routing for all 12 internal nets. Pattern: source/drain → diff contact (mv*diffc) → M1 stub → connecting wire → next contact OR rail. Each wire ≥0.23 µm width (M1.1). Spacing ≥0.23 µm (M1.2a). Patches sized so total wire area exceeds 0.1444 µm² (M1.3).

Sub-steps within Phase D:
- D1: VPWR source connections — 4 PMOS sources to top rail (~30 min)
- D2: VGND source connections — 4 NMOS sources to bottom rail (~30 min)
- D3: Clk distribution — connect 4 Clk-gated FET gates with horizontal M1 stripe (~30 min)
- D4: dyn net — connect XPRE.drain, XNTREE.drain, XPDRVP.gate, XPDRVN.gate (~45 min)
- D5: out_b net — most-connected internal node (4 drains, 2 gates) (~60 min)
- D6: Out + A external pin stubs (~15 min)
After each sub-step: render PNG, KLayout DRC, sanity-check M1.* counts dropping. **Estimated total Phase D: 3-4 hours.**

**Step 7 — Phase E LVS.**
Add Magic `port make` labels on M1 for each pin. Run `ext2spice` to extract netlist. Run `netgen -batch lvs` against `lsdl_inv_x1.spice`. Iterate any pin-name or device-mismatch errors per the `debug-lvs` skill. **Estimated time: 1-2 hours.**

### Acceptance criteria

The cell is "DRC + LVS clean" when, in standalone:
- KLayout DRC reports `Klayout DRC run is clean.` for all rules **except** DF.13_MV / DF.14_MV (documented as chip-level)
- Netgen LVS reports `Cells match uniquely.`
- Magic DRC matches (incremental count = 0 after `drc catchup`)

If DV.8 remains open: document as `KNOWN_ISSUES.md` entry, with the specific Magic tech-file root cause.

### Time budget

Realistic estimate: **~7-10 hours of iteration** to close all 9 rule classes + complete Phase D + Phase E. Phase D (routing) is the longest single piece. Each rule has compounding interactions, so the budget is conservative.

### Files to modify in the implementation

- `lsdl_lib/cells/lsdl_basic/lsdl_inv_x1_layout.tcl` — all the structural changes (well overhang, NMOS Y adjustment, M1 routing, port labels)
- `lsdl_lib/scripts/parse_drc.py` — NEW; parse `.lyrdb` for per-rule violation coordinates
- `lsdl_lib/scripts/build_layout.sh` — extend with LVS step
- `lsdl_lib/cells/lsdl_basic/README.md` — NEW; document DF.13_MV/DF.14_MV chip-level deferral
- `.claude/skills/lsdl-magic-headless-layout/SKILL.md` — large update per Part 1 above

### Verification

```bash
# After each step:
./lsdl_lib/scripts/build_layout.sh
rm -rf /soe/czeng14/projects/brainstorm-domino-tmp/drc_runs/drc_run_*
./lsdl_lib/scripts/run_in_container.sh "python3 /soe/czeng14/software/pdk/gf180mcuD/libs.tech/klayout/drc/run_drc.py --path=/mada/users/czeng14/projects/brainstorm/domino/lsdl_lib/cells/lsdl_basic/lsdl_inv_x1.gds --topcell=lsdl_inv_x1 --variant=D --run_mode=flat --no_offgrid --run_dir=/soe/czeng14/projects/brainstorm-domino-tmp/drc_runs --mp=4 2>&1 | grep -E 'Violated rules|Klayout DRC'"
python3 ./lsdl_lib/scripts/parse_drc.py /soe/czeng14/projects/brainstorm-domino-tmp/drc_runs/drc_run_*

# Final LVS verification:
./lsdl_lib/scripts/run_in_container.sh "<magic ext2spice ...; netgen -batch lvs ...>"
# expect: 'Cells match uniquely.'
```

---

# Phase D Detailed Routing Plan for `lsdl_inv_x1`

## Context

After Phase A-C work, 24 cell-level KLayout DRC violations remain (M1.3 = 11, M1.2a = 13), plus DF.13_MV/DF.14_MV (deferred as chip-level rules). Pin labels are also missing, so Netgen LVS cannot yet run. The cell has placement, wells, rails, and 5V markers correct — but **no signal routing**.

Closing the remaining DRC errors AND making the cell functionally usable as a standard cell both require **the same step**: properly route the 9 signal nets across the cell. The 24 M1 violations are symptoms of orphan gate-contact patches; real routing merges those patches into per-net wires that satisfy M1.3 (min area) and M1.2a (spacing).

The intended outcome: a DRC-clean cell (except 2 chip-level rules) AND LVS-clean against `lsdl_inv_x1.spice`, ready to use as a standard cell in LibreLane PnR.

**Constraints from clarification:**
- M1-only routing (matches stock GF180MCU 9T cells, simpler)
- Hold cell width to **12.15 µm** first; allow up to **15 µm** if M1 won't fit after reordering/M2-jumpers; never beyond 15 µm.

## Net inventory (from `lsdl_inv_x1.spice`)

11 distinct nets total. Per-net pin list with (X, Y) target coordinates (cell-local µm).

The current placement (PMOS centerline y=4.0, NMOS centerline y=1.0, X positions per `XS_P`/`XS_N`):

| # | FET | type | X | Sources/Drains | Gate | Notes |
|---|---|---|---|---|---|---|
| P0 | XPRE      | PMOS | 1.20  | S=VPWR, D=dyn     | Clk  | Precharge |
| P1 | XFBP      | PMOS | 3.15  | S=VPWR, D=cut_fb_src | Out  | Feedback p |
| P2 | XCUTFB    | PMOS | 5.10  | S=cut_fb_src, D=out_b | Clk  | Cut feedback |
| P3 | XPDRVP-a  | PMOS | 7.05  | S=VPWR, D=out_b   | dyn  | Predriver p (split fingers a+b) |
| P4 | XPDRVP-b  | PMOS | 9.00  | S=VPWR, D=out_b   | dyn  | Predriver p |
| P5 | XODRVP    | PMOS | 10.95 | S=VPWR, D=Out     | out_b | Output drv p |
| N0 | XNTREE    | NMOS | 1.20  | S=foot_top, D=dyn | A    | Eval n-tree |
| N1 | XFOOT     | NMOS | 3.15  | S=VGND, D=foot_top | Clk  | Foot dev |
| N2 | XHDR      | NMOS | 5.10  | S=VGND, D=hdr_src | Clk  | Header |
| N3 | XPDRVN    | NMOS | 7.05  | S=hdr_src, D=out_b | dyn  | Predriver n |
| N4 | XFBN      | NMOS | 9.00  | S=VGND, D=out_b   | Out  | Feedback n |
| N5 | XODRVN    | NMOS | 10.95 | S=VGND, D=Out     | out_b | Output drv n |

Per-net connection counts (descending complexity):
| Net | Connections | Pins |
|---|---|---|
| VPWR    | 5 PMOS sources + N-well taps | P0.S, P1.S, P3.S, P4.S, P5.S |
| VGND    | 4 NMOS sources + P-sub taps  | N1.S, N2.S, N4.S, N5.S |
| out_b   | 4 D + 2 G                    | P2.D, P3.D, P4.D, N3.D, N4.D, P5.G, N5.G |
| Out     | 2 D + 2 G + 1 pin            | P5.D, N5.D, P1.G, N4.G, (pin) |
| Clk     | 4 G + 1 pin                  | P0.G, P2.G, N1.G, N2.G, (pin) |
| dyn     | 2 D + 2 G                    | P0.D, N0.D, P3.G, P4.G, N3.G |
| cut_fb_src | 1 D + 1 S (adjacent)      | P1.D, P2.S |
| hdr_src    | 1 D + 1 S (adjacent)      | N2.D, N3.S |
| foot_top   | 1 D + 1 S (adjacent)      | N0.S, N1.D |
| A          | 1 G + 1 pin               | N0.G |

## Track scheme — M1 layer assignments

Vertical Y budget breakdown (5.04 µm row):

```
y = 4.58 .. 5.04     VPWR rail (M1, full cell width)     ← P S/D taps here
y = 4.30 .. 4.58     VPWR connection band (vertical M1 stubs from P-S/D taps)
y = 4.15 .. 4.85     PMOS top diffusion (S/D contacts)   [W=1.5 cells: 4.15..4.85; W=0.5: 4.45..4.85]
y = 4.0              PMOS gate (Magic poly)
y = 3.15 .. 3.85     PMOS bottom diffusion (S/D contacts)
y = 3.10 .. 4.10     PMOS gate-contact M1 (already painted by Phase C-lite)
─── mid-cell free space (y = 1.85 .. 3.10), about 1.25 µm vertical ───
y = 2.05 .. 2.28     ★ Track A: mid-cell horizontal M1 (width 0.23)
y = 2.51 .. 2.74     ★ Track B: mid-cell horizontal M1 (width 0.23)
─── below: NMOS row ───
y = 0.90 .. 1.90     NMOS gate-contact M1 (already painted)
y = 1.15 .. 1.45     NMOS top diffusion (S/D contacts)
y = 1.0              NMOS gate (Magic poly)
y = 0.55 .. 0.85     NMOS bottom diffusion (S/D contacts) ← N S/D taps here
y = 0.46 .. 0.85     VGND connection band (vertical M1 stubs from N-S/D taps)
y = 0.0  .. 0.46     VGND rail (M1, full cell width)
```

Mid-cell has room for **2 horizontal M1 tracks** at y=2.05–2.28 and y=2.51–2.74, separated by 0.23 µm (M1.2a OK).

**Track assignment:**
| Track | Y range | Net | Spans X | Rationale |
|---|---|---|---|---|
| A | 2.05–2.28 | **out_b** | x=4.9 → 11.2 | Most-connected internal net; spans P2..P5, N3..N5; covers right half |
| B | 2.51–2.74 | **Out** | x=2.9 → 11.2 | Output net; spans P1, N4 (gates) to P5, N5 (drains) |

**Clk** routing uses **gate-contact M1 stubs themselves** as a "stripe" — XPRE and XCUTFB PMOS gates are at the same Y range (3.10..4.10); a short horizontal M1 connector at y=3.55 between them suffices. Same for XFOOT and XHDR NMOS (y=0.90..1.90). To bridge PMOS-Clk and NMOS-Clk, a **vertical M1 stub at x=5.10** (XCUTFB position, which aligns with XHDR) runs from y=1.90 to y=3.10 (through mid-cell) — this passes between Track A (y=2.05..2.28) and the NMOS gate row at y=1.90 by routing at x=5.10 where neither Track A nor Track B has geometry (we control where the tracks start/stop in X).

**dyn** routing: P0.D, N0.D, P3.G, P4.G, N3.G. Span x=1.2..9.0. The drains at x=1.2 are in PMOS top diff (y=4.15..4.85) and NMOS top diff (y=1.15..1.45). The gates at x=7.05 / 9.0 are at the gate-contact M1 patches y=3.10..4.10 and y=0.90..1.90. Use a **horizontal M1 wire at y=1.65** (between NMOS top contact and gate-contact M1) running x=1.2..9.0, connecting:
- XNTREE.D contact (at x=1.2, y=1.15..1.45) via short vertical stub up
- XPDRVN.G contact (at x=7.05, y=0.90..1.90) directly
- Then vertical stub up at x=7.05 through mid-cell (between Track A and Track B at carefully chosen X) to PMOS gate-contact M1 at y=3.10
- XPRE.D (at x=1.2, y=4.15..4.85) gets connected via a separate vertical stub at x=1.2 going through both mid-cell tracks (carefully placed to avoid Track A/B horizontal extents)

(This is getting complex. Implementation must verify visually after each net is added.)

**Internal chain nets (cut_fb_src, hdr_src, foot_top)** are easy — each connects two adjacent FETs (P1↔P2, N2↔N3, N0↔N1). A short M1 jumper at the shared diffusion edge connects them, OR if the device generator's diffusion polygons already abut, no extra wire is needed (Magic extraction sees them as connected).

**A** pin: short M1 stub from XNTREE gate-contact at x=1.2, y=0.90..1.90 out to a labeled pin point. Pin can go on the cell-boundary track (e.g., x=0.5).

## Step-by-step execution sequence (D1-D9)

Each step ends with: rebuild → render PNG → KLayout DRC → fix any new violations → commit before next step. If a step creates >5 new violations, BACK OUT before continuing.

### D1: VPWR source distribution (5 stubs)

Add vertical M1 stubs from each PMOS source diff-contact up to the VPWR rail. 5 stubs at X positions of PMOS S contacts (which depend on FET orientation; verify in rendered PNG which side of each FET is "source"). Each stub: width 0.23 µm, Y range y=4.10 → 5.04 (overlaps top of PMOS diff contact, extends up into rail).

**Expected DRC delta:** all M1.2a violations in the top rail area drop (currently 2 reported at y=4.49). M1.3 may drop too if any PMOS gate-contact M1 merges with these stubs (would actually create a short — need to check).

### D2: VGND source distribution (4 stubs)

Mirror of D1 for NMOS sources. Vertical M1 stubs from each NMOS S diff-contact down to VGND rail. Y range y=0.0 → 0.85.

**Expected DRC delta:** M1.2a violations at y=0.46 boundary drop (currently 8 reported).

### D3: Internal-chain nets (cut_fb_src, hdr_src, foot_top)

For each chain, paint a small M1 jumper between the abutting diffusion contacts of the two adjacent FETs. ~3 short wires total. Verify in rendered PNG that wires don't short to unrelated FETs.

**Expected DRC delta:** minor; mostly closes 1-2 M1.3 violations on chain nets.

### D4: Clk fanout (4 gates)

Two sub-wires:
- PMOS Clk wire: horizontal M1 at y=3.55, x=1.0..5.3, connecting XPRE.G ↔ XCUTFB.G gate-contact M1 patches. Width 0.23 µm.
- NMOS Clk wire: horizontal M1 at y=1.45, x=3.0..5.3, connecting XFOOT.G ↔ XHDR.G gate-contact M1 patches. Width 0.23 µm.
- Bridge: vertical M1 stub at x=5.10, y=1.45..3.55, connecting the two wires. Must avoid Track A (out_b) and Track B (Out) which can be designed to NOT extend through x=5.10 if those tracks end at x=5.5 or start at x=5.5.

**Expected DRC delta:** closes 4 M1.3 violations (XPRE.G, XCUTFB.G, XFOOT.G, XHDR.G all merge into Clk net).

### D5: dyn net (2 drains + 3 gates)

Horizontal M1 wire at y=1.65 spanning x=1.0..7.5, with vertical stubs:
- Up at x=1.2 to XPRE.D (y=4.15..4.85) — passes through Track A and Track B regions (those tracks must avoid x=1.2)
- Down to XNTREE.D top contact via the gate-contact M1 at x=1.2
- Out to XPDRVN.G at x=7.05 (gate-contact M1)
- Up at x=7.05 to XPDRVP-a.G and XPDRVP-b.G — vertical stub through mid-cell

Track A (out_b) starts at x=4.9, so the vertical at x=1.2 doesn't conflict. Track B (Out) starts at x=2.9, so the x=1.2 vertical doesn't conflict either. The x=7.05 vertical may conflict with Track A and Track B; deal with by inserting a small notch in those tracks at x=7.05 (split each track into two segments).

**Expected DRC delta:** closes 5 M1.3 violations on dyn-connected gates/drains.

### D6: out_b net (Track A + connecting stubs)

Paint Track A: horizontal M1 at y=2.05..2.28, x=4.9..11.2 (notched around x=7.05 if D5 stub is there — split into two segments x=4.9..6.9 and x=7.2..11.2; an M2 jumper or a sliver re-route can close the gap if needed).

Add vertical stubs from Track A to:
- XCUTFB.D at x=5.10, going up to PMOS diff contact at y=3.85
- XPDRVP-a.D at x=7.05, going up to y=3.85 (need to coordinate with dyn's x=7.05 stub — different Y range so they don't touch if Track A is at y=2.05–2.28 and the dyn-up-stub is at y=2.28..3.10)
- XPDRVP-b.D at x=9.00, going up to y=3.85
- XPDRVN.D at x=7.05, going down to NMOS diff contact at y=1.45
- XFBN.D at x=9.00, going down to y=1.45
- XODRVP.G at x=10.95, going up to gate-contact M1 at y=3.10..4.10
- XODRVN.G at x=10.95, going down to gate-contact M1 at y=0.90..1.90

**Expected DRC delta:** closes ~8 M1.3 violations on out_b-connected pins.

### D7: Out net (Track B + connecting stubs)

Paint Track B: horizontal M1 at y=2.51..2.74, x=2.9..11.2 (notched around x=7.05 if conflicts with D5).

Vertical stubs to:
- XFBP.G at x=3.15, going up to gate-contact M1 at y=3.10
- XFBN.G at x=9.00, going down to gate-contact M1 at y=1.90
- XODRVP.D at x=10.95, going up to PMOS top diff contact at y=4.15
- XODRVN.D at x=10.95, going down to NMOS top diff contact at y=1.15
- **Out pin patch**: extend Track B's right end out to the cell-boundary at x=12.1, with M1 widened to ≥0.6 µm at the pin location (provides pin access region for LibreLane router)

**Expected DRC delta:** closes ~4 M1.3 violations on Out-connected pins; creates a pin access region.

### D8: A pin

Vertical M1 stub from XNTREE.G gate-contact M1 (x=1.2, y=0.90..1.90) extended left to x=0.2 (cell-boundary track) with widened pin patch (0.5×0.5 µm).

**Expected DRC delta:** closes 1 M1.3 on A net; provides pin access.

### D9: Magic `port make` labels + LVS

Add Magic `flabel` + `port` commands for each pin. Pattern from stock cell:

```tcl
# Make pin labels at the M1 pin access regions
puts "==== Adding port labels..."
box values [um2iu 0.2] [um2iu 0.7] [um2iu 0.7] [um2iu 1.2]
label "A" metal1
port make 1 input

box values [um2iu 5.0] [um2iu 1.45] [um2iu 5.5] [um2iu 1.7]
label "Clk" metal1
port make 2 input

box values [um2iu 11.6] [um2iu 2.51] [um2iu 12.1] [um2iu 2.74]
label "Out" metal1
port make 3 output

# Rails
box values 0 [um2iu 4.58] [um2iu 12.15] [um2iu 5.04]
label "VPWR" metal1
port make 4 inout

box values 0 0 [um2iu 12.15] [um2iu 0.46]
label "VGND" metal1
port make 5 inout
```

Then in `build_layout.sh` add an `ext2spice` + `netgen lvs` step:

```bash
# ext2spice
"${ROOT}/scripts/run_in_container.sh" \
    "cd ${CELL_DIR} && magic -dnull -noconsole \
       -rcfile /soe/czeng14/software/pdk/gf180mcuD/libs.tech/magic/gf180mcuD.magicrc \
       -T gf180mcuD <<'EOF'
load lsdl_inv_x1
extract all
ext2spice lvs
ext2spice -o lsdl_inv_x1_extracted.spice
quit -noprompt
EOF" > "${LOG_DIR}/extract.log" 2>&1

# Netgen LVS
"${ROOT}/scripts/run_in_container.sh" \
    "netgen -batch lvs \
        '${CELL_DIR}/lsdl_inv_x1_extracted.spice lsdl_inv_x1' \
        '${CELL_DIR}/lsdl_inv_x1.spice lsdl_inv_x1' \
        /soe/czeng14/software/pdk/gf180mcuD/libs.tech/netgen/gf180mcuD_setup.tcl" \
    > "${LOG_DIR}/lvs.log" 2>&1
grep -E 'Cells match|mismatch' "${LOG_DIR}/lvs.log" | tail -5
```

**Expected outcome:** `Netgen LVS: Cells match uniquely`.

## Iteration discipline

After EACH step D1-D9:
1. Run `./lsdl_lib/scripts/build_layout.sh` (rebuilds .mag, .gds, .png)
2. Run KLayout DRC (`run_drc.py`)
3. Run `parse_drc.py` to count current violations
4. **If new violations count > 5 above baseline for this step:** back out the change, examine PNG, adjust, retry.
5. **Otherwise:** commit the change conceptually (just keep going), proceed to next step.
6. After D9, run full LVS.

Render PNG → multimodal Read by Claude → visually verify the routing is sensible.

## Decision rules for routing conflicts

If a step creates an M1.2a (M1 spacing < 0.23 µm) violation that wasn't there before:
1. **First**: try shifting the new wire by 0.05 µm in the constrained direction.
2. **Second**: shorten the wire (split into two segments separated by ≥ 0.23 µm).
3. **Third**: reroute via a different track (e.g., move from mid-cell to gate-contact-row).
4. **Fourth**: if all else fails, allow cell width to grow by 0.3 µm to insert a new track column.

If a step creates an M1.3 (min area < 0.1444 µm²) violation:
1. Most likely cause: a leftover orphan from removed routing. Verify the wire actually connects what it should.

If a step creates a poly/diff rule violation:
1. M1 paint shouldn't trigger these. Check that the box bounds for `paint metal1` didn't extend into other layers' regions by mistake.

## Critical files

- `lsdl_lib/cells/lsdl_basic/lsdl_inv_x1_layout.tcl` — append routing logic per D1-D9.
- `lsdl_lib/scripts/build_layout.sh` — extend with LVS step (after D9).
- `.claude/skills/lsdl-magic-headless-layout/SKILL.md` — add a "routing patterns" section after Phase D succeeds, documenting which patterns worked.

## Verification

Acceptance:
```bash
# DRC clean (except 2 chip-level rules)
./lsdl_lib/scripts/build_layout.sh
python3 lsdl_lib/scripts/parse_drc.py /soe/czeng14/projects/brainstorm-domino-tmp/drc_runs/
# Expected: 'Total cell-level violations: 0'

# LVS clean
grep 'match' /soe/czeng14/projects/brainstorm-domino-tmp/lvs.log
# Expected: 'Cells match uniquely.'
```

## Time budget

Realistic estimate: **4-6 hours**.
- D1+D2 (rails): 30 min (mechanical, mostly safe additions)
- D3 (internal chains): 20 min (3 small wires)
- D4 (Clk): 40 min (3 sub-wires + 1 bridge)
- D5 (dyn): 60 min (most complex spanning net)
- D6+D7 (Track A + Track B + stubs): 90 min (highest M1.2a risk, may need re-routing)
- D8 (A pin): 15 min
- D9 (ports + LVS iteration): 60-90 min (LVS may surface naming/parallel-device mismatches)

## Plan-doc edits after Phase D succeeds

- Add "routing patterns" section to `lsdl-magic-headless-layout/SKILL.md` with the track-scheme template, FET-side-bias proc, and pin-label one-liner.
- Mark Wave 0 layout phase as **complete** in `phase1_cells_tapeout.md` (under "Cross-cutting → Cell library, Wave 0").
- Update the Belluomini Fig. 1 cell topology section of `phase1_cells.md` with the actual cell width achieved (12.15 µm vs the original prediction of "~10 µm").

---

# LibreCell Integration — adopt SMT cell synthesis on GF180MCU (current decision)

## Context

Hand-routing DRC+LVS-clean LSDL cells in Magic (the R5–R10 work) is slow and error-prone — the inverter alone consumed many iterations to reach a clean geometric skeleton, with contacts/routing/LVS still ahead. Research surfaced an open-source tool that automates exactly this and runs on our *actual* tapeout node:

- **LibreCell (`lclayout`)** — automated CMOS standard-cell layout generator. Input: SPICE `.subckt` with sizes. Output: GDS + LEF + Magic. Engine: **Z3 (SMT)** for simultaneous place-and-route (optional GLPK ILP). Fully license-free (lclayout AGPL, Z3 MIT, GLPK GPL). Source: https://codeberg.org/librecell/lclayout
- **LibreSilicon `Tech.GF180MCU`** — a complete, hand-written GF180MCU enablement for lclayout: 5 V gate lengths (NMOS 500 nm / PMOS 600 nm), `9 × 560 nm = 5.04 µm` row (matches our `GF018hv5v_green_sc9` site), correct GDS layers (COMP 22/0, nwell 21/0, LVPWELL 204/0, dualgate 55/0), metal1 spacing 230 nm, and auto-derivation of contact spacing from diffusion+enclosure. Configurable `TARGETVOLTAGE`/`TRACKS`/`DNWELL`. Source: https://gitlab.libresilicon.com/generator-tools/standard-cell-generator (dir `Tech.GF180MCU/`)

**Decision:** Adopt **LibreCell as the primary cell-layout-synthesis tool for this GF180MCU project.** It produces correct-by-construction (SMT-verified) layouts on the tapeout node with no license. **SO3-Cell and SMTCell-MH are retained in the project docs for future advanced-node (FinFET / PROBE3.0) work**, not used for this tapeout (both are FinFET-only; SO3-Cell additionally needs a Gurobi license). Magic + Netgen remain the **authoritative sign-off** — LibreCell encodes a rule subset, so its output must still clear the official GF180 KLayout DRC and Netgen LVS.

Intended outcome: replace the per-cell hand-routing grind with `spice → lclayout → DRC/LVS`, and keep the hand-Magic flow (R5–R10) only as a fallback if the LSDL topology won't converge in the SMT router.

## Caveats driving the plan

1. LibreCell is self-described "very early stage"; needs `PYTHONHASHSEED=42`. The GF180 tech file has TODO comments ("likely needs tuning", "one layer might be missing"). Expect to debug the enablement.
2. LSDL is not a textbook cell: feedback latch, single `Clk` fanning out to 4 gates, 11 FETs, shared internal nets. Whether the SMT placer/router converges on it at 9-track is **unproven** — this is the spike's central risk.
3. Output must pass our existing sign-off gates regardless, so LibreCell de-risks but does not replace DRC/LVS.

## Work plan

### L1 — Install + stage (project-local, no root dirs)
- Create `lsdl_lib/librecell/` in the project. Install `lclayout` + `z3-solver` (and GLPK) into the existing Python env / container. Confirm `lclayout --help` runs.
- Clone the LibreSilicon `Tech.GF180MCU/` files into `lsdl_lib/librecell/tech_gf180mcu/` (`librecell_tech.py`, `design.ngspice`, `transistors.ngspice`, `nmos.sp`, `pmos.sp`, `template.lef`, `tracks.txt`, `libresilicon.tech`, `Makefile`).
- Point the tech file's PDK paths at our installed `gf180mcuD` PDK. Set env `TARGETVOLTAGE=5V TRACKS=9 DNWELL=True PYTHONHASHSEED=42`.

### L2 — Enablement validation spike (stock combinational cell)
- Run lclayout on a simple known cell (e.g. NAND2 / INV) using the GF180 tech → GDS.
- Run the **existing** GF180 KLayout DRC (`run_drc.py`) + render. Goal: confirm the enablement yields a near-DRC-clean stock cell before trying LSDL. Fix tech-file gaps (the "one missing layer", tap/well overhang, dualgate enclosure) here, reusing lessons from the hand-Magic skill.

### L3 — LSDL inverter through LibreCell
- Convert `lsdl_inv_x1.spice` to the lclayout input form (flat `.subckt`, transistor W/L; map `pfet_05v0`/`nfet_05v0` to the tech's device names). Keep pin names A, Clk, Out, VPWR, VGND.
- `lclayout --tech …/librecell_tech.py --netlist lsdl_inv_x1.sp --cell lsdl_inv_x1 --output-dir …`.
- Sign-off: GF180 KLayout DRC + Netgen LVS against the hand-source `lsdl_inv_x1.spice` (reuse `build_layout.sh`/`parse_drc.py`; same "device-count→power/body→opens→shorts" debug order).
- **Convergence handling:** if the router times out or reports infeasible at 9-track — raise track budget, relax `MISALIGN`/padding knobs, or split the cell. If still infeasible, record why and fall back to hand-Magic R5–R10 for the inverter.

### L4 — LSDL NAND2 through LibreCell
- Repeat L3 for `lsdl_nand2_x1.spice` (adds the series-NMOS eval tree + `nint` charge-share node). Confirm DRC + LVS clean.

### L5 — Adopt as the library flow
- If L3–L4 succeed: make `spice → lclayout → DRC/LVS` the standard per-cell flow for Wave 1/2; the descriptor (`lsdl_lib/descriptor/`) emits the lclayout netlist. Hand-Magic becomes the exception path only.

## Project-document edits

- **`overview.md`**
  - Line 11 — change cell-synthesis tooling to: *LibreCell (`lclayout`, Z3 SMT) on planar GF180MCU is primary for this tapeout; SO3-Cell / SMTCellUCSD-MH retained for future FinFET/advanced-node exploration.*
  - Line 27 (Phase 1 item 2) — reword to "Drive LibreCell with LSDL constraints (fixed Fig. 1 latch template, single-Clk fanout, named internal nodes); SO3-Cell/SMTCell-MH noted as advanced-node alternatives."
- **`phase1_cells.md`**
  - Rewrite **Task 2** (lines 156–190): primary path = LibreCell on GF180MCU (Z3 SMT, license-free, correct-by-construction); inputs = LSDL `.subckt`; sign-off via existing GF180 DRC + Netgen LVS. Move the SO3-Cell "extend for dynamic cells" content into a clearly-labeled **"Future / advanced-node alternative"** subsection alongside SMTCell-MH; keep the ICCAD/SLIP references there. Preserve the LSDL-specific constraints (single-Clk connectivity, fixed latch template, internal-node naming, stack-≥4 fallback) — they now apply to LibreCell.
  - Task 0 (line 86) — note that hand-Magic reference cells remain the disproof baseline and the LibreCell fallback.
  - Task 4 (line 299) / refs (lines 183–185, 441) — keep SO3-Cell as a future-work citation, not the active inner tool.
- **`phase1_cells_tapeout.md`**
  - Decision 2 (line 245) — extend: *cell-layout generator = LibreCell (lclayout, GF180MCU tech); Magic + Netgen remain authoritative sign-off; KLayout informational.*
  - Add **Decision 12**: *Cell layout synthesis = LibreCell (Z3 SMT) on GF180MCU. SO3-Cell / SMTCell-MH deferred to future advanced-node work.*
- **`lsdl_lib/README.md`** / **`lsdl_lib/scripts/README.md`** / **`lsdl_lib/descriptor/SCHEMA.md`** — note that `.mag`/`.gds` may now be **generated by LibreCell** from the `.spice` source (not only hand-authored), with Magic/Netgen still the LVS/DRC authority.

## Verification

```bash
# L2/L3/L4 — after each lclayout run:
PYTHONHASHSEED=42 TARGETVOLTAGE=5V TRACKS=9 lclayout \
  --tech lsdl_lib/librecell/tech_gf180mcu/librecell_tech.py \
  --netlist <cell>.sp --cell <cell> --output-dir lsdl_lib/librecell/out
# DRC (existing runner) — expect cell-level clean (DF.13_MV/DF.14_MV chip-level OK):
./lsdl_lib/scripts/run_in_container.sh "python3 .../run_drc.py --path=<cell>.gds --topcell=<cell> ..."
python3 lsdl_lib/scripts/parse_drc.py /soe/czeng14/projects/brainstorm-domino-tmp/drc_runs/
# LVS against hand-source spice — expect 'Cells match uniquely.'
```

Success = `lsdl_inv_x1` and `lsdl_nand2_x1` generated by LibreCell, cell-level DRC clean, Netgen LVS match. Fallback = hand-Magic R5–R10 if SMT routing won't converge.

---

# L4 — LSDL NAND2 through the hardened LibreCell flow

## Context
`lsdl_inv_x1` is fully signed off via LibreCell: 0 cell-level DRC, 5V-marked, block-level
Netgen LVS "Circuits match uniquely" (no port errors), LEF pins correct, plus a DRC-clean
11T tap/endcap/fill support library. Every fix lives in shared, reusable scripts. **L4 is the
generalization test:** run `lsdl_nand2_x1` through the *exact same* flow with **no new tech
patches expected**, proving the flow produces a library, not a one-off. Skill:
`lsdl-librecell-gf180`; full rationale in `lsdl_lib/librecell/LESSONS.md`.

## What's new in NAND2 vs the inverter (the only deltas)
From `cells/lsdl_basic/lsdl_nand2_x1.spice`: **12 FETs** (= INV's 11 + one extra series NMOS
`XNB`), **6 pins** `A1 A2 Clk Out VPWR VGND` (INV had 5), and a **series NMOS eval stack**
`dyn→XNA→nint→XNB→foot_top` with a new internal **charge-share node `nint`**. Device split:
5 PMOS + **7 NMOS** (INV: 5+6). Sizing is already specified in the hand-source (reuse as-is).
`nint` is purely an internal net for layout/LVS (just route + match it); its charge-sharing
behavior is a SPICE/PVT concern, not a DRC/LVS one.

## Central risk to watch
The **series-NMOS stack** makes the NMOS row more connectivity-constrained than the INV's
single eval NMOS. The known lever if routing won't converge at 11T: raise `--place-max-candidates`,
then `TRACKS=13` (already proven to route the INV). This is exactly the generalization question L4 answers.

## Plan (reuse the hardened flow end-to-end)

1. **Write the lclayout netlist** `lsdl_lib/librecell/lsdl_nand2_x1.sp` — translate the
   hand-source to the lclayout contract (primitive `M D G S B`, model names `nmos`/`pmos`,
   netlist `l=` matching the tech: NMOS 0.6 / PMOS 0.5). Pins `A1 A2 Clk Out VPWR VGND`.
2. **Generate + DRC**: `gen_and_drc.sh lsdl_nand2_x1 11` (wipes run dir; `--placer smt`).
   Expect convergence + a small, known DRC set. Per-class, in the proven order, using
   `parse_drc.py --rule … --coords`. **No new tech edits expected** — the patches in
   `tech_gf180mcu/librecell_tech.py` + the codegen patches (`standalone.py` implant bands /
   LVPWELL clip) are generic. If a new class appears, root-cause by coordinate first.
   If routing fails: bump candidates → `TRACKS=13`.
3. **Markers**: `librecell_postprocess.py <gds> <gds>_5v.gds lsdl_nand2_x1` — boundary
   DUALGATE + FET5VDEF + well-rectangularize are already generic (work for any width). Re-DRC →
   expect 0 cell-level (+ chip-level DF.13/14 deferred).
4. **Generalize the port + LEF scripts for 6 pins / arbitrary inputs** (small, one-time):
   - `mk_ports_gds.py`: instead of the inverter-specific hardcoded `DEFAULT_PINS`, **auto-detect
     each I/O net's label position** from the lclayout-written labels (given the I/O net-name
     list `A1 A2 Clk Out VPWR VGND`), pick one representative metal1 label per net, strip the
     rest. Keeps it reusable for all future cells.
   - `fix_lef_pins.py`: generalize the `SPEC` so any `A*` input → INPUT/SIGNAL, `Out`→OUTPUT,
     `VPWR`→POWER, `VGND`→GROUND (covers A1/A2 and future multi-input cells).
5. **Ports + cell LVS**: `declare_magic_ports.tcl` (`port makeall` on the port-clean GDS,
   `ext2spice lvs` — **no `cthresh/rthresh`**). Verify `.subckt lsdl_nand2_x1 A1 A2 Clk Out
   VPWR VGND` matches the hand-source name+order.
6. **Block LVS** (the authoritative match): build `tap | lsdl_nand2_x1 | tap` via
   `build_support.py combo` (reuses the existing 11T tap), port-clean the block, extract,
   `netgen -batch lvs` vs `lsdl_nand2_x1.spice`. Expect **"Circuits match uniquely"**, bulk
   VPWR/VGND, 12 devices / 11 nets (10 INV-style + `nint`).
7. **Seam re-check** (cheap, since support cells are proven): DRC `tap|nand2|tap` and a
   `fill|nand2|fill` to confirm the wider cell still abuts cleanly under the row contract.
8. **Freeze + document**: `signoff_lsdl_nand2_x1/` (GDS/LEF/mag/SPICE/LVS log + MANIFEST);
   note in `LESSONS.md` whether any NAND2-specific issue arose (ideally "flow generalized,
   zero new tech patches"); mark L4 done.

## Critical files
- New: `lsdl_lib/librecell/lsdl_nand2_x1.sp` (lclayout netlist), `signoff_lsdl_nand2_x1/`.
- Reuse unchanged: `gen_and_drc.sh`, `librecell_postprocess.py`, `declare_magic_ports.tcl`,
  `magic_extract.tcl`, `build_support.py`, `tech_gf180mcu/librecell_tech.py`, the patched
  `lclayout/standalone.py`, the 11T support cells in `signoff_support_11t/`.
- Small generalization edits: `lsdl_lib/scripts/mk_ports_gds.py` (auto-detect pin positions),
  `lsdl_lib/scripts/fix_lef_pins.py` (input-name pattern).

## Verification
- `gen_and_drc.sh` → routing successful + internal LVS SUCCESS.
- KLayout DRC on the 5V-marked GDS → 0 cell-level (DF.13/14 chip-level only).
- Block Netgen LVS → "Circuits match uniquely", 12 devices, bulk = VPWR/VGND, no port errors.
- `tap|nand2|tap` + `fill|nand2|fill` DRC → 0 cell-level.
- Acceptance: NAND2 reaches the same signoff state as the INV with **no new tech patches**
  (only the two generic script generalizations). If a tech patch was needed, document why.

---

# Wave 1 + Library-Collateral Hardening + Tapeout Roadmap

## Context
Two LSDL cells (`inv`, `nand2`) are sign-off clean via the LibreCell flow, with an 11T
tap/endcap/fill support library and a port-clean block LVS. The flow is proven to generalize
(NAND2 needed zero new tech patches). Now: (a) re-anchor the whole path to the **final
tapeout**, (b) **harden the per-cell collateral** (so each new cell is PnR-trustworthy, not
just DRC/LVS-clean), then (c) **generate the full Wave 1 mapper cell set**. L5 (Liberty/Verilog
generators) is deliberately deferred. Decisions: harden-flow-first; full Wave 1 scope (8 BASIC
+ 2 COMPLEX); **X1-only** drive strength (per-cell X2 added on demand after adder STA);
static-CMOS comparison is a **separate later track** (stock `gf180mcu_fd_sc_mcu9t5v0`, no cell design).

> **Drive-strength policy (note):** Wave 1 ships **X1 only**. After we place & route the
> 16-bit adder and run timing analysis, **if a specific net is starved, we generate an X2 of
> just that one cell** — a ~10-minute rerun of the proven flow. No speculative X2/X4 up front;
> drive strength is added load-driven, per-cell, only where the adder timing report demands it.
> (LSDL note: fan-out can't be fixed by buffer insertion — every cell is a clocked flop — so
> the fix is always the driving cell's output-driver strength, i.e. an Xn variant.)

## Tapeout roadmap (where Wave 1 sits)
Final die = **3 benchmarks × {LSDL, static-CMOS} = 6 instances** + 2-phase clock generator +
×6 LFSR/capture/RO measurement + 7 power domains + 47 pads, integrated via **LibreLane** on the
wafer.space `gf180mcu-project-template`. Benchmarks: **16-bit adder** (proof-of-concept, needs
only Wave 1 cells), **32-way mux** (power advantage; +Wave 2 `MUX_SEG`), **32-bit priority
encoder** (delay advantage; +Wave 2 `OR_TREE`, `PRI_ENC_CELL`). Path:
**Wave 1 cells (this plan) → adder LibreLane block (LSDL + CMOS) → Wave 2 wide cells → mux &
encoder blocks → measurement+clkgen+pads integration → full-chip DRC/LVS/sign-off → submit.**
Static-CMOS side and infrastructure (clkgen/LFSR/capture/dividers/pads) use the **stock library
unchanged** — no LSDL cell design there.

## Phase A — Harden the per-cell collateral flow (on inv/nand2 first)
Establish three reusable gates so every Wave 1 cell is PnR-ready, proven on the two done cells:
1. **LEF-vs-GDS audit** (`scripts/audit_lef.py`, new): parse the (fixed) LEF and the GDS; verify
   every pin's PORT rect lies on real metal of that net, layers/USE/DIRECTION are correct,
   the cell BBOX/SIZE matches the boundary (63/0), and power rails are PINs. Reuse
   `fix_lef_pins.py` for direction/use.
2. **OpenROAD pin-access check** (`scripts/check_pin_access.py` or a tiny OpenROAD `detailed_route`
   smoke in the container): load the LEF on the GF180 tech LEF + tracks, confirm each signal pin
   has ≥1 legal on-grid access point on its metal layer. Fail = pin off-track / unreachable.
3. **PEX timing/glitch** (`scripts/pex_validate.py`, new): Magic RC extraction
   (`ext2spice` *with* parasitics — cthresh/rthresh tuned, the opposite of the LVS mode) →
   re-run the cell's existing testbench (`testbench/tb_<cell>.sp`) on the **extracted** netlist
   via `pvt_sweep.py` → confirm eval delay and the **glitch < 10% VDD** rule still hold with
   parasitics. Reuse `pvt_sweep.py`, `magic_extract.tcl` (add a parasitic variant).
Acceptance: inv + nand2 pass all three. These become the standard tail of every cell's run.

## Phase B — Generate Wave 1 cells through the hardened flow
For each cell: write `lsdl_lib/librecell/<cell>.sp` (clone `lsdl_nand2_x1.sp`, swap the eval
tree, X1 output driver as-is), then run the full chain:
`gen_and_drc.sh <cell> 11` → `librecell_postprocess.py` (markers) → `mk_ports_gds.py`
(auto-detect pins) + `declare_magic_ports.tcl` → block Netgen LVS → **Phase-A gates** →
`fix_lef_pins.py` → freeze `signoff_<cell>/`.

**B1 — 8 BASIC cells** (single eval tree, proven template; eval-tree netlists from the Wave 1 table):
`AND2/3/4` (series stack, +`nint` nodes), `OR2/3/4` (parallel pulls, shared foot),
`AOI21` ((A·B)+C), `AOI22` ((A·B)+(C·D)), `MUX2` ((S·A)+(!S·B)). NMOS width scaled by stack
height (AND4/OR4 ~1.5×). Watch: deeper stacks / wider cells may need `--place-max-candidates`↑
or `TRACKS=13` (known levers); PL.5 pitch already handled by the 3-track gate pitch.

**B2 — 2 COMPLEX cells** (`NAND_CMPLX_X1`, `NAND_CMPLX_AOI`) — paper Fig 3a: **two eval trees**
(`dyn1`/`dyn2`), **two precharge PMOS + two foot NMOS**, **NAND-form predriver** combining both
dynamic nodes. This is a NEW topology (the predriver differs from the inv/nand2 single-tree
inverter). Design the netlist from Fig 3a, validate the SPICE (charge-sharing on both trees)
before layout, then run the same flow. Treat as its own sub-effort with the seam/DRC methodology;
expect possible new routing/DRC findings (document any).

## Critical files
- New per cell: `lsdl_lib/librecell/<cell>.sp`, `signoff_<cell>/`.
- New collateral scripts: `lsdl_lib/scripts/audit_lef.py`, `check_pin_access.py`, `pex_validate.py`;
  extend `magic_extract.tcl` with a parasitic-extraction variant.
- Reuse unchanged: `gen_and_drc.sh`, `librecell_postprocess.py`, `mk_ports_gds.py`,
  `declare_magic_ports.tcl`, `fix_lef_pins.py`, `build_support.py`, `pvt_sweep.py`,
  `tech_gf180mcu/librecell_tech.py`, patched `lclayout/standalone.py`, `signoff_support_11t/`.
- New hand-source SPICE references under `cells/lsdl_basic/` for each Wave 1 cell (for LVS),
  mirroring `lsdl_nand2_x1.spice`.

## Verification (per cell, all must pass)
- `gen_and_drc.sh`: routing successful + internal LVS SUCCESS.
- GF180 KLayout DRC on the 5V-marked GDS: **0 cell-level** (chip-level DF.13/14 deferred).
- Block Netgen LVS (`tap|<cell>|tap`): **Circuits match uniquely**, bulk VPWR/VGND, no port errors.
- Seam DRC `tap|<cell>|tap` + `fill|<cell>|fill`: 0 cell-level.
- **LEF audit pass**, **pin-access pass**, **PEX glitch<10%VDD + delay pass** (Phase-A gates).
- Acceptance for the set: all 10 Wave 1 cells frozen in `signoff_<cell>/`; the **adder-complete
  subset** (AND2/3/4, OR2/3/4, AOI21, AOI22, NAND_CMPLX_AOI) ready to feed the first LibreLane
  adder block. Document any cell that needed a tech patch or TRACKS=13.

## Deferred (not this plan)
L5 Liberty/Verilog generators (`gen_liberty.py`, `gen_verilog_wrapper.py`); the LibreLane adder
block itself; Wave 2 wide cells; static-CMOS comparison flow; per-cell X2 drive strengths.
