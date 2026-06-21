# Dynamic Logic via Coding Agents — Project Overview

## Goal

Coding-agent-driven dynamic logic design in the dual clock rail, domino +
static-latched output, no-weak-cells style.

## Stack / Targets

- **Tech nodes:** ASAP7 (predictive 7nm FinFET) and Skywater 130nm.
- **Cell synthesis tooling:** SO3-Cell, then SMTCellUCSD-MH if multi-row needed.
- **Foundation flow:** Pedroso two-phase ORFS flow
  ([thesis](related/paolo_two_phase_clocking_thesis.pdf)) as Phase 0.
- **Compiler infrastructure:** LiveHD + ABC + Yosys + OpenROAD.

## Phase 0 — Baseline (exists)

- Pedroso two-phase clocking flow in ORFS.
- FF → two-phase latch conversion, ABC retime (`ret_opt_4_cmp_rsz_buf`),
  dual CTS via TritonCTS, two-coloring static verifier (OpenROAD Python API).
- Use clock-gated variant as default substrate.

## Phase 1 — Cell Foundation

1. SPICE-in-the-loop fitness function (delay, precharge, noise margin,
   charge sharing, leakage, area) for ASAP7 and Skywater.
2. Extend SO3-Cell / SMTCellUCSD-MH with dynamic-cell constraints
   (precharge PMOS, clock-pin connectivity, no keepers, static-latch output).
3. Define target cell family (domino AND-OR, dual-rail XOR, dynamic mux2/4,
   static-latch output stage, precharge driver). Fix max stack height per node.
4. Agent-driven synthesis + characterization loop; openEvolve outer loop.
5. Liberty/LEF emission (dynamic cells as STA black boxes).
6. Sanity benchmark (e.g., 8-bit CLA adder), SPICE-verified end-to-end.

## Phase 2 — Compiler Passes

7. LiveHD unateness analyzer per Φ1/Φ2 partition — **best effort**, with
   source-line provenance back to RTL where it fails.
8. Slack-marking pass on the post-retime two-phase netlist; tags cones by
   timing margin for downstream "convert to dynamic?" decisions.
9. RTL-rewrite coding agent — consumes (cone, non-unate reason, slack) tuples
   and proposes RTL transformations (DeMorgan, dual-rail, Shannon, intent
   rewrites).
10. LEC + cosim oracle for verifying RTL rewrites (prerequisite for trusting
    task 9 unsupervised).
11. Dynamic-cell mapping pass — selective conversion of qualifying cones;
    others stay static.
12. Verification obligation generator (charge-sharing, monotonicity,
    dual-rail consistency) for mapped cones.

## Phase 3 — Dual Clock + Parasitic-Aware

13. Non-overlapping Φ1/Φ2 generator (programmable non-overlap window,
    test-mode aware — see Opt-F).
14. Post-PnR parasitic-aware re-verification (evaluate window under
    extracted RC, charge sharing with extracted caps, non-overlap margin
    under skew).
15. Two-coloring extension to cover dynamic cones (precharge/evaluate
    clock checks beyond the Pedroso latch-boundary check).

## Phase 4 — Power/Clock Optimization

16. Clock gating across latches + precharge (extends Pedroso clock-gated
    variant; gate both rails coordinately at evaluate-complete boundaries).
17. *(Optional)* Half-cycle-ahead valid extraction — rewrite to expose
    valids derivable one phase earlier; suppress precharge on dead cycles.

## Optional / Stretch

- **Opt-A** Cross-PDK design-style study (ASAP7 vs. Skywater) — falls out
  of Phase 1 nearly free.
- **Opt-B** Power gating with header-cluster grouping (depends on task 17
  for wakeup lead time).
- **Opt-C** Speculation + late repair for cases where valid can't be
  computed early.
- **Opt-D** Slack-aware re-retiming — feed task-8 slack marks back into
  ABC to bias toward balancing dynamic-candidate cones.
- **Opt-E** Scan-chain insertion (LSSD-style, two-phase). Needs scannable
  variant of the static-latch output stage added to Phase 1 cell family.
  Mandatory if heading toward tape-out.
- **Opt-F** At-speed test for post-silicon yield — two-pulse launch/capture
  at functional Φ1/Φ2, with dynamic-specific fault models (slow precharge,
  slow evaluate, charge-sharing margin loss, non-overlap violation).
  Agent-driven test pattern generation from Phase 1 characterization data.

## Dependency Notes

- Phase 1 (cells) is on the critical path for everything downstream and
  can run in parallel with Phase 2 compiler work on the existing static
  Pedroso output.
- Task 10 (LEC/cosim) gates task 9 (RTL-rewrite agent) running unsupervised.
- Tasks 8 + 11 are tightly coupled (slack drives dynamic-conversion
  decision); kept separate so the slack pass is reusable.
- Opt-E and Opt-F back-propagate to Phase 1 cell-family decisions —
  decide in/out before finalizing task 3.
- Opt-F depends on task 13 supporting a test-mode clock injection.
