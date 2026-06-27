# lsdl_priencoder32 — block signoff (rev: simple)

32-bit priority encoder (highest-index), outputs `vld` + `pos[4:0]`. Composed
entirely from **signed-off Wave-1 cells** (NOR4/NAND4/NOR2/3/NAND2/3/INV) — the
wide ORs are `NAND4(NOR4×4)` trees (NMOS-only evaluate, the LSDL delay showcase).
**Zero NOR8/NOR16** (those are quarantined — see librecell/EXPERIMENTAL_lsdl_nor8_x1.md).

## Signoff gates — ALL CLEAN
| gate | result |
|---|---|
| functional selftest | PASS (434 vectors) |
| KLayout full MV DRC | **0** (all rules) |
| antenna | **0** |
| route DRC | **0** |
| Netgen block LVS | **Circuits match uniquely** — 6872=6872 devices, 3542=3542 nets, clean pins, no forced equates |
| die | **331.7 × 331.7 µm = 0.110 mm²** (6× under 0.7 mm² budget) |
| cells | 570 (160 NOR4, 9 NAND4, 12 NOR3/2, 55 NAND2/3, 322 INV) |
| setup / hold | +0.032 ns / −0.197 ns (hold = pre-CTS; flat clock; CTS/timing deferred) |

## Reproducible flow
```
gen_lsdl_priencoder.py --width 32 --out priencoder32.v        # structural netlist (selftest PASS)
openroad -no_init -exit pnr/run_pnr.tcl                       # place/route -> DEF/ODB (flat c1/c2)
def2gds.py lsdl_priencoder32_ds.def ... lsdl_priencoder32     # stream + implant heal
pnr/heal_pplus_close.py <gds> lsdl_priencoder32_final.gds drc_enc 0.21 3.0   # widen PP.1 + close (deterministic)
```
LVS golden: `gen_lsdl_priencoder.py --spice` (cell subckts + structure) vs Magic-extracted
(**flatten before extract** — def2gds flattens implants to the top cell, so per-cell
extraction mis-reads FETs; flat extraction is correct). Keep ONE VPWR/VGND label
to avoid VPWR_uq0 port-error artifacts.

## Notes / follow-ups
- **Rev B (suffix-OR)**: the 322 INVs are mostly C1/C2 balancing from independent
  per-bit `hi[i]` ORs; a shared parallel-prefix suffix-OR would cut ~3×. Optional —
  this rev is already 6× under budget. Build only if the LSDL-vs-CMOS comparison
  wants a leaner benchmark.
- **Hold / CTS**: flat clock, hold −0.197 ns. Add the lsdl_clkbuf clock tree (as the
  adder does) + hold fix before timing signoff. Not a DRC/LVS/area blocker.
- def2gds auto thin-PPLUS-sliver + the marker-driven `heal_pplus_close.py` are the
  generic implant-cleanup path (reusable for the CMOS encoder + future blocks).
